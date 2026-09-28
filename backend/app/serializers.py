"""Turns database rows into the JSON the frontend uses."""
from app.core.config import settings
from app.models import domain
from app.services import classify, sdg, trust_engine
from app.services.cloudinary_service import CloudinaryService


def iso(v):
    return v.isoformat() if v else None


def evidence_code(eid: int) -> str:
    return f"EV-{eid:04d}"


def image_url(e: domain.EvidenceAsset) -> str | None:
    if e.cloudinary_url:
        return e.cloudinary_url
    if e.local_file:
        return f"{settings.PUBLIC_API_URL}/media/{e.local_file}"
    return None


def thumb_url(e: domain.EvidenceAsset, w=640, h=480) -> str | None:
    return CloudinaryService.thumb_url(e, w, h) if e.cloudinary_public_id else image_url(e)


def status_of(e) -> str:
    return e.integrity.status if e.integrity and e.integrity.status else "UNVERIFIABLE"


def evidence_light(e: domain.EvidenceAsset) -> dict:
    raw = (e.ai_analysis.raw_response or {}) if e.ai_analysis else {}
    integ = e.integrity
    status = status_of(e)
    return {
        "id": e.id, "code": evidence_code(e.id), "original_filename": e.original_filename,
        "cloudinary_url": image_url(e), "image_url": image_url(e), "thumb_url": thumb_url(e),
        "cloudinary_public_id": e.cloudinary_public_id,
        "capture_time": iso(e.capture_time), "uploaded_at": iso(e.uploaded_at),
        "latitude": e.latitude, "longitude": e.longitude,
        "project_id": e.project_id, "site_id": e.site_id, "site_name": e.site.name if e.site else None,
        "capture_source": e.capture_source or "upload",
        "processing_status": e.processing_status, "phash": e.phash,
        "integrity_status": status, "status_label": trust_engine.STATUS_LABELS.get(status, status),
        "trust_score": integ.score if integ else None,
        "checks_available": integ.available if integ else None, "checks_total": integ.total if integ else None,
        "headline_reasons": trust_engine.headline_reasons(integ.signals if integ else {}, 2),
        "activity": raw.get("activity") or ((e.ai_analysis.activities or [None])[0] if e.ai_analysis else None),
        "tags": raw.get("tags") or [],
        "review_status": e.review_status,
        "sdgs": [sdg.info(n) for n in sdg.evidence_sdgs(e, e.project)],
        **classify.labels(e),
        "duplicate_of_evidence_id": e.duplicate_of_evidence_id,
        "original_or_derived": "ORIGINAL",
        "metadata_status": ((integ.signals or {}).get("metadata") or {}).get("status", "unavailable") if integ else "unavailable",
        "captured_by": _captured_by(e),
    }


def _captured_by(e) -> dict | None:
    v = getattr(e, "volunteer", None)
    if not v:
        return None
    from app.services.volunteers import mask
    return {"name": v.name, "phone_masked": mask(v.phone), "device": v.device_name}


def evidence_full(e: domain.EvidenceAsset, db=None) -> dict:
    d = evidence_light(e)
    integ = e.integrity
    ai = e.ai_analysis
    raw = (ai.raw_response or {}) if ai else {}
    matches = []
    for m in (integ.duplicate_matches or []) if integ else []:
        other = db.get(domain.EvidenceAsset, m["id"]) if db else None
        matches.append({**m, "code": evidence_code(m["id"]),
                        "image_url": image_url(other) if other else m.get("image_url"),
                        "thumb_url": thumb_url(other) if other else m.get("image_url"),
                        "status": status_of(other) if other else None})
    d.update({
        "device_info": e.device_info, "software": e.software, "width": e.width, "height": e.height,
        "mime_type": e.mime_type, "file_size": e.file_size,
        "location": {"latitude": e.latitude, "longitude": e.longitude},
        "capture_meta": {k: v for k, v in (e.capture_meta or {}).items() if k != "user_agent"},
        "seal": {
            "sha256": e.sha256, "md5": e.md5, "cloudinary_etag": e.cloudinary_etag,
            "cloudinary_matches": (e.cloudinary_etag == e.md5) if (e.cloudinary_etag and e.md5) else None,
            "cloudinary_phash": e.cloudinary_phash, "cloudinary_asset_id": e.cloudinary_asset_id,
            "cloudinary_version": e.cloudinary_version,
        },
        "provenance": e.provenance, "weather": e.weather,
        "ai_analysis": {
            "provider": ai.provider, "observations": ai.observations or [], "objects": ai.objects or [],
            "activities": ai.activities or [], "details": raw,
        } if ai else None,
        "ai_error": (e.capture_meta or {}).get("ai_error"),
        "integrity": {
            "status": integ.status, "engine_status": integ.engine_status,
            "status_label": trust_engine.STATUS_LABELS.get(integ.status, integ.status),
            "engine_status_label": trust_engine.STATUS_LABELS.get(integ.engine_status or "", integ.engine_status),
            "score": integ.score, "available": integ.available, "total": integ.total,
            "signals": integ.signals or {}, "computed_at": iso(integ.computed_at),
        } if integ else None,
        "duplicate_matches": matches,
        "project_name": e.project.name if e.project else None,
        "sdg_reason": raw.get("sdg_reason"),
        "cloudinary_record": cloudinary_record(e),
    })
    return d


def cloudinary_record(e) -> dict | None:
    """What ImpactProof stores on the Cloudinary asset, shown on the evidence page."""
    if not e.cloudinary_public_id or not e.integrity:
        return None
    payload = CloudinaryService.trust_payload(e, e.integrity)
    if not payload:
        return None
    return {"public_id": payload["public_id"], "tags": payload["tags"], "metadata": payload["metadata"],
            "context": payload["context"], "structured_metadata": CloudinaryService.metadata_available,
            "derived": {"thumbnail": thumb_url(e), "public_copy": CloudinaryService.public_url(e)}}


def site_dict(s: domain.Site, evidence=None) -> dict:
    items = [e for e in (evidence or []) if e.site_id == s.id]
    good = [e for e in items if status_of(e) == "CORROBORATED"]
    last = max((e.capture_time or e.uploaded_at for e in good), default=None)
    return {"id": s.id, "name": s.name, "project_id": s.project_id, "latitude": s.latitude,
            "longitude": s.longitude, "radius_m": s.radius_m or 300, "description": s.description,
            "evidence_count": len(items), "corroborated_count": len(good), "last_corroborated_at": iso(last)}


def project_dict(p: domain.Project) -> dict:
    return {"id": p.id, "name": p.name, "description": p.description, "organization": p.organization,
            "start_date": iso(p.start_date), "end_date": iso(p.end_date), "created_at": iso(p.created_at),
            "sdgs": [sdg.info(n) for n in sdg.valid(p.sdgs)]}


def sdg_summary(evidence: list, project) -> list[dict]:
    """How many corroborated photos support each goal."""
    counts = {}
    for e in evidence:
        if status_of(e) != "CORROBORATED":
            continue
        for n in sdg.evidence_sdgs(e, project):
            counts[n] = counts.get(n, 0) + 1
    goals = sdg.valid(project.sdgs) if project else []
    order = goals + sorted(n for n in counts if n not in goals)
    return [{**sdg.info(n), "photos": counts.get(n, 0)} for n in order]
