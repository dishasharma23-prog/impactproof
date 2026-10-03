from typing import Optional

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import domain
from app.services import audit_service
from app.services import volunteers as vs

router = APIRouter()


class VolunteerIn(BaseModel):
    name: str
    phone: str
    project_id: Optional[int] = None


class PairIn(BaseModel):
    phone: str
    code: str
    device_name: Optional[str] = None


@router.get("/volunteers")
def list_volunteers(project_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(domain.Volunteer)
    if project_id is not None:
        q = q.filter((domain.Volunteer.project_id == project_id) | (domain.Volunteer.project_id.is_(None)))
    return [vs.to_dict(v, db) for v in q.order_by(domain.Volunteer.created_at.desc()).all()]


@router.post("/volunteers")
def add_volunteer(body: VolunteerIn, db: Session = Depends(get_db)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Add the volunteer's name.")
    try:
        phone = vs.normalise_phone(body.phone)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if db.query(domain.Volunteer).filter(domain.Volunteer.phone == phone, domain.Volunteer.active.is_(True)).first():
        raise HTTPException(status_code=409, detail="This phone number is already registered.")
    v = domain.Volunteer(name=name, phone=phone, project_id=body.project_id)
    db.add(v)
    db.flush()
    code = vs.new_code(v)
    audit_service.log(db, "volunteer", v.id, "register", f"Registered volunteer {name} ({vs.mask(phone)}).",
                      {"project_id": body.project_id})
    db.commit()
    return {**vs.to_dict(v, db), "pairing_code": code}


@router.post("/volunteers/{vid}/code")
def new_code(vid: int, db: Session = Depends(get_db)):
    v = db.get(domain.Volunteer, vid)
    if not v or not v.active:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    code = vs.new_code(v)
    audit_service.log(db, "volunteer", v.id, "code", f"New pairing code for {v.name} ({vs.mask(v.phone)}).",
                      {"project_id": v.project_id})
    db.commit()
    return {**vs.to_dict(v, db), "pairing_code": code}


@router.delete("/volunteers/{vid}")
def deactivate(vid: int, db: Session = Depends(get_db)):
    v = db.get(domain.Volunteer, vid)
    if not v:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    v.active = False
    v.device_key_hash = None
    v.pairing_code_hash = None
    audit_service.log(db, "volunteer", v.id, "deactivate", f"Removed {v.name} ({vs.mask(v.phone)}); their device can no longer upload.",
                      {"project_id": v.project_id})
    db.commit()
    return {"ok": True}


@router.post("/volunteers/pair")
def pair(body: PairIn, db: Session = Depends(get_db)):
    try:
        res = vs.pair(db, body.phone, body.code, body.device_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not res:
        raise HTTPException(status_code=401, detail="That phone number and code don't match. Ask your coordinator for a new code.")
    v, key = res
    audit_service.log(db, "volunteer", v.id, "pair", f"{v.name} ({vs.mask(v.phone)}) paired {body.device_name or 'a device'}.",
                      {"project_id": v.project_id})
    db.commit()
    return {"device_key": key, "volunteer": vs.to_dict(v, db)}


@router.get("/volunteers/me")
def me(key: str, db: Session = Depends(get_db)):
    v = vs.by_key(db, key)
    if not v:
        raise HTTPException(status_code=401, detail="This device is not paired.")
    return vs.to_dict(v, db)


class QrIn(BaseModel):
    data: str


@router.post("/volunteers/qr.svg")
def sign_in_qr(body: QrIn):
    """QR code for the sign-in link shown on the Volunteers page. Sent in the body, not the URL, so the
    single-use pairing code inside it never lands in access logs."""
    if not body.data.startswith(("http://", "https://")) or len(body.data) > 500:
        raise HTTPException(status_code=400, detail="Give the field app's address, starting with https://")
    img = qrcode.make(body.data, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    return Response(img.to_string(), media_type="image/svg+xml", headers={"Cache-Control": "no-store"})
