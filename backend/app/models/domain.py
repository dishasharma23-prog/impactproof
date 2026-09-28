from datetime import datetime

from sqlalchemy import (JSON, Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    organization = Column(String, nullable=True)      # used by the visible-text check
    start_date = Column(Date, nullable=True)          # project period, used by the date check
    end_date = Column(Date, nullable=True)
    sdgs = Column(JSON, nullable=True)                # UN Sustainable Development Goals this project serves
    created_at = Column(DateTime, default=datetime.utcnow)
    sites = relationship('Site', back_populates='project')


class Site(Base):
    __tablename__ = 'sites'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'))
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    radius_m = Column(Float, nullable=True, default=300)
    description = Column(String, nullable=True)
    project = relationship('Project', back_populates='sites')
    evidence = relationship('EvidenceAsset', back_populates='site')


class EvidenceAsset(Base):
    __tablename__ = 'evidence_assets'
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)
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
    semantic_index_status = Column(String, default='PENDING')
    duplicate_of_evidence_id = Column(Integer, ForeignKey('evidence_assets.id'), nullable=True)

    # Added for the trust engine
    capture_source = Column(String, nullable=True, default='upload')  # upload | in_app
    capture_meta = Column(JSON, nullable=True)       # live GPS, accuracy, client time, capture token check
    software = Column(String, nullable=True)         # EXIF Software tag (editing apps)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    mime_type = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    sha256 = Column(String, nullable=True)           # seal of the exact bytes received
    md5 = Column(String, nullable=True)
    cloudinary_etag = Column(String, nullable=True)  # Cloudinary's MD5 of the stored original
    cloudinary_phash = Column(String, nullable=True)
    cloudinary_asset_id = Column(String, nullable=True)
    cloudinary_version = Column(String, nullable=True)
    local_file = Column(String, nullable=True)       # copy kept in backend/storage for re-checks
    volunteer_id = Column(Integer, ForeignKey('volunteers.id'), nullable=True)  # who captured it (field app)
    provenance = Column(JSON, nullable=True)         # C2PA / IPTC digital source type findings
    weather = Column(JSON, nullable=True)            # Open-Meteo lookup at capture time and place
    review_status = Column(String, nullable=True)    # None | APPROVED | REJECTED
    stage_override = Column(String, nullable=True)     # before | during | after | other, set by a person
    category_override = Column(String, nullable=True)

    site = relationship('Site', back_populates='evidence')
    project = relationship('Project')
    ai_analysis = relationship('AIAnalysis', back_populates='evidence', uselist=False)
    integrity = relationship('IntegrityAssessment', back_populates='evidence', uselist=False)
    duplicate_of_evidence = relationship('EvidenceAsset', remote_side=[id])
    volunteer = relationship('Volunteer')


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
    engine_status = Column(String, nullable=True)   # verdict before any reviewer decision
    score = Column(Integer, nullable=True)
    available = Column(Integer, nullable=True)
    total = Column(Integer, nullable=True)
    duplicate_matches = Column(JSON, nullable=True)
    computed_at = Column(DateTime, nullable=True)
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


class Claim(Base):
    __tablename__ = 'claims'
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)
    text = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    public_token = Column(String, nullable=True, index=True)   # for the public verification page

    project = relationship('Project')
    evidence_links = relationship('ClaimEvidenceLink', back_populates='claim')


class ClaimEvidenceLink(Base):
    __tablename__ = 'claim_evidence_links'
    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey('claims.id'))
    evidence_id = Column(Integer, ForeignKey('evidence_assets.id'))
    linked_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint('claim_id', 'evidence_id', name='uq_claim_evidence'),)

    claim = relationship('Claim', back_populates='evidence_links')
    evidence = relationship('EvidenceAsset')


class ReviewDecision(Base):
    __tablename__ = 'review_decisions'
    id = Column(Integer, primary_key=True, index=True)
    evidence_id = Column(Integer, ForeignKey('evidence_assets.id'), index=True)
    decision = Column(String)       # APPROVED | REJECTED | REOPENED
    reason = Column(Text)
    reviewer = Column(String)
    engine_status = Column(String)  # what the engine said at the time
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditEvent(Base):
    """Append-only history of everything that happened to evidence and claims."""
    __tablename__ = 'audit_events'
    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, index=True)   # evidence | claim | project | site
    entity_id = Column(Integer, index=True)
    action = Column(String)
    summary = Column(Text)
    detail = Column(JSON, nullable=True)
    actor = Column(String, default='system')
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class CacheEntry(Base):
    """Small key-value cache, e.g. AI descriptions of before/after pairs."""
    __tablename__ = 'cache_entries'
    key = Column(String, primary_key=True)
    data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class UsedCaptureToken(Base):
    __tablename__ = 'used_capture_tokens'
    token_id = Column(String, primary_key=True)
    used_at = Column(DateTime, default=datetime.utcnow)


class EarlyAccessRequest(Base):
    __tablename__ = 'early_access_requests'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    organisation = Column(String)
    email = Column(String)
    role = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Volunteer(Base):
    """A field volunteer, registered by phone number. Their device pairs once with a code and then uploads with a key."""
    __tablename__ = 'volunteers'
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False, index=True)       # normalised, e.g. +919876543210
    pairing_code_hash = Column(String, nullable=True)        # 6-digit code, hashed; cleared once used
    pairing_expires_at = Column(DateTime, nullable=True)
    device_key_hash = Column(String, nullable=True, index=True)
    device_name = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    paired_at = Column(DateTime, nullable=True)
    last_upload_at = Column(DateTime, nullable=True)
