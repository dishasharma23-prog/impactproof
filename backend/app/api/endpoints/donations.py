"""Pay on proof: donors fund a specific claim by UPI, straight to the NGO, and get a receipt that shows the
verified photos behind it. The NGO confirms each payment once it arrives; money counts as released only when
the claim is supported by corroborated photos."""
import re
import secrets
from datetime import datetime
from typing import Optional
from urllib.parse import quote

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models import domain
from app.serializers import iso
from app.services import audit_service, claim_service

router = APIRouter()
UPI_RE = re.compile(r"^[A-Za-z0-9._-]{2,64}@[A-Za-z][A-Za-z0-9.-]{1,48}$")
MAX_AMOUNT = 1_000_000


def _svg(data: str) -> Response:
    img = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    return Response(img.to_string(), media_type="image/svg+xml", headers={"Cache-Control": "no-store"})


def _claim_by_token(db, token: str) -> domain.Claim:
    c = db.query(domain.Claim).filter(domain.Claim.public_token == token).first()
    if not c:
        raise HTTPException(status_code=404, detail="This verification link is not valid.")
    return c


def _upi_link(project, amount: int, note: str) -> Optional[str]:
    if not project or not project.upi_id:
        return None
    name = project.upi_name or project.organization or project.name or "NGO"
    return (f"upi://pay?pa={quote(project.upi_id, safe='@')}&pn={quote(name)}&am={amount}.00&cu=INR"
            f"&tn={quote(note[:60])}")


def _support(db, c):
    from app.api.endpoints.claims import linked_evidence
    return claim_service.support(linked_evidence(db, c.id))


def _summary(db, c) -> dict:
    rows = db.query(domain.Donation).filter(domain.Donation.claim_id == c.id).all()
    confirmed = [d for d in rows if d.status == "confirmed"]
    pending = [d for d in rows if d.status == "pending"]
    raised = sum(d.amount for d in confirmed)
    support = _support(db, c)
    proven = support["state"] == "SUPPORTED"
    return {"raised": raised, "donors": len({d.donor_name.lower() for d in confirmed}),
            "pending": len(pending), "pending_amount": sum(d.amount for d in pending),
            "released": raised if proven else 0, "held": 0 if proven else raised,
            "support_state": support["state"], "support_label": support["label"]}


def _donation_dict(d: domain.Donation) -> dict:
    return {"id": d.id, "donor_name": d.donor_name, "amount": d.amount, "method": d.method, "utr": d.utr,
            "status": d.status, "receipt_token": d.receipt_token, "created_at": iso(d.created_at),
            "confirmed_at": iso(d.confirmed_at), "confirmed_by": d.confirmed_by}


# ---------------------------------------------------------------- public (donors)
@router.get("/public/claims/{token}/funding")
def public_funding(token: str, db: Session = Depends(get_db)):
    c = _claim_by_token(db, token)
    p = c.project
    return {**_summary(db, c), "upi": bool(p and p.upi_id),
            "payee": (p.upi_name or p.organization or p.name) if p else None}


@router.get("/public/claims/{token}/upi.svg")
def public_upi_qr(token: str, amount: int, db: Session = Depends(get_db)):
    c = _claim_by_token(db, token)
    if amount < 1 or amount > MAX_AMOUNT:
        raise HTTPException(status_code=400, detail="Choose an amount between ₹1 and ₹10,00,000.")
    link = _upi_link(c.project, amount, f"ImpactProof claim {c.id}")
    if not link:
        raise HTTPException(status_code=404, detail="This NGO has not set up UPI payments yet.")
    return _svg(link)


@router.get("/public/claims/{token}/upi-link")
def public_upi_link(token: str, amount: int, db: Session = Depends(get_db)):
    c = _claim_by_token(db, token)
    if amount < 1 or amount > MAX_AMOUNT:
        raise HTTPException(status_code=400, detail="Choose an amount between ₹1 and ₹10,00,000.")
    link = _upi_link(c.project, amount, f"ImpactProof claim {c.id}")
    if not link:
        raise HTTPException(status_code=404, detail="This NGO has not set up UPI payments yet.")
    return {"link": link}


class DonationIn(BaseModel):
    donor_name: str
    amount: int
    utr: Optional[str] = None

    @field_validator("donor_name")
    @classmethod
    def name_ok(cls, v):
        v = v.strip()
        if not v or len(v) > 80:
            raise ValueError("Enter your name (up to 80 characters).")
        return v

    @field_validator("amount")
    @classmethod
    def amount_ok(cls, v):
        if v < 1 or v > MAX_AMOUNT:
            raise ValueError("Choose an amount between ₹1 and ₹10,00,000.")
        return v

    @field_validator("utr")
    @classmethod
    def utr_ok(cls, v):
        v = (v or "").strip().replace(" ", "")
        if v and not re.fullmatch(r"[A-Za-z0-9]{6,30}", v):
            raise ValueError("The UPI reference number should be 6 to 30 letters or digits.")
        return v or None


@router.post("/public/claims/{token}/donations")
def create_donation(token: str, body: DonationIn, db: Session = Depends(get_db)):
    c = _claim_by_token(db, token)
    upi = bool(c.project and c.project.upi_id)
    if upi and not body.utr:
        raise HTTPException(status_code=400, detail="Enter the UPI reference number (UTR) from your payment app.")
    d = domain.Donation(claim_id=c.id, project_id=c.project_id, donor_name=body.donor_name, amount=body.amount,
                        method="upi" if upi else "demo", utr=body.utr if upi else None,
                        status="pending", receipt_token=secrets.token_urlsafe(10))
    db.add(d)
    db.flush()
    audit_service.log(db, "claim", c.id, "donation_pledged",
                      f"{body.donor_name} pledged ₹{body.amount:,} to this claim"
                      f"{' by UPI' if upi else ' (demo payment)'}; awaiting the NGO's confirmation.",
                      {"donation_id": d.id, "amount": body.amount, "method": d.method}, actor=body.donor_name)
    db.commit()
    return {"receipt_token": d.receipt_token}


@router.get("/public/receipts/{rtoken}")
def public_receipt(rtoken: str, db: Session = Depends(get_db)):
    d = db.query(domain.Donation).filter(domain.Donation.receipt_token == rtoken).first()
    if not d:
        raise HTTPException(status_code=404, detail="This receipt link is not valid.")
    from app.api.endpoints.claims import ensure_token, verify_url
    c = d.claim
    ensure_token(db, c)
    s = _summary(db, c)
    return {"donation": {k: v for k, v in _donation_dict(d).items() if k not in ("utr", "confirmed_by")},
            "utr_last4": d.utr[-4:] if d.utr else None,
            "claim": {"text": c.text, "project": c.project.name if c.project else None,
                      "organization": c.project.organization if c.project else None,
                      "verify_token": c.public_token, "verify_url": verify_url(c)},
            "proof": {"state": s["support_state"], "label": s["support_label"]},
            "receipt_url": f"{settings.PUBLIC_APP_URL.rstrip('/')}/receipt/{rtoken}"}


@router.get("/public/receipts/{rtoken}/qr.svg")
def public_receipt_qr(rtoken: str, db: Session = Depends(get_db)):
    d = db.query(domain.Donation).filter(domain.Donation.receipt_token == rtoken).first()
    if not d:
        raise HTTPException(status_code=404, detail="This receipt link is not valid.")
    return _svg(f"{settings.PUBLIC_APP_URL.rstrip('/')}/receipt/{rtoken}")


# ---------------------------------------------------------------- staff (NGO)
@router.get("/claims/{claim_id}/donations")
def claim_donations(claim_id: int, db: Session = Depends(get_db)):
    c = db.get(domain.Claim, claim_id)
    if not c:
        raise HTTPException(status_code=404, detail="Claim not found")
    rows = (db.query(domain.Donation).filter(domain.Donation.claim_id == c.id)
            .order_by(domain.Donation.created_at.desc()).all())
    return {"summary": _summary(db, c), "donations": [_donation_dict(d) for d in rows],
            "upi_configured": bool(c.project and c.project.upi_id)}


class DecisionIn(BaseModel):
    decision: str
    reviewer: str = "NGO staff"


@router.post("/donations/{donation_id}/decision")
def decide(donation_id: int, body: DecisionIn, db: Session = Depends(get_db)):
    d = db.get(domain.Donation, donation_id)
    if not d:
        raise HTTPException(status_code=404, detail="Donation not found")
    if body.decision not in ("confirmed", "rejected", "pending"):
        raise HTTPException(status_code=400, detail="Decision must be confirmed, rejected or pending.")
    d.status = body.decision
    d.confirmed_at = datetime.utcnow() if body.decision == "confirmed" else None
    d.confirmed_by = (body.reviewer.strip()[:80] or "NGO staff") if body.decision != "pending" else None
    verb = {"confirmed": "Confirmed", "rejected": "Rejected", "pending": "Reopened"}[body.decision]
    audit_service.log(db, "claim", d.claim_id, f"donation_{body.decision}",
                      f"{verb} ₹{d.amount:,} from {d.donor_name}.", {"donation_id": d.id}, actor=d.confirmed_by or "NGO staff")
    db.commit()
    return _donation_dict(d)


class PaymentsIn(BaseModel):
    upi_id: Optional[str] = None
    upi_name: Optional[str] = None


@router.get("/projects/{project_id}/payments")
def get_payments(project_id: int, db: Session = Depends(get_db)):
    p = db.get(domain.Project, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"upi_id": p.upi_id, "upi_name": p.upi_name}


@router.put("/projects/{project_id}/payments")
def set_payments(project_id: int, body: PaymentsIn, db: Session = Depends(get_db)):
    p = db.get(domain.Project, project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    upi = (body.upi_id or "").strip()
    if upi and not UPI_RE.match(upi):
        raise HTTPException(status_code=400, detail="That doesn't look like a UPI ID (for example name@okaxis).")
    p.upi_id = upi or None
    p.upi_name = (body.upi_name or "").strip()[:60] or None
    audit_service.log(db, "project", p.id, "payments_updated",
                      "UPI payments turned on." if p.upi_id else "UPI payments turned off (demo payments only).")
    db.commit()
    return {"upi_id": p.upi_id, "upi_name": p.upi_name}
