import os

files = {}

files['app/core/config.py'] = '''from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = 'postgresql://postgres:password@localhost:5432/impactproof'
    CLOUDINARY_URL: str = ''
    GEMINI_API_KEY: str = ''
    QDRANT_URL: str = 'http://localhost:6333'

    class Config:
        env_file = '.env'

settings = Settings()
'''

files['.env.example'] = '''DATABASE_URL=postgresql://postgres:password@localhost:5432/impactproof
CLOUDINARY_URL=
GEMINI_API_KEY=
QDRANT_URL=http://localhost:6333
'''

files['app/models/domain.py'] = '''from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON, Boolean
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    sites = relationship('Site', back_populates='project')

class Site(Base):
    __tablename__ = 'sites'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'))
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    project = relationship('Project', back_populates='sites')
    evidence = relationship('EvidenceAsset', back_populates='site')

class EvidenceAsset(Base):
    __tablename__ = 'evidence_assets'
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey('sites.id'), nullable=True)
    cloudinary_url = Column(String, nullable=True)
    cloudinary_public_id = Column(String, nullable=True)
    original_filename = Column(String)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    capture_time = Column(DateTime, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    device_info = Column(String, nullable=True)
    phash = Column(String, nullable=True)
    processing_status = Column(String, default='PENDING')
    site = relationship('Site', back_populates='evidence')
    ai_analysis = relationship('AIAnalysis', back_populates='evidence', uselist=False)
    integrity = relationship('IntegrityAssessment', back_populates='evidence', uselist=False)

class AIAnalysis(Base):
    __tablename__ = 'ai_analyses'
    id = Column(Integer, primary_key=True, index=True)
    evidence_id = Column(Integer, ForeignKey('evidence_assets.id'))
    provider = Column(String)
    observations = Column(JSON)
    objects = Column(JSON)
    activities = Column(JSON)
    raw_response = Column(JSON, nullable=True)
    evidence = relationship('EvidenceAsset', back_populates='ai_analysis')

class IntegrityAssessment(Base):
    __tablename__ = 'integrity_assessments'
    id = Column(Integer, primary_key=True, index=True)
    evidence_id = Column(Integer, ForeignKey('evidence_assets.id'))
    status = Column(String)
    signals = Column(JSON)
    evidence = relationship('EvidenceAsset', back_populates='integrity')

class Transformation(Base):
    __tablename__ = 'transformations'
    id = Column(Integer, primary_key=True, index=True)
    original_id = Column(Integer, ForeignKey('evidence_assets.id'))
    derivative_id = Column(Integer, ForeignKey('evidence_assets.id'))
    type = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    original_evidence = relationship('EvidenceAsset', foreign_keys=[original_id])
    derivative_evidence = relationship('EvidenceAsset', foreign_keys=[derivative_id])
'''

for path, content in files.items():
    os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
print('Models and config generated.')

