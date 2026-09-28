from app.db.database import ensure_schema
import sys

def init_db():
    print("Creating database tables...")
    try:
        ensure_schema()
        print("Tables created successfully.")
    except Exception as e:
        print(f"Error creating tables: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_db()
