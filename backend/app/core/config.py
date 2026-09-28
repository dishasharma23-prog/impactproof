import os
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg2://postgres:password@localhost:5432/impactproof"
    CLOUDINARY_URL: str = ""
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    CLOUDINARY_FOLDER: str = "impactproof"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""             # needed for Qdrant Cloud; leave empty for the local Docker Qdrant

    # Where the Next.js app runs. Used for links and QR codes on reports.
    PUBLIC_APP_URL: str = "http://localhost:3000"
    PUBLIC_API_URL: str = ""   # prefix for local images when Cloudinary is off; empty = same origin as the app
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    STORAGE_DIR: str = str(BACKEND_DIR / "storage")
    APP_SECRET: str = ""                 # signs capture tokens; generated automatically if empty
    WEATHER_ENABLED: bool = True
    DUPLICATE_THRESHOLD: int = 10        # max pHash difference (of 64 bits) to count as the same image
    PAIR_RADIUS_M: float = 40            # photos this close are the same viewpoint for before/after
    PAIR_MIN_GAP_MINUTES: int = 30
    STALE_SITE_DAYS: int = 30            # a site with no new evidence for this long is flagged in reports


settings = Settings()

# Hosting providers hand out "postgres://..." addresses; SQLAlchemy needs "postgresql://".
if settings.DATABASE_URL.startswith("postgres://"):
    settings.DATABASE_URL = "postgresql://" + settings.DATABASE_URL[len("postgres://"):]

Path(settings.STORAGE_DIR).mkdir(parents=True, exist_ok=True)
(Path(settings.STORAGE_DIR) / "originals").mkdir(parents=True, exist_ok=True)

if not settings.APP_SECRET:
    key_file = Path(settings.STORAGE_DIR) / "app_secret.key"
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32))
    settings.APP_SECRET = key_file.read_text().strip()


def cloudinary_enabled() -> bool:
    return bool((settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET)
                or settings.CLOUDINARY_URL.startswith("cloudinary://"))


import cloudinary  # noqa: E402

if settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET:
    os.environ.pop('CLOUDINARY_URL', None)
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )
elif settings.CLOUDINARY_URL.startswith("cloudinary://"):
    os.environ['CLOUDINARY_URL'] = settings.CLOUDINARY_URL
    cloudinary.reset_config()
    cloudinary.config(secure=True)
