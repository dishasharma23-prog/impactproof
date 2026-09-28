import os

files = {}

files['app/main.py'] = '''from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db, engine
from app.models import domain
from app.services.cloudinary_service import CloudinaryService
from app.services.hash_service import HashService
from app.services.vision_service import VisionService
from app.services.metadata_service import MetadataService
from app.services.integrity_service import IntegrityService
from app.core.config import settings
import shutil
import os

# Create tables explicitly since Alembic isn't configured for this fast-path yet.
domain.Base.metadata.create_all(bind=engine)

app = FastAPI(title='ImpactProof API')
vision_service = VisionService()

@app.get('/api/health')
def health_check(db: Session = Depends(get_db)):
    db_status = 'ok'
    try:
        db.execute('SELECT 1')
    except Exception:
        db_status = 'failed'
    
    return {
        'database': db_status,
        'cloudinary': 'configured' if settings.CLOUDINARY_URL else 'missing',
        'gemini': 'configured' if settings.GEMINI_API_KEY else 'missing',
        'qdrant': 'configured' if settings.QDRANT_URL else 'missing'
    }

@app.post('/api/evidence/upload')
async def upload_evidence(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not settings.CLOUDINARY_URL:
        raise HTTPException(status_code=500, detail='Cloudinary is not configured')
    
    file_location = f'temp_{file.filename}'
    with open(file_location, 'wb+') as file_object:
        shutil.copyfileobj(file.file, file_object)
    
    try:
        # 1. Cloudinary
        cloudinary_res = CloudinaryService.upload_image(file_location)
        
        # 2. Metadata
        metadata = MetadataService.extract_metadata(file_location)
        
        # 3. pHash
        phash = HashService.calculate_phash(file_location)
        
        # Duplicate check
        duplicate = False
        if phash:
            dup = db.query(domain.EvidenceAsset).filter(domain.EvidenceAsset.phash == phash).first()
            if dup:
                duplicate = True
        
        # 4. Integrity
        integrity_res = IntegrityService.assess_integrity(metadata, duplicate)
        
        # 5. Vision Analysis
        analysis_res = vision_service.analyze_evidence(file_location)
        
        # 6. Save Evidence
        evidence = domain.EvidenceAsset(
            cloudinary_url=cloudinary_res.get('secure_url'),
            cloudinary_public_id=cloudinary_res.get('public_id'),
            original_filename=file.filename,
            capture_time=metadata.get('capture_time'),
            latitude=metadata.get('latitude'),
            longitude=metadata.get('longitude'),
            device_info=metadata.get('device_info'),
            phash=phash,
            processing_status='COMPLETED' if analysis_res['status'] == 'COMPLETED' else 'FAILED'
        )
        db.add(evidence)
        db.commit()
        db.refresh(evidence)
        
        # Save AI
        if analysis_res['data']:
            ai_data = analysis_res['data']
            ai = domain.AIAnalysis(
                evidence_id=evidence.id,
                provider=analysis_res['provider'],
                observations=ai_data.observations,
                objects=ai_data.objects,
                activities=ai_data.activities,
                raw_response=ai_data.raw_response
            )
            db.add(ai)
        
        # Save Integrity
        integ = domain.IntegrityAssessment(
            evidence_id=evidence.id,
            status=integrity_res['status'],
            signals=integrity_res['signals']
        )
        db.add(integ)
        db.commit()
        
        return {'evidence_id': evidence.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(file_location):
            os.remove(file_location)

@app.get('/api/evidence/{evidence_id}')
def get_evidence(evidence_id: int, db: Session = Depends(get_db)):
    evidence = db.query(domain.EvidenceAsset).filter(domain.EvidenceAsset.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail='Evidence not found')
    
    return {
        'id': evidence.id,
        'original_filename': evidence.original_filename,
        'cloudinary_url': evidence.cloudinary_url,
        'capture_time': evidence.capture_time,
        'uploaded_at': evidence.uploaded_at,
        'processing_status': evidence.processing_status,
        'location': {
            'latitude': evidence.latitude,
            'longitude': evidence.longitude
        },
        'device_info': evidence.device_info,
        'phash': evidence.phash,
        'ai_analysis': {
            'provider': evidence.ai_analysis.provider if evidence.ai_analysis else None,
            'observations': evidence.ai_analysis.observations if evidence.ai_analysis else [],
            'objects': evidence.ai_analysis.objects if evidence.ai_analysis else [],
            'activities': evidence.ai_analysis.activities if evidence.ai_analysis else []
        } if evidence.ai_analysis else None,
        'integrity': {
            'status': evidence.integrity.status if evidence.integrity else 'UNKNOWN',
            'signals': evidence.integrity.signals if evidence.integrity else {}
        } if evidence.integrity else None
    }
'''

for path, content in files.items():
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
print('Main API generated.')

