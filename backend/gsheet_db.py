import os
import json
# pyrefly: ignore [missing-import]
import gspread
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

class GoogleSheetsDB:
    def __init__(self):
        load_dotenv()
        creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        self.sheet_id = "1tj5UY_z3pHxdFobRo971ZIl-pA_eDezmUBY7RWVTTbM"
        self.gc = None
        self.sheet = None
        self.yt_ws = None
        self.yt_headers = []
        
        if not creds_json:
            print("❌ GOOGLE_SERVICE_ACCOUNT_JSON not found. GSheetDB disabled.")
            return
            
        try:
            creds_dict = json.loads(creds_json)
            self.gc = gspread.service_account_from_dict(creds_dict)
            self.sheet = self.gc.open_by_key(self.sheet_id)
            self.yt_ws = self.sheet.worksheet("YouTube")
            self.yt_headers = self.yt_ws.row_values(1)
            print(f"✅ GSheetDB Connected. YouTube Headers: {len(self.yt_headers)}")
        except Exception as e:
            print(f"❌ Failed to connect to Google Sheets: {e}")
            self.gc = None

    def _get_col_letter(self, col_idx):
        """Convert 1-indexed column number to letter (e.g. 1 -> A, 27 -> AA)"""
        string = ""
        while col_idx > 0:
            col_idx, remainder = divmod(col_idx - 1, 26)
            string = chr(65 + remainder) + string
        return string

    def _get_row_index(self, video_id):
        # Column 1 is video_id
        try:
            video_ids = self.yt_ws.col_values(1)
            return video_ids.index(video_id) + 1
        except ValueError:
            return None
        except Exception as e:
            print(f"GSheetDB Error getting row: {e}")
            return None

    def update_youtube_row(self, video_id, data_dict):
        """
        data_dict: {"title": "...", "transcript": "...", etc}
        Keys must match the header names in the Google Sheet.
        """
        if not self.gc or not self.yt_ws:
            return
            
        try:
            # Dynamically refresh headers to prevent caching issues when columns are added
            self.yt_headers = self.yt_ws.row_values(1)

            row_idx = self._get_row_index(video_id)
            
            # Stringify all dict items and enforce Google Sheets 50,000 character limit per cell
            safe_data = {}
            for k, v in data_dict.items():
                if isinstance(v, (dict, list)):
                    string_val = json.dumps(v, ensure_ascii=False)
                else:
                    string_val = str(v) if v is not None else ""
                
                # Truncate if exceeds safe limit (leaving room for the truncation notice)
                if len(string_val) > 49000:
                    string_val = string_val[:49000] + "... [TRUNCATED DUE TO GOOGLE SHEETS 50K CHAR LIMIT]"
                
                safe_data[k] = string_val
                    
            if not row_idx:
                # Create new row
                row_data = [""] * len(self.yt_headers)
                row_data[0] = video_id
                for k, v in safe_data.items():
                    if k in self.yt_headers:
                        row_data[self.yt_headers.index(k)] = v
                self.yt_ws.append_row(row_data)
                print(f"📊 Added new row to Google Sheets for video: {video_id}")
            else:
                # Fetch existing row
                row_data = self.yt_ws.row_values(row_idx)
                # Pad if row is short
                row_data += [""] * (len(self.yt_headers) - len(row_data))
                
                # Update values
                updated = False
                for k, v in safe_data.items():
                    if k in self.yt_headers:
                        col_idx = self.yt_headers.index(k)
                        if row_data[col_idx] != v:
                            row_data[col_idx] = v
                            updated = True
                
                if updated:
                    # Update row in one API call
                    end_col = self._get_col_letter(len(self.yt_headers))
                    cell_range = f"A{row_idx}:{end_col}{row_idx}"
                    self.yt_ws.update(values=[row_data], range_name=cell_range)
                    print(f"📊 Updated existing row in Google Sheets for video: {video_id}")
        except Exception as e:
            print(f"❌ GSheetDB Update Error: {e}")

    def get_youtube_row(self, video_id):
        if not self.gc or not self.yt_ws:
            return None
        try:
            row_idx = self._get_row_index(video_id)
            if not row_idx:
                return None
            row_data = self.yt_ws.row_values(row_idx)
            # Map back to dict using headers
            result = {}
            for i, val in enumerate(row_data):
                if i < len(self.yt_headers):
                    result[self.yt_headers[i]] = val
            return result
        except Exception as e:
            print(f"❌ GSheetDB Get Error: {e}")
            return None
