from app.services.qdrant_service import qdrant_service
print(f"Final embedding model: gemini-embedding-2")
text_repr = "This is a test of the dimension size."
embedding = qdrant_service._get_embedding(text_repr)
print(f"Actual vector dimension: {len(embedding)}")

try:
    cols = qdrant_service._client.get_collections().collections
    col_info = qdrant_service._client.get_collection("impactproof_evidence")
    print(f"Qdrant collection dimension: {col_info.config.params.vectors.size}")
except Exception as e:
    print(f"Qdrant collection dimension error: {e}")

