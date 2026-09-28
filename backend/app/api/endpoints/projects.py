from datetime import date
from statistics import median
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models import domain
from app.serializers import evidence_light, image_url, project_dict, sdg_summary, site_dict, thumb_url
from app.services import audit_service, classify, claim_service, pairing, pipeline, sdg, trust_engine
from app.services.geo import haversine_m
from app.services.vision_service import VisionError, vision_service

router = APIRouter()


class ProjectIn(BaseModel):
    name: str
    description: str = ""
    organization: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    sdgs: list[int] = []


class SiteIn(BaseModel):
    name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_m: float = 300
    description: Optional[str] = None


def _project(db, pid) -> domain.Project:
    p = db.get(domain.Project, pid)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


@router.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    pipeline.default_project(db)
    return [project_dict(p) for p in db.query(domain.Project).order_by(domain.Project.id).all()]


@router.post("/projects")
def create_project(body: ProjectIn, db: Session = Depends(get_db)):
    p = domain.Project(**{**body.model_dump(), "sdgs": sdg.valid(body.sdgs)})
    db.add(p)
    db.flush()
    audit_service.log(db, "project", p.id, "created", f"Project “{p.name}” created.")
    db.commit()
    return project_dict(p)


@router.put("/projects/{project_id}")
def update_project(project_id: int, body: ProjectIn, db: Session = Depends(get_db)):
    p = _project(db, project_id)
    for k, v in body.model_dump().items():
        setattr(p, k, sdg.valid(v) if k == "sdgs" else v)
    audit_service.log(db, "project", p.id, "updated", "Project details updated; all evidence was checked again.",
                      body.model_dump(mode="json"))
    db.commit()
    pipeline.retrust_all(db)
    return project_dict(p)


@router.get("/projects/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db)):
    p = _project(db, project_id)
    ev = [e for e in pipeline.load_all(db) if e.project_id == p.id]
    return {**project_dict(p), "sites": [site_dict(s, ev) for s in p.sites]}


@router.get("/projects/{project_id}/overview")
def overview(project_id: int, db: Session = Depends(get_db)):
    p = _project(db, project_id)
    ev = [e for e in pipeline.load_all(db) if e.project_id == p.id]
    counts = {k: 0 for k in trust_engine.STATUS_LABELS}
    for e in ev:
        counts[e.integrity.status if e.integrity else "UNVERIFIABLE"] += 1
    ev_sorted = sorted(ev, key=lambda e: e.uploaded_at or e.id, reverse=True)
    return {
        "project": project_dict(p), "counts": counts, "total": len(ev),
        "sites": [site_dict(s, ev) for s in p.sites],
        "coverage": claim_service.coverage(p.sites, ev, p),
        "evidence": [evidence_light(e) for e in ev_sorted],
        "review_count": sum(1 for e in ev if e.integrity and e.integrity.status in
                            ("SUSPICIOUS", "NEEDS_REVIEW", "UNVERIFIABLE") and not e.review_status),
        "claims": db.query(domain.Claim).filter(domain.Claim.project_id == p.id).count(),
        "sdgs": sdg_summary(ev, p),
    }


@router.get("/sdgs")
def list_sdgs():
    return [sdg.info(n) for n in sdg.SDGS]


@router.post("/projects/{project_id}/sites")
def create_site(project_id: int, body: SiteIn, db: Session = Depends(get_db)):
    p = _project(db, project_id)
    s = domain.Site(project_id=p.id, **body.model_dump())
    db.add(s)
    db.flush()
    audit_service.log(db, "site", s.id, "created", f"Site “{s.name}” added to {p.name}.", body.model_dump())
    db.commit()
    pipeline.retrust_all(db)
    return site_dict(s)


@router.put("/sites/{site_id}")
def update_site(site_id: int, body: SiteIn, db: Session = Depends(get_db)):
    s = db.get(domain.Site, site_id)
    if not s:
        raise HTTPException(status_code=404, detail="Site not found")
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    audit_service.log(db, "site", s.id, "updated", f"Site “{s.name}” updated.", body.model_dump())
    db.commit()
    pipeline.retrust_all(db)
    return site_dict(s)


@router.delete("/sites/{site_id}")
def delete_site(site_id: int, db: Session = Depends(get_db)):
    s = db.get(domain.Site, site_id)
    if not s:
        raise HTTPException(status_code=404, detail="Site not found")
    for e in db.query(domain.EvidenceAsset).filter(domain.EvidenceAsset.site_id == s.id).all():
        e.site_id = None
    audit_service.log(db, "site", s.id, "deleted", f"Site “{s.name}” removed.")
    db.delete(s)
    db.commit()
    pipeline.retrust_all(db)
    return {"deleted": site_id}


@router.get("/projects/{project_id}/suggest-sites")
def suggest_sites(project_id: int, db: Session = Depends(get_db)):
    """Groups photo locations into candidate sites (photos within 200 m of each other)."""
    p = _project(db, project_id)
    pts = [e for e in pipeline.load_all(db) if e.project_id == p.id and e.latitude is not None]
    clusters = []
    for e in pts:
        for c in clusters:
            if haversine_m(e.latitude, e.longitude, c["lat"], c["lng"]) <= 200:
                c["items"].append(e)
                c["lat"] = median(x.latitude for x in c["items"])
                c["lng"] = median(x.longitude for x in c["items"])
                break
        else:
            clusters.append({"lat": e.latitude, "lng": e.longitude, "items": [e]})
    existing = [(s.latitude, s.longitude) for s in p.sites if s.latitude is not None]
    out = []
    for c in sorted(clusters, key=lambda c: -len(c["items"])):
        if any(haversine_m(c["lat"], c["lng"], a, b) < 150 for a, b in existing):
            continue
        spread = max(haversine_m(c["lat"], c["lng"], x.latitude, x.longitude) for x in c["items"])
        out.append({"latitude": round(c["lat"], 6), "longitude": round(c["lng"], 6), "photos": len(c["items"]),
                    "radius_m": int(max(150, min(1000, spread * 1.5 + 50)))})
    return out


@router.get("/sites/{site_id}/reference")
def site_reference(site_id: int, db: Session = Depends(get_db)):
    """Latest trustworthy photo of a site, used as the ghost overlay in the camera."""
    s = db.get(domain.Site, site_id)
    if not s:
        raise HTTPException(status_code=404, detail="Site not found")
    items = [e for e in pipeline.load_all(db) if e.site_id == s.id and e.integrity
             and e.integrity.status not in ("SUSPICIOUS", "REJECTED")]
    items.sort(key=lambda e: e.capture_time or e.uploaded_at, reverse=True)
    if not items:
        return {"site": site_dict(s), "reference": None}
    e = items[0]
    return {"site": site_dict(s), "reference": {**evidence_light(e), "overlay_url": thumb_url(e, 1280, 960),
                                                "full_url": image_url(e)}}


@router.get("/projects/{project_id}/pairs")
def pairs(project_id: int, db: Session = Depends(get_db)):
    p = _project(db, project_id)
    ev = [e for e in pipeline.load_all(db) if e.project_id == p.id]
    by_id = {e.id: e for e in ev}
    out = pairing.find_pairs(ev, {s.id: s for s in p.sites})
    for pr in out:
        cached = db.get(domain.CacheEntry, "pair:" + pr["key"])
        pr["description"] = cached.data if cached else None
        pr["before_evidence"] = evidence_light(by_id[pr["before"]])
        pr["after_evidence"] = evidence_light(by_id[pr["after"]])
    return out


class PairIn(BaseModel):
    before: int
    after: int


@router.post("/pairs/describe")
def describe_pair(body: PairIn, db: Session = Depends(get_db)):
    a, b = db.get(domain.EvidenceAsset, body.before), db.get(domain.EvidenceAsset, body.after)
    if not a or not b:
        raise HTTPException(status_code=404, detail="Evidence not found")
    if not vision_service.enabled:
        raise HTTPException(status_code=400, detail="Add a GEMINI_API_KEY to describe changes.")
    try:
        result = vision_service.describe_pair(pipeline.image_bytes(a), pipeline.image_bytes(b), a.project)
    except (VisionError, pipeline.IngestError) as ex:
        raise HTTPException(status_code=400, detail=str(ex))
    key = f"pair:{a.id}__{b.id}"
    entry = db.get(domain.CacheEntry, key) or domain.CacheEntry(key=key)
    entry.data = result
    db.merge(entry)
    db.commit()
    return result


GROUPS = ("stage", "category", "site", "date")


@router.get("/projects/{project_id}/gallery")
def gallery(project_id: int, group: str = "stage", db: Session = Depends(get_db)):
    """Photos arranged into sections: by work stage, activity, site or day."""
    if group not in GROUPS:
        raise HTTPException(status_code=400, detail=f"group must be one of {', '.join(GROUPS)}")
    p = _project(db, project_id)
    ev = sorted([e for e in pipeline.load_all(db) if e.project_id == p.id],
                key=lambda e: e.capture_time or e.uploaded_at)
    sections: dict[str, dict] = {}

    def add(key, title, e, order):
        sec = sections.setdefault(key, {"key": key, "title": title, "order": order, "items": []})
        sec["items"].append(evidence_light(e))

    stage_order = list(classify.STAGES)
    cat_order = list(classify.CATEGORIES)
    for e in ev:
        if group == "stage":
            k = classify.stage_of(e)
            add(k, classify.STAGES[k], e, stage_order.index(k))
        elif group == "category":
            k = classify.category_of(e)
            add(k, classify.CATEGORIES[k], e, cat_order.index(k))
        elif group == "site":
            if e.site:
                add(f"site_{e.site.id}", e.site.name, e, e.site.id)
            else:
                add("none", "Not at a project site", e, 10 ** 9)
        else:
            d = (e.capture_time or e.uploaded_at)
            add(d.date().isoformat(), d.strftime("%A %d %B %Y"), e, -d.toordinal())
    out = sorted(sections.values(), key=lambda s: s["order"])
    for sec in out:
        counts = {}
        for it in sec["items"]:
            counts[it["integrity_status"]] = counts.get(it["integrity_status"], 0) + 1
        sec["counts"] = counts
        sec.pop("order")
    return {"group": group, "total": len(ev), "sections": out,
            "stages": classify.STAGES, "categories": classify.CATEGORIES}
