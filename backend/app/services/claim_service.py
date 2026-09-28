"""Claims are the product: every claim knows which evidence supports it and how strongly."""
from datetime import datetime, timedelta

from app.core.config import settings
from app.services import trust_engine

SUPPORT_LABELS = {"SUPPORTED": "Supported", "PARTIAL": "Partly supported", "CONTESTED": "Contested",
                  "UNSUPPORTED": "Unsupported"}


def _status(e):
    return e.integrity.status if e.integrity else "UNVERIFIABLE"


def support(evidence: list) -> dict:
    """How well the linked evidence supports a claim."""
    counts = {}
    for e in evidence:
        counts[_status(e)] = counts.get(_status(e), 0) + 1
    good = counts.get("CORROBORATED", 0)
    bad = counts.get("SUSPICIOUS", 0) + counts.get("REJECTED", 0)
    if not evidence or good == 0:
        state = "CONTESTED" if bad else "UNSUPPORTED"
    elif bad:
        state = "CONTESTED"
    elif good == len(evidence):
        state = "SUPPORTED"
    else:
        state = "PARTIAL"
    reasons = {
        "SUPPORTED": f"All {good} linked photos are corroborated.",
        "PARTIAL": f"{good} of {len(evidence)} linked photos are corroborated; the rest still need checking.",
        "CONTESTED": f"{bad} linked photo{'s' if bad != 1 else ''} failed checks (suspicious or rejected). "
                     f"Remove {'them' if bad != 1 else 'it'} or explain before publishing.",
        "UNSUPPORTED": "No linked photo is corroborated yet, so this claim should not be published.",
    }
    public = {
        "SUPPORTED": f"All {good} photos behind this claim passed independent checks.",
        "PARTIAL": f"{good} of {len(evidence)} photos behind this claim passed independent checks; the others could not be verified.",
        "CONTESTED": f"{bad} photo{'s' if bad != 1 else ''} linked to this claim failed checks. "
                     f"{'They are' if bad != 1 else 'It is'} listed below, not hidden.",
        "UNSUPPORTED": "No photo behind this claim has passed the checks yet.",
    }
    return {"state": state, "label": SUPPORT_LABELS[state], "reason": reasons[state], "public_reason": public[state],
            "counts": counts, "corroborated": good, "total": len(evidence)}


def coverage(sites: list, evidence: list, project) -> dict:
    """Guards against cherry-picking: which sites have no recent corroborated evidence?"""
    ref = datetime.utcnow()
    if project and project.end_date and project.end_date < ref.date():
        ref = datetime.combine(project.end_date, datetime.min.time())
    cutoff = ref - timedelta(days=settings.STALE_SITE_DAYS)
    rows = []
    for s in sites:
        good = [e for e in evidence if e.site_id == s.id and _status(e) == "CORROBORATED"]
        last = max((e.capture_time or e.uploaded_at for e in good), default=None)
        rows.append({"site_id": s.id, "site_name": s.name, "corroborated": len(good),
                     "last_evidence": last.isoformat() if last else None,
                     "stale": last is None or last < cutoff})
    stale = [r for r in rows if r["stale"]]
    return {"sites": rows, "stale_count": len(stale), "site_count": len(rows),
            "stale_days": settings.STALE_SITE_DAYS,
            "summary": _coverage_summary(len(stale), len(rows), settings.STALE_SITE_DAYS)}


def _coverage_summary(stale: int, total: int, days: int) -> str:
    if not total:
        return "No sites defined for this project yet."
    if not stale:
        return f"Every site has corroborated evidence from the last {days} days."
    sites = "site has" if stale == 1 else "sites have"
    return f"{stale} of {total} {sites} no corroborated evidence from the last {days} days."


def flagged_reasons(e) -> list[str]:
    reasons = trust_engine.headline_reasons(e.integrity.signals if e.integrity else {}, 3)
    if not reasons and _status(e) == "UNVERIFIABLE":
        reasons = ["Not enough information in the file to verify where or when it was taken."]
    return reasons
