import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Try to load the database URL from .env, or use the provided one as fallback
load_dotenv()
DB_URL = os.getenv("DATABASE_URL", "postgresql://neondb_owner:npg_15JeHXKVSZCs@ep-wandering-morning-ap280pr7-pooler.c-7.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require")

def inspect_database():
    print(f"[*] Connecting to database: {DB_URL.split('@')[-1].split('/')[0]} ...")
    
    try:
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
        cur = conn.cursor()
        
        output_lines = []
        output_lines.append("="*60)
        output_lines.append("DATABASE ARCHITECTURE AND DATA DUMP")
        output_lines.append("="*60 + "\n")
        
        # 1. Get all public tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        tables = cur.fetchall()
        
        if not tables:
            output_lines.append("No tables found in the 'public' schema.")
        
        for table in tables:
            table_name = table['table_name']
            output_lines.append(f"📦 TABLE: {table_name}")
            output_lines.append("-" * 40)
            
            # 2. Get columns and types
            cur.execute(f"""
                SELECT column_name, data_type, character_maximum_length, is_nullable
                FROM information_schema.columns 
                WHERE table_name = %s 
                ORDER BY ordinal_position;
            """, (table_name,))
            columns = cur.fetchall()
            
            output_lines.append("SCHEMA:")
            for col in columns:
                type_desc = col['data_type']
                if col['character_maximum_length']:
                    type_desc += f"({col['character_maximum_length']})"
                null_str = "NULL" if col['is_nullable'] == "YES" else "NOT NULL"
                output_lines.append(f"  - {col['column_name'].ljust(20)} | {type_desc.ljust(25)} | {null_str}")
            
            output_lines.append("\nDATA (First 5 Rows):")
            
            # 3. Get Data (limit 5)
            try:
                cur.execute(f"SELECT * FROM \"{table_name}\" LIMIT 5;")
                rows = cur.fetchall()
                if not rows:
                    output_lines.append("  (Table is empty)")
                else:
                    import json
                    for idx, row in enumerate(rows, 1):
                        # Convert datetime/uuid to string for easy json printing
                        safe_row = {k: str(v) if v is not None else None for k, v in row.items()}
                        output_lines.append(f"  Row {idx}: {json.dumps(safe_row, indent=2).replace(chr(10), chr(10)+'    ')}")
            except Exception as e:
                output_lines.append(f"  Error fetching data: {e}")
                conn.rollback() # reset transaction state
                
            output_lines.append("\n" + "="*60 + "\n")
        
        # Write to file
        output_text = "\n".join(output_lines)
        with open("db_architecture.txt", "w", encoding="utf-8") as f:
            f.write(output_text)
            
        print("[+] Inspection complete! Architecture and data saved to 'db_architecture.txt'")
        print("Here is a preview:\n")
        print("\n".join(output_lines[:50]))
        if len(output_lines) > 50:
            print("... (see db_architecture.txt for the rest)")
            
    except Exception as e:
        print(f"[-] Database Error: {e}")
    finally:
        if 'conn' in locals() and conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    inspect_database()
