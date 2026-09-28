from app.db.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE evidence_assets ADD COLUMN semantic_index_status VARCHAR DEFAULT 'PENDING';"))
        conn.commit()
    except Exception as e:
        print(e)

