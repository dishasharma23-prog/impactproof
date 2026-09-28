"""Intelligent grouping for the gallery: work stage and activity category for every photo.

The AI proposes a stage and category; a person can override them. Older analyses without
these fields fall back to simple rules on what the AI observed.
"""
STAGES = {
    "before": "Before the work",
    "during": "During the work",
    "after": "After the work",
    "other": "Other",
}
CATEGORIES = {
    "waste": "Waste and litter",
    "planting": "Planting and greenery",
    "water": "Water and sanitation",
    "construction": "Construction and repair",
    "education": "Education and training",
    "health": "Health and care",
    "community": "People and community",
    "site": "Site overview",
    "other": "Other",
}
_KEYWORDS = [
    ("planting", ("plant", "sapling", "tree", "seed", "garden", "green")),
    ("waste", ("litter", "waste", "garbage", "trash", "plastic", "clean", "sweep", "bag")),
    ("water", ("water", "pump", "tap", "well", "tank", "toilet", "sanitation")),
    ("construction", ("build", "construct", "repair", "brick", "cement", "paint")),
    ("education", ("class", "school", "student", "teach", "book", "training")),
    ("health", ("health", "clinic", "medical", "doctor", "vaccin")),
    ("community", ("meeting", "crowd", "group", "volunteer", "people")),
]


def _raw(e) -> dict:
    return (e.ai_analysis.raw_response or {}) if e.ai_analysis else {}


def stage_of(e) -> str:
    if e.stage_override in STAGES:
        return e.stage_override
    r = _raw(e)
    if r.get("stage") in STAGES:
        return r["stage"]
    if not r:
        return "other"
    people = (r.get("people_count_estimate") or 0) > 0
    working = any(w in (r.get("activity") or "").lower() for w in ("collect", "clean", "plant", "dig", "pick", "carry", "build", "sweep"))
    if people and working:
        return "during"
    if r.get("waste_visible") or r.get("damage_visible"):
        return "before"
    if r.get("vegetation_visible") or r.get("construction_visible"):
        return "after"
    return "other"


def category_of(e) -> str:
    if e.category_override in CATEGORIES:
        return e.category_override
    r = _raw(e)
    if r.get("category") in CATEGORIES:
        return r["category"]
    text = " ".join([str(r.get("activity") or ""), " ".join(map(str, r.get("tags") or []))]).lower()
    for cat, words in _KEYWORDS:
        if any(w in text for w in words):
            return cat
    return "site" if r else "other"


def labels(e) -> dict:
    s, c = stage_of(e), category_of(e)
    return {"stage": s, "stage_label": STAGES[s], "category": c, "category_label": CATEGORIES[c],
            "stage_source": "person" if e.stage_override else ("ai" if _raw(e).get("stage") else "rules"),
            "category_source": "person" if e.category_override else ("ai" if _raw(e).get("category") else "rules")}
