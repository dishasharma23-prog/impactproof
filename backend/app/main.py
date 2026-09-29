import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.endpoints import claims, evidence, projects, volunteers
from app.core.config import cloudinary_enabled, settings
from app.db.database import SessionLocal, ensure_schema, get_db
from app.models import domain
from app.services import pipeline
from app.services.vision_service import vision_service

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("impactproof")

def startup():
    ensure_schema()
    db = SessionLocal()
    try:
        project = pipeline.default_project(db)
        orphans = db.query(domain.EvidenceAsset).filter(domain.EvidenceAsset.project_id.is_(None)).all()
        for e in orphans:
            e.project_id = project.id
        import secrets
        for c in db.query(domain.Claim).filter(domain.Claim.public_token.is_(None)).all():
            c.public_token = secrets.token_urlsafe(9)
            if not c.project_id:
                c.project_id = project.id
        db.commit()
        pipeline.retrust_all(db)
    finally:
        db.close()
    try:
        from app.services.qdrant_service import qdrant_service
        qdrant_service.create_collection()
    except Exception as e:
        log.warning(f"Qdrant not available: {e}")


@asynccontextmanager
async def lifespan(_app):
    startup()
    yield


app = FastAPI(title="ImpactProof API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?|https://.*\.(ngrok-free\.app|ngrok\.app|trycloudflare\.com)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(claims.router, prefix="/api/claims", tags=["claims"])
app.include_router(claims.public_router, prefix="/api", tags=["public"])
app.include_router(evidence.router, prefix="/api", tags=["evidence"])
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(volunteers.router, prefix="/api", tags=["volunteers"])
app.mount("/media", StaticFiles(directory=str(pipeline.ORIGINALS)), name="media")




@app.get("/api/ping")
def ping():
    """Instant liveness check for the host and uptime monitors: touches nothing external."""
    return {"ok": True}


@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "failed"
    qdrant = "missing"
    if settings.QDRANT_URL:
        try:
            from app.services.qdrant_service import qdrant_service
            qdrant_service._client.get_collections()
            qdrant = "ok"
        except Exception:
            qdrant = "unreachable"
    return {
        "database": db_status,
        "cloudinary": "configured" if cloudinary_enabled() else "missing",
        "cloud_name": settings.CLOUDINARY_CLOUD_NAME or None,
        "gemini": "configured" if vision_service.enabled else "missing",
        "qdrant": qdrant,
        "weather": "enabled" if settings.WEATHER_ENABLED else "disabled",
        "public_app_url": settings.PUBLIC_APP_URL,
    }
