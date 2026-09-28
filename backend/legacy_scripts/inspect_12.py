from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models import domain

def inspect():
    db = SessionLocal()
    try:
        ev = db.query(domain.EvidenceAsset).filter(domain.EvidenceAsset.id == 12).first()
        if ev:
            print(f"ID: {ev.id}")
            print(f"Cloudinary: {ev.cloudinary_url}")
            print(f"Processing Status: {ev.processing_status}")
            print(f"Semantic Index Status: {ev.semantic_index_status}")
            print(f"pHash: {ev.phash}")
    finally:
        db.close()

if __name__ == "__main__":
    inspect()

