import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def init_db():
    if not DATABASE_URL:
        print("[!] No DATABASE_URL found in .env")
        return

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Create Analysis table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS truthlens_analysis (
                id SERIAL PRIMARY KEY,
                url TEXT UNIQUE,
                title TEXT,
                trust_index FLOAT,
                risk_level TEXT,
                manipulation_score FLOAT,
                evidence_confidence FLOAT,
                detected_claims JSONB,
                raw_nlp_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create Viral Monitoring table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS viral_monitoring (
                id SERIAL PRIMARY KEY,
                platform TEXT,
                video_id TEXT UNIQUE,
                author TEXT,
                risk_score FLOAT,
                metadata JSONB,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        print("[*] Neon Database initialized successfully.")
    except Exception as e:
        print(f"[!] Database error: {e}")

if __name__ == "__main__":
    init_db()
