import secrets
from datetime import datetime
from typing import List, Optional

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models import domain
from app.serializers import evidence_code, evidence_light, iso, project_dict, sdg_summary, thumb_url
from app.services import audit_service, claim_service, pairing, pipeline, sdg, trust_engine
from app.services.cloudinary_service import CloudinaryService

router = APIRouter()


class ClaimCreate(BaseModel):
    project_id: Optional[int] = None
    text: str

    @field_validator("text")
    @classmethod
    def text_must_not_be_empty(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Claim text cannot be empty")
        if len(v) > 2000:
            raise ValueError("Claim text is too long")
        return v


class ClaimEvidenceLinkCreate(BaseModel):
    evidence_id: int


def _claim(db, claim_id) -> domain.Claim:
    c = db.get(domain.Claim, claim_id)
    if not c:
        raise HTTPException(status_code=404, detail="Claim not found")
    return c


def ensure_token(db, c: domain.Claim) -> str:
    if not c.public_token:
        c.public_token = secrets.token_urlsafe(9)
        db.commit()
    return c.public_token


def verify_url(c: domain.Claim) -> str:
    return f"{settings.PUBLIC_APP_URL.rstrip('/')}/verify/{c.public_token}"


def linked_evidence(db, claim_id) -> list:
    ids = [l.evidence_id for l in db.query(domain.ClaimEvidenceLink).filter(domain.ClaimEvidenceLink.claim_id == claim_id)]
    return sorted([e for e in pipeline.load_all(db) if e.id in ids], key=lambda e: e.capture_time or e.uploaded_at)


def claim_light(db, c: domain.Claim, evidence=None) -> dict:
    ev = evidence if evidence is not None else linked_evidence(db, c.id)
    return {"id": c.id, "text": c.text, "project_id": c.project_id, "created_at": iso(c.created_at),
            "evidence_count": len(ev), "support": claim_service.support(ev), "public_token": c.public_token}

@router.get("", include_in_schema=False)
@router.get("/")
def get_claims(project_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(domain.Claim).order_by(domain.Claim.created_at.desc())
    if project_id:
        q = q.filter(domain.Claim.project_id == project_id)
    return [claim_light(db, c) for c in q.all()]

@router.post("", include_in_schema=False)
@router.post("/")
def create_claim(claim: ClaimCreate, db: Session = Depends(get_db)):
    project_id = claim.project_id or pipeline.default_project(db).id
    if not db.get(domain.Project, project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    c = domain.Claim(project_id=project_id, text=claim.text, public_token=secrets.token_urlsafe(9))
    db.add(c)
    db.flush()
    audit_service.log(db, "claim", c.id, "created", f"Claim created: “{c.text[:120]}”")
    db.commit()
    return claim_light(db, c, [])


@router.get("/{claim_id}")
def get_claim(claim_id: int, db: Session = Depends(get_db)):
    c = _claim(db, claim_id)
    ensure_token(db, c)
    ev = linked_evidence(db, c.id)
    items = []
    for e in ev:
        d = evidence_light(e)
        dup = db.get(domain.EvidenceAsset, e.duplicate_of_evidence_id) if e.duplicate_of_evidence_id else None
        d["duplicate_of_evidence"] = {"id": dup.id, "cloudinary_url": thumb_url(dup), "phash": dup.phash} if dup else None
        d["flag_reasons"] = claim_service.flagged_reasons(e) if d["integrity_status"] != "CORROBORATED" else []
        items.append(d)
    return {**claim_light(db, c, ev), "evidence": items, "verify_url": verify_url(c),
            "project": project_dict(c.project) if c.project else None}


@router.post("/{claim_id}/evidence")
def link_evidence(claim_id: int, link: ClaimEvidenceLinkCreate, db: Session = Depends(get_db)):
    c = _claim(db, claim_id)
    e = db.get(domain.EvidenceAsset, link.evidence_id)
    if not e:
        raise HTTPException(status_code=404, detail="Evidence not found")
    exists = db.query(domain.ClaimEvidenceLink).filter(domain.ClaimEvidenceLink.claim_id == claim_id,
                                                       domain.ClaimEvidenceLink.evidence_id == e.id).first()
    if exists:
        raise HTTPException(status_code=409, detail="Evidence is already linked to this claim.")
    db.add(domain.ClaimEvidenceLink(claim_id=c.id, evidence_id=e.id))
    status = e.integrity.status if e.integrity else "UNVERIFIABLE"
    audit_service.log(db, "claim", c.id, "linked", f"Linked {evidence_code(e.id)} "
                                                  f"({trust_engine.STATUS_LABELS.get(status, status)}).")
    audit_service.log(db, "evidence", e.id, "linked", f"Linked to claim #{c.id}.")
    db.commit()
    return {"status": "success"}


@router.delete("/{claim_id}/evidence/{evidence_id}")
def unlink_evidence(claim_id: int, evidence_id: int, db: Session = Depends(get_db)):
    link = db.query(domain.ClaimEvidenceLink).filter(domain.ClaimEvidenceLink.claim_id == claim_id,
                                                     domain.ClaimEvidenceLink.evidence_id == evidence_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    db.delete(link)
    audit_service.log(db, "claim", claim_id, "unlinked", f"Removed {evidence_code(evidence_id)} from this claim.")
    audit_service.log(db, "evidence", evidence_id, "unlinked", f"Removed from claim #{claim_id}.")
    db.commit()
    return {"status": "success"}


@router.get("/{claim_id}/candidates")
def get_evidence_candidates(claim_id: int, db: Session = Depends(get_db)):
    c = _claim(db, claim_id)
    from app.services.qdrant_service import qdrant_service
    linked = {l.evidence_id for l in db.query(domain.ClaimEvidenceLink).filter(domain.ClaimEvidenceLink.claim_id == c.id)}
    hits = qdrant_service.search(query=c.text, limit=12) if settings.QDRANT_URL else []
    out = []
    for hit in hits:
        e = db.get(domain.EvidenceAsset, hit["evidence_id"])
        if not e or e.id in linked or (c.project_id and e.project_id != c.project_id):
            continue
        out.append({**evidence_light(e), "similarity": hit["similarity"]})
    return out


def _report_item(e, public=False) -> dict:
    integ = e.integrity
    signals = (integ.signals or {}) if integ else {}
    checks = [{"label": s["label"], "status": s["status"], "reason": s["reason"]}
              for s in signals.values() if isinstance(s, dict)]
    status = integ.status if integ else "UNVERIFIABLE"
    raw = (e.ai_analysis.raw_response or {}) if e.ai_analysis else {}
    item = {
        "id": e.id, "code": evidence_code(e.id), "status": status,
        "status_label": trust_engine.STATUS_LABELS.get(status, status),
        "score": integ.score if integ else None, "available": integ.available if integ else None,
        "total": integ.total if integ else None,
        "capture_time": iso(e.capture_time), "site_name": e.site.name if e.site else None,
        "capture_source": e.capture_source or "upload", "activity": raw.get("activity"),
        "description": raw.get("description"), "checks": checks,
        "reasons": claim_service.flagged_reasons(e) if status != "CORROBORATED" else [],
        "reviewed": e.review_status,
        "sdgs": [sdg.info(n) for n in sdg.evidence_sdgs(e, e.project)],
        "seal": {"sha256": e.sha256, "cloudinary_matches": (e.cloudinary_etag == e.md5) if e.cloudinary_etag and e.md5 else None},
    }
    if public:
        item["image_url"] = CloudinaryService.public_url(e) if e.cloudinary_public_id else None
        item["latitude"] = round(e.latitude, 3) if e.latitude is not None else None
        item["longitude"] = round(e.longitude, 3) if e.longitude is not None else None
    else:
        item["image_url"] = thumb_url(e, 960, 720)
        item["latitude"], item["longitude"] = e.latitude, e.longitude
    return item


def build_report(db, c: domain.Claim, public=False) -> dict:
    ev = linked_evidence(db, c.id)
    project = c.project
    supporting = [e for e in ev if e.integrity and e.integrity.status == "CORROBORATED"]
    flagged = [e for e in ev if e not in supporting]
    all_project = [e for e in pipeline.load_all(db) if project and e.project_id == project.id]
    ids = {e.id for e in supporting}
    pairs = [p for p in pairing.find_pairs(supporting, {s.id: s for s in (project.sites if project else [])})
             if p["before"] in ids and p["after"] in ids]
    by_id = {e.id: e for e in supporting}
    for p in pairs:
        cached = db.get(domain.CacheEntry, "pair:" + p["key"])
        p["description"] = cached.data if cached else None
        p["before_image"] = (CloudinaryService.public_url(by_id[p["before"]]) if public else thumb_url(by_id[p["before"]], 960, 720))
        p["after_image"] = (CloudinaryService.public_url(by_id[p["after"]]) if public else thumb_url(by_id[p["after"]], 960, 720))
    dates = sorted(e.capture_time for e in ev if e.capture_time)
    return {
        "report_title": "Impact brief",
        "generated_at": datetime.utcnow().isoformat(),
        "claim_id": c.id, "claim_text": c.text,
        "project_name": project.name if project else "Independent claim",
        "project": project_dict(project) if project else None,
        "site_name": next((e.site.name for e in supporting if e.site), None),
        "support": claim_service.support(ev),
        "period": [iso(dates[0]), iso(dates[-1])] if dates else None,
        "supporting": [_report_item(e, public) for e in supporting],
        "flagged": [_report_item(e, public) for e in flagged],
        "pairs": pairs,
        "sdgs": [x for x in sdg_summary(supporting, project) if x["photos"] > 0],
        "coverage": claim_service.coverage(project.sites if project else [], all_project, project),
        "verify_url": verify_url(c),
        "qr_url": f"{settings.PUBLIC_API_URL}/api/claims/{c.id}/qr.svg",
        "method": ("Each photo was checked for capture method, location against project sites, capture date "
                   "against the project period, reuse against all other evidence (perceptual hashing), content "
                   "credentials (C2PA), camera metadata, visual content, visible text and the recorded weather. "
                   "AI describes photos; fixed rules decide verdicts; people review anything uncertain. "
                   "Only corroborated photos support this claim."),
        # kept for older screens
        "evidence": [{**_report_item(e, public), "cloudinary_url": thumb_url(e), "integrity_status": e.integrity.status if e.integrity else None}
                     for e in ev],
    }


@router.get("/{claim_id}/report")
def get_claim_report(claim_id: int, db: Session = Depends(get_db)):
    c = _claim(db, claim_id)
    ensure_token(db, c)
    return build_report(db, c)


@router.get("/{claim_id}/qr.svg")
def claim_qr(claim_id: int, db: Session = Depends(get_db)):
    c = _claim(db, claim_id)
    ensure_token(db, c)
    img = qrcode.make(verify_url(c), image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    return Response(content=img.to_string(), media_type="image/svg+xml")


public_router = APIRouter()


@public_router.get("/public/claims/{token}")
def public_claim(token: str, db: Session = Depends(get_db)):
    c = db.query(domain.Claim).filter(domain.Claim.public_token == token).first()
    if not c:
        raise HTTPException(status_code=404, detail="This verification link is not valid.")
    report = build_report(db, c, public=True)
    report.pop("evidence", None)
    if report.get("project"):
        report["project"] = {k: report["project"][k] for k in ("name", "organization", "start_date", "end_date", "sdgs")}
    return report
