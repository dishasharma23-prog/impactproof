"""Two field devices sharing an in-memory Qdrant server: offline memory, policy, sync, conflicts, HQ upload."""
import io
import json
import random

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from qdrant_client import QdrantClient

from field.api import create_app
from field.config import Config
from field.embed import HashEmbedder


def jpeg(seed: int) -> bytes:
    r = random.Random(seed)
    im = Image.new("RGB", (320, 240), (r.randint(0, 255),) * 3)
    d = ImageDraw.Draw(im)
    for _ in range(25):
        x, y = r.randint(0, 300), r.randint(0, 220)
        d.rectangle([x, y, x + r.randint(10, 90), y + r.randint(10, 90)], fill=(r.randint(0, 255), r.randint(0, 255), r.randint(0, 255)))
    b = io.BytesIO()
    im.save(b, "JPEG")
    return b.getvalue()


HQ_UPLOADS = []
HQ_EXTRA_EVIDENCE = []  # extra rows the mock HQ lists, e.g. a reviewer's later decision


def hq_handler(request: httpx.Request):
    if request.url.path == "/api/volunteers/pair":
        body = json.loads(request.content)
        if body.get("code") != "123456":
            return httpx.Response(401, json={"detail": "That phone number and code don't match."})
        return httpx.Response(200, json={"device_key": "key-" + body["phone"][-4:], "volunteer": {
            "name": "Asha", "phone_masked": "+91 ••••• " + body["phone"][-5:], "project_id": 1}})
    if request.url.path == "/api/evidence/upload":
        if not request.headers.get("x-device-key", "").startswith("key-"):
            return httpx.Response(401, json={"detail": "This device is not registered."})
        HQ_UPLOADS.append(request)
        n = len(HQ_UPLOADS)
        return httpx.Response(200, json={"evidence_id": n, "evidence": {"code": f"EV-{n:04d}", "integrity_status": "CORROBORATED",
                                                                         "status_label": "Corroborated"}})
    if request.url.path == "/api/projects":
        return httpx.Response(200, json=[{"id": 1, "name": "Campus cleanup"}])
    if request.url.path == "/api/projects/1":
        return httpx.Response(200, json={"id": 1, "name": "Campus cleanup", "sites": [
            {"id": 1, "name": "Library lawn", "radius_m": 300, "corroborated_count": 4, "last_corroborated_at": "2026-09-26T10:00:00",
             "latitude": 28.5, "longitude": 77.2}]})
    if request.url.path == "/api/evidence":
        return httpx.Response(200, json=HQ_EXTRA_EVIDENCE + [{"id": 9, "code": "EV-0009", "integrity_status": "CORROBORATED", "status_label": "Corroborated", "site_name": "Library lawn",
                                          "activity": "volunteers filling garbage bags near the drain", "capture_time": "2026-09-26T10:00:00",
                                          "thumb_url": None, "tags": ["cleanup"]}])
    return httpx.Response(404)


@pytest.fixture()
def devices(tmp_path):
    server = QdrantClient(":memory:")
    http = httpx.Client(transport=httpx.MockTransport(hq_handler), base_url="http://hq")
    apps = {}
    for dev in ("alpha", "beta"):
        cfg = Config(device_id=dev, data_dir=tmp_path, embedder="hash", hq_url="http://hq", memory_budget=50)
        app = create_app(cfg, client=server, http=http, embedder=HashEmbedder(), start_background=False)
        apps[dev] = TestClient(app)
        assert apps[dev].post("/api/pair", json={"phone": "98765 4321" + str(len(apps)), "code": "123456"}).status_code == 200
    yield apps["alpha"], apps["beta"], server
    for c in apps.values():
        c.app.state.memory.close()


def test_offline_memory_and_policy(devices):
    a, b, _ = devices
    a.post("/api/network", json={"offline": True})
    assert a.get("/api/status").json()["connectivity"]["online"] is False
    n1 = a.post("/api/notes", json={"text": "Drain behind the library is blocked with plastic bottles", "site": "Library lawn"}).json()
    assert n1["sync_state"] == "pending"
    n2 = a.post("/api/notes", json={"text": "Call caretaker Ramesh on 98765 43210 about the gate"}).json()
    assert n2["sync_state"] == "local_only" and "phone number" in n2["sync_reason"]
    n3 = a.post("/api/notes", json={"text": "My personal reminder", "private": True}).json()
    assert n3["sync_state"] == "local_only"
    img = jpeg(1)
    c1 = a.post("/api/captures", files={"file": ("a.jpg", img, "image/jpeg")},
                data={"caption": "garbage bags filled at the drain", "site": "Library lawn", "lat": "28.5", "lng": "77.2"}).json()
    assert c1["sync_state"] == "pending" and c1["image_url"].startswith("/photos/")
    c2 = a.post("/api/captures", files={"file": ("b.jpg", img, "image/jpeg")}, data={"caption": "same shot again"}).json()
    assert c2["sync_state"] == "skipped" and "Near-duplicate" in c2["sync_reason"]
    r = a.get("/api/search", params={"q": "blocked drain plastic"}).json()
    assert r["offline"] is True and r["results"][0]["id"] == n1["id"]
    kw = a.get("/api/search", params={"q": "caretaker gate", "mode": "keyword"}).json()
    assert kw["results"][0]["id"] == n2["id"], "private items are still searchable on the device itself"
    assert a.post("/api/sync").json()["online"] is False


def test_sync_between_devices_and_hq(devices):
    a, b, server = devices
    HQ_UPLOADS.clear()
    note = a.post("/api/notes", json={"text": "Saplings at the east gate need water", "site": "East gate"}).json()
    a.post("/api/notes", json={"text": "email me at x@y.org"})
    cap = a.post("/api/captures", files={"file": ("c.jpg", jpeg(2), "image/jpeg")},
                 data={"caption": "cleared drain after cleanup", "lat": "28.5", "lng": "77.2", "tz_offset_min": "-330"}).json()
    a.post("/api/network", json={"network": "mobile"})
    s = a.post("/api/sync").json()
    assert s["pushed"]["sent"] == 2 and s["photos"]["waiting"] == 1 and not HQ_UPLOADS
    assert a.get(f"/api/items/{cap['id']}").json()["photo_state"] == "waiting_wifi"
    a.post("/api/network", json={"network": "wifi"})
    s = a.post("/api/sync").json()
    assert s["photos"]["uploaded"] == 1 and len(HQ_UPLOADS) == 1
    body = HQ_UPLOADS[0].content
    assert b"ImpactProof" in body, "the photo carries device EXIF for HQ checks"
    assert a.get(f"/api/items/{cap['id']}").json()["hq_status"] == "CORROBORATED"
    assert server.count("field_memory").count == 2, "private/personal notes never reach the server"

    sb = b.post("/api/sync").json()
    assert sb["pulled"]["received"] == 2 and sb["hq"]["items"] == 2
    b.post("/api/network", json={"offline": True})
    r = b.get("/api/search", params={"q": "water the saplings"}).json()
    assert r["results"][0]["id"] == note["id"] and r["results"][0]["origin"] == "peer"
    hq = b.get("/api/search", params={"q": "garbage bags drain", "kinds": "hq_evidence"}).json()
    assert hq["results"] and hq["results"][0]["kind"] == "hq_evidence"
    b.post("/api/network", json={"offline": False})

    # deletion propagates as a tombstone
    a.delete(f"/api/items/{note['id']}")
    a.post("/api/sync")
    assert b.post("/api/sync").json()["pulled"]["removed"] == 1
    assert b.get(f"/api/items/{note['id']}").status_code == 404


def test_conflicting_facts(devices):
    a, b, _ = devices
    a.post("/api/facts", json={"key": "Library lawn: bags collected", "value": "12"})
    a.post("/api/sync")
    b.post("/api/sync")
    assert b.get("/api/items", params={"kind": "fact"}).json()[0]["value"] == "12"
    # both change it while offline
    for dev, val in ((a, "14"), (b, "15")):
        dev.post("/api/network", json={"offline": True})
        dev.post("/api/facts", json={"key": "Library lawn: bags collected", "value": val})
        dev.post("/api/network", json={"offline": False})
    a.post("/api/sync")
    sb = b.post("/api/sync").json()
    assert sb["pushed"]["conflicts"] + sb["pulled"]["conflicts"] == 1
    fact = b.get("/api/items", params={"state": "conflict"}).json()[0]
    assert fact["value"] == "15" and fact["conflict"]["value"] == "14"
    assert b.post("/api/facts", json={"key": "Library lawn: bags collected", "value": "16"}).status_code == 409
    r = b.post(f"/api/items/{fact['id']}/resolve", json={"choice": "merge", "value": "29"}).json()
    assert r["sync_state"] == "pending"
    b.post("/api/sync")
    a.post("/api/sync")
    assert a.get("/api/items", params={"kind": "fact"}).json()[0]["value"] == "29"
    acts = [e["kind"] for e in b.get("/api/activity").json()]
    assert "conflict" in acts


def test_memory_budget(tmp_path):
    server = QdrantClient(":memory:")
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    a = TestClient(create_app(Config(device_id="a", data_dir=tmp_path, embedder="hash"), client=server, http=http,
                              embedder=HashEmbedder(), start_background=False))
    small = Config(device_id="b", data_dir=tmp_path, embedder="hash", memory_budget=3)
    b = TestClient(create_app(small, client=server, http=http, embedder=HashEmbedder(), start_background=False))
    for i in range(6):
        a.post("/api/notes", json={"text": f"observation number {i} about the east field"})
    a.post("/api/sync")
    s = b.post("/api/sync").json()
    assert s["pulled"]["received"] == 6 and s["evicted"] == 3
    assert b.get("/api/status").json()["origins"]["peer"] == 3
    a.app.state.memory.close(); b.app.state.memory.close()


def test_persistence(tmp_path):
    server = QdrantClient(":memory:")
    cfg = Config(device_id="p", data_dir=tmp_path, embedder="hash")
    a = TestClient(create_app(cfg, client=server, embedder=HashEmbedder(), start_background=False))
    a.post("/api/notes", json={"text": "remember me after restart"})
    a.app.state.memory.close()
    a2 = TestClient(create_app(cfg, client=server, embedder=HashEmbedder(), start_background=False))
    assert a2.get("/api/search", params={"q": "remember restart"}).json()["results"][0]["text"] == "remember me after restart"
    a2.app.state.memory.close()


def test_editing_a_received_fact_is_not_a_conflict(devices):
    a, b, _ = devices
    a.post("/api/facts", json={"key": "East gate: saplings alive", "value": "20"})
    a.post("/api/sync")
    b.post("/api/sync")
    b.post("/api/facts", json={"key": "East gate: saplings alive", "value": "18"})
    s = b.post("/api/sync").json()
    assert s["pushed"] == {"sent": 1, "conflicts": 0}
    a.post("/api/sync")
    assert a.get("/api/items", params={"kind": "fact"}).json()[0]["value"] == "18"


def test_search_leaves_out_unrelated_items(devices):
    a, _, _ = devices
    a.post("/api/notes", json={"text": "Drain behind the library is blocked with plastic bottles"})
    a.post("/api/notes", json={"text": "Saplings near the east gate need watering"})
    r = a.get("/api/search", params={"q": "caretaker key"}).json()
    assert r["results"] == []
    r = a.get("/api/search", params={"q": "blocked drain"}).json()
    assert [x["text"] for x in r["results"]] == ["Drain behind the library is blocked with plastic bottles"]


def test_hq_verdict_changes_reach_the_device(devices):
    a, _, _ = devices
    HQ_UPLOADS.clear()
    cap = a.post("/api/captures", files={"file": ("d.jpg", jpeg(3), "image/jpeg")}, data={"caption": "drain"}).json()
    a.post("/api/sync")
    item = a.get(f"/api/items/{cap['id']}").json()
    assert item["hq_status"] == "CORROBORATED" and item["hq_code"]
    HQ_EXTRA_EVIDENCE[:] = [{"id": item["hq_evidence_id"], "code": item["hq_code"], "integrity_status": "REJECTED",
                             "status_label": "Rejected"}]
    try:
        a.post("/api/sync")
    finally:
        HQ_EXTRA_EVIDENCE.clear()
    assert a.get(f"/api/items/{cap['id']}").json()["hq_status"] == "REJECTED"
    assert any("now Rejected" in e["message"] for e in a.get("/api/activity").json())


def test_unpaired_device_keeps_photos_until_sign_in(tmp_path):
    server = QdrantClient(":memory:")
    http = httpx.Client(transport=httpx.MockTransport(hq_handler), base_url="http://hq")
    HQ_UPLOADS.clear()
    a = TestClient(create_app(Config(device_id="solo", data_dir=tmp_path, embedder="hash", hq_url="http://hq"),
                              client=server, http=http, embedder=HashEmbedder(), start_background=False))
    assert a.get("/api/status").json()["volunteer"] is None
    cap = a.post("/api/captures", files={"file": ("p.jpg", jpeg(5), "image/jpeg")}, data={"caption": "tank"}).json()
    a.post("/api/sync")
    assert a.get(f"/api/items/{cap['id']}").json()["photo_state"] == "not_paired" and not HQ_UPLOADS
    assert a.post("/api/pair", json={"phone": "9876543210", "code": "999999"}).status_code == 401
    v = a.post("/api/pair", json={"phone": "9876543210", "code": "123456"}).json()
    assert v["name"] == "Asha" and "device_key" not in v, "the key never leaves the device's own storage"
    assert a.get("/api/status").json()["volunteer"]["phone_masked"].endswith("43210")
    a.post("/api/sync")
    assert a.get(f"/api/items/{cap['id']}").json()["photo_state"] == "at_hq" and len(HQ_UPLOADS) == 1
    a.delete("/api/pair")
    assert a.get("/api/status").json()["volunteer"] is None
    a.app.state.memory.close()
