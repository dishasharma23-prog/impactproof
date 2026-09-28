"""Evidence pipeline: one file in, one sealed and checked evidence record out."""
import hashlib
import io
import logging
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from PIL import Image
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models import domain
from app.services import audit_service, capture_tokens, provenance_service, trust_engine, weather_service
from app.services.cloudinary_service import CloudinaryService
from app.services.hash_service import HashService
from app.services.metadata_service import MetadataService
from app.services.vision_service import vision_service

log = logging.getLogger(__name__)
ALLOWED = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
ORIGINALS = Path(settings.STORAGE_DIR) / "originals"


class IngestError(Exception):
    pass


def default_project(db: Session) -> domain.Project:
    p = db.query(domain.Project).order_by(domain.Project.id.asc()).first()
    if not p:
        p = domain.Project(name="My first project", description="Field work documented with photos.")
        db.add(p)
        db.commit()
        db.refresh(p)
    return p


def _detect_mime(data: bytes, declared: str | None) -> str:
    try:
        with Image.open(io.BytesIO(data)) as im:
            fmt = (im.format or "").upper()
            im.verify()
    except Exception:
        raise IngestError("This file is not a readable image.")
    mime = {"JPEG": "image/jpeg", "MPO": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(fmt)
    if not mime:
        raise IngestError(f"Unsupported image type ({fmt or declared}). Use JPG, PNG or WEBP. "
                          f"iPhone users: set Camera > Formats > Most Compatible.")
    return mime


def ingest(db: Session, data: bytes, filename: str, declared_type: str | None, project_id: int | None,
           site_id: int | None = None, capture: dict | None = None, actor: str = "uploader",
           cloudinary_existing: dict | None = None) -> domain.EvidenceAsset:
    """cloudinary_existing: the asset was already uploaded to Cloudinary (Upload Widget); don't upload again."""
    mime = _detect_mime(data, declared_type)
    project = db.get(domain.Project, project_id) if project_id else default_project(db)
    if not project:
        raise IngestError("Unknown project.")
    site = db.get(domain.Site, site_id) if site_id else None
    if site and site.project_id != project.id:
        site = None

    sha256 = hashlib.sha256(data).hexdigest()
    md5 = hashlib.md5(data).hexdigest()
    local_name = f"{uuid.uuid4().hex}{ALLOWED[mime]}"
    local_path = ORIGINALS / local_name
    local_path.write_bytes(data)

    meta = MetadataService.extract_metadata(str(local_path))
    phash = HashService.calculate_phash(str(local_path))
    provenance = provenance_service.assess(str(local_path), data)

    e = domain.EvidenceAsset(
        project_id=project.id, site_id=site.id if site else None, original_filename=filename or local_name,
        capture_time=meta["capture_time"], latitude=meta["latitude"], longitude=meta["longitude"],
        device_info=meta["device_info"], software=meta["software"], width=meta["width"], height=meta["height"],
        mime_type=mime, file_size=len(data), sha256=sha256, md5=md5, phash=phash, local_file=local_name,
        provenance=provenance, capture_source="upload", processing_status="PROCESSING",
        uploaded_at=datetime.utcnow(),
    )

    if capture:  # taken with the in-app camera
        token_body, token_error = capture_tokens.verify(capture.get("token") or "")
        if token_body and not token_error:
            used = db.get(domain.UsedCaptureToken, token_body["tid"])
            if used:
                token_error = "Capture token was already used for another photo."
            else:
                db.add(domain.UsedCaptureToken(token_id=token_body["tid"]))
        offset = int(capture.get("tz_offset_min") or 0)       # JS getTimezoneOffset(): UTC - local, minutes
        server_local = datetime.utcnow() - timedelta(minutes=offset)
        e.capture_source = "in_app"
        e.capture_time = server_local.replace(microsecond=0)
        if capture.get("gps_lat") is not None and capture.get("gps_lng") is not None:
            e.latitude, e.longitude = round(float(capture["gps_lat"]), 6), round(float(capture["gps_lng"]), 6)
        e.capture_meta = {
            "gps_lat": capture.get("gps_lat"), "gps_lng": capture.get("gps_lng"),
            "gps_accuracy_m": capture.get("gps_accuracy"), "client_time": capture.get("client_time"),
            "server_received_utc": datetime.utcnow().isoformat(timespec="seconds"),
            "token_error": token_error or None, "selected_site_id": site.id if site else None,
            "user_agent": (capture.get("user_agent") or "")[:200],
        }

    db.add(e)
    db.flush()  # assigns e.id

    if cloudinary_existing:
        res = cloudinary_existing
        e.cloudinary_url = res.get("secure_url")
        e.cloudinary_public_id = res.get("public_id")
        e.cloudinary_etag = res.get("etag")
        e.cloudinary_phash = res.get("phash")
        e.cloudinary_asset_id = res.get("asset_id")
        e.cloudinary_version = str(res.get("version") or "")
    elif CloudinaryService.enabled():
        try:
            res = CloudinaryService.upload_image(str(local_path), f"ev_{e.id:04d}_{sha256[:8]}", project.id)
            e.cloudinary_url = res.get("secure_url")
            e.cloudinary_public_id = res.get("public_id")
            e.cloudinary_etag = res.get("etag")
            e.cloudinary_phash = res.get("phash")
            e.cloudinary_asset_id = res.get("asset_id")
            e.cloudinary_version = str(res.get("version") or "")
        except Exception as ex:
            db.rollback()
            local_path.unlink(missing_ok=True)
            raise IngestError(f"Cloudinary upload failed: {str(ex)[:200]}")

    analysis = vision_service.analyze_evidence(str(local_path), mime, project)
    if analysis["data"]:
        d = analysis["data"]
        db.add(domain.AIAnalysis(evidence_id=e.id, provider=analysis["provider"], observations=d.observations,
                                 objects=d.objects, activities=d.activities, raw_response=d.raw_response))
    e.processing_status = "COMPLETED" if analysis["status"] == "COMPLETED" else "AI_FAILED"
    if analysis.get("error"):
        e.capture_meta = {**(e.capture_meta or {}), "ai_error": analysis["error"][:300]}

    if e.latitude is not None and e.capture_time:
        e.weather = weather_service.lookup(e.latitude, e.longitude, e.capture_time)

    source = ("ImpactProof camera" if e.capture_source == "in_app"
              else "Cloudinary Upload Widget" if cloudinary_existing else "file upload")
    audit_service.log(db, "evidence", e.id, "received",
                      f"Received {e.original_filename} by {source}. SHA-256 {sha256[:16]}…", {
                          "sha256": sha256, "md5": md5, "cloudinary_public_id": e.cloudinary_public_id,
                          "cloudinary_etag_matches": (e.cloudinary_etag == md5) if e.cloudinary_etag else None,
                          "provenance": provenance.get("verdict")}, actor)
    db.commit()
    retrust_all(db, focus_ids={e.id})
    db.refresh(e)
    index_semantic(db, e)
    return e


def load_all(db: Session) -> list[domain.EvidenceAsset]:
    return (db.query(domain.EvidenceAsset)
            .options(joinedload(domain.EvidenceAsset.ai_analysis), joinedload(domain.EvidenceAsset.integrity),
                     joinedload(domain.EvidenceAsset.project))
            .order_by(domain.EvidenceAsset.id.asc()).all())


def retrust_all(db: Session, focus_ids=frozenset(), actor="system") -> None:
    """Recompute every verdict. A new upload can change older verdicts (e.g. reuse), so all are rechecked."""
    evidence = load_all(db)
    projects = {p.id: p for p in db.query(domain.Project).all()}
    sites_by_project = {}
    for s in db.query(domain.Site).all():
        sites_by_project.setdefault(s.project_id, []).append(s)

    changed = []
    for e in evidence:
        project = projects.get(e.project_id)
        result = trust_engine.compute(e, project, sites_by_project.get(e.project_id, []), evidence)
        integ = e.integrity
        old = integ.status if integ else None
        if not integ:
            integ = domain.IntegrityAssessment(evidence_id=e.id)
            db.add(integ)
            e.integrity = integ
        integ.status = result["status"]
        integ.engine_status = result["engine_status"]
        integ.signals = result["signals"]
        integ.score = result["score"]
        integ.available = result["available"]
        integ.total = result["total"]
        integ.duplicate_matches = result["duplicate_matches"]
        integ.computed_at = datetime.utcnow()

        reuse = result["signals"]["reuse"]
        e.duplicate_of_evidence_id = reuse.get("match_id") if reuse["status"] in ("fail", "warn") else None
        selected = (e.capture_meta or {}).get("selected_site_id")
        e.site_id = result["site_id"] or selected or (e.site_id if result["signals"]["location"]["status"] == "unavailable" else None)

        if old != integ.status:
            changed.append(e)
            if old is not None or e.id in focus_ids:
                label = trust_engine.STATUS_LABELS.get(integ.status, integ.status)
                reasons = trust_engine.headline_reasons(integ.signals, 2)
                audit_service.log(db, "evidence", e.id, "verdict",
                                  f"Verdict: {label}" + (f" (was {trust_engine.STATUS_LABELS.get(old, old)})" if old else "")
                                  + (f". {reasons[0]}" if reasons else ""),
                                  {"from": old, "to": integ.status, "score": integ.score}, actor)
    db.commit()
    payloads = [p for p in (CloudinaryService.trust_payload(e, e.integrity) for e in evidence
                            if e in changed or e.id in focus_ids) if p]
    if payloads:  # slow network calls: don't make the person wait for them
        threading.Thread(target=lambda: [CloudinaryService.push_trust(p) for p in payloads], daemon=True).start()


def image_bytes(e: domain.EvidenceAsset) -> tuple[bytes, str]:
    """The original file: from local storage if kept, otherwise downloaded from Cloudinary."""
    if e.local_file and (ORIGINALS / e.local_file).exists():
        return (ORIGINALS / e.local_file).read_bytes(), e.mime_type or "image/jpeg"
    if e.cloudinary_url and e.cloudinary_url.startswith("http"):
        r = httpx.get(e.cloudinary_url, timeout=30, follow_redirects=True)
        r.raise_for_status()
        return r.content, r.headers.get("content-type", "image/jpeg").split(";")[0]
    raise IngestError("The original image is not available.")


def ensure_local(e: domain.EvidenceAsset) -> Path:
    if e.local_file and (ORIGINALS / e.local_file).exists():
        return ORIGINALS / e.local_file
    data, mime = image_bytes(e)
    name = f"{uuid.uuid4().hex}{ALLOWED.get(mime, '.jpg')}"
    (ORIGINALS / name).write_bytes(data)
    e.local_file = name
    e.mime_type = e.mime_type or mime
    if not e.sha256:
        e.sha256 = hashlib.sha256(data).hexdigest()
        e.md5 = hashlib.md5(data).hexdigest()
    return ORIGINALS / name


def rerun_checks(db: Session, e: domain.EvidenceAsset, actor="reviewer") -> domain.EvidenceAsset:
    """Re-run AI analysis, provenance, metadata-derived checks and weather for one record."""
    path = ensure_local(e)
    data = path.read_bytes()
    if not e.provenance:
        e.provenance = provenance_service.assess(str(path), data)
    if e.capture_source != "in_app":
        meta = MetadataService.extract_metadata(str(path))
        e.software = e.software or meta["software"]
        e.width, e.height = e.width or meta["width"], e.height or meta["height"]
    if not e.phash:
        e.phash = HashService.calculate_phash(str(path))
    analysis = vision_service.analyze_evidence(str(path), e.mime_type or "image/jpeg", e.project)
    if analysis["data"]:
        d = analysis["data"]
        ai = e.ai_analysis or domain.AIAnalysis(evidence_id=e.id)
        ai.provider, ai.observations, ai.objects, ai.activities, ai.raw_response = (
            analysis["provider"], d.observations, d.objects, d.activities, d.raw_response)
        if not e.ai_analysis:
            db.add(ai)
        e.processing_status = "COMPLETED"
    elif analysis.get("error"):
        db.commit()
        raise IngestError(analysis["error"])
    if e.latitude is not None and e.capture_time:
        e.weather = weather_service.lookup(e.latitude, e.longitude, e.capture_time)
    audit_service.log(db, "evidence", e.id, "rechecked", "AI analysis and checks were run again.", None, actor)
    db.commit()
    retrust_all(db, focus_ids={e.id}, actor=actor)
    db.refresh(e)
    index_semantic(db, e)
    return e


def index_semantic(db: Session, e: domain.EvidenceAsset) -> None:
    """Semantic search indexing runs in the background (it calls Gemini embeddings and Qdrant)."""
    from app.services.qdrant_service import qdrant_service
    try:
        text = qdrant_service.generate_semantic_text(e.ai_analysis, e)
    except Exception as ex:
        log.warning(f"Semantic text failed for EV-{e.id:04d}: {ex}")
        return
    payload = {"project_id": e.project_id, "site_id": e.site_id,
               "capture_time": e.capture_time.isoformat() if e.capture_time else None,
               "integrity_status": e.integrity.status if e.integrity else None,
               "original_or_derived": "ORIGINAL", "cloudinary_public_id": e.cloudinary_public_id}
    eid = e.id

    def work():
        from app.db.database import SessionLocal
        status = "INDEXED"
        try:
            qdrant_service.upsert_evidence(eid, text, payload)
        except Exception as ex:
            log.warning(f"Semantic indexing skipped for EV-{eid:04d}: {ex}")
            status = "FAILED"
        s2 = SessionLocal()
        try:
            rec = s2.get(domain.EvidenceAsset, eid)
            if rec:
                rec.semantic_index_status = status
                s2.commit()
        finally:
            s2.close()

    threading.Thread(target=work, daemon=True).start()


def ingest_from_cloudinary(db: Session, public_id: str, project_id: int | None, site_id: int | None,
                           filename: str | None, actor: str = "uploader") -> domain.EvidenceAsset:
    """For photos uploaded straight to Cloudinary by the Upload Widget: fetch the stored original, confirm
    it matches Cloudinary's own checksum, then run the same checks as any other upload."""
    if not CloudinaryService.enabled():
        raise IngestError("Cloudinary is not configured.")
    if not public_id.startswith(settings.CLOUDINARY_FOLDER + "/"):
        raise IngestError("That asset was not uploaded through ImpactProof.")
    existing = db.query(domain.EvidenceAsset).filter(domain.EvidenceAsset.cloudinary_public_id == public_id).first()
    if existing:
        return existing
    try:
        res = CloudinaryService.fetch_resource(public_id)
        r = httpx.get(res["secure_url"], timeout=60, follow_redirects=True)
        r.raise_for_status()
    except Exception as ex:
        raise IngestError(f"Could not fetch the photo from Cloudinary: {str(ex)[:200]}")
    data = r.content
    if res.get("etag") and hashlib.md5(data).hexdigest() != res["etag"]:
        raise IngestError("The file downloaded from Cloudinary does not match Cloudinary's checksum.")
    name = filename or f"{res.get('original_filename') or public_id.rsplit('/', 1)[-1]}.{res.get('format') or 'jpg'}"
    return ingest(db, data, name, None, project_id, site_id, None, actor, cloudinary_existing=res)
