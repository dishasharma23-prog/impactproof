"""UN Sustainable Development Goals: names and official colours."""

SDGS = {
    1: ("No poverty", "#E5243B"), 2: ("Zero hunger", "#DDA63A"), 3: ("Good health and well-being", "#4C9F38"),
    4: ("Quality education", "#C5192D"), 5: ("Gender equality", "#FF3A21"), 6: ("Clean water and sanitation", "#26BDE2"),
    7: ("Affordable and clean energy", "#FCC30B"), 8: ("Decent work and economic growth", "#A21942"),
    9: ("Industry, innovation and infrastructure", "#FD6925"), 10: ("Reduced inequalities", "#DD1367"),
    11: ("Sustainable cities and communities", "#FD9D24"), 12: ("Responsible consumption and production", "#BF8B2E"),
    13: ("Climate action", "#3F7E44"), 14: ("Life below water", "#0A97D9"), 15: ("Life on land", "#56C02B"),
    16: ("Peace, justice and strong institutions", "#00689D"), 17: ("Partnerships for the goals", "#19486A"),
}


def valid(nums) -> list[int]:
    out = []
    for n in nums or []:
        try:
            n = int(n)
        except (TypeError, ValueError):
            continue
        if n in SDGS and n not in out:
            out.append(n)
    return out


def info(n: int) -> dict:
    name, color = SDGS[n]
    return {"number": n, "name": name, "color": color}


def evidence_sdgs(e, project) -> list[int]:
    """Goals a photo supports: what the AI saw, limited to the project's goals when the project has any."""
    raw = (e.ai_analysis.raw_response or {}) if e.ai_analysis else {}
    seen = valid(raw.get("sdgs"))
    goals = valid(getattr(project, "sdgs", None)) if project else []
    return [n for n in seen if n in goals] if goals else seen
