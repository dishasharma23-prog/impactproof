from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models import domain
from app.serializers import evidence_code, evidence_full, evidence_light
from app.services import audit_service, capture_tokens, pipeline, trust_engine
from app.services.cloudinary_service import CloudinaryService

router = APIRouter()
MAX_BYTES = 25 * 1024 * 1024


def _get(db, evidence_id) -> domain.EvidenceAsset:
    e = db.get(domain.EvidenceAsset, evidence_id)
    if not e:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return e


@router.post("/evidence/upload")
async def upload_evidence(
    file: UploadFile = File(...),
    project_id: Optional[int] = Form(None), site_id: Optional[int] = Form(None),
    capture_token: Optional[str] = Form(None), gps_lat: Optional[float] = Form(None),
    gps_lng: Optional[float] = Form(None), gps_accuracy: Optional[float] = Form(None),
    client_time: Optional[str] = Form(None), tz_offset_min: Optional[int] = Form(None),
    uploader: Optional[str] = Form(None), device_key: Optional[str] = Form(None),
    x_device_key: Optional[str] = Header(None), db: Session = Depends(get_db),
):
    # Field devices upload with the key they got when a registered volunteer paired them.
    # A key that is wrong or revoked is refused; web uploads by staff send no key.
    key = x_device_key or device_key
    volunteer = None
    if key:
        from app.services import volunteers as vs
        volunteer = vs.by_key(db, key)
        if not volunteer:
            raise HTTPException(status_code=401, detail="This device is not registered. Pair it with a volunteer's phone number in ImpactProof.")
        uploader = f"{volunteer.name} ({vs.mask(volunteer.phone)})"
        project_id = project_id or volunteer.project_id
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="File is larger than 25 MB.")
    capture = None
    if capture_token:
        capture = {"token": capture_token, "gps_lat": gps_lat, "gps_lng": gps_lng, "gps_accuracy": gps_accuracy,
                   "client_time": client_time, "tz_offset_min": tz_offset_min}
    try:
        # Checking a photo calls Cloudinary, Gemini and the weather service (10 to 30 s). Run it in a worker
        # thread so the server keeps answering other requests, including the host's health checks, meanwhile.
        from starlette.concurrency import run_in_threadpool
        e = await run_in_threadpool(pipeline.ingest, db, data, file.filename or "upload.jpg", file.content_type,
                                    project_id, site_id, capture, actor=uploader or "uploader")
    except pipeline.IngestError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    if volunteer:
        from datetime import datetime as _dt
        e.volunteer_id = volunteer.id
        volunteer.last_upload_at = _dt.utcnow()
        db.commit()
        db.refresh(e)
    return {
        "evidence_id": e.id, "processing_status": e.processing_status,
        "semantic_index_status": e.semantic_index_status,
        "cloudinary": {"status": "SUCCESS" if e.cloudinary_public_id else "OFF"},
        "ai": {"status": "COMPLETED" if e.ai_analysis else "FAILED",
               "provider": e.ai_analysis.provider if e.ai_analysis else None},
        "integrity": {"status": e.integrity.status if e.integrity else None},
        "evidence": evidence_light(e),
    }


@router.get("/evidence")
def list_evidence(project_id: Optional[int] = None, status: Optional[str] = None, q: Optional[str] = None,
                  site_id: Optional[int] = None, db: Session = Depends(get_db)):
    items = pipeline.load_all(db)
    items.sort(key=lambda e: e.uploaded_at or e.id, reverse=True)
    if project_id:
        items = [e for e in items if e.project_id == project_id]
    if site_id:
        items = [e for e in items if e.site_id == site_id]
    if status:
        items = [e for e in items if (e.integrity.status if e.integrity else "UNVERIFIABLE") == status]
    if q and q.strip():
        items = keyword_filter(items, q)
    return [evidence_light(e) for e in items]


def keyword_filter(items, q):
    words = q.lower().split()

    def hay(e):
        raw = (e.ai_analysis.raw_response or {}) if e.ai_analysis else {}
        parts = [evidence_code(e.id), e.original_filename or "", raw.get("activity", ""), raw.get("description", ""),
                 " ".join(map(str, raw.get("tags") or [])), " ".join(map(str, raw.get("visible_text") or [])),
                 " ".join(e.ai_analysis.observations or []) if e.ai_analysis else "",
                 e.site.name if e.site else ""]
        return " ".join(parts).lower()
    return [e for e in items if all(w in hay(e) for w in words)]


class SearchRequest(BaseModel):
    query: str
    project_id: Optional[int] = None
    site_id: Optional[int] = None
    limit: int = 12


@router.post("/evidence/search")
def search_evidence(req: SearchRequest, db: Session = Depends(get_db)):
    from app.services.qdrant_service import qdrant_service
    hits = qdrant_service.search(query=req.query, limit=req.limit * 2) if settings.QDRANT_URL else []
    results, mode = [], "semantic"
    for hit in hits:
        e = db.get(domain.EvidenceAsset, hit["evidence_id"])
        if not e or (req.project_id and e.project_id != req.project_id):
            continue
        results.append({**evidence_light(e), "evidence_id": e.id, "similarity": hit["similarity"]})
    if not results:
        mode = "keyword"
        items = [e for e in pipeline.load_all(db) if not req.project_id or e.project_id == req.project_id]
        results = [{**evidence_light(e), "evidence_id": e.id, "similarity": None}
                   for e in keyword_filter(items, req.query)]
    return {"query": req.query, "mode": mode, "results": results[:req.limit]}


@router.get("/evidence/{evidence_id}")
def get_evidence(evidence_id: int, db: Session = Depends(get_db)):
    return full_view(_get(db, evidence_id), db)


def full_view(e, db) -> dict:
    """Everything the evidence page shows, including linked claims and review decisions."""
    d = evidence_full(e, db)
    links = db.query(domain.ClaimEvidenceLink).filter(domain.ClaimEvidenceLink.evidence_id == e.id).all()
    d["claims"] = [{"id": l.claim_id, "text": l.claim.text if l.claim else ""} for l in links]
    d["reviews"] = [{"decision": r.decision, "reason": r.reason, "reviewer": r.reviewer,
                     "engine_status": r.engine_status, "created_at": r.created_at.isoformat()}
                    for r in db.query(domain.ReviewDecision).filter(domain.ReviewDecision.evidence_id == e.id)
                    .order_by(domain.ReviewDecision.created_at.desc()).all()]
    return d


@router.get("/evidence/{evidence_id}/history")
def evidence_history(evidence_id: int, db: Session = Depends(get_db)):
    _get(db, evidence_id)
    events = (db.query(domain.AuditEvent).filter(domain.AuditEvent.entity_type == "evidence",
                                                 domain.AuditEvent.entity_id == evidence_id)
              .order_by(domain.AuditEvent.created_at.asc(), domain.AuditEvent.id.asc()).all())
    return [audit_service.to_dict(ev) for ev in events]


@router.post("/evidence/{evidence_id}/recheck")
def recheck(evidence_id: int, db: Session = Depends(get_db)):
    e = _get(db, evidence_id)
    try:
        e = pipeline.rerun_checks(db, e)
    except pipeline.IngestError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    return full_view(e, db)


class ReviewIn(BaseModel):
    decision: str
    reason: str
    reviewer: str

    @field_validator("decision")
    @classmethod
    def valid_decision(cls, v):
        v = v.upper()
        if v not in ("APPROVED", "REJECTED", "REOPENED"):
            raise ValueError("Decision must be APPROVED, REJECTED or REOPENED")
        return v

    @field_validator("reason")
    @classmethod
    def reason_required(cls, v):
        if len(v.strip()) < 8:
            raise ValueError("Write a short reason (at least 8 characters) so the decision can be audited.")
        return v.strip()

    @field_validator("reviewer")
    @classmethod
    def reviewer_required(cls, v):
        if not v.strip():
            raise ValueError("Enter the reviewer's name.")
        return v.strip()[:80]


@router.post("/evidence/{evidence_id}/review")
def review(evidence_id: int, body: ReviewIn, db: Session = Depends(get_db)):
    e = _get(db, evidence_id)
    engine_status = e.integrity.engine_status if e.integrity else None
    db.add(domain.ReviewDecision(evidence_id=e.id, decision=body.decision, reason=body.reason,
                                 reviewer=body.reviewer, engine_status=engine_status))
    e.review_status = None if body.decision == "REOPENED" else body.decision
    verb = {"APPROVED": "Approved", "REJECTED": "Rejected", "REOPENED": "Reopened"}[body.decision]
    audit_service.log(db, "evidence", e.id, "review",
                      f"{verb} by {body.reviewer}: {body.reason}",
                      {"decision": body.decision, "engine_status": engine_status}, body.reviewer)
    db.commit()
    pipeline.retrust_all(db, focus_ids={e.id}, actor=body.reviewer)
    db.refresh(e)
    return full_view(e, db)


class DeleteIn(BaseModel):
    ids: list[int] = []
    actor: str = ""
    reason: str = ""


@router.delete("/evidence/{evidence_id}")
def delete_one(evidence_id: int, actor: str = "", reason: str = "", db: Session = Depends(get_db)):
    _get(db, evidence_id)
    from app.services.deletion import delete_evidence
    return {"deleted": delete_evidence(db, [evidence_id], actor or "unknown", reason)}


@router.post("/evidence/delete")
def delete_many(body: DeleteIn, db: Session = Depends(get_db)):
    if not body.ids:
        raise HTTPException(status_code=400, detail="Choose at least one photo to delete.")
    from app.services.deletion import delete_evidence
    return {"deleted": delete_evidence(db, body.ids, body.actor or "unknown", body.reason)}


class CampaignIn(BaseModel):
    caption: str = ""
    blur_faces: bool = True


@router.post("/evidence/{evidence_id}/campaign")
def campaign(evidence_id: int, body: CampaignIn, db: Session = Depends(get_db)):
    e = _get(db, evidence_id)
    if (e.integrity.status if e.integrity else None) != "CORROBORATED":
        raise HTTPException(status_code=400, detail="Campaign images can only be made from corroborated evidence.")
    if not e.cloudinary_public_id:
        raise HTTPException(status_code=400, detail="This photo is not on Cloudinary, so campaign images cannot be made.")
    out = CloudinaryService.campaign_derivatives(e, body.caption, body.blur_faces)
    audit_service.log(db, "evidence", e.id, "derivative",
                      f"Created {len(out)} campaign images{' with faces blurred' if body.blur_faces else ''}. "
                      f"The original was not changed.", {"caption": body.caption, "formats": [d["key"] for d in out]})
    db.commit()
    return out


@router.get("/capture/token")
def capture_token(project_id: Optional[int] = None, site_id: Optional[int] = None):
    return capture_tokens.issue(project_id, site_id)


@router.get("/review/queue")
def review_queue(project_id: Optional[int] = None, db: Session = Depends(get_db)):
    order = {"SUSPICIOUS": 0, "NEEDS_REVIEW": 1, "UNVERIFIABLE": 2}
    items = [e for e in pipeline.load_all(db)
             if (not project_id or e.project_id == project_id) and e.integrity
             and e.integrity.status in order and not e.review_status]
    items.sort(key=lambda e: (order[e.integrity.status], -(e.id)))
    return [evidence_light(e) for e in items]


@router.get("/review/decisions")
def recent_decisions(project_id: Optional[int] = None, limit: int = 30, db: Session = Depends(get_db)):
    q = db.query(domain.ReviewDecision).order_by(domain.ReviewDecision.created_at.desc())
    out = []
    for r in q.limit(200).all():
        e = db.get(domain.EvidenceAsset, r.evidence_id)
        if not e or (project_id and e.project_id != project_id):
            continue
        out.append({"evidence": evidence_light(e), "decision": r.decision, "reason": r.reason,
                    "reviewer": r.reviewer, "engine_status": r.engine_status,
                    "engine_status_label": trust_engine.STATUS_LABELS.get(r.engine_status or "", r.engine_status),
                    "created_at": r.created_at.isoformat()})
        if len(out) >= limit:
            break
    return out


@router.get("/audit")
def audit_log(limit: int = 50, project_id: Optional[int] = None, db: Session = Depends(get_db)):
    limit = min(limit, 500)
    if project_id is None:
        events = db.query(domain.AuditEvent).order_by(domain.AuditEvent.id.desc()).limit(limit).all()
        return [audit_service.to_dict(ev) for ev in events]
    ev_ids = {i for (i,) in db.query(domain.EvidenceAsset.id).filter(domain.EvidenceAsset.project_id == project_id)}
    claim_ids = {i for (i,) in db.query(domain.Claim.id).filter(domain.Claim.project_id == project_id)}

    def mine(ev):
        if ev.entity_type == "evidence" and ev.entity_id in ev_ids:
            return True
        if ev.entity_type == "claim" and ev.entity_id in claim_ids:
            return True
        if ev.entity_type == "project" and ev.entity_id == project_id:
            return True
        return isinstance(ev.detail, dict) and ev.detail.get("project_id") == project_id
    out = []
    for ev in db.query(domain.AuditEvent).order_by(domain.AuditEvent.id.desc()).limit(2000):
        if mine(ev):
            out.append(audit_service.to_dict(ev))
            if len(out) >= limit:
                break
    return out


# ---------- Cloudinary Upload Widget ----------
@router.get("/cloudinary/widget-config")
def widget_config():
    import cloudinary
    cfg = cloudinary.config()
    enabled = CloudinaryService.enabled()
    return {"enabled": enabled, "cloud_name": cfg.cloud_name if enabled else None,
            "api_key": cfg.api_key if enabled else None, "folder": settings.CLOUDINARY_FOLDER}


class SignIn(BaseModel):
    params_to_sign: dict


@router.post("/cloudinary/sign")
def sign_widget(body: SignIn):
    if not CloudinaryService.enabled():
        raise HTTPException(status_code=400, detail="Cloudinary is not configured.")
    folder = str(body.params_to_sign.get("folder") or "")
    if not folder.startswith(settings.CLOUDINARY_FOLDER + "/"):
        raise HTTPException(status_code=400, detail="Uploads must go to the ImpactProof folder.")
    return {"signature": CloudinaryService.widget_signature(body.params_to_sign)}


class FromCloudinaryIn(BaseModel):
    public_id: str
    project_id: Optional[int] = None
    site_id: Optional[int] = None
    original_filename: Optional[str] = None


@router.post("/evidence/from-cloudinary")
def from_cloudinary(body: FromCloudinaryIn, db: Session = Depends(get_db)):
    try:
        e = pipeline.ingest_from_cloudinary(db, body.public_id, body.project_id, body.site_id, body.original_filename)
    except pipeline.IngestError as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    return {"evidence_id": e.id, "evidence": evidence_light(e)}


# ---------- early access ----------
class EarlyAccessIn(BaseModel):
    name: str
    organisation: str
    email: str
    role: Optional[str] = None
    message: Optional[str] = None

    @field_validator("name", "organisation")
    @classmethod
    def required(cls, v):
        if not v.strip():
            raise ValueError("Please fill in your name and organisation.")
        return v.strip()[:200]

    @field_validator("email")
    @classmethod
    def email_ok(cls, v):
        import re
        v = v.strip()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
            raise ValueError("Enter a valid email address.")
        return v[:200]


@router.post("/early-access")
def early_access(body: EarlyAccessIn, db: Session = Depends(get_db)):
    r = domain.EarlyAccessRequest(name=body.name, organisation=body.organisation, email=body.email,
                                  role=(body.role or "")[:100], message=(body.message or "")[:2000])
    db.add(r)
    db.commit()
    return {"ok": True, "count": db.query(domain.EarlyAccessRequest).count()}


@router.get("/early-access")
def early_access_list(db: Session = Depends(get_db)):
    rows = db.query(domain.EarlyAccessRequest).order_by(domain.EarlyAccessRequest.created_at.desc()).all()
    return [{"id": r.id, "name": r.name, "organisation": r.organisation, "email": r.email, "role": r.role,
             "message": r.message, "created_at": r.created_at.isoformat()} for r in rows]


class ClassificationIn(BaseModel):
    stage: Optional[str] = None
    category: Optional[str] = None
    reviewer: Optional[str] = None


@router.put("/evidence/{evidence_id}/classification")
def set_classification(evidence_id: int, body: ClassificationIn, db: Session = Depends(get_db)):
    """A person corrects the AI's stage or category. Empty string returns it to the AI's choice."""
    from app.services import classify
    e = _get(db, evidence_id)
    changes = []
    if body.stage is not None:
        if body.stage and body.stage not in classify.STAGES:
            raise HTTPException(status_code=400, detail="Unknown stage")
        e.stage_override = body.stage or None
        changes.append(f"stage to {classify.STAGES[body.stage] if body.stage else 'the AI suggestion'}")
    if body.category is not None:
        if body.category and body.category not in classify.CATEGORIES:
            raise HTTPException(status_code=400, detail="Unknown category")
        e.category_override = body.category or None
        changes.append(f"category to {classify.CATEGORIES[body.category] if body.category else 'the AI suggestion'}")
    if changes:
        audit_service.log(db, "evidence", e.id, "classified", "Set " + " and ".join(changes) + ".", body.model_dump(),
                          body.reviewer or "reviewer")
    db.commit()
    pipeline.retrust_all(db, focus_ids={e.id}, actor=body.reviewer or "reviewer")
    db.refresh(e)
    return full_view(e, db)
