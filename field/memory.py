"""On-device semantic memory, stored in a Qdrant Edge shard inside the app's data folder.

Every item (photo capture, field note, site fact, or knowledge pulled from HQ or other devices)
is one point with three kinds of vectors:
  text  dense meaning of its words        (bge-small, 384)
  clip  what a photo looks like           (CLIP, 512), so "garbage bags" finds pictures
  bm25  exact keywords                    (sparse, computed on device by Qdrant Edge)
"""
import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import qdrant_edge as q

from field.embed import CLIP_DIM, TEXT_DIM

FACT_NS = uuid.UUID("3f2b6c1e-8d4a-4f7e-9a51-2c7e0b9d4a10")
DENSE_MARGIN = 0.08  # cosine distance from the best match beyond which dense hits are dropped
KINDS = ("capture", "note", "fact", "hq_site", "hq_evidence")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fact_id(key: str) -> str:
    """Facts with the same key share one ID on every device, which is what makes conflicts detectable."""
    return str(uuid.uuid5(FACT_NS, key.strip().lower()))


def _search_text(p: dict) -> str:
    parts = [p.get("title") or "", p.get("text") or "", p.get("site") or "", " ".join(p.get("tags") or [])]
    if p.get("kind") == "fact":
        parts.append(f"{p.get('key')} {p.get('value')}")
    return " ".join(x for x in parts if x).strip()


class Memory:
    def __init__(self, path: Path, embedder):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.embedder = embedder
        self.bm25 = q.Bm25(q.Bm25Config(language="english"))
        self.lock = threading.RLock()
        meta_file = self.path.parent / "memory_meta.json"
        meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
        if any(self.path.iterdir()):
            self.shard = q.EdgeShard.load(str(self.path))
        else:
            self.shard = q.EdgeShard.create(str(self.path), q.EdgeConfig(
                vectors={"text": q.EdgeVectorParams(size=TEXT_DIM, distance=q.Distance.Cosine),
                         "clip": q.EdgeVectorParams(size=CLIP_DIM, distance=q.Distance.Cosine)},
                sparse_vectors={"bm25": q.EdgeSparseVectorParams(modifier=q.Modifier.Idf)}))
            for f, t in (("kind", q.PayloadSchemaType.Keyword), ("origin", q.PayloadSchemaType.Keyword),
                         ("sync_state", q.PayloadSchemaType.Keyword), ("life", q.PayloadSchemaType.Keyword),
                         ("site", q.PayloadSchemaType.Keyword)):
                self.shard.update(q.UpdateOperation.create_field_index(f, t))
        self.embedder_changed = meta.get("embedder") not in (None, embedder.name)
        meta_file.write_text(json.dumps({"embedder": embedder.name}))

    # ---------------------------------------------------------------- writing
    def vectors_for(self, payload: dict, image_path: str | None = None) -> dict:
        text = _search_text(payload) or payload.get("kind", "item")
        v = {"text": self.embedder.text(text), "bm25": self.bm25.embed_document(text)}
        if image_path and Path(image_path).exists():
            v["clip"] = self.embedder.image(image_path)
        return v

    def upsert(self, point_id: str, payload: dict, image_path: str | None = None, vectors: dict | None = None):
        deleted = bool(payload.get("deleted", False))
        # Qdrant Edge filters booleans unreliably, so a keyword mirrors the flag for filtering
        payload = {**payload, "deleted": deleted, "life": "deleted" if deleted else "active"}
        with self.lock:
            vec = vectors or self.vectors_for(payload, image_path)
            self.shard.update(q.UpdateOperation.upsert_points([q.Point(point_id, vec, payload)]))
            self.shard.flush()
        return point_id

    def set_payload(self, point_id: str, patch: dict):
        with self.lock:
            self.shard.update(q.UpdateOperation.set_payload([point_id], patch))
            self.shard.flush()

    def delete(self, point_id: str):
        with self.lock:
            self.shard.update(q.UpdateOperation.delete_points([point_id]))
            self.shard.flush()

    # ---------------------------------------------------------------- reading
    def get(self, point_id: str, with_vector=False) -> dict | None:
        with self.lock:
            recs = self.shard.retrieve([point_id], with_payload=True, with_vector=with_vector)
        if not recs:
            return None
        r = recs[0]
        out = {"id": str(r.id), **(r.payload or {})}
        if with_vector:
            out["_vector"] = r.vector
        return out

    def all(self, flt: q.Filter | None = None, with_vector=False) -> list[dict]:
        out, offset = [], None
        with self.lock:
            while True:
                recs, offset = self.shard.scroll(q.ScrollRequest(offset=offset, limit=256, filter=flt,
                                                                 with_payload=True, with_vector=with_vector))
                for r in recs:
                    d = {"id": str(r.id), **(r.payload or {})}
                    if with_vector:
                        d["_vector"] = r.vector
                    out.append(d)
                if offset is None:
                    break
        return out

    def count(self, flt: q.Filter | None = None) -> int:
        with self.lock:
            return self.shard.count(q.CountRequest(filter=flt))

    @staticmethod
    def match(**kv) -> q.Filter:
        conds = []
        for k, v in kv.items():
            if isinstance(v, (list, tuple)):
                conds.append(q.FieldCondition(key=k, match=q.MatchAny(list(v))))
            else:
                conds.append(q.FieldCondition(key=k, match=q.MatchValue(v)))
        return q.Filter(must=conds)

    def search(self, query: str, mode: str = "all", kinds: list[str] | None = None, limit: int = 12) -> dict:
        """Hybrid search on device: dense meaning + BM25 keywords (+ CLIP for photos), fused with RRF."""
        t0 = time.perf_counter()
        must = [q.FieldCondition(key="life", match=q.MatchValue("active"))]
        if kinds:
            must.append(q.FieldCondition(key="kind", match=q.MatchAny(kinds)))
        flt = q.Filter(must=must)
        text_vec = self.embedder.text(query)
        sparse = self.bm25.embed_query(query)
        clip_vec = self.embedder.clip_text(query) if mode == "photos" else None
        # Each signal is its own on-device query; results are fused with reciprocal-rank fusion.
        # "all" = meaning + keywords (hybrid); "photos" = what pictures look like (CLIP) + their captions.
        floor = getattr(self.embedder, "text_floor", 0.0)
        signals = []  # (query, weight, is_keyword, min score); keyword first so dense trimming can keep keyword hits
        if mode in ("all", "keyword"):
            signals.append((q.Query.Nearest(sparse, using="bm25"), 1.0, True, 0.0))
        if mode in ("all", "semantic"):
            signals.append((q.Query.Nearest(text_vec, using="text"), 1.0, False, floor))
        if clip_vec is not None:
            signals.append((q.Query.Nearest(clip_vec, using="clip"), 1.0, False, 0.0))
            signals.append((q.Query.Nearest(text_vec, using="text"), 0.5, False, floor))
        fused, payloads, keyword_ids = {}, {}, set()
        with self.lock:
            for query_, weight, is_keyword, min_score in signals:
                hits = self.shard.query(q.QueryRequest(limit=40, query=query_, filter=flt, with_payload=True))
                if is_keyword:
                    hits = [h for h in hits if h.score > 0]
                    keyword_ids.update(str(h.id) for h in hits)
                elif hits:
                    # dense search always returns the nearest items, even unrelated ones,
                    # so keep only those close to the best match (or that matched a keyword)
                    top = hits[0].score
                    hits = [h for h in hits if (h.score >= top - DENSE_MARGIN and h.score >= min_score) or str(h.id) in keyword_ids]
                for rank, h in enumerate(hits):
                    pid = str(h.id)
                    fused[pid] = fused.get(pid, 0.0) + weight / (60 + rank)
                    payloads[pid] = h.payload or {}
        order = sorted(fused, key=lambda k: -fused[k])[:limit]
        hits = [(pid, fused[pid], payloads[pid]) for pid in order]
        ms = (time.perf_counter() - t0) * 1000
        results = [{"id": pid, "score": round(score, 4), **payload} for pid, score, payload in hits]
        stamp = now_iso()
        for r in results:  # remember what is useful, for the memory budget
            if r.get("origin") != "local":
                self.set_payload(r["id"], {"last_used_at": stamp})
        return {"query": query, "mode": mode, "ms": round(ms, 1), "results": results}

    def similar_captures(self, image_vec, limit=3) -> list[dict]:
        flt = q.Filter(must=[q.FieldCondition(key="kind", match=q.MatchValue("capture")),
                             q.FieldCondition(key="life", match=q.MatchValue("active"))])
        with self.lock:
            hits = self.shard.query(q.QueryRequest(limit=limit, query=q.Query.Nearest(image_vec, using="clip"),
                                                   filter=flt, with_payload=True))
        return [{"id": str(h.id), "score": h.score, **(h.payload or {})} for h in hits]

    def info(self) -> dict:
        with self.lock:
            i = self.shard.info()
        # real blocks used; Qdrant preallocates sparse files, so the apparent size overstates it
        size = sum(getattr(st, "st_blocks", 0) * 512 or st.st_size for st in (f.stat() for f in self.path.rglob("*") if f.is_file()))
        return {"points": i.points_count, "segments": i.segments_count, "indexed_vectors": i.indexed_vectors_count,
                "disk_bytes": size, "embedder": self.embedder.name}

    def close(self):
        with self.lock:
            self.shard.flush()
            self.shard.close()
