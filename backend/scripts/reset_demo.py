"""Wipe all evidence, claims, reviews and history so you can load a clean demo dataset.

Projects and sites are kept. Cloudinary assets are NOT deleted (delete the 'impactproof'
folder in the Cloudinary Media Library if you want a clean slate there too).

    python -m scripts.reset_demo            (asks for confirmation)
    python -m scripts.reset_demo --yes
    python -m scripts.reset_demo --yes --all   (also removes projects and sites)
"""
import argparse
import shutil
from pathlib import Path

from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine, ensure_schema

TABLES = ["claim_evidence_links", "claims", "review_decisions", "audit_events", "cache_entries", "used_capture_tokens",
          "ai_analyses", "integrity_assessments", "transformations", "evidence_assets"]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--all", action="store_true", help="also delete projects and sites")
    args = ap.parse_args()
    if not args.yes and input("Delete all evidence, claims and history? Type yes: ").strip().lower() != "yes":
        raise SystemExit("Cancelled.")
    ensure_schema()
    tables = TABLES + (["sites", "projects"] if args.all else [])
    with engine.begin() as c:
        if engine.dialect.name == "postgresql":   # also restarts numbering at EV-0001
            c.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
        else:
            for t in tables:
                c.execute(text(f"DELETE FROM {t}"))
    originals = Path(settings.STORAGE_DIR) / "originals"
    shutil.rmtree(originals, ignore_errors=True)
    originals.mkdir(parents=True, exist_ok=True)
    try:
        from app.services.qdrant_service import qdrant_service
        if qdrant_service._client:
            qdrant_service._client.delete_collection("impactproof_evidence")
            qdrant_service.create_collection()
    except Exception as e:
        print(f"(Qdrant not reset: {e})")
    print("Done. Restart the backend, then upload your dataset.")
