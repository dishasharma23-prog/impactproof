"""Edge-to-cloud sync between this device's Qdrant Edge shard and a shared Qdrant Server collection.

Push: pending items go up in priority order (facts, notes, then photo details). Photo files go to
ImpactProof HQ only on Wi-Fi, where they get verified. Pull: what other devices synced, plus HQ
knowledge (sites and verified evidence), comes down so it can be searched offline.
Facts carry versions; if two devices changed the same fact while offline, that's a conflict a
person resolves. Knowledge pulled from elsewhere is capped by a memory budget.
"""
import json
import threading
import time
from datetime import datetime
from pathlib import Path

import httpx
import qdrant_edge as q
from qdrant_client import QdrantClient, models

from field.embed import CLIP_DIM, TEXT_DIM
from field.memory import Memory, now_iso
from field.policy import PRIORITY

LOCAL_ONLY_FIELDS = ("image_file", "sync_state", "sync_reason", "base_version", "conflict", "photo_state",
                     "last_used_at", "synced_at", "private")


def _to_client_vec(v: dict) -> dict:
    out = {}
    for k, val in (v or {}).items():
        if k == "bm25":
            out[k] = models.SparseVector(indices=list(val.indices), values=list(val.values))
        else:
            out[k] = list(val)
    return out


def _to_edge_vec(v: dict) -> dict:
    out = {}
    for k, val in (v or {}).items():
        if isinstance(val, models.SparseVector):
            out[k] = q.SparseVector(list(val.indices), list(val.values))
        elif isinstance(val, dict) and "indices" in val:
            out[k] = q.SparseVector(list(val["indices"]), list(val["values"]))
        else:
            out[k] = list(val)
    return out


class SyncEngine:
    def __init__(self, cfg, memory: Memory, activity, client: QdrantClient | None = None, http=None):
        self.cfg, self.memory, self.activity = cfg, memory, activity
        self._client = client
        self.http = http or httpx.Client(timeout=30)
        self.simulated_offline = False
        self.network = "wifi"               # wifi | mobile
        self.allow_media_on_mobile = False
        self.last_sync: dict | None = None
        self.last_pull_ts = 0.0
        self.lock = threading.Lock()
        self._stop = threading.Event()
        self._online_cache = (0.0, False, "")

    # ---------------------------------------------------------------- connectivity
    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(url=self.cfg.qdrant_url, api_key=self.cfg.qdrant_api_key or None, timeout=3)
        return self._client

    def connectivity(self, force=False) -> dict:
        if self.simulated_offline:
            return {"online": False, "reason": "Offline mode is on (simulating no signal)."}
        ts, ok, why = self._online_cache
        if not force and time.time() - ts < 3:
            return {"online": ok, "reason": why}
        try:
            self.client.get_collections()
            ok, why = True, "Connected to the sync server."
        except Exception as e:
            ok, why = False, f"Can't reach the sync server ({type(e).__name__})."
        self._online_cache = (time.time(), ok, why)
        return {"online": ok, "reason": why}

    def ensure_collection(self):
        name = self.cfg.server_collection
        if not self.client.collection_exists(name):
            self.client.create_collection(
                name,
                vectors_config={"text": models.VectorParams(size=TEXT_DIM, distance=models.Distance.COSINE),
                                "clip": models.VectorParams(size=CLIP_DIM, distance=models.Distance.COSINE)},
                sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)})
            for f, schema in (("device_id", models.PayloadSchemaType.KEYWORD),
                              ("updated_ts", models.PayloadSchemaType.FLOAT)):
                try:
                    self.client.create_payload_index(name, f, schema)
                except Exception:
                    pass

    # ---------------------------------------------------------------- sync
    def sync(self, reason="manual") -> dict:
        if not self.lock.acquire(blocking=False):
            return {"skipped": "A sync is already running."}
        try:
            conn = self.connectivity(force=True)
            if not conn["online"]:
                return {"online": False, "reason": conn["reason"]}
            t0 = time.perf_counter()
            self.ensure_collection()
            pushed = self._push()
            photos = self._upload_photos()
            pulled = self._pull()
            hq = self._pull_hq()
            evicted = self._enforce_budget()
            summary = {"online": True, "reason": reason, "pushed": pushed, "photos": photos, "pulled": pulled,
                       "hq": hq, "evicted": evicted, "ms": round((time.perf_counter() - t0) * 1000),
                       "at": now_iso()}
            self.last_sync = summary
            parts = [f"sent {pushed['sent']}", f"received {pulled['received']}"]
            if pushed["conflicts"] or pulled["conflicts"]:
                parts.append(f"{pushed['conflicts'] + pulled['conflicts']} conflict(s) need a decision")
            if photos["uploaded"]:
                parts.append(f"{photos['uploaded']} photo(s) sent to HQ")
            if photos["waiting"]:
                parts.append(f"{photos['waiting']} photo(s) waiting for Wi-Fi")
            if hq.get("items"):
                parts.append(f"{hq['items']} HQ items refreshed")
            if evicted:
                parts.append(f"{evicted} old item(s) evicted to stay within the memory budget")
            self.activity.log("sync", "Synced: " + ", ".join(parts) + ".", summary=summary)
            return summary
        except Exception as e:
            self.activity.log("error", f"Sync failed: {e}")
            return {"online": False, "reason": f"Sync failed: {e}"}
        finally:
            self.lock.release()

    def _server_payload(self, item: dict) -> dict:
        p = {k: v for k, v in item.items() if k not in LOCAL_ONLY_FIELDS and not k.startswith("_") and k != "id"}
        p["has_image"] = bool(item.get("image_file"))
        p["updated_ts"] = time.time()
        return p

    def _push(self) -> dict:
        items = self.memory.all(self.memory.match(sync_state="pending", origin="local"))
        items.sort(key=lambda i: (PRIORITY.get(i.get("kind"), 9), i.get("created_at") or ""))
        sent = conflicts = 0
        name = self.cfg.server_collection
        for item in items:
            full = self.memory.get(item["id"], with_vector=True)
            if item.get("kind") == "fact":
                srv = self.client.retrieve(name, [item["id"]], with_payload=True)
                if srv:
                    sp = srv[0].payload or {}
                    if (sp.get("version", 0) > item.get("base_version", 0) and sp.get("device_id") != self.cfg.device_id
                            and str(sp.get("value")) != str(item.get("value"))):
                        self._mark_conflict(item, sp)
                        conflicts += 1
                        continue
                    version = max(sp.get("version", 0), item.get("base_version", 0)) + 1
                else:
                    version = item.get("base_version", 0) + 1
                item = {**item, "version": version}
            payload = self._server_payload(item)
            self.client.upsert(name, [models.PointStruct(id=item["id"], vector=_to_client_vec(full["_vector"]),
                                                         payload=payload)])
            patch = {"sync_state": "synced", "synced_at": now_iso(), "sync_reason": "On the sync server."}
            if item.get("kind") == "fact":
                patch.update(version=item["version"], base_version=item["version"])
            if item.get("kind") == "capture" and item.get("image_file"):
                patch["sync_reason"] = "Details on the sync server."
            self.memory.set_payload(item["id"], patch)
            sent += 1
        return {"sent": sent, "conflicts": conflicts}

    def _mark_conflict(self, item: dict, theirs: dict):
        self.memory.set_payload(item["id"], {
            "sync_state": "conflict",
            "sync_reason": f"Changed on {theirs.get('device_name') or theirs.get('device_id')} while you were offline.",
            "conflict": {"value": theirs.get("value"), "device_id": theirs.get("device_id"),
                         "device_name": theirs.get("device_name"), "updated_at": theirs.get("updated_at"),
                         "version": theirs.get("version", 0)}})
        self.activity.log("conflict", f"Conflict on “{item.get('key')}”: this device says {item.get('value')}, "
                                      f"{theirs.get('device_name') or theirs.get('device_id')} says {theirs.get('value')}.",
                          id=item["id"])

    def _pull(self) -> dict:
        name = self.cfg.server_collection
        flt = models.Filter(must=[models.FieldCondition(key="updated_ts", range=models.Range(gt=self.last_pull_ts))],
                            must_not=[models.FieldCondition(key="device_id", match=models.MatchValue(value=self.cfg.device_id))])
        received = conflicts = removed = 0
        newest = self.last_pull_ts
        offset = None
        while True:
            pts, offset = self.client.scroll(name, scroll_filter=flt, limit=128, offset=offset,
                                             with_payload=True, with_vectors=True)
            for pt in pts:
                p = dict(pt.payload or {})
                newest = max(newest, p.get("updated_ts", 0))
                pid = str(pt.id)
                local = self.memory.get(pid)
                if p.get("deleted"):
                    if local and local.get("origin") != "local":
                        self.memory.delete(pid)
                        removed += 1
                    continue
                if p.get("kind") == "fact" and local:
                    if local.get("sync_state") == "pending" and str(local.get("value")) != str(p.get("value")) \
                            and p.get("version", 0) > local.get("base_version", 0):
                        self._mark_conflict(local, p)
                        conflicts += 1
                        continue
                    if local.get("sync_state") == "conflict":
                        continue
                    p.update(origin=local.get("origin", "peer"), sync_state="synced", base_version=p.get("version", 0),
                             sync_reason=f"Latest value from {p.get('device_name') or p.get('device_id')}.")
                else:
                    p.update(origin="peer", sync_state="synced",
                             sync_reason=f"From {p.get('device_name') or p.get('device_id')}, via the sync server.")
                    if p.get("kind") == "fact":
                        p["base_version"] = p.get("version", 0)
                p["synced_at"] = now_iso()
                self.memory.upsert(pid, p, vectors=_to_edge_vec(pt.vector))
                received += 1
            if offset is None:
                break
        self.last_pull_ts = newest
        return {"received": received, "conflicts": conflicts, "removed": removed}

    # ---------------------------------------------------------------- photos to ImpactProof HQ
    def _upload_photos(self) -> dict:
        items = [i for i in self.memory.all(self.memory.match(kind="capture", origin="local", sync_state="synced"))
                 if i.get("photo_state") in (None, "waiting_wifi", "waiting") and i.get("image_file")]
        if not self.cfg.hq_url:
            for i in items:
                if i.get("photo_state") != "kept_on_device":
                    self.memory.set_payload(i["id"], {"photo_state": "kept_on_device"})
            return {"uploaded": 0, "waiting": 0, "note": "No HQ configured; photos stay on the device."}
        if self.network == "mobile" and not self.allow_media_on_mobile:
            for i in items:
                self.memory.set_payload(i["id"], {"photo_state": "waiting_wifi",
                                                  "sync_reason": "Details synced; photo waits for Wi-Fi."})
            return {"uploaded": 0, "waiting": len(items)}
        pairing = self.pairing()
        if not pairing:
            for i in items:
                if i.get("photo_state") != "not_paired":
                    self.memory.set_payload(i["id"], {"photo_state": "not_paired",
                                                      "sync_reason": "Photo kept on this device until a volunteer signs in (Sync tab)."})
            return {"uploaded": 0, "waiting": len(items), "note": "Not signed in: photos stay on the device."}
        uploaded = 0
        for i in items:
            path = Path(i["image_file"])
            if not path.exists():
                continue
            try:
                data = {"uploader": self.cfg.label}
                if self.cfg.hq_project_id:
                    data["project_id"] = str(self.cfg.hq_project_id)
                r = self.http.post(f"{self.cfg.hq_url.rstrip('/')}/api/evidence/upload", data=data,
                                   headers={"X-Device-Key": pairing["device_key"]},
                                   files={"file": (path.name, path.read_bytes(), "image/jpeg")})
                if r.status_code == 401:
                    self.clear_pairing()
                    self.activity.log("hq", "HQ no longer recognises this device; sign in again to upload photos.")
                    self.memory.set_payload(i["id"], {"photo_state": "not_paired",
                                                      "sync_reason": "HQ refused the device key; sign in again (Sync tab)."})
                    break
                r.raise_for_status()
                body = r.json()
                ev = body.get("evidence") or {}
                self.memory.set_payload(i["id"], {
                    "photo_state": "at_hq", "hq_evidence_id": body.get("evidence_id"),
                    "hq_status": ev.get("integrity_status"), "hq_status_label": ev.get("status_label"),
                    "hq_code": ev.get("code"),
                    "sync_reason": f"Photo verified at ImpactProof HQ as {ev.get('code')}: {ev.get('status_label')}."})
                self.activity.log("hq", f"Photo sent to HQ as {ev.get('code')}: {ev.get('status_label')}.", id=i["id"])
                uploaded += 1
            except Exception as e:
                self.memory.set_payload(i["id"], {"photo_state": "waiting", "sync_reason": f"HQ upload failed: {e}"})
        return {"uploaded": uploaded, "waiting": 0}

    # ---------------------------------------------------------------- volunteer pairing
    @property
    def _pairing_file(self) -> Path:
        return self.cfg.device_dir / "pairing.json"

    def pairing(self) -> dict | None:
        try:
            return json.loads(self._pairing_file.read_text())
        except Exception:
            return None

    def pair(self, phone: str, code: str) -> dict:
        """Exchange a registered phone number + pairing code for this device's upload key (needs HQ, once)."""
        if not self.cfg.hq_url:
            raise RuntimeError("No ImpactProof HQ address is set for this device.")
        r = self.http.post(f"{self.cfg.hq_url.rstrip('/')}/api/volunteers/pair",
                           json={"phone": phone, "code": code, "device_name": self.cfg.label}, timeout=20)
        if r.status_code != 200:
            try:
                detail = r.json().get("detail")
            except Exception:
                detail = r.text
            raise PermissionError(detail or "Pairing failed.")
        body = r.json()
        v = body["volunteer"]
        rec = {"device_key": body["device_key"], "name": v["name"], "phone_masked": v["phone_masked"],
               "project_id": v.get("project_id"), "paired_at": now_iso()}
        self._pairing_file.write_text(json.dumps(rec))
        if v.get("project_id") and not self.cfg.hq_project_id:
            self.cfg.hq_project_id = v["project_id"]
        self.activity.log("pair", f"Signed in as {v['name']} ({v['phone_masked']}). Photos now upload in their name.")
        for i in self.memory.all(self.memory.match(kind="capture", origin="local", photo_state="not_paired")):
            self.memory.set_payload(i["id"], {"photo_state": "waiting", "sync_reason": "Photo will upload at the next sync."})
        return rec

    def clear_pairing(self):
        self._pairing_file.unlink(missing_ok=True)

    # ---------------------------------------------------------------- HQ knowledge for offline use
    def _pull_hq(self) -> dict:
        if not self.cfg.hq_url:
            return {"items": 0}
        base = self.cfg.hq_url.rstrip("/")
        try:
            projects = self.http.get(f"{base}/api/projects").json()
            pid = self.cfg.hq_project_id or (projects[0]["id"] if projects else None)
            if pid is None:
                return {"items": 0}
            proj = self.http.get(f"{base}/api/projects/{pid}").json()
            all_evidence = self.http.get(f"{base}/api/evidence", params={"project_id": pid}).json()
        except Exception as e:
            return {"items": 0, "error": str(e)}
        evidence = [e for e in all_evidence if e.get("integrity_status") == "CORROBORATED"]
        self._refresh_my_verdicts({e["id"]: e for e in all_evidence})
        import uuid
        ns = uuid.UUID("7b0e2a3c-5d11-4c9a-8f5e-1a2b3c4d5e6f")
        n = 0
        for s in proj.get("sites", []):
            text = (f"Site {s['name']} of project {proj.get('name')}. Radius {int(s.get('radius_m') or 0)} m. "
                    f"{s.get('corroborated_count', 0)} verified photos"
                    + (f", last on {s['last_corroborated_at'][:10]}." if s.get("last_corroborated_at") else ", none yet."))
            self._upsert_if_changed(str(uuid.uuid5(ns, f"site:{s['id']}")), {
                "kind": "hq_site", "origin": "hq", "title": s["name"], "text": text, "site": s["name"],
                "lat": s.get("latitude"), "lng": s.get("longitude"), "sync_state": "synced",
                "sync_reason": "Downloaded from ImpactProof HQ for offline use.", "created_at": now_iso(),
                "updated_at": now_iso(), "synced_at": now_iso()})
            n += 1
        for e in evidence[:200]:
            text = f"{e.get('activity') or 'Field photo'} at {e.get('site_name') or 'unknown site'}, " \
                   f"captured {str(e.get('capture_time') or '')[:10]}. Verified as {e.get('status_label')}."
            self._upsert_if_changed(str(uuid.uuid5(ns, f"ev:{e['id']}")), {
                "kind": "hq_evidence", "origin": "hq", "title": f"{e['code']} ({e.get('status_label')})", "text": text,
                "site": e.get("site_name") or "", "thumb_url": e.get("thumb_url"), "hq_evidence_id": e["id"],
                "tags": e.get("tags") or [], "sync_state": "synced", "created_at": e.get("capture_time") or now_iso(),
                "updated_at": now_iso(), "synced_at": now_iso(),
                "sync_reason": "Verified evidence from ImpactProof HQ, kept for offline search."})
            n += 1
        return {"items": n, "project_id": pid}

    def _upsert_if_changed(self, point_id: str, payload: dict):
        """HQ items are pulled on every sync; only re-embed the ones whose text changed."""
        old = self.memory.get(point_id)
        if old and old.get("text") == payload.get("text") and old.get("title") == payload.get("title"):
            return
        if old and old.get("last_used_at"):
            payload["last_used_at"] = old["last_used_at"]
        self.memory.upsert(point_id, payload)

    def _refresh_my_verdicts(self, by_id: dict):
        """A reviewer at HQ may approve or reject a photo later; keep the device's copy of the verdict current."""
        for i in self.memory.all(self.memory.match(kind="capture", origin="local", photo_state="at_hq")):
            e = by_id.get(i.get("hq_evidence_id"))
            if e and e.get("integrity_status") != i.get("hq_status"):
                self.memory.set_payload(i["id"], {"hq_status": e.get("integrity_status"), "hq_status_label": e.get("status_label"),
                                                   "hq_code": e.get("code"),
                                                   "sync_reason": f"Photo verified at ImpactProof HQ as {e.get('code')}: {e.get('status_label')}."})
                self.activity.log("hq", f"HQ updated {e.get('code')}: now {e.get('status_label')}.", id=i["id"])

    def _enforce_budget(self) -> int:
        """Keep what was synced in from elsewhere within budget; drop the least recently useful first."""
        items = self.memory.all(self.memory.match(origin=["peer", "hq"]))
        over = len(items) - self.cfg.memory_budget
        if over <= 0:
            return 0
        items.sort(key=lambda i: (i.get("last_used_at") or i.get("synced_at") or "", i.get("created_at") or ""))
        for i in items[:over]:
            self.memory.delete(i["id"])
        return over

    # ---------------------------------------------------------------- conflicts
    def resolve(self, point_id: str, choice: str, value=None) -> dict:
        item = self.memory.get(point_id)
        if not item or item.get("sync_state") != "conflict":
            raise ValueError("No conflict to resolve for this item.")
        theirs = item.get("conflict") or {}
        server_version = theirs.get("version", 0)
        if choice == "theirs":
            patch = {"value": theirs.get("value"), "sync_state": "synced", "base_version": server_version,
                     "version": server_version, "conflict": None, "updated_at": now_iso(),
                     "sync_reason": f"Kept {theirs.get('device_name') or theirs.get('device_id')}'s value."}
            new = {**item, **patch}
            self.memory.upsert(point_id, new)
            msg = f"Resolved “{item.get('key')}”: kept the other device's value ({theirs.get('value')})."
        else:
            final = item.get("value") if choice == "mine" else value
            new = {**item, "value": final, "sync_state": "pending", "base_version": server_version, "conflict": None,
                   "updated_at": now_iso(), "device_id": self.cfg.device_id, "device_name": self.cfg.label,
                   "sync_reason": "Resolved; queued to sync." }
            self.memory.upsert(point_id, new)
            msg = f"Resolved “{item.get('key')}”: {'kept this device’s value' if choice == 'mine' else 'merged to'} {final}."
        self.activity.log("conflict", msg, id=point_id)
        return self.memory.get(point_id)

    # ---------------------------------------------------------------- background loop
    def start(self):
        def loop():
            while not self._stop.wait(self.cfg.auto_sync_seconds):
                if self.connectivity()["online"]:
                    self.sync(reason="auto")
        threading.Thread(target=loop, daemon=True).start()

    def stop(self):
        self._stop.set()
