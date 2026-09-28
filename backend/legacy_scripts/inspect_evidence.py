from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models import domain

def inspect():
    db = SessionLocal()
    try:
        for ev_id in [6, 7, 8, 10]:
            ev = db.query(domain.EvidenceAsset).filter(domain.EvidenceAsset.id == ev_id).first()
            if not ev:
                print(f"EV-00{ev_id:02d}: NOT FOUND")
                continue
                
            link = db.query(domain.ClaimEvidenceLink).filter(
                domain.ClaimEvidenceLink.evidence_id == ev_id,
                domain.ClaimEvidenceLink.claim_id == 2
            ).first()
            is_linked = "Yes" if link else "No"
            
            is_seed = "Seed/Demo" if "media_" in str(ev.original_filename) else "Newly Uploaded"
            
            print(f"--- EV-00{ev_id:02d} ---")
            print(f"Cloudinary public_id: {ev.cloudinary_public_id}")
            print(f"Linked to Claim 2: {is_linked}")
            print(f"Duplicate of: {ev.duplicate_of_evidence_id}")
            print(f"Semantic Index Status: {ev.semantic_index_status}")
            print(f"Asset Type: {is_seed} (Filename: {ev.original_filename})")
            print("")
    finally:
        db.close()

if __name__ == "__main__":
    inspect()

