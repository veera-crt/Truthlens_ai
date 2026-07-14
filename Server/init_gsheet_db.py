# pyrefly: ignore [missing-import]
import gspread
import os
import json
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

def init_db():
    # Explicitly find .env from parent directory since this script is now in Server/
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(dotenv_path)
    
    creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        print(f"❌ GOOGLE_SERVICE_ACCOUNT_JSON not found in {dotenv_path}")
        return
        
    creds_dict = json.loads(creds_json)
    sheet_id = "1tj5UY_z3pHxdFobRo971ZIl-pA_eDezmUBY7RWVTTbM"
    
    print(f"🔄 Connecting to Google Sheets using service account from .env...")
    gc = gspread.service_account_from_dict(creds_dict)
    sheet = gc.open_by_key(sheet_id)
    
    # Define required sheets and their headers (Primary IDs first)
    required_sheets = {
        "YouTube": ["video_id", "title", "channel", "views", "likes", "comments", "date", "description", "raw_metadata", "transcript", "evidence_summary", "trust_score", "virality_score", "manipulation_score", "red_flags"],
        "Instagram": ["post_id", "author", "content", "likes", "comments", "trust_index", "risk_level", "timestamp", "post_url"],
        "Twitter": ["tweet_id", "author", "content", "retweets", "likes", "trust_index", "risk_level", "timestamp", "tweet_url"]
    }
    
    print(f"✅ Connected to sheet: '{sheet.title}'")
    
    for name, columns in required_sheets.items():
        try:
            ws = sheet.worksheet(name)
            print(f"✅ Worksheet '{name}' already exists. Forcing header update to new schema...")
            # Ensure headers exist and are updated
            ws.clear() # Clear everything to ensure a fresh start as requested
            ws.insert_row(columns, 1)
        except gspread.exceptions.WorksheetNotFound:
            print(f"➕ Creating worksheet '{name}'...")
            ws = sheet.add_worksheet(title=name, rows="1000", cols=str(max(10, len(columns))))
            ws.append_row(columns)
            
            # Make the header bold and dark
            ws.format('A1:J1', {
                "backgroundColor": {"red": 0.1, "green": 0.1, "blue": 0.1},
                "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}, "bold": True}
            })
            print(f"✅ Created '{name}' and added headers.")
            
    # Optionally delete default "Sheet1" if it's empty to keep the DB clean
    try:
        sheet1 = sheet.worksheet("Sheet1")
        if len(sheet.worksheets()) > 1:
            sheet.del_worksheet(sheet1)
            print("🗑️ Cleaned up default 'Sheet1'.")
    except Exception:
        pass
        
    print("🎉 Google Sheet Database Initialization Complete!")

if __name__ == "__main__":
    init_db()
