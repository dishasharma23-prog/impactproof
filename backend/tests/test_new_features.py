"""SDG tagging, Cloudinary widget intake, structured metadata payload and early-access sign-ups."""
import hashlib
from datetime import datetime, timedelta

from tests.helpers import ai_result, photo
from tests.test_end_to_end import NEXT_AI, client, upload  # noqa: F401  (shared fixture)


def test_sdgs_flow(client):
    c = client
    p = c.post("/api/projects", json={"name": "Campus green drive", "description": "Litter cleanup and planting",
                                      "sdgs": [11, 15, 99, 15]}).json()
    assert [g["number"] for g in p["sdgs"]] == [11, 15]
    assert len(c.get("/api/sdgs").json()) == 17
    c.post(f"/api/projects/{p['id']}/sites", json={"name": "Garden", "latitude": 28.5, "longitude": 77.2, "radius_m": 400})
    NEXT_AI["raw"] = ai_result(sdgs=[15, 13, 6], sdg_reason="Saplings are being planted.")
    e = upload(c, photo(40, 28.5001, 77.2001, datetime.now() - timedelta(days=1)), "plant.jpg", project_id=p["id"])
    d = c.get(f"/api/evidence/{e['id']}").json()
    assert [g["number"] for g in d["sdgs"]] == [15], "limited to the project's goals"
    assert d["integrity"]["status"] == "CORROBORATED"
    ov = c.get(f"/api/projects/{p['id']}/overview").json()
    assert {g["number"]: g["photos"] for g in ov["sdgs"]} == {11: 0, 15: 1}
    claim = c.post("/api/claims/", json={"text": "Planted saplings in the garden", "project_id": p["id"]}).json()
    c.post(f"/api/claims/{claim['id']}/evidence", json={"evidence_id": e["id"]})
    rep = c.get(f"/api/claims/{claim['id']}/report").json()
    assert rep["sdgs"] == [{"number": 15, "name": "Life on land", "color": "#56C02B", "photos": 1}]


def test_cloudinary_payload_has_metadata(client):
    from app.db.database import SessionLocal
    from app.models import domain
    from app.services.cloudinary_service import CloudinaryService
    db = SessionLocal()
    e = db.query(domain.EvidenceAsset).filter(domain.EvidenceAsset.original_filename == "plant.jpg").first()
    e.cloudinary_public_id = "impactproof/project_x/ev_test"
    payload = CloudinaryService.trust_payload(e, e.integrity)
    assert payload["metadata"]["ip_trust_status"] == "corroborated"
    assert payload["metadata"]["ip_sdgs"] == ["sdg_15"]
    assert "sdg_15" in payload["tags"] and "trust_corroborated" in payload["tags"]
    assert payload["metadata"]["ip_sha256"] == e.sha256
    db.rollback()
    db.close()


def test_widget_intake(client, monkeypatch):
    from app.services import pipeline
    data = photo(41, 28.5002, 77.2002, datetime.now() - timedelta(hours=5))
    res = {"public_id": "impactproof/project_1/widget/abc", "secure_url": "https://res.cloudinary.com/x/abc.jpg",
           "etag": hashlib.md5(data).hexdigest(), "phash": "ff00ff00ff00ff00", "version": 1, "asset_id": "a1",
           "format": "jpg", "original_filename": "IMG_1001"}

    class R:
        content = data

        def raise_for_status(self):
            pass

    monkeypatch.setattr(pipeline.CloudinaryService, "enabled", staticmethod(lambda: True))
    monkeypatch.setattr(pipeline.CloudinaryService, "fetch_resource", staticmethod(lambda pid: res))
    monkeypatch.setattr(pipeline.httpx, "get", lambda *a, **k: R())
    r = client.post("/api/evidence/from-cloudinary", json={"public_id": res["public_id"]})
    assert r.status_code == 200, r.text
    d = client.get(f"/api/evidence/{r.json()['evidence_id']}").json()
    assert d["cloudinary_public_id"] == res["public_id"] and d["seal"]["cloudinary_matches"] is True
    assert d["original_filename"] == "IMG_1001.jpg"
    again = client.post("/api/evidence/from-cloudinary", json={"public_id": res["public_id"]})
    assert again.json()["evidence_id"] == r.json()["evidence_id"], "same asset is not ingested twice"
    bad = client.post("/api/evidence/from-cloudinary", json={"public_id": "someone_else/abc"})
    assert bad.status_code == 400
    res2 = {**res, "public_id": "impactproof/project_1/widget/tampered", "etag": "0" * 32}
    monkeypatch.setattr(pipeline.CloudinaryService, "fetch_resource", staticmethod(lambda pid: res2))
    assert client.post("/api/evidence/from-cloudinary", json={"public_id": res2["public_id"]}).status_code == 400


def test_widget_sign_rejects_other_folders(client, monkeypatch):
    from app.api.endpoints import evidence
    monkeypatch.setattr(evidence.CloudinaryService, "enabled", staticmethod(lambda: True))
    monkeypatch.setattr(evidence.CloudinaryService, "widget_signature", staticmethod(lambda p: "sig"))
    ok = client.post("/api/cloudinary/sign", json={"params_to_sign": {"folder": "impactproof/project_1", "timestamp": 1}})
    assert ok.json() == {"signature": "sig"}
    assert client.post("/api/cloudinary/sign", json={"params_to_sign": {"folder": "other", "timestamp": 1}}).status_code == 400


def test_early_access(client):
    bad = client.post("/api/early-access", json={"name": "A", "organisation": "B", "email": "nope"})
    assert bad.status_code == 422
    ok = client.post("/api/early-access", json={"name": "Asha", "organisation": "Green Hands", "email": "asha@example.org",
                                                 "role": "Programme lead", "message": "We spend 3 days per report."})
    assert ok.json()["ok"] and ok.json()["count"] >= 1
    assert client.get("/api/early-access").json()[0]["organisation"] == "Green Hands"


def test_gallery_and_classification(client):
    c = client
    p = c.post("/api/projects", json={"name": "Gallery test", "description": "Cleanup"}).json()
    t = datetime.now() - timedelta(days=2)
    NEXT_AI["raw"] = ai_result(stage="before", category="waste")
    a = upload(c, photo(60, 28.6, 77.3, t), "a.jpg", project_id=p["id"])
    NEXT_AI["raw"] = ai_result(stage="during", category="waste")
    b = upload(c, photo(61, 28.6, 77.3, t + timedelta(hours=1)), "b.jpg", project_id=p["id"])
    NEXT_AI["raw"] = ai_result(activity="saplings in a planted row", tags=["sapling"], waste_visible=False,
                               people_count_estimate=0)   # older-style analysis: no stage or category
    NEXT_AI["raw"].pop("stage", None)
    cc = upload(c, photo(62, 28.6, 77.3, t + timedelta(days=1)), "c.jpg", project_id=p["id"])
    g = c.get(f"/api/projects/{p['id']}/gallery?group=stage").json()
    assert [s["key"] for s in g["sections"]] == ["before", "during", "after"]
    assert g["sections"][2]["items"][0]["id"] == cc["id"] and g["sections"][2]["items"][0]["stage_source"] == "rules"
    cats = c.get(f"/api/projects/{p['id']}/gallery?group=category").json()
    assert {s["key"] for s in cats["sections"]} == {"waste", "planting"}
    assert len(c.get(f"/api/projects/{p['id']}/gallery?group=date").json()["sections"]) == 2
    r = c.put(f"/api/evidence/{b['id']}/classification", json={"stage": "after", "reviewer": "Disha"}).json()
    assert r["stage"] == "after" and r["stage_source"] == "person"
    assert c.put(f"/api/evidence/{b['id']}/classification", json={"stage": "nope"}).status_code == 400
    assert c.get(f"/api/projects/{p['id']}/gallery?group=bogus").status_code == 400
    assert a["stage"] == "before"


def test_delete_evidence(client):
    c = client
    p = c.post("/api/projects", json={"name": "Delete test", "description": "Litter cleanup"}).json()
    c.post(f"/api/projects/{p['id']}/sites", json={"name": "Yard", "latitude": 27.1, "longitude": 77.1, "radius_m": 400})
    when = datetime.now() - timedelta(days=2)
    NEXT_AI["raw"] = ai_result()
    original = upload(c, photo(77, 27.1001, 77.1001, when), "orig.jpg", project_id=p["id"])
    NEXT_AI["raw"] = ai_result()
    copy = upload(c, photo(77, None, None, None, crop=8), "copy.jpg", project_id=p["id"])
    assert c.get(f"/api/evidence/{copy['id']}").json()["integrity"]["status"] == "SUSPICIOUS", "a reused copy"
    claim = c.post("/api/claims/", json={"text": "Cleaned the yard", "project_id": p["id"]}).json()
    c.post(f"/api/claims/{claim['id']}/evidence", json={"evidence_id": original["id"]})

    r = c.delete(f"/api/evidence/{original['id']}", params={"actor": "Disha", "reason": "Test upload"}).json()
    assert r["deleted"][0]["claims"] == [claim["id"]]
    assert c.get(f"/api/evidence/{original['id']}").status_code == 404
    assert c.get(f"/api/claims/{claim['id']}").json()["evidence"] == []
    after = c.get(f"/api/evidence/{copy['id']}").json()["integrity"]["status"]
    assert after != "SUSPICIOUS", "with the original gone, the copy is no longer a reuse of anything"
    rows = c.get("/api/audit", params={"limit": 200}).json()
    assert any(f"Deleted EV-{original['id']:04d}" in (a.get("summary") or "") and "Test upload" in a["summary"]
               and a.get("actor") == "Disha" for a in rows), "the deletion stays in the audit log"

    r = c.post("/api/evidence/delete", json={"ids": [copy["id"]], "actor": "Disha"}).json()
    assert [d["id"] for d in r["deleted"]] == [copy["id"]]
    assert c.post("/api/evidence/delete", json={"ids": []}).status_code == 400


def test_volunteers_pair_and_upload(client):
    c = client
    p = c.post("/api/projects", json={"name": "Volunteer test", "description": "cleanup"}).json()
    r = c.post("/api/volunteers", json={"name": "Disha", "phone": "098765 43210", "project_id": p["id"]}).json()
    assert r["phone"] == "+919876543210" and r["phone_masked"] == "+91 ••••• 43210" and len(r["pairing_code"]) == 6
    assert c.post("/api/volunteers", json={"name": "Again", "phone": "+91 98765 43210"}).status_code == 409
    assert c.post("/api/volunteers", json={"name": "X", "phone": "12"}).status_code == 400
    assert c.post("/api/volunteers/pair", json={"phone": "9876543210", "code": "000000"}).status_code == 401
    ok = c.post("/api/volunteers/pair", json={"phone": "9876543210", "code": r["pairing_code"], "device_name": "Disha's iPhone"}).json()
    key = ok["device_key"]
    assert ok["volunteer"]["paired"] is True
    assert c.post("/api/volunteers/pair", json={"phone": "9876543210", "code": r["pairing_code"]}).status_code == 401, "codes are single use"

    NEXT_AI["raw"] = ai_result()
    up = c.post("/api/evidence/upload", files={"file": ("f.jpg", photo(90, 27.2, 77.2, datetime.now() - timedelta(hours=2)), "image/jpeg")},
                headers={"X-Device-Key": key})
    assert up.status_code == 200
    ev = c.get(f"/api/evidence/{up.json()['evidence_id']}").json()
    assert ev["captured_by"]["name"] == "Disha" and ev["captured_by"]["phone_masked"] == "+91 ••••• 43210"
    assert ev["project_id"] == p["id"], "a paired device uploads into its volunteer's project"
    assert "+919876543210" not in str(ev), "the full number is never exposed with evidence"

    bad = c.post("/api/evidence/upload", files={"file": ("g.jpg", photo(91), "image/jpeg")}, headers={"X-Device-Key": "nope"})
    assert bad.status_code == 401
    c.delete(f"/api/volunteers/{r['id']}")
    gone = c.post("/api/evidence/upload", files={"file": ("h.jpg", photo(92), "image/jpeg")}, headers={"X-Device-Key": key})
    assert gone.status_code == 401, "removing a volunteer revokes their device"
    assert c.get("/api/volunteers", params={"project_id": p["id"]}).json()[0]["uploads"] == 1
