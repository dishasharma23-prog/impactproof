"""Add every photo in a folder to a project, with all checks, without using the browser.

    python -m scripts.ingest_folder "C:\\path\\to\\photos" --project 1
"""
import argparse
import mimetypes
from pathlib import Path

from app.db.database import SessionLocal, ensure_schema
from app.services import pipeline

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--project", type=int, default=None, help="project id (default: first project)")
    args = ap.parse_args()
    ensure_schema()
    db = SessionLocal()
    files = sorted(p for p in Path(args.folder).iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
    print(f"Adding {len(files)} photos…")
    for f in files:
        try:
            e = pipeline.ingest(db, f.read_bytes(), f.name, mimetypes.guess_type(f.name)[0], args.project)
            label = e.integrity.status if e.integrity else "?"
            print(f"EV-{e.id:04d}  {label:<13} {f.name}")
        except Exception as ex:
            db.rollback()
            print(f"FAILED  {f.name}: {ex}")
    db.close()
