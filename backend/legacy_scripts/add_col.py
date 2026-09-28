from app.db.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE evidence_assets ADD COLUMN duplicate_of_evidence_id INTEGER REFERENCES evidence_assets(id);"))
        conn.commit()
    except Exception as e:
        print(e)

