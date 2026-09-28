import os

files = {}

files['app/services/metadata_service.py'] = '''from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from datetime import datetime
from typing import Dict, Any, Optional

class MetadataService:
    @staticmethod
    def get_decimal_from_dms(dms, ref):
        try:
            degrees = dms[0]
            minutes = dms[1]
            seconds = dms[2]
            decimal = float(degrees) + float(minutes)/60 + float(seconds)/3600
            if ref in ['S', 'W']:
                decimal = -decimal
            return decimal
        except Exception:
            return None

    @staticmethod
    def extract_metadata(file_path: str) -> Dict[str, Any]:
        metadata = {
            'capture_time': None,
            'latitude': None,
            'longitude': None,
            'device_info': None
        }
        try:
            image = Image.open(file_path)
            exif_data = image._getexif()
            if not exif_data:
                return metadata
            
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == 'DateTimeOriginal':
                    try:
                        metadata['capture_time'] = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                    except Exception:
                        pass
                elif tag == 'Make' or tag == 'Model':
                    current = metadata['device_info'] or ''
                    metadata['device_info'] = f'{current} {value}'.strip()
                elif tag == 'GPSInfo':
                    gps_data = {}
                    for t in value:
                        sub_tag = GPSTAGS.get(t, t)
                        gps_data[sub_tag] = value[t]
                    if 'GPSLatitude' in gps_data and 'GPSLatitudeRef' in gps_data:
                        metadata['latitude'] = MetadataService.get_decimal_from_dms(gps_data['GPSLatitude'], gps_data['GPSLatitudeRef'])
                    if 'GPSLongitude' in gps_data and 'GPSLongitudeRef' in gps_data:
                        metadata['longitude'] = MetadataService.get_decimal_from_dms(gps_data['GPSLongitude'], gps_data['GPSLongitudeRef'])
        except Exception as e:
            print(f'Metadata extraction error: {e}')
        return metadata
'''

files['app/services/cloudinary_service.py'] = '''import cloudinary
import cloudinary.uploader
from app.core.config import settings

if settings.CLOUDINARY_URL:
    cloudinary.config(cloudinary_url=settings.CLOUDINARY_URL)

class CloudinaryService:
    @staticmethod
    def upload_image(file_path: str) -> dict:
        if not settings.CLOUDINARY_URL:
            raise Exception('CLOUDINARY_URL is not configured.')
        response = cloudinary.uploader.upload(
            file_path,
            image_metadata=True,
            exif=True
        )
        return response
'''

files['app/services/vision_service.py'] = '''from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
from google import genai
from google.genai import types
from app.core.config import settings

class EvidenceAnalysis(BaseModel):
    observations: List[str]
    objects: List[str]
    activities: List[str]
    raw_response: Dict[str, Any]

class VisionProvider(ABC):
    @abstractmethod
    def analyze(self, image_path: str) -> EvidenceAnalysis:
        pass

class CloudinaryVisionProvider(VisionProvider):
    def analyze(self, image_path: str) -> EvidenceAnalysis:
        raise Exception('Cloudinary Vision addon not implemented/available.')

class GeminiVisionProvider(VisionProvider):
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None

    def analyze(self, image_path: str) -> EvidenceAnalysis:
        if not self.client:
            raise Exception('GEMINI_API_KEY is not configured.')
        
        try:
            # Read file as bytes instead of using path for SDK compat
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
                    'Analyze this image for environmental/impact projects. Return JSON ONLY with keys: observations (array of strings), objects (array of strings), activities (array of strings).' 
                ],
                config=types.GenerateContentConfig(
                    response_mime_type='application/json'
                )
            )
            data = json.loads(response.text)
            return EvidenceAnalysis(
                observations=data.get('observations', []),
                objects=data.get('objects', []),
                activities=data.get('activities', []),
                raw_response=data
            )
        except Exception as e:
            raise Exception(f'Gemini API call failed: {str(e)}')

class VisionService:
    def __init__(self):
        self.primary = CloudinaryVisionProvider()
        self.fallback = GeminiVisionProvider()

    def analyze_evidence(self, image_path: str) -> dict:
        status = 'FAILED'
        provider = 'none'
        analysis = None
        try:
            analysis = self.primary.analyze(image_path)
            status = 'COMPLETED'
            provider = 'cloudinary'
        except Exception as e:
            print(f'Primary provider failed: {e}')
            try:
                analysis = self.fallback.analyze(image_path)
                status = 'COMPLETED'
                provider = 'gemini'
            except Exception as e2:
                print(f'Fallback failed: {e2}')
        
        if analysis:
            return {'status': status, 'provider': provider, 'data': analysis}
        return {'status': status, 'provider': provider, 'data': None}
'''

files['app/services/integrity_service.py'] = '''class IntegrityService:
    @staticmethod
    def assess_integrity(evidence_data: dict, has_duplicate: bool) -> dict:
        signals = {}
        
        signals['metadata'] = {'status': 'AVAILABLE' if evidence_data.get('capture_time') or evidence_data.get('device_info') else 'MISSING'}
        signals['gps'] = {'status': 'AVAILABLE' if evidence_data.get('latitude') else 'MISSING'}
        signals['timestamp'] = {'status': 'AVAILABLE' if evidence_data.get('capture_time') else 'MISSING'}
        signals['phash'] = {'status': 'AVAILABLE' if evidence_data.get('phash') else 'MISSING'}
        signals['duplicate_check'] = {'status': 'POTENTIAL_MATCH' if has_duplicate else 'NO_MATCH'}
        
        # Determine overall status
        if has_duplicate:
            status = 'POTENTIAL_REUSE'
        elif signals['gps']['status'] == 'AVAILABLE' and signals['timestamp']['status'] == 'AVAILABLE':
            status = 'CORROBORATED'
        else:
            status = 'REQUIRES_REVIEW'
            
        return {
            'status': status,
            'signals': signals
        }
'''

for path, content in files.items():
    os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
print('Services generated.')

