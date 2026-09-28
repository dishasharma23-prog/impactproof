from app.services.qdrant_service import qdrant_service
from app.db.database import SessionLocal
from app.models.domain import EvidenceAsset

qdrant_service._client.delete_collection("impactproof_evidence")
from qdrant_client.models import VectorParams, Distance
qdrant_service._client.create_collection(
    collection_name="impactproof_evidence",
    vectors_config=VectorParams(size=3072, distance=Distance.COSINE),
)

db = SessionLocal()
for asset in db.query(EvidenceAsset).all():
    asset.semantic_index_status = "PENDING"
db.commit()

