"""Deleting evidence. The photo is removed everywhere (database, local copy, Cloudinary, search index,
claims), but a short record of the deletion stays in the audit log, as an evidence system should."""
import logging

from sqlalchemy.orm import Session

from app.models import domain
from app.services import audit_service, pipeline
from app.services.cloudinary_service import CloudinaryService

log = logging.getLogger(__name__)


def _remove_from_cloudinary(public_id: str) -> str:
    if not public_id or not CloudinaryService.enabled():
        return "not on Cloudinary"
    try:
        import cloudinary.uploader
        r = cloudinary.uploader.destroy(public_id, invalidate=True)
        return "removed from Cloudinary" if r.get("result") in ("ok", "not found") else f"Cloudinary said {r.get('result')}"
    except Exception as e:  # never block a delete on the network
        log.warning("Cloudinary delete failed for %s: %s", public_id, e)
        return "Cloudinary copy could not be removed (delete it in the Media Library)"


def _remove_from_search(evidence_id: int) -> None:
    try:
        from app.services.qdrant_service import qdrant_service
        if qdrant_service._client:
            from qdrant_client.models import PointIdsList
            qdrant_service._client.delete("impactproof_evidence", points_selector=PointIdsList(points=[evidence_id]))
    except Exception as e:
        log.warning("Qdrant delete failed for %s: %s", evidence_id, e)


def delete_evidence(db: Session, ids: list[int], actor: str, reason: str = "") -> list[dict]:
    """Delete these evidence items and re-check what remains (reuse verdicts can change)."""
    done = []
    for e in db.query(domain.EvidenceAsset).filter(domain.EvidenceAsset.id.in_(ids)).all():
        code = f"EV-{e.id:04d}"
        claims = [l.claim_id for l in db.query(domain.ClaimEvidenceLink).filter(domain.ClaimEvidenceLink.evidence_id == e.id)]
        cloud = _remove_from_cloudinary(e.cloudinary_public_id)
        _remove_from_search(e.id)
        if e.local_file:
            (pipeline.ORIGINALS / e.local_file).unlink(missing_ok=True)
        for model, col in ((domain.ClaimEvidenceLink, domain.ClaimEvidenceLink.evidence_id),
                           (domain.ReviewDecision, domain.ReviewDecision.evidence_id),
                           (domain.AIAnalysis, domain.AIAnalysis.evidence_id),
                           (domain.IntegrityAssessment, domain.IntegrityAssessment.evidence_id)):
            db.query(model).filter(col == e.id).delete(synchronize_session=False)
        db.query(domain.Transformation).filter((domain.Transformation.original_id == e.id) |
                                               (domain.Transformation.derivative_id == e.id)).delete(synchronize_session=False)
        db.query(domain.EvidenceAsset).filter(domain.EvidenceAsset.duplicate_of_evidence_id == e.id) \
            .update({"duplicate_of_evidence_id": None}, synchronize_session=False)
        summary = f"Deleted {code} ({e.original_filename or 'photo'}), SHA-256 {(e.sha256 or '')[:12]}…; {cloud}."
        if claims:
            summary += f" It was removed from {len(claims)} claim{'s' if len(claims) != 1 else ''}."
        if reason:
            summary += f" Reason: {reason}"
        audit_service.log(db, "evidence", e.id, "delete", summary,
                          {"sha256": e.sha256, "claims": claims, "project_id": e.project_id}, actor)
        db.delete(e)
        done.append({"id": e.id, "code": code, "claims": claims, "cloudinary": cloud})
    db.commit()
    if done:
        pipeline.retrust_all(db, actor=actor)
    return done
