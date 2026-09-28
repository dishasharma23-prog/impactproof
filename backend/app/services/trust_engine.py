"""Explainable trust engine. Deterministic rules only: AI observes, rules decide, humans resolve.

Every check returns pass / warn / fail / unavailable with one plain-language reason.
The score is a weighted average over the checks that had data, so missing metadata lowers
coverage instead of the score. Unknown is never treated as fake.
"""
from datetime import date, datetime, timedelta

from app.core.config import settings
from app.services.geo import fmt_distance, haversine_m
from app.services.hash_service import HashService

WEIGHTS = {"capture": 15, "location": 25, "timestamp": 20, "reuse": 25, "provenance": 20,
           "metadata": 10, "content": 15, "text": 10, "weather": 10}
LABELS = {"capture": "Capture method", "location": "Location", "timestamp": "Capture date",
          "reuse": "Reuse check", "provenance": "Content credentials", "metadata": "Camera metadata",
          "content": "Visual content", "text": "Visible text", "weather": "Weather at capture"}
HARD_FAIL = ("reuse", "location", "timestamp", "provenance")
CREDIT = {"pass": 1.0, "warn": 0.5, "fail": 0.0}
STATUS_LABELS = {"CORROBORATED": "Corroborated", "NEEDS_REVIEW": "Needs review", "SUSPICIOUS": "Suspicious",
                 "UNVERIFIABLE": "Unverifiable", "REJECTED": "Rejected"}
EDITING_SOFTWARE = ("photoshop", "lightroom", "gimp", "snapseed", "canva", "picsart", "facetune", "pixelmator",
                    "affinity", "midjourney", "dall", "stable diffusion", "firefly", "remini", "meitu", "photoroom")


def _sig(key, status, reason, **extra):
    return {"key": key, "label": LABELS[key], "status": status, "reason": reason, "weight": WEIGHTS[key], **extra}


def _day(d) -> str:
    return d.strftime("%d %b %Y")


def _raw(e) -> dict:
    return (e.ai_analysis.raw_response or {}) if e.ai_analysis else {}


def _ai_ready(e) -> bool:
    return "relevant_to_project" in _raw(e)


# ---------------------------------------------------------------- individual checks
def capture_signal(e):
    meta = e.capture_meta or {}
    if e.capture_source != "in_app" and (e.software or "").strip() == "ImpactProof Field":
        return _sig("capture", "unavailable", "Captured offline with the ImpactProof Field app and synced later. "
                                              "Its device stamp is not signed yet, so the checks below rely on the file's own data.")
    if e.capture_source != "in_app":
        return _sig("capture", "unavailable", "Uploaded as a file, not taken with the ImpactProof camera, "
                                              "so the checks below rely on the file's own data.")
    if meta.get("token_error"):
        return _sig("capture", "warn", f"Taken in the app, but {meta['token_error'][0].lower() + meta['token_error'][1:]}")
    acc = meta.get("gps_accuracy_m")
    if meta.get("gps_lat") is None:
        return _sig("capture", "warn", "Taken live with the ImpactProof camera, but location access was off.")
    if acc is not None and acc > 150:
        return _sig("capture", "warn", f"Taken live with the ImpactProof camera, but the GPS fix was weak (±{acc:.0f} m).")
    acc_txt = f" (GPS ±{acc:.0f} m)" if acc is not None else ""
    return _sig("capture", "pass", f"Taken live with the ImpactProof camera{acc_txt}. Location and time were "
                                   f"recorded at capture, not read from the file.")


def location_signal(e, sites):
    if e.latitude is None or e.longitude is None:
        return _sig("location", "unavailable", "No GPS data in the file. This is common for photos shared "
                                               "through messaging apps."), None
    placed = [s for s in sites if s.latitude is not None and s.longitude is not None]
    if not placed:
        return _sig("location", "unavailable", "The project has no site locations set yet."), None
    slack = min((e.capture_meta or {}).get("gps_accuracy_m") or 0, 100) if e.capture_source == "in_app" else 0
    ranked = sorted(((haversine_m(e.latitude, e.longitude, s.latitude, s.longitude), s) for s in placed),
                    key=lambda x: x[0])
    d, site = ranked[0]
    radius = float(site.radius_m or 300)
    if d <= radius + slack:
        return _sig("location", "pass", f"Taken {fmt_distance(d)} from the center of {site.name}, inside its "
                                        f"{fmt_distance(radius)} radius."), site
    return _sig("location", "fail", f"Taken {fmt_distance(d)} from the nearest project site ({site.name}), "
                                    f"outside every site's area."), None


def timestamp_signal(e, project):
    if not e.capture_time:
        return _sig("timestamp", "unavailable", "No capture date in the file.")
    captured = e.capture_time
    if e.capture_source == "in_app" and not (e.capture_meta or {}).get("token_error"):
        prefix = "Time recorded by the server at capture"
    else:
        prefix = None
        uploaded = e.uploaded_at or datetime.utcnow()
        if captured > uploaded + timedelta(days=1):
            return _sig("timestamp", "fail", f"The file's capture date ({_day(captured)}) is later than the upload date.")
    start, end = project.start_date if project else None, project.end_date if project else None
    if not start and not end:
        if prefix:
            return _sig("timestamp", "pass", f"{prefix}: {_day(captured)}.")
        return _sig("timestamp", "unavailable", "The project has no start and end date set yet.")
    day = captured.date()
    if (start and day < start) or (end and day > end):
        period = f"{_day(start) if start else 'any time'} to {_day(end) if end else 'now'}"
        return _sig("timestamp", "fail", f"Taken on {_day(day)}, outside the project period ({period}).")
    return _sig("timestamp", "pass", f"{prefix + ': ' if prefix else 'Taken on '}{_day(day)}, within the project period.")


def _earlier(other, e) -> bool:
    """Is `other` the original? A dated photo is treated as the original of an undated copy."""
    a, b = other.capture_time, e.capture_time
    if a and b and a != b:
        return a < b
    if b and not a:
        return False
    if a and not b:
        return True
    return other.id < e.id


def _same_view(a, b) -> bool:
    """Both photos taken at the same spot at clearly different times (repeat photography for before/after)."""
    if a.project_id != b.project_id or None in (a.latitude, b.latitude, a.capture_time, b.capture_time):
        return False
    close = haversine_m(a.latitude, a.longitude, b.latitude, b.longitude) <= max(settings.PAIR_RADIUS_M * 2, 60)
    apart = abs((a.capture_time - b.capture_time).total_seconds()) >= settings.PAIR_MIN_GAP_MINUTES * 60
    return close and apart


def _visible_changes(a, b) -> list[str]:
    from app.services.pairing import signal_changes
    ra = (a.ai_analysis.raw_response or {}) if a.ai_analysis else {}
    rb = (b.ai_analysis.raw_response or {}) if b.ai_analysis else {}
    return signal_changes(ra, rb)


def reuse_signal(e, all_evidence):
    threshold = settings.DUPLICATE_THRESHOLD
    by_id = {o.id: o for o in all_evidence}
    matches = []
    for o in all_evidence:
        if o.id == e.id:
            continue
        d = HashService.hamming(e.phash, o.phash)
        if d is None or d > threshold:
            continue
        burst = bool(o.project_id == e.project_id and e.capture_time and o.capture_time
                     and abs((e.capture_time - o.capture_time).total_seconds()) <= 3600 and d > 0)
        same_file = bool(e.sha256 and o.sha256 == e.sha256)
        matches.append({"id": o.id, "distance": d, "project_id": o.project_id,
                        "project_name": o.project.name if o.project else None,
                        "captured_at": o.capture_time.isoformat() if o.capture_time else None,
                        "uploaded_at": o.uploaded_at.isoformat() if o.uploaded_at else None,
                        "earlier": _earlier(o, e), "burst": burst, "same_file": same_file,
                        "same_view": _same_view(e, o), "image_url": o.cloudinary_url})
    matches.sort(key=lambda m: (m["distance"], m["id"]))
    others = len(all_evidence) - 1
    if not e.phash:
        return _sig("reuse", "unavailable", "Could not compute a perceptual hash for this image."), matches
    if not matches:
        return _sig("reuse", "pass", f"No visually similar image among {others} other evidence items."), matches

    live = e.capture_source == "in_app" and not (e.capture_meta or {}).get("token_error")
    earlier = [m for m in matches if m["earlier"] and not m["burst"]]
    changed, similar = [], []
    for m in earlier:
        code = f"EV-{m['id']:04d}"
        when = f" on {_day(datetime.fromisoformat(m['captured_at']))}" if m["captured_at"] else ""
        if m["same_file"] and m["project_id"] == e.project_id:
            return _sig("reuse", "warn", f"This exact file was already uploaded as {code}. Count it once.",
                        match_id=m["id"]), matches
        if m["same_view"] or live:
            changes = _visible_changes(by_id[m["id"]], e)
            if changes:
                changed.append(m)  # repeat photo of the same view with visible change: before/after evidence
                continue
            if m["distance"] <= 4:
                why = "taken live in the app" if live else "taken at the same spot"
                return _sig("reuse", "warn", f"Almost identical to {code}{when}, {why}, and no visible change was "
                                             f"detected. It may be a re-used photo or an unchanged scene; a reviewer "
                                             f"should confirm.", match_id=m["id"]), matches
            similar.append(m)
            continue
        where = f"project {m['project_name']}" if m["project_id"] != e.project_id and m["project_name"] else \
            ("another project" if m["project_id"] != e.project_id else "this project")
        kind = "Identical" if m["distance"] == 0 else "Near-identical"
        return _sig("reuse", "fail", f"{kind} to earlier evidence {code} from {where}{when} "
                                     f"(difference {m['distance']} of 64 bits). This looks like a reused photo.",
                    match_id=m["id"]), matches

    if changed:
        codes = ", ".join(f"EV-{m['id']:04d}" for m in changed[:3])
        return _sig("reuse", "pass", f"Same view as {codes}, photographed again later with visible changes, which is "
                                     f"what before-and-after evidence looks like."), matches
    if similar:
        codes = ", ".join(f"EV-{m['id']:04d}" for m in similar[:3])
        return _sig("reuse", "pass", f"Similar framing to {codes} from the same spot, taken at a different time: a "
                                     f"repeat photo of the same view, not a copy."), matches
    if all(m["burst"] for m in matches):
        ids = ", ".join(f"EV-{m['id']:04d}" for m in matches[:3])
        return _sig("reuse", "pass", f"Similar to {ids}, taken minutes apart at the same project, which looks like "
                                     f"several shots of one moment."), matches
    later = ", ".join(f"EV-{m['id']:04d}" for m in matches if not m["earlier"])
    return _sig("reuse", "pass", f"This is the earliest version. Later near-copies ({later}) are checked against it."), matches


def provenance_signal(e):
    p = e.provenance
    if not p:
        return _sig("provenance", "unavailable", "Not checked. This file was added before content-credential "
                                                 "checks existed.")
    tools = ", ".join(p.get("tools") or []) or "an AI tool"
    v = p.get("verdict")
    if v == "ai_generated":
        return _sig("provenance", "fail", f"Content credentials in the file say this image was generated by AI ({tools}).")
    if v == "ai_edited":
        return _sig("provenance", "warn", f"Content credentials say this image was edited with AI ({tools}).")
    if v == "tampered":
        return _sig("provenance", "fail", "Content credentials are attached but no longer match the image, "
                                          "so it was changed after signing.")
    signer = (p.get("manifest") or {}).get("signer")
    if v == "camera":
        return _sig("provenance", "pass", f"Content credentials record a camera capture{f' (signed by {signer})' if signer else ''}.")
    if v == "credentials_present":
        return _sig("provenance", "pass", f"Content credentials attached{f' (signed by {signer})' if signer else ''}; "
                                          f"they record no AI generation.")
    return _sig("provenance", "unavailable", "No content credentials (C2PA). Most phone photos do not carry them "
                                             "yet, and screenshots remove them.")


def metadata_signal(e):
    if e.capture_source == "in_app":
        return _sig("metadata", "unavailable", "Taken with the ImpactProof camera, which records location and time "
                                               "directly instead of relying on file metadata.")
    software = (e.software or "").lower()
    if software and any(tool in software for tool in EDITING_SOFTWARE):
        return _sig("metadata", "warn", f"The file was last saved by editing software ({e.software}).")
    have = {"GPS": e.latitude is not None, "capture date": e.capture_time is not None, "device": bool(e.device_info)}
    if all(have.values()):
        return _sig("metadata", "pass", f"Complete camera metadata from {e.device_info}.")
    if not any(have.values()):
        return _sig("metadata", "unavailable", "No camera metadata. Messaging apps and screenshots remove it, "
                                               "so this is not proof of anything.")
    missing = ", ".join(k for k, v in have.items() if not v)
    return _sig("metadata", "unavailable", f"Partial camera metadata (missing {missing}).")


def content_signal(e):
    if not e.ai_analysis:
        return _sig("content", "unavailable", "AI analysis did not run for this photo.")
    if not _ai_ready(e):
        return _sig("content", "unavailable", "AI analysis is from an older version. Run it again to check content.")
    r = _raw(e)
    warns = []
    if r.get("looks_like_screen_or_stock"):
        warns.append(f"May be a screenshot, stock image or graphic ({r.get('screen_or_stock_reason') or 'visual cues'}).")
    if r.get("is_collage_or_composite"):
        warns.append(f"Several images appear to be combined into one ({r.get('collage_reason') or 'visible panel borders'}).")
    if r.get("appears_ai_generated"):
        warns.append(f"Shows visual signs of AI generation ({r.get('ai_generated_reason') or 'visual cues'}). "
                     f"Visual detection is unreliable, so this is a warning, not a verdict.")
    if r.get("relevant_to_project") is False:
        warns.append(f"May not show this project's work. {r.get('relevance_reason') or ''}".strip())
    if warns:
        return _sig("content", "warn", " ".join(warns))
    return _sig("content", "pass", f"Shows {r.get('activity') or 'field activity'}, consistent with the project.")


def text_signal(e, project):
    if not _ai_ready(e):
        return _sig("text", "unavailable", "Visible text was not read (AI analysis missing or outdated).")
    r = _raw(e)
    texts = [t for t in r.get("visible_text") or [] if str(t).strip()]
    if not texts:
        return _sig("text", "unavailable", "No readable text in the photo.")
    problems = []
    years = r.get("visible_years") or []
    if project and (project.start_date or project.end_date) and years:
        lo = project.start_date.year if project.start_date else None
        hi = project.end_date.year if project.end_date else None
        odd = [y for y in years if (lo and y < lo) or (hi and y > hi)]
        if odd:
            span = f"{lo}" if lo == hi else f"{lo or '…'} to {hi or '…'}"
            problems.append(f"The photo shows the year {', '.join(map(str, odd))}, but the project runs {span}. "
                            f"Check whether this is older infrastructure or an older photo.")
    org = (project.organization or "").strip().lower() if project else ""
    orgs = [o for o in r.get("visible_organizations") or [] if str(o).strip()]
    if org and orgs:
        other = [o for o in orgs if org not in o.lower() and o.lower() not in org]
        if other:
            problems.append(f"Visible text names {', '.join(repr(o) for o in other[:2])}, not the project's "
                            f"organisation ({project.organization}).")
    shown = "; ".join(f"“{t}”" for t in texts[:3])
    if problems:
        return _sig("text", "warn", " ".join(problems), text=texts[:6])
    return _sig("text", "pass", f"Readable text is consistent with the project: {shown}.", text=texts[:6])


def weather_signal(e):
    w = e.weather
    if not w:
        if e.latitude is None or e.capture_time is None:
            return _sig("weather", "unavailable", "No weather check: it needs both GPS and a capture time.")
        if not settings.WEATHER_ENABLED:
            return _sig("weather", "unavailable", "Weather checks are turned off in settings.")
        return _sig("weather", "unavailable", "Weather records for that place and hour could not be fetched.")
    if w.get("error"):
        return _sig("weather", "unavailable", w["error"])
    if not _ai_ready(e):
        return _sig("weather", "unavailable", f"Recorded {w['precip_24h_mm']} mm of rain in the 24 hours before, "
                                              f"but there is no AI observation to compare with.")
    r = _raw(e)
    wet, raining = bool(r.get("ground_wet")), bool(r.get("rain_falling"))
    p24, p3 = w.get("precip_24h_mm") or 0, w.get("precip_3h_mm") or 0
    if raining and (w.get("precip_at_hour_mm") or 0) == 0 and p3 < 0.2:
        return _sig("weather", "warn", "The photo shows rain falling, but Open-Meteo recorded no rain at this "
                                       "place and hour.")
    if wet and p24 < 0.2:
        return _sig("weather", "warn", "The photo shows wet ground, but Open-Meteo recorded no rain here in the "
                                       "24 hours before it was taken.")
    if not wet and not raining and p3 >= 5:
        return _sig("weather", "warn", f"Open-Meteo recorded {p3} mm of rain in the 3 hours before, but the "
                                       f"ground looks dry.")
    cond = "wet conditions" if (wet or raining) else "dry conditions"
    return _sig("weather", "pass", f"Consistent with the recorded weather: {p24} mm of rain in the 24 hours "
                                   f"before, and the photo shows {cond}.")


# ---------------------------------------------------------------- verdict
def compute(e, project, sites, all_evidence) -> dict:
    loc, site = location_signal(e, sites)
    reuse, matches = reuse_signal(e, all_evidence)
    signals = [capture_signal(e), loc, timestamp_signal(e, project), reuse, provenance_signal(e),
               metadata_signal(e), content_signal(e), text_signal(e, project), weather_signal(e)]
    by_key = {s["key"]: s for s in signals}
    available = [s for s in signals if s["status"] != "unavailable"]
    total_w = sum(s["weight"] for s in available)
    score = round(100 * sum(s["weight"] * CREDIT[s["status"]] for s in available) / total_w) if total_w else None

    if any(by_key[k]["status"] == "fail" for k in HARD_FAIL):
        status = "SUSPICIOUS"
    elif len(available) < 3 or (by_key["location"]["status"] == "unavailable"
                                and by_key["timestamp"]["status"] == "unavailable"):
        status = "UNVERIFIABLE"
    elif (score or 0) < 75 or any(s["status"] in ("warn", "fail") for s in available):
        status = "NEEDS_REVIEW"
    else:
        status = "CORROBORATED"

    engine_status = status
    if e.review_status == "APPROVED":
        status = "CORROBORATED"
    elif e.review_status == "REJECTED":
        status = "REJECTED"

    return {
        "status": status, "engine_status": engine_status, "score": score,
        "available": len(available), "total": len(signals),
        "signals": {s["key"]: s for s in signals}, "duplicate_matches": matches[:8],
        "site_id": site.id if site else None,
    }


def headline_reasons(signals: dict, limit=3) -> list[str]:
    order = {"fail": 0, "warn": 1}
    items = sorted((s for s in (signals or {}).values() if isinstance(s, dict) and s.get("status") in order),
                   key=lambda s: order[s["status"]])
    return [s["reason"] for s in items[:limit]]
