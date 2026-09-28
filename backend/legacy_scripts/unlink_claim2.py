from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models import domain

def unlink():
    db = SessionLocal()
    try:
        # Delete links from Claim 2 for EV-6, EV-7, EV-8
        links = db.query(domain.ClaimEvidenceLink).filter(
            domain.ClaimEvidenceLink.claim_id == 2,
            domain.ClaimEvidenceLink.evidence_id.in_([6, 7, 8])
        ).all()
        
        count = len(links)
        for link in links:
            db.delete(link)
        db.commit()
        
        print(f"Unlinked {count} evidence assets from Claim 2.")
        
        # Query remaining evidence IDs for Claim 2
        remaining_links = db.query(domain.ClaimEvidenceLink).filter(
            domain.ClaimEvidenceLink.claim_id == 2
        ).all()
        
        remaining_ids = [link.evidence_id for link in remaining_links]
        print(f"Remaining evidence IDs for Claim 2: {remaining_ids}")
        
    finally:
        db.close()

if __name__ == "__main__":
    unlink()

