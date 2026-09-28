import sys

code = """
@router.get("/{claim_id}/report")
def get_claim_report(claim_id: int, db: Session = Depends(get_db)):
    from datetime import datetime
    claim = db.query(domain.Claim).filter(domain.Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
        
    project_name = claim.project.name if claim.project else "Independent Impact Claim"
    
    links = db.query(domain.ClaimEvidenceLink).filter(domain.ClaimEvidenceLink.claim_id == claim_id).all()
    evidence_ids = [link.evidence_id for link in links]
    evidence = db.query(domain.EvidenceAsset).filter(domain.EvidenceAsset.id.in_(evidence_ids)).all()
    
    # Extract site name from evidence if claim does not have one
    site_names = [e.site.name for e in evidence if getattr(e, "site", None)]
    site_name = site_names[0] if site_names else None
    
    evidence_list = []
    for e in evidence:
        integrity_status = e.integrity.status if e.integrity else "UNKNOWN"
            
        dup_dict = None
        if e.duplicate_of_evidence:
            dup_dict = {
                "id": e.duplicate_of_evidence.id,
                "cloudinary_url": e.duplicate_of_evidence.cloudinary_url,
                "phash": e.duplicate_of_evidence.phash
            }
            
        evidence_list.append({
            "id": e.id,
            "cloudinary_url": e.cloudinary_url,
            "capture_time": e.capture_time.isoformat() if e.capture_time else None,
            "latitude": e.latitude,
            "longitude": e.longitude,
            "original_or_derived": "ORIGINAL",
            "integrity_status": integrity_status,
            "phash": e.phash,
            "duplicate_of_evidence": dup_dict
        })
        
    return {
        "report_title": "Impact Brief",
        "generated_at": datetime.utcnow().isoformat(),
        "project_name": project_name,
        "site_name": site_name,
        "claim_text": claim.text,
        "evidence": evidence_list
    }
"""

with open("app/api/endpoints/claims.py", "a") as f:
    f.write(code)
print("Done appending report endpoint")

