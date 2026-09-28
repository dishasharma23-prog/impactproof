"""Volunteers are registered by phone number; their field device pairs once with a 6-digit code and
from then on uploads with a secret device key. Keys and codes are stored hashed."""
import hashlib
import re
import secrets
from datetime import datetime, timedelta

from app.models import domain

CODE_TTL = timedelta(hours=48)


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def normalise_phone(raw: str, default_cc: str = "91") -> str:
    """'+91 98765 43210', '098765 43210' and '9876543210' all become '+919876543210'."""
    s = (raw or "").strip()
    plus = s.startswith("+")
    d = re.sub(r"\D", "", s)
    if plus:
        out = "+" + d
    elif d.startswith("00"):
        out = "+" + d[2:]
    elif len(d) == 11 and d.startswith("0"):
        out = f"+{default_cc}{d[1:]}"
    elif len(d) == 10:
        out = f"+{default_cc}{d}"
    else:
        out = "+" + d
    if not 8 <= len(out) - 1 <= 15:
        raise ValueError("That doesn't look like a phone number. Include the country code if it isn't Indian.")
    return out


def mask(phone: str) -> str:
    """+919876543210 -> +91 ••••• 43210 (only the last five digits are shown)."""
    if not phone:
        return ""
    cc = phone[:3] if phone.startswith("+91") else phone[:-10] or phone[:3]
    return f"{cc} ••••• {phone[-5:]}"


def new_code(v: domain.Volunteer) -> str:
    code = f"{secrets.randbelow(10**6):06d}"
    v.pairing_code_hash = _h(f"{v.phone}:{code}")
    v.pairing_expires_at = datetime.utcnow() + CODE_TTL
    return code


def pair(db, phone: str, code: str, device_name: str | None) -> tuple[domain.Volunteer, str] | None:
    phone = normalise_phone(phone)
    v = db.query(domain.Volunteer).filter(domain.Volunteer.phone == phone, domain.Volunteer.active.is_(True)).first()
    if not v or not v.pairing_code_hash or v.pairing_code_hash != _h(f"{phone}:{(code or '').strip()}"):
        return None
    if v.pairing_expires_at and v.pairing_expires_at < datetime.utcnow():
        return None
    key = secrets.token_urlsafe(32)
    v.device_key_hash = _h(key)
    v.device_name = (device_name or "")[:80] or None
    v.pairing_code_hash = None           # single use
    v.pairing_expires_at = None
    v.paired_at = datetime.utcnow()
    return v, key


def by_key(db, key: str | None) -> domain.Volunteer | None:
    if not key:
        return None
    return db.query(domain.Volunteer).filter(domain.Volunteer.device_key_hash == _h(key),
                                             domain.Volunteer.active.is_(True)).first()


def to_dict(v: domain.Volunteer, db=None) -> dict:
    uploads = 0
    if db is not None:
        uploads = db.query(domain.EvidenceAsset).filter(domain.EvidenceAsset.volunteer_id == v.id).count()
    return {"id": v.id, "name": v.name, "phone": v.phone, "phone_masked": mask(v.phone), "project_id": v.project_id,
            "active": v.active, "paired": bool(v.device_key_hash), "device_name": v.device_name,
            "code_pending": bool(v.pairing_code_hash), "created_at": v.created_at.isoformat() if v.created_at else None,
            "paired_at": v.paired_at.isoformat() if v.paired_at else None,
            "last_upload_at": v.last_upload_at.isoformat() if v.last_upload_at else None, "uploads": uploads}
