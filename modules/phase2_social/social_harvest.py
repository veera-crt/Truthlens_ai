"""
PHASE 2: Cross-Platform Data Harvesting (Open Source Tools)
Supports: YouTube (yt-dlp), Instagram (Instaloader), X/Twitter (snscrape)
Designed for: Unified Intelligence Queue & TruthLens Narrative Analysis
"""

import os
import time
import json
from datetime import datetime, timedelta
import instaloader
try:
    import snscrape.modules.twitter as sntwitter
except Exception as e:
    sntwitter = None
    print(f"[!] Warning: snscrape could not be imported (incompatible with Python 3.12+). Twitter scraping fallback will be active. Error: {e}")
import yt_dlp


# ─────────────────────────────────────────────
# INSTAGRAM HARVESTER (via Instaloader)
# ─────────────────────────────────────────────
class InstagramIntelligence:
    """
    Fetches Instagram metadata, reels, captions, and comments
    using the Instaloader open-source library.
    """
    def __init__(self):
        self.L = instaloader.Instaloader()
        # To avoid rate limits, we use a generic session if available
        username = os.getenv("INSTAGRAM_USERNAME")
        if username:
            try:
                self.L.load_session_from_file(username)
                print(f"[*] Loaded Instagram session for {username}")
            except Exception as e:
                print(f"[!] Could not load Instagram session for {username}: {e}")

    def get_post_intelligence(self, shortcode: str):
        """Analyze a specific Instagram post/reel by shortcode."""
        try:
            post = instaloader.Post.from_shortcode(self.L.context, shortcode)
            
            # Try to get comments (may be limited by auth)
            comments = []
            try:
                for c in post.get_comments():
                    comments.append({
                        "author": c.owner.username,
                        "text": c.text,
                        "likes": c.likes_count,
                        "time": c.created_at_utc.isoformat(),
                        "flagged": "#truthlens" in c.text.lower()
                    })
                    if len(comments) >= 15: break
            except:
                pass
                
            post_data = {
                "platform": "instagram",
                "id": post.shortcode,
                "author": post.owner_username,
                "caption": post.caption,
                "likes": post.likes,
                "comments_count": post.comments,
                "timestamp": post.date_utc.isoformat(),
                "is_video": post.is_video,
                "video_url": post.video_url if post.is_video else None,
                "thumbnail": post.url,
                "url": f"https://www.instagram.com/p/{post.shortcode}/",
                "hashtags": post.caption_hashtags,
                "comments_list": comments
            }
            return post_data
        except Exception as e:
            return {"error": str(e)}

    def get_profile_intelligence(self, username: str, post_limit: int = 5):
        """Monitor specific influential accounts for narrative propagation."""
        try:
            profile = instaloader.Profile.from_username(self.L.context, username)
            results = []
            
            for post in profile.get_posts():
                if len(results) >= post_limit:
                    break
                
                post_data = {
                    "platform": "instagram",
                    "id": post.shortcode,
                    "author": username,
                    "caption": post.caption,
                    "likes": post.likes,
                    "comments_count": post.comments,
                    "timestamp": post.date_utc.isoformat(),
                    "is_video": post.is_video,
                    "url": f"https://www.instagram.com/p/{post.shortcode}/",
                    "hashtags": post.caption_hashtags
                }
                results.append(post_data)
                
            return {"status": "success", "data": results}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_hashtag_intelligence(self, hashtag: str, limit: int = 10):
        """Track hashtags to identify coordinated misinformation campaigns."""
        try:
            posts = instaloader.Hashtag.from_name(self.L.context, hashtag).get_posts()
            results = []
            
            for post in posts:
                if len(results) >= limit:
                    break
                
                results.append({
                    "platform": "instagram",
                    "id": post.shortcode,
                    "caption": post.caption,
                    "timestamp": post.date_utc.isoformat(),
                    "url": f"https://www.instagram.com/p/{post.shortcode}/"
                })
            return {"status": "success", "data": results}
        except Exception as e:
            return {"status": "error", "message": str(e)}

# ─────────────────────────────────────────────
# X (TWITTER) HARVESTER (via snscrape)
# ─────────────────────────────────────────────
class XIntelligence:
    """
    Tracks narratives, hashtags, and breaking trends on X.
    NOTE: snscrape is currently limited by X's technical changes.
    """
    def get_narrative_stream(self, query: str, limit: int = 20):
        """Search for specific keywords/narratives across X."""
        if sntwitter is None:
            return {"status": "error", "message": "X Scraping is disabled because snscrape is incompatible with Python 3.12+."}
        try:
            results = []
            # snscrape.modules.twitter.TwitterSearchScraper
            scraper = sntwitter.TwitterSearchScraper(query)
            
            for i, tweet in enumerate(scraper.get_items()):
                if i >= limit:
                    break
                
                results.append({
                    "platform": "x",
                    "id": tweet.id,
                    "content": tweet.rawContent,
                    "author": tweet.user.username,
                    "timestamp": tweet.date.isoformat(),
                    "likes": tweet.likeCount,
                    "retweets": tweet.retweetCount,
                    "url": tweet.url
                })
            
            return {"status": "success", "data": results}
        except Exception as e:
            # Fallback/Error reporting for hackathon visibility
            return {"status": "error", "message": f"X Scraping Error: {str(e)}"}


# ─────────────────────────────────────────────
# YOUTUBE HARVESTER (via yt-dlp)
# ─────────────────────────────────────────────
class YouTubeIntelligence:
    """
    Unified YouTube monitoring for transcripts and metadata.
    """
    def get_video_metadata(self, url: str):
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'best',
            'skip_download': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    "platform": "youtube",
                    "id": info.get('id'),
                    "title": info.get('title'),
                    "description": info.get('description'),
                    "view_count": info.get('view_count'),
                    "timestamp": info.get('upload_date'),
                    "author": info.get('uploader')
                }
        except Exception as e:
            return {"error": str(e)}

# ─────────────────────────────────────────────
# UNIFIED INTELLIGENCE QUEUE
# ─────────────────────────────────────────────
class TruthLensMiddleware:
    """
    The orchestrator for the Phase 2 multi-stream pipeline.
    """
    def __init__(self):
        self.instagram = InstagramIntelligence()
        self.x = XIntelligence()
        self.youtube = YouTubeIntelligence()

    def sync_intelligence_queue(self, topic: str):
        """
        Gathers intelligence from all 3 platforms for a specific narrative topic.
        """
        print(f"[TruthLens] Syncing Intelligence for topic: {topic}...")
        
        # 1. YouTube Intelligence
        # Using a search query to find related videos, dynamically filtered to the current month & year
        now = datetime.now()
        start_of_month = f"{now.year}-{now.month:02d}-01"
        yt_search_query = f"ytsearch40:{topic} news after:{start_of_month}"
        
        yt_results = []
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl:
                res = ydl.extract_info(yt_search_query, download=False)
                if 'entries' in res:
                    for entry in res['entries']:
                        yt_results.append({
                            "platform": "youtube",
                            "id": entry.get("id"),
                            "title": entry.get("title"),
                            "url": f"https://www.youtube.com/watch?v={entry.get('id')}"
                        })
        except Exception as e:
            print(f"YouTube Sync Error: {e}")
        
        # 2. Instagram Intelligence
        ig_results = self.instagram.get_hashtag_intelligence(topic.replace(" ", ""), limit=15)
        
        # 3. X/Twitter Intelligence
        x_results = self.x.get_narrative_stream(topic, limit=20)
        
        unified_queue = {
            "topic": topic,
            "timestamp": datetime.now().isoformat(),
            "streams": {
                "youtube": yt_results,
                "instagram": ig_results.get("data", []),
                "x": x_results.get("data", [])
            },
            "status": "synchronized"
        }
        
        # In a real app, this would push to a Redis/DB queue
        return unified_queue

if __name__ == "__main__":
    # Quick Test Loop
    middleware = TruthLensMiddleware()
    sample_intelligence = middleware.sync_intelligence_queue("AI Misinformation")
    print(json.dumps(sample_intelligence, indent=2))
