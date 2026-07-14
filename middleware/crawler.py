import yt_dlp
import datetime
import time
from phase2_social import TruthLensMiddleware

CATEGORIES = [
    "News", "Politics", "AI", "Technology",
    "Health", "Crypto", "Military", "Space", "Religion", "Education",
    "Finance", "Disaster coverage", "Election content", "Celebrity content"
]

class CategoryIntelligence:
    def __init__(self, db_session=None):
        self.db = db_session
        self.social = TruthLensMiddleware()
        self.ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'skip_download': True,
            'daterange': yt_dlp.utils.DateRange(
                start=(datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y%m%d')
            )
        }

    def crawl_all(self):
        """
        Iterates through all categories and identifies high-acceleration content 
        across YouTube, Instagram, and X.
        """
        results = []
        for cat in CATEGORIES:
            print(f"[*] Multi-Stream Crawling Category: {cat}")
            
            # 1. YouTube Intelligence
            yt_videos = self.fetch_youtube_category(cat)
            
            # 2. Social Intelligence (Instagram + X)
            social_intelligence = self.social.sync_intelligence_queue(cat)
            
            combined_entry = {
                "category": cat,
                "timestamp": datetime.datetime.now().isoformat(),
                "youtube": yt_videos,
                "social": social_intelligence.get("streams", {})
            }
            
            results.append(combined_entry)
            # Sleep to avoid rate limits
            time.sleep(1)
        return results

    def fetch_youtube_category(self, category_name):
        query = f"ytsearch10:{category_name} trending news viral"
        vids = []
        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            try:
                res = ydl.extract_info(query, download=False)
                if 'entries' in res:
                    for entry in res['entries']:
                        if not entry: continue
                        
                        # ── STRICT SAFETY FILTER ──────────────────────
                        age_limit = entry.get("age_limit", 0)
                        if age_limit >= 18: continue
                        
                        title = entry.get("title", "").lower()
                        blocklist = ["xxx", "nsfw", "adult", "porn", "sexy", "hot girl", "nude"]
                        if any(x in title for x in blocklist):
                            continue

                        views = int(entry.get("view_count") or 0)
                        if views < 5000: continue
                            
                        vids.append({
                            "id": entry.get("id"),
                            "title": entry.get("title"),
                            "views": views,
                            "category": category_name,
                            "velocity": self.calculate_velocity(entry)
                        })
            except Exception as e:
                print(f"[!] Error fetching YouTube {category_name}: {e}")
        return vids

    def calculate_velocity(self, entry):
        return 1.0 
