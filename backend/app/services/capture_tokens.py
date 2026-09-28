"""Short-lived signed tokens handed to the in-app camera.

A capture token proves the photo was uploaded within minutes of the camera page being opened,
so an old photo cannot be passed off as a live capture through the app. It is not a hardware
attestation: that needs a native app with device signing (on the roadmap).
"""
import base64
import hashlib
import hmac
import json
import secrets
import time

from app.core.config import settings

MAX_AGE_S = 15 * 60


def _sign(payload: bytes) -> str:
    return hmac.new(settings.APP_SECRET.encode(), payload, hashlib.sha256).hexdigest()


def issue(project_id: int | None, site_id: int | None) -> dict:
    body = {"tid": secrets.token_hex(8), "iat": int(time.time()), "project_id": project_id, "site_id": site_id}
    raw = base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":")).encode()).decode()
    return {"token": f"{raw}.{_sign(raw.encode())}", "expires_in": MAX_AGE_S}


def verify(token: str) -> tuple[dict | None, str]:
    try:
        raw, sig = token.rsplit(".", 1)
    except (ValueError, AttributeError):
        return None, "Capture token is malformed."
    if not hmac.compare_digest(sig, _sign(raw.encode())):
        return None, "Capture token signature is invalid."
    try:
        body = json.loads(base64.urlsafe_b64decode(raw.encode()))
    except Exception:
        return None, "Capture token is unreadable."
    age = time.time() - body.get("iat", 0)
    if age > MAX_AGE_S:
        return body, f"Capture token expired {int(age / 60)} minutes after the camera was opened."
    return body, ""
