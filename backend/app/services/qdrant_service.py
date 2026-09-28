from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from google import genai
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class QdrantService:
    _instance = None
    _client = None
    _genai_client = None

    def __init__(self):
        if QdrantService._client is None and settings.QDRANT_URL:
            try:
                QdrantService._client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None, timeout=20)
            except Exception as e:
                logger.error(f"Failed to connect to Qdrant: {e}")
        
        if QdrantService._genai_client is None and settings.GEMINI_API_KEY:
            QdrantService._genai_client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def _get_embedding(self, text: str) -> list[float]:
        result = self._genai_client.models.embed_content(
            model="gemini-embedding-2",
            contents=text
        )
        return result.embeddings[0].values

    def create_collection(self):
        if not self._client:
            return
        collection_name = "impactproof_evidence"
        try:
            collections = self._client.get_collections().collections
            if not any(c.name == collection_name for c in collections):
                self._client.create_collection(
                    collection_name=collection_name,
                    # gemini-embedding-2 returns 3072-dimensional vectors
                    vectors_config=VectorParams(size=3072, distance=Distance.COSINE),
                )
                logger.info(f"Created Qdrant collection: {collection_name}")
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")

    def generate_semantic_text(self, ai_analysis, evidence=None) -> str:
        parts = []
        
        if evidence:
            if evidence.capture_time:
                parts.append(f"Captured on: {evidence.capture_time.isoformat()}")
            if evidence.latitude and evidence.longitude:
                parts.append(f"Location: {evidence.latitude}, {evidence.longitude}")
            if evidence.device_info:
                parts.append(f"Device: {evidence.device_info}")
            if evidence.site:
                parts.append(f"Site Name: {evidence.site.name}")
                if evidence.site.project:
                    parts.append(f"Project Name: {evidence.site.project.name}")

        if ai_analysis:
            raw = getattr(ai_analysis, "raw_response", None) or {}
            for key in ("activity", "description"):
                if raw.get(key):
                    parts.append(str(raw[key]))
            if raw.get("tags"):
                parts.append("Tags: " + ", ".join(map(str, raw["tags"])))
            if raw.get("visible_text"):
                parts.append("Visible text: " + "; ".join(map(str, raw["visible_text"])))
            if getattr(ai_analysis, "observations", None):
                parts.extend(ai_analysis.observations)
            if getattr(ai_analysis, "objects", None):
                parts.append("Objects: " + ", ".join(ai_analysis.objects))
            if getattr(ai_analysis, "activities", None):
                parts.append("Activities: " + ", ".join(ai_analysis.activities))
                
        if not parts:
            return "Uncategorized evidence asset"
            
        return " ".join(parts)

    def upsert_evidence(self, evidence_id: int, text_representation: str, payload: dict):
        if not self._client or not self._genai_client:
            raise ValueError("Qdrant or Gemini not configured")
            
        vector = self._get_embedding(text_representation)
        
        payload["evidence_id"] = evidence_id
        
        point = PointStruct(
            id=evidence_id,
            vector=vector,
            payload=payload
        )
        
        self._client.upsert(
            collection_name="impactproof_evidence",
            points=[point]
        )

    def search(self, query: str, limit: int = 10):
        if not self._client or not self._genai_client:
            return []
        try:
            vector = self._get_embedding(query)
            hits = self._client.query_points(
                collection_name="impactproof_evidence",
                query=vector,
                limit=limit
            ).points
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
        
        return [
            {
                "evidence_id": hit.payload.get("evidence_id"),
                "similarity": hit.score,
                "payload": hit.payload
            }
            for hit in hits
        ]

qdrant_service = QdrantService()

