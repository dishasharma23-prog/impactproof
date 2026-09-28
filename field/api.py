"""The field device's local API and UI. Everything here works without a network."""
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from field import exif, policy
from field.activity import Activity
from field.config import ROOT, Config
from field.embed import make_embedder
from field.memory import Memory, fact_id, now_iso
from field.sync import SyncEngine

STATES = ("pending", "synced", "local_only", "skipped", "conflict")


def create_app(cfg: Config, client=None, http=None, embedder=None, start_background=True) -> FastAPI:
    cfg.device_dir.mkdir(parents=True, exist_ok=True)
    photos = cfg.device_dir / "photos"
    photos.mkdir(exist_ok=True)
    emb = embedder or make_embedder(cfg.embedder, cache_dir=str(ROOT / "models"))
    memory = Memory(cfg.device_dir / "shard", emb)
    activity = Activity(cfg.device_dir / "activity.jsonl")
    engine = SyncEngine(cfg, memory, activity, client=client, http=http)
    app = FastAPI(title=f"ImpactProof Field ({cfg.device_id})")
    app.state.cfg, app.state.memory, app.state.engine, app.state.activity = cfg, memory, engine, activity
    if memory.embedder_changed:
        activity.log("warning", "The embedding model changed since this memory was built; search quality "
                                "improves after re-adding items.")
    activity.log("device", f"{cfg.label} started. Memory holds {memory.count()} items.")

    if start_background:
        @app.on_event("startup")
        def _bg():
            engine.start()

        @app.on_event("shutdown")
        def _close():
            engine.stop()
            memory.close()

    def base_item(kind: str, **kw) -> dict:
        ts = now_iso()
        return {"kind": kind, "origin": "local", "device_id": cfg.device_id, "device_name": cfg.label,
                "created_at": ts, "updated_at": ts, "tags": [], **kw}

    def summary(i: dict) -> dict:
        i = {k: v for k, v in i.items() if not k.startswith("_")}
        if i.get("image_file"):
            i["image_url"] = f"/photos/{Path(i['image_file']).name}"
        return i

    # ---------------------------------------------------------------- status
    @app.get("/api/status")
    def status():
        conn = engine.connectivity()
        counts = {s: memory.count(memory.match(sync_state=s, life="active")) for s in STATES}
        kinds = {k: memory.count(memory.match(kind=k, life="active")) for k in ("capture", "note", "fact", "hq_site", "hq_evidence")}
        origins = {o: memory.count(memory.match(origin=o, life="active")) for o in ("local", "peer", "hq")}
        waiting_photos = memory.count(memory.match(kind="capture", origin="local", photo_state="waiting_wifi"))
        return {"device_id": cfg.device_id, "device_name": cfg.label, "connectivity": conn,
                "simulated_offline": engine.simulated_offline, "network": engine.network,
                "allow_media_on_mobile": engine.allow_media_on_mobile, "sync_states": counts, "kinds": kinds,
                "origins": origins, "waiting_photos": waiting_photos, "last_sync": engine.last_sync,
                "memory": memory.info(), "budget": cfg.memory_budget, "server": cfg.qdrant_url,
                "hq": cfg.hq_url or None, "auto_sync_seconds": cfg.auto_sync_seconds,
                "volunteer": ({k: v for k, v in p.items() if k != "device_key"} if (p := engine.pairing()) else None)}

    class NetworkIn(BaseModel):
        offline: Optional[bool] = None
        network: Optional[str] = None
        allow_media_on_mobile: Optional[bool] = None

    class PairIn(BaseModel):
        phone: str
        code: str

    @app.post("/api/pair")
    def pair(body: PairIn):
        if not engine.connectivity()["online"]:
            raise HTTPException(status_code=409, detail="Signing in needs a connection to ImpactProof once. Try again when online.")
        try:
            rec = engine.pair(body.phone, body.code)
        except PermissionError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Couldn't reach ImpactProof: {e}")
        return {k: v for k, v in rec.items() if k != "device_key"}

    @app.delete("/api/pair")
    def unpair():
        engine.clear_pairing()
        activity.log("pair", "Signed out. Photos stay on this device until someone signs in.")
        return {"ok": True}

    @app.post("/api/network")
    def set_network(body: NetworkIn):
        if body.offline is not None and body.offline != engine.simulated_offline:
            engine.simulated_offline = body.offline
            activity.log("network", "Went offline (simulated)." if body.offline else "Back online.")
        if body.network in ("wifi", "mobile") and body.network != engine.network:
            engine.network = body.network
            activity.log("network", f"Connection type: {'Wi-Fi' if body.network == 'wifi' else 'mobile data'}.")
        if body.allow_media_on_mobile is not None:
            engine.allow_media_on_mobile = body.allow_media_on_mobile
        return status()

    @app.post("/api/sync")
    def sync_now():
        return engine.sync(reason="manual")

    # ---------------------------------------------------------------- capture
    @app.post("/api/captures")
    async def capture(file: UploadFile = File(...), caption: str = Form(""), site: str = Form(""),
                      lat: Optional[float] = Form(None), lng: Optional[float] = Form(None),
                      tz_offset_min: Optional[int] = Form(None), private: bool = Form(False)):
        raw = await file.read()
        local_now = datetime.utcnow() - timedelta(minutes=tz_offset_min or 0)
        try:
            data = exif.stamp(raw, local_now, lat, lng, device=cfg.label)
        except Exception:
            raise HTTPException(status_code=400, detail="That file is not a readable image.")
        pid = str(uuid.uuid4())
        path = photos / f"{pid}.jpg"
        path.write_bytes(data)
        item = base_item("capture", title=caption[:80] or "Field photo", text=caption, site=site.strip(),
                         lat=lat, lng=lng, private=private, captured_local=local_now.isoformat(timespec="seconds"),
                         image_file=str(path))
        img_vec = emb.image(str(path))
        dup = None
        for m in memory.similar_captures(img_vec, limit=3):
            if m["score"] >= policy.DUPLICATE_SIMILARITY and m.get("origin") == "local":
                try:
                    age = abs((datetime.fromisoformat(item["created_at"]) - datetime.fromisoformat(m["created_at"])).total_seconds())
                except Exception:
                    age = 0
                if age <= policy.DUPLICATE_WINDOW_S:
                    dup = {"id": m["id"], "short": m["id"][:8]}
                    break
        state, reason = policy.classify_new(item, dup)
        item.update(sync_state=state, sync_reason=reason, duplicate_of=dup["id"] if dup else None)
        vec = memory.vectors_for(item)
        vec["clip"] = img_vec
        memory.upsert(pid, item, vectors=vec)
        activity.log("capture", f"Photo captured{' at ' + site if site else ''}: {reason}", id=pid)
        return summary(memory.get(pid))

    class NoteIn(BaseModel):
        text: str
        site: str = ""
        tags: list[str] = []
        private: bool = False

    @app.post("/api/notes")
    def add_note(body: NoteIn):
        if not body.text.strip():
            raise HTTPException(status_code=400, detail="Write something first.")
        pid = str(uuid.uuid4())
        item = base_item("note", title=body.text.strip()[:80], text=body.text.strip(), site=body.site.strip(),
                         tags=[t.strip() for t in body.tags if t.strip()], private=body.private)
        state, reason = policy.classify_new(item)
        item.update(sync_state=state, sync_reason=reason)
        memory.upsert(pid, item)
        activity.log("note", f"Note saved: {reason}", id=pid)
        return summary(memory.get(pid))

    class FactIn(BaseModel):
        key: str
        value: str
        site: str = ""

    @app.post("/api/facts")
    def set_fact(body: FactIn):
        """A shared, updatable fact such as 'North bank: bags collected = 14'. Same key = same record everywhere."""
        key = body.key.strip()
        if not key:
            raise HTTPException(status_code=400, detail="Give the fact a name.")
        pid = fact_id(key)
        cur = memory.get(pid)
        if cur and cur.get("sync_state") == "conflict":
            raise HTTPException(status_code=409, detail="Resolve the conflict on this fact first.")
        item = {**(cur or base_item("fact", base_version=0, version=0)), "key": key, "value": body.value.strip(),
                "title": key, "text": f"{key}: {body.value.strip()}", "site": body.site.strip() or (cur or {}).get("site", ""),
                "updated_at": now_iso(), "device_id": cfg.device_id, "device_name": cfg.label, "origin": "local"}
        state, reason = policy.classify_new(item)
        item.update(sync_state=state, sync_reason=reason)
        memory.upsert(pid, item)
        activity.log("fact", f"Fact “{key}” set to {body.value.strip()}.", id=pid)
        return summary(memory.get(pid))

    # ---------------------------------------------------------------- memory
    @app.get("/api/items")
    def items(kind: Optional[str] = None, state: Optional[str] = None, origin: Optional[str] = None):
        flt = {"life": "active"}
        if kind:
            flt["kind"] = kind
        if state:
            flt["sync_state"] = state
        if origin:
            flt["origin"] = origin
        rows = memory.all(memory.match(**flt))
        rows.sort(key=lambda i: i.get("updated_at") or i.get("created_at") or "", reverse=True)
        return [summary(r) for r in rows]

    @app.get("/api/items/{pid}")
    def item(pid: str):
        i = memory.get(pid)
        if not i:
            raise HTTPException(status_code=404, detail="Not in this device's memory.")
        return summary(i)

    @app.delete("/api/items/{pid}")
    def delete_item(pid: str):
        i = memory.get(pid)
        if not i:
            raise HTTPException(status_code=404, detail="Not found.")
        if i.get("origin") != "local" or i.get("sync_state") in ("local_only", "skipped") or i.get("sync_state") == "pending" and not i.get("synced_at"):
            memory.delete(pid)
            activity.log("delete", f"Removed “{i.get('title')}” from this device.")
        else:  # already on the server: send a tombstone so other devices drop it too
            memory.upsert(pid, {**i, "deleted": True, "sync_state": "pending", "updated_at": now_iso(),
                                "sync_reason": "Deletion queued to sync."})
            activity.log("delete", f"Deleted “{i.get('title')}”; other devices will drop it after the next sync.")
        return {"deleted": pid}

    class ShareIn(BaseModel):
        private: bool

    @app.post("/api/items/{pid}/privacy")
    def set_privacy(pid: str, body: ShareIn):
        i = memory.get(pid)
        if not i or i.get("origin") != "local":
            raise HTTPException(status_code=404, detail="Only this device's own items can be changed.")
        i["private"] = body.private
        state, reason = policy.classify_new({**i, "kind": i["kind"]})
        if not body.private and i.get("sync_state") == "synced":
            state, reason = "synced", i.get("sync_reason")
        memory.set_payload(pid, {"private": body.private, "sync_state": state, "sync_reason": reason})
        activity.log("privacy", f"“{i.get('title')}” marked {'private' if body.private else 'shareable'}.")
        return summary(memory.get(pid))

    class ResolveIn(BaseModel):
        choice: str                 # mine | theirs | merge
        value: Optional[str] = None

    @app.post("/api/items/{pid}/resolve")
    def resolve(pid: str, body: ResolveIn):
        if body.choice not in ("mine", "theirs", "merge") or (body.choice == "merge" and not (body.value or "").strip()):
            raise HTTPException(status_code=400, detail="Choose mine, theirs, or merge with a value.")
        try:
            return summary(engine.resolve(pid, body.choice, (body.value or "").strip() or None))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/search")
    def search(q: str, mode: str = "all", kinds: Optional[str] = None, limit: int = 12):
        if mode not in ("all", "semantic", "keyword", "photos"):
            raise HTTPException(status_code=400, detail="Unknown search mode.")
        kind_list = [k for k in (kinds or "").split(",") if k] or (["capture", "hq_evidence"] if mode == "photos" else None)
        res = memory.search(q, mode, kind_list, limit)
        res["results"] = [summary(r) for r in res["results"]]
        res["offline"] = not engine.connectivity()["online"]
        return res

    @app.get("/api/activity")
    def get_activity(n: int = 100):
        return activity.recent(n)

    @app.get("/photos/{name}")
    def photo(name: str):
        p = photos / Path(name).name
        if not p.exists():
            raise HTTPException(status_code=404, detail="Photo not on this device.")
        return FileResponse(p)

    app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

    @app.get("/")
    def index():
        return FileResponse(ROOT / "static" / "index.html")

    return app
