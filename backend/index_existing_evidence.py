import os
from app.db.database import SessionLocal
from app.models.domain import EvidenceAsset, AIAnalysis  # noqa
from app.services.qdrant_service import qdrant_service

def run():
    print("Initializing Qdrant collection...")
    qdrant_service.create_collection()
    
    db = SessionLocal()
    assets = db.query(EvidenceAsset).all()
    
    indexed = 0
    skipped = 0
    failed = 0
    
    for asset in assets:
        if asset.semantic_index_status == "INDEXED":
            skipped += 1
            continue
            
        try:
            ai_analysis = db.query(AIAnalysis).filter(AIAnalysis.evidence_id == asset.id).first()
            semantic_text = qdrant_service.generate_semantic_text(ai_analysis, asset)
            
            project_id = asset.site.project_id if asset.site else None
            site_id = asset.site_id
            
            payload = {
                "project_id": project_id,
                "site_id": site_id,
                "capture_time": asset.capture_time.isoformat() if asset.capture_time else None,
                "integrity_status": asset.integrity.status if asset.integrity else "UNKNOWN",
                "original_or_derived": "ORIGINAL",
                "cloudinary_public_id": asset.cloudinary_public_id
            }
            
            qdrant_service.upsert_evidence(asset.id, semantic_text, payload)
            
            asset.semantic_index_status = "INDEXED"
            db.commit()
            indexed += 1
            print(f"Indexed EV-{asset.id:04d}")
        except Exception as e:
            print(f"Failed to index EV-{asset.id:04d}: {e}")
            asset.semantic_index_status = "FAILED"
            db.commit()
            failed += 1
            
    print("\n--- Indexing Report ---")
    print(f"Indexed: {indexed}")
    print(f"Skipped: {skipped}")
    print(f"Failed:  {failed}")

if __name__ == "__main__":
    run()

