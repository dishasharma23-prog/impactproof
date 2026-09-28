"""Before/after pairs: photos of the same viewpoint taken at different times."""
from app.core.config import settings
from app.services.classify import stage_of
from app.services.geo import haversine_m

EXCLUDED = ("SUSPICIOUS", "REJECTED")


def _status(e):
    return e.integrity.status if e.integrity else "UNVERIFIABLE"


def signal_changes(a: dict, b: dict) -> list[str]:
    if not a or not b:
        return []
    out = []
    names = {"waste_visible": "Visible waste", "vegetation_visible": "Vegetation", "water_visible": "Water",
             "construction_visible": "Construction", "damage_visible": "Visible damage"}
    for key, label in names.items():
        if key not in a or key not in b:
            continue
        if a.get(key) and not b.get(key):
            out.append(f"{label} seen before, not seen after")
        elif not a.get(key) and b.get(key):
            out.append(f"{label} not seen before, seen after")
    for key, noun in (("sapling_count_estimate", "Saplings"), ("people_count_estimate", "People")):
        sa, sb = a.get(key), b.get(key)
        if isinstance(sa, int) and isinstance(sb, int) and sa != sb and noun == "Saplings":
            out.append(f"{noun} visible: about {sa} before, about {sb} after (AI estimate)")
    return out


def _pick_pair(items: list):
    """Earliest 'before' photo and latest 'after' photo at a viewpoint, preferring corroborated ones.
    Falls back to the earliest and latest photos when the stages are not known."""
    def best(cands, latest):
        good = [e for e in cands if _status(e) == "CORROBORATED"] or cands
        return good[-1] if latest else good[0]
    befores = [e for e in items if stage_of(e) == "before"]
    afters = [e for e in items if stage_of(e) == "after"]
    before = best(befores, False) if befores else items[0]
    later = [e for e in (afters or items) if e.capture_time > before.capture_time]
    after = best(later, True) if later else items[-1]
    return before, after


def find_pairs(evidence: list, sites: dict) -> list[dict]:
    usable = [e for e in evidence if e.capture_time and _status(e) not in EXCLUDED
              and (e.latitude is not None or e.site_id)]
    usable.sort(key=lambda e: e.capture_time)

    groups = []  # {"lat","lng","site_id","items"}
    for e in usable:
        placed = False
        for g in groups:
            if e.latitude is not None and g["lat"] is not None:
                if haversine_m(e.latitude, e.longitude, g["lat"], g["lng"]) <= settings.PAIR_RADIUS_M:
                    g["items"].append(e)
                    placed = True
                    break
            elif e.latitude is None and g["lat"] is None and e.site_id and e.site_id == g["site_id"]:
                g["items"].append(e)
                placed = True
                break
        if not placed:
            groups.append({"lat": e.latitude, "lng": e.longitude, "site_id": e.site_id, "items": [e]})

    pairs = []
    for g in groups:
        if len(g["items"]) < 2:
            continue
        before, after = _pick_pair(g["items"])
        gap_min = (after.capture_time - before.capture_time).total_seconds() / 60
        if gap_min < settings.PAIR_MIN_GAP_MINUTES:
            continue
        site = sites.get(before.site_id or after.site_id)
        dist = None
        if before.latitude is not None and after.latitude is not None:
            dist = round(haversine_m(before.latitude, before.longitude, after.latitude, after.longitude))
        raw_a = (before.ai_analysis.raw_response or {}) if before.ai_analysis else {}
        raw_b = (after.ai_analysis.raw_response or {}) if after.ai_analysis else {}
        pairs.append({
            "key": f"{before.id}__{after.id}", "before": before.id, "after": after.id,
            "site_id": site.id if site else None, "site_name": site.name if site else None,
            "lat": g["lat"], "lng": g["lng"], "photos_at_viewpoint": len(g["items"]),
            "gap_days": round(gap_min / 1440, 1), "gap_hours": round(gap_min / 60, 1), "distance_m": dist,
            "signal_changes": signal_changes(raw_a, raw_b),
            "both_corroborated": _status(before) == "CORROBORATED" and _status(after) == "CORROBORATED",
        })
    for i, p in enumerate(pairs, start=1):
        p["label"] = p["site_name"] or f"Viewpoint {i}"
    return pairs
