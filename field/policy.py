"""Decides, for every item, what stays on the device and what goes to the cloud, and says why.

  local_only  never leaves the device: marked private, or contains personal data
  skipped     not worth sending: a near-duplicate of a photo already captured here
  pending     queued for sync; photos' image files wait for Wi-Fi unless allowed on mobile data
  synced      on the server (and, for photos, at ImpactProof HQ)
  conflict    another device changed the same fact while this one was offline
"""
import re

PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
AADHAAR = re.compile(r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)")
DUPLICATE_SIMILARITY = 0.95
DUPLICATE_WINDOW_S = 15 * 60


def personal_data(text: str) -> str | None:
    t = text or ""
    if PHONE.search(t):
        return "a phone number"
    if EMAIL.search(t):
        return "an email address"
    if AADHAAR.search(t):
        return "an ID-like number"
    return None


def classify_new(item: dict, near_duplicate: dict | None = None) -> tuple[str, str]:
    """Returns (sync_state, reason) for a newly created local item."""
    if item.get("private"):
        return "local_only", "Marked private, so it stays on this device."
    found = personal_data(" ".join(str(item.get(k) or "") for k in ("text", "title", "value")))
    if found:
        return "local_only", f"Contains {found}, so it stays on this device."
    if near_duplicate:
        return "skipped", (f"Near-duplicate of a photo taken here moments ago ({near_duplicate['short']}); "
                           f"kept on device, not sent.")
    if item.get("kind") == "capture":
        return "pending", "Queued: details sync first, the photo itself when on Wi-Fi."
    return "pending", "Queued to sync when online."


PRIORITY = {"fact": 0, "note": 1, "capture": 2}   # small, important items first on a weak connection
