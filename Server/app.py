"""
app.py — Main Flask API
Integrates Phases 1-6 into unified REST endpoints.
"""
import sys
import os
import json
import datetime

# Add the parent directory to sys.path so we can import from modules/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yt_dlp
# pyrefly: ignore [missing-import]
from static_ffmpeg import run
ffmpeg_path, _ = run.get_or_fetch_platform_executables_else_raise()
os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
# Load .env from the parent directory
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

# pyrefly: ignore [missing-import]
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

from modules.phase3_nlp.forensic_nlp import ForensicNLPEngine
from modules.phase5_network.graph import GraphEngine
from modules.phase1_transcription.transcription import TranscriptionEngine
from modules.phase6_fusion.risk_engine import TruthLensRiskEngine
from backend.gsheet_db import GoogleSheetsDB

# Explicitly define template/static folders since app.py is nested in Server/
app = Flask(__name__, template_folder="../templates", static_folder="../static")
CORS(app)

CATEGORIES = [
    "Politics",
    "Health",
    "Finance",
    "Technology"
]

# ─────────────────────────────────────────────
# MODULE INSTANCES (Unified Engines)
# ─────────────────────────────────────────────
nlp_engine = ForensicNLPEngine()
graph_engine = GraphEngine()
transcription_engine = TranscriptionEngine(model_size="base")
risk_engine = TruthLensRiskEngine()
gsheet_db = GoogleSheetsDB()


# pyrefly: ignore [missing-import]
from apscheduler.schedulers.background import BackgroundScheduler
import threading

# ── Global Predictive Intelligence Storage ────
RISK_HEATMAP = []
HEATMAP_LOCK = threading.Lock()

def scheduled_analysis():
    """
    Background task that runs every 5 minutes.
    1. Fetches trending videos.
    2. Analyzes each one through the full TruthLens pipeline.
    3. Calculates Virality Risk Scores.
    """
    global RISK_HEATMAP
    print("LOG: Starting scheduled viral analysis...")
    
    # Use internal logic to fetch trending
    try:
        trending_videos = []
        # Calculate date for exactly past 2 days
        two_days_ago = (datetime.datetime.now() - datetime.timedelta(days=2)).strftime('%Y%m%d')
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True, 
            'extract_flat': False, # Changed to False to get upload_date for filtering
            'skip_download': True,
            'playlistend': 15,     # Limit to 15 recent videos to keep it fast
            'daterange': yt_dlp.utils.DateRange(start=two_days_ago),
            'socket_timeout': 15
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"LOG: Searching for viral content since {two_days_ago} (Past 2 Days)...")
            try:
                import random
                now = datetime.datetime.now()
                current_month_start = f"{now.year}-{now.month:02d}-01"
                exclusions = "-entertainment -gaming -music -movie -song -vlog"
                date_filter = f"after:{current_month_start}"
                
                queries = ["breaking news today", "latest viral news this week", "recent trending updates"]
                search_query = f"{random.choice(queries)} {date_filter} {exclusions}"
                print(f"[*] Autopilot Trending Fetch: {search_query}")
                res = ydl.extract_info(f"ytsearch15:{search_query}", download=False)
            except Exception as e:
                print(f"LOG: Primary search failed: {e}. Falling back...")
                res = ydl.extract_info("ytsearch8:trending past 2 days", download=False)
                
            if 'entries' in res:
                trending_videos = res['entries']

        new_heatmap = []
        for v in trending_videos:
            if not isinstance(v, dict): continue
            vid = v.get("id")
            if not vid: continue
            
            # ── STRICT DATE FILTER ──────────────────────
            # Ensure the video was uploaded in the past 2 days
            upload_date = v.get("upload_date")
            if upload_date and upload_date < two_days_ago:
                print(f"LOG: Skipping old video from {upload_date}: {vid}")
                continue
            
            # ── SAFETY & VIRAL FILTER ──────────────────────
            # 1. Age Restriction Check (Block 18+)
            age_limit = v.get("age_limit", 0)
            if age_limit >= 18: 
                print(f"LOG: Skipping age-restricted content: {vid}")
                continue
                
            # 2. Minimum Reach Check
            views = int(v.get("view_count") or 0)
            if views < 5000: continue 
            
            try:
                title = v.get("title", "")
                likes = int(v.get("like_count") or 0)
                
                # Calculate engagement dynamics
                engagement_rate = (likes / views * 100) if views > 0 else 0
                
                # Full 6-phase analysis integration
                p2 = {}
                # Use a fast heuristic for background heatmap to prevent Ollama spam on Autopilot
                manip_words = ["shocking", "secret", "banned", "truth", "urgent", "share", "deleted", "exposed", "breaking"]
                fast_score = 0.8 if any(w in title.lower() for w in manip_words) else 0.2
                p3 = {
                    "manipulation_score": fast_score,
                    "trust_index": 100 - (fast_score * 100),
                    "risk_level": "HIGH" if fast_score > 0.7 else "LOW"
                }
                p5 = {}
                p6 = risk_engine.compute_final_verdict(yt_metadata=v, social_results=p2, nlp_results=p3, vision_results={}, graph_results=p5)
                
                trust_index = (1 - p6.get("composite_score", 0.5)) * 100
                verdict = p6.get("risk_level", "Unknown")
                
                # Predictive Virality Risk Score
                # Risk increases if: Trust is Low AND Engagement is High
                virality_factor = (views / 200000) + (engagement_rate / 2)
                risk_score = min(100, (100 - trust_index) * (1 + virality_factor))
                
                # Sector Identification
                sector = "General"
                combined_text = (title + " " + " ".join(v.get("tags", []))).lower()
                if any(x in combined_text for x in ["election", "policy", "government", "minister", "modi", "politics"]):
                    sector = "Politics"
                elif any(x in combined_text for x in ["doctor", "health", "vaccine", "covid", "cure"]):
                    sector = "Health"
                elif any(x in combined_text for x in ["finance", "crypto", "stock", "bank", "scam"]):
                    sector = "Finance"
                elif any(x in combined_text for x in ["tech", "ai", "software", "iphone", "tesla"]):
                    sector = "Technology"

                new_heatmap.append({
                    "video_id": vid,
                    "title": title,
                    "thumbnail": v.get("thumbnail") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                    "views": views,
                    "likes": likes,
                    "engagement_rate": round(engagement_rate, 2),
                    "trust_index": trust_index,
                    "risk_score": round(risk_score, 2),
                    "analysis": verdict,
                    "sector": sector,
                    "timestamp": datetime.datetime.now().isoformat()
                })
            except Exception as e:
                print(f"LOG: Analysis failed for {vid}: {e}")

        with HEATMAP_LOCK:
            # Sort by Risk Score (Descending) and keep top 40
            combined = new_heatmap + RISK_HEATMAP
            # Dedup by video_id
            seen = set()
            deduped = []
            for item in combined:
                if item['video_id'] not in seen:
                    deduped.append(item)
                    seen.add(item['video_id'])
            
            RISK_HEATMAP = sorted(deduped, key=lambda x: x['risk_score'], reverse=True)[:40]
            
        print(f"LOG: Scheduled analysis complete. {len(new_heatmap)} videos added to Heatmap.")
    except Exception as e:
        print(f"LOG: Global scheduled task error: {e}")

# Initialize and start the scheduler (DISABLED AS PER USER REQUEST)
# scheduler = BackgroundScheduler()
# scheduler.add_job(func=scheduled_analysis, trigger="interval", hours=5)
# scheduler.start()

# Start the first run in a thread so it doesn't block startup
# threading.Thread(target=scheduled_analysis, daemon=True).start()

# Helper Functions for Scoring & DB Caching Alignment
def calculate_virality_score(stats, nlp_result):
    views = stats.get("views", 0) if stats else 0
    likes = stats.get("likes", 0) if stats else 0
    if views > 0:
        return min(100.0, (views / 500000.0) * 50.0 + (likes / 50000.0) * 50.0)
    else:
        # Fallback to NLP virality multiplier
        multiplier = nlp_result.get("virality_multiplier", 1.0) if nlp_result else 1.0
        return min(100.0, multiplier * 50.0)

def construct_cached_pipeline_data(video_id, cached_row):
    try:
        from modules.phase6_fusion.trust_fusion import classify_risk
        
        trust_val = float(cached_row.get("trust_score", "0").replace("%", ""))
        virality_val = float(cached_row.get("virality_score", "0").replace("%", ""))
        manip_val = float(cached_row.get("manipulation_score", "0").replace("%", ""))
        
        claims_str = cached_row.get("evidence_summary", "[]")
        parsed_claims = json.loads(claims_str) if claims_str else []
        
        risk = classify_risk((100.0 - trust_val) / 100.0)
        
        red_flags_str = cached_row.get("red_flags", "")
        red_flags_list = [f.strip() for f in red_flags_str.split("|") if f.strip()] if red_flags_str else []
        
        stats = {
            "views": int(cached_row.get("views") or 0),
            "likes": int(cached_row.get("likes") or 0),
            "comments": int(cached_row.get("comments") or 0),
        }
        
        return {
            "trust_index": trust_val,
            "report": {
                "composite_score": (100.0 - trust_val) / 100.0,
                "risk_level": risk["label"],
                "risk_color": risk["color"],
                "risk_description": risk["description"],
                "confidence": 0.85,
                "red_flags": red_flags_list,
                "recommendation": risk["description"]
            },
            "phase_outputs": {
                "phase1_stats": stats,
                "phase3_nlp": {
                    "manipulation_score": manip_val / 100.0,
                    "virality_score": virality_val,
                    "claim_analysis": parsed_claims,
                    "red_flags": red_flags_list,
                    "transcript": cached_row.get("transcript", "")
                },
                "phase5_graph": {
                    "coordination_score": manip_val / 100.0,
                    "bot_suspects": [],
                    "suspicious_clusters": []
                }
            }
        }
    except Exception as e:
        print(f"Error constructing cached pipeline data: {e}")
        return None

# ═══════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/api/risk/heatmap", methods=["GET"])
def get_risk_heatmap():
    """
    Returns the live misinformation risk heatmap.
    """
    with HEATMAP_LOCK:
        return jsonify(RISK_HEATMAP)


# ── Phase 1 (YouTube) — existing endpoint ────
@app.route("/api/youtube/analyze", methods=["POST"])
def youtube_analyze():
    """
    Body: { "video_id": "dQw4w9WgXcQ" }
    Uses yt-dlp to fetch complete metadata.
    """
    body = request.get_json(force=True) or {}
    import re
    video_id = body.get("video_id", "").strip()
    if not video_id:
        return jsonify({"error": "video_id required"}), 400
        
    # If the user passed a full URL instead of an ID, extract the ID
    if len(video_id) > 11 and ("youtube.com" in video_id or "youtu.be" in video_id):
        match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", video_id)
        if match:
            video_id = match.group(1)
            
    # Handle the frontend's hardcoded "test" health-check ping gracefully
    if video_id == "test":
        return jsonify({"status": "online", "message": "API is reachable"}), 200
        
    if len(video_id) != 11:
        return jsonify({"error": f"Invalid YouTube video ID format: {video_id}. Must be 11 characters."}), 400


    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'no_warnings': True,
        'extract_flat': False,
        'socket_timeout': 15,
        'extractor_args': {'youtube': {'player_client': ['ios', 'android']}}
    }
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    try:
        # pyrefly: ignore [missing-import]
        from youtube_comment_downloader import YoutubeCommentDownloader
        downloader = YoutubeCommentDownloader()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Safety Check: Block 18+
            if info.get("age_limit", 0) >= 18:
                return jsonify({"error": "Content restricted: Adult content (18+) is blocked by TruthLens AI Safety Policy."}), 403

            # Format upload_date
            upload_date = info.get("upload_date", "")
            if len(upload_date) == 8:
                formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}T00:00:00Z"
            else:
                formatted_date = datetime.datetime.now().isoformat() + "Z"

            # Filter formats to get useful download links
            formats = []
            for f in info.get("formats", []):
                if f.get("vcodec") != "none" and f.get("acodec") != "none":
                    formats.append({
                        "format_id": f.get("format_id"),
                        "ext": f.get("ext"),
                        "resolution": f.get("resolution"),
                        "url": f.get("url")
                    })

            # Extract comments and prioritize those with #truthlens
            comments = []
            flagged_comments = []
            try:
                comment_iter = downloader.get_comments_from_url(url, sort_by=0) 
                count = 0
                for c in comment_iter:
                    text = c.get("text", "")
                    is_flagged = "#truthlens" in text.lower()
                    
                    comment_obj = {
                        "author": c.get("author"),
                        "text": text,
                        "likes": c.get("votes", 0),
                        "time": c.get("time"),
                        "flagged": is_flagged
                    }
                    
                    if is_flagged:
                        flagged_comments.append(comment_obj)
                    else:
                        comments.append(comment_obj)
                    
                    count += 1
                    if count >= 30: # Fetch more to find flags
                        break
                
                # Combine: Flagged ones first
                final_comments = flagged_comments + comments
                comments = final_comments[:20]
            except Exception as ce:
                print(f"Comment Downloader Error: {ce}")
            title = info.get("title", "")
            description = info.get("description", "") or ""
            
            response_data = {
                "video_id": video_id,
                "title": title,
                "description": description,
                "thumbnail": info.get("thumbnail"),
                "upload_date": formatted_date,
                "channel": info.get("uploader"),
                "tags": info.get("tags", []),
                "views": int(info.get("view_count") or 0),
                "likes": int(info.get("like_count") or 0),
                "comments": int(info.get("comment_count") or 0),
                "comments_list": comments,
                "has_community_flag": len(flagged_comments) > 0,
                "formats": formats[:10],
                "raw_metadata": info
            }
            
            # Check if we have final scores cached in DB
            cached_full_pipeline_data = None
            if gsheet_db:
                try:
                    cached_row = gsheet_db.get_youtube_row(video_id)
                    if cached_row and cached_row.get("trust_score") and "%" in cached_row.get("trust_score", ""):
                        cached_full_pipeline_data = construct_cached_pipeline_data(video_id, cached_row)
                except Exception as ce:
                    print(f"Error checking cache in youtube_analyze: {ce}")
            
            if cached_full_pipeline_data:
                response_data["misinformation_analysis"] = cached_full_pipeline_data["report"]
                response_data["misinformation_analysis"]["trust_index"] = cached_full_pipeline_data["trust_index"]
                response_data["misinformation_analysis"]["manipulation_score"] = cached_full_pipeline_data["phase_outputs"]["phase3_nlp"]["manipulation_score"]
                response_data["misinformation_analysis"]["evidence_confidence"] = 1.0 - cached_full_pipeline_data["phase_outputs"]["phase3_nlp"]["manipulation_score"]
                response_data["misinformation_analysis"]["claim_analysis"] = cached_full_pipeline_data["phase_outputs"]["phase3_nlp"]["claim_analysis"]
                response_data["cached_full_pipeline_data"] = cached_full_pipeline_data
            
            # Sync to Google Sheets if not already cached
            if not cached_full_pipeline_data and gsheet_db:
                try:
                    threading.Thread(target=gsheet_db.update_youtube_row, args=(video_id, {
                        "title": title,
                        "channel": response_data["channel"],
                        "views": response_data["views"],
                        "likes": response_data["likes"],
                        "comments": response_data["comments"],
                        "date": formatted_date,
                        "description": description,
                        "raw_metadata": info
                    })).start()
                except Exception as e:
                    print(f"Failed to start thread for gsheet: {e}")
                
            return jsonify(response_data)
    except Exception as e:
        import traceback
        print(f"ERROR in youtube_analyze: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@app.route("/api/youtube/transcript", methods=["POST"])
def youtube_transcript():
    """
    Body: { "url": "https://www.youtube.com/watch?v=XXXX" }
    """
    body = request.get_json(force=True) or {}
    url = body.get("url", "").strip()
    if not url:
        return jsonify({"error": "url required"}), 400
        
    print(f"[*] Transcribing: {url}")
    
    # Check cache first
    import re
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    if match:
        vid = match.group(1)
        if gsheet_db:
            try:
                db_row = gsheet_db.get_youtube_row(vid)
                if db_row and db_row.get("transcript") and db_row.get("transcript").strip():
                    print(f"[*] Found cached transcript in DB for {vid}")
                    return jsonify({
                        "text": db_row.get("transcript"),
                        "method": "Google Sheets Cache Lookup",
                        "language": "en",
                        "language_probability": 1.0,
                        "segments": [],
                        "is_cached": True
                    })
            except Exception as e:
                print(f"Error checking cached transcript: {e}")

    result = transcription_engine.process_youtube(url)
    
    if not result.get("error"):
        if match:
            vid = match.group(1)
            try:
                threading.Thread(target=gsheet_db.update_youtube_row, args=(vid, {
                    "transcript": result.get("text", "")
                })).start()
            except Exception as e:
                print(f"Failed to sync transcript to DB: {e}")
                
    return jsonify(result)

@app.route('/api/categories', methods=['GET'])
def get_categories():
    return jsonify(CATEGORIES)

@app.route("/api/youtube/trending", methods=["GET"])
def youtube_trending():
    category = request.args.get("category", "trending")
    exclude_ids = set(request.args.get("exclude", "").split(","))
    videos = []
    # Past 2 days date calculation (used for fallback tracking if needed)
    two_days_ago = (datetime.datetime.now() - datetime.timedelta(days=2)).strftime('%Y%m%d')
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'skip_download': True,
        'socket_timeout': 15
    }
    try:
        import random
        now = datetime.datetime.now()
        # Create dynamic date strings for current month and past week
        current_month_start = f"{now.year}-{now.month:02d}-01"
        seven_days_ago = (now - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Build search query with strict negative filters to block entertainment
        exclusions = "-entertainment -gaming -music -movie -song -vlog"
        date_filter = f"after:{current_month_start}"
        
        queries = ["global news viral trending today", "breaking news recent", "viral news this week", "latest trending topics today"]
        base_query = f"{category} today" if category != "trending" else random.choice(queries)
        
        search_query = f"{base_query} {date_filter} {exclusions}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"[*] YouTube Trending Fetch: {search_query}")
            res = ydl.extract_info(f"ytsearch40:{search_query}", download=False)
            if 'entries' in res:
                for entry in res['entries']:
                    if entry and entry.get("id"):
                        if entry.get("id") in exclude_ids: continue
                        
                        # Safety Check: Block Livestreams and long videos (>20 mins) to prevent Autopilot hangs
                        if entry.get("is_live") or entry.get("live_status") == "is_live": continue
                        duration = entry.get("duration") or 0
                        if duration > 1200: continue
                        
                        # Safety Check: Block 18+ and XXX
                        age_limit = entry.get("age_limit", 0)
                        title = entry.get("title", "").lower()
                        blocklist = ["xxx", "nsfw", "adult", "porn", "sexy", "hot girl", "nude"]
                        if age_limit >= 18 or any(x in title for x in blocklist): continue
                        videos.append({
                            "video_id": entry.get("id"),
                            "title": entry.get("title"),
                            "channel": entry.get("uploader") or entry.get("channel") or "Viral Monitor",
                            "views": int(entry.get("view_count") or 0),
                            "thumbnail": entry.get("thumbnail") or f"https://i.ytimg.com/vi/{entry.get('id')}/hqdefault.jpg",
                        })
                        if len(videos) >= 15: break
    except Exception as e:
        print(f"Trending Error: {e}")
    return jsonify(videos)

# ── Phase 3: NLP Analysis ─────────────────────
@app.route("/api/nlp/analyze", methods=["POST"])
def nlp_analyze():
    """
    Body: { "text": "..." }                     — single text
       OR { "posts": [{"author":..,"content":..}] }  — batch
    """
    body = request.get_json(force=True) or {}

    text = body.get("text", "")
    posts = body.get("posts", [])
    
    if posts and not text:
        # Concatenate posts for full spectrum analysis
        text = "\n".join([p.get("content", "") for p in posts])
        
    if not text:
        return jsonify({"error": "text or posts required"}), 400
        
    result = nlp_engine.analyze_full_spectrum(text)
    return jsonify(result)


# ── Phase 5: Graph Coordination ───────────────
@app.route("/api/graph/analyze", methods=["POST"])
def graph_analyze():
    return jsonify({"status": "disabled", "message": "Graph coordination endpoint is deactivated."})


# ── Phase 6: Full Trust Pipeline ──────────────
@app.route("/api/trust/full", methods=["POST"])
def trust_full():
    """
    Full pipeline: provide video_id (YouTube) + text content.
    Runs all phases and returns composite trust index.

    Body: {
        "video_id":   "...",         (optional)
        "image_url":  "...",         (optional)
        "text":       "...",         (required)
        "posts":      [...],         (optional, for coordination)
        "stats":      { views, likes, comments }   (optional override)
    }
    """
    body = request.get_json(force=True) or {}
    video_id = body.get("video_id")

    # Check cache first!
    if video_id and gsheet_db and not body.get("bypass_cache", False):
        try:
            cached_row = gsheet_db.get_youtube_row(video_id)
            if cached_row and cached_row.get("trust_score") and "%" in cached_row.get("trust_score", ""):
                cached_full_pipeline_data = construct_cached_pipeline_data(video_id, cached_row)
                if cached_full_pipeline_data:
                    return jsonify(cached_full_pipeline_data)
        except Exception as ce:
            print(f"Error loading cache in trust_full: {ce}")

    # Phase 1 stats
    stats = body.get("stats", {"views": 0, "likes": 0, "comments": 0})
    
    # If stats are empty/0, try fetching metadata stats from the DB
    if video_id and gsheet_db and (stats.get("views") == 0 or stats.get("likes") == 0):
        try:
            db_row = gsheet_db.get_youtube_row(video_id)
            if db_row and db_row.get("views"):
                stats = {
                    "views": int(db_row.get("views") or 0),
                    "likes": int(db_row.get("likes") or 0),
                    "comments": int(db_row.get("comments") or 0)
                }
        except Exception as ce:
            print(f"Error fetching stats from DB in trust_full: {ce}")

    # Phase 2 mock harvest
    harvest_result = {"sources": []}

    # Phase 3 NLP
    text = body.get("text", "")
    if video_id and not text and gsheet_db:
        try:
            db_row = gsheet_db.get_youtube_row(video_id)
            if db_row and db_row.get("transcript"):
                text = db_row.get("transcript")
        except Exception:
            pass

    if video_id and not text:
        # Run transcription live and save to DB
        url = f"https://www.youtube.com/watch?v={video_id}"
        trans_result = transcription_engine.process_youtube(url)
        text = trans_result.get("text", "")
        if gsheet_db and text:
            try:
                gsheet_db.update_youtube_row(video_id, {"transcript": text})
            except Exception:
                pass

    posts = body.get("posts", [])
    if text and not posts:
        posts = [{"author": "target", "content": text, "platform": "unknown"}]
        
    if posts and not text:
        text = "\n".join([p.get("content", "") for p in posts])
        
    nlp_result = nlp_engine.analyze_full_spectrum(text) if text else {}

    # Phase 5 Graph (Removed as requested)
    graph_result = {}

    # Compute verdict with actual stats
    yt_metadata_dict = {
        "view_count": stats.get("views", 0),
        "like_count": stats.get("likes", 0),
        "comment_count": stats.get("comments", 0)
    }

    report = risk_engine.compute_final_verdict(
        yt_metadata=yt_metadata_dict,
        social_results=harvest_result,
        nlp_results=nlp_result,
        vision_results={},
        graph_results=graph_result,
    )

    trust_index = 100 - (report.get("composite_score", 0) * 100)
    virality_score = calculate_virality_score(stats, nlp_result)
    manip_score = nlp_result.get("manipulation_score", 0) * 100

    if video_id:
        try:
            evidence_summary = json.dumps(nlp_result.get("claim_analysis", []), ensure_ascii=False)
            
            db_update = {
                "evidence_summary": evidence_summary,
                "trust_score": f"{trust_index:.1f}%",
                "virality_score": f"{virality_score:.1f}%",
                "manipulation_score": f"{manip_score:.1f}%",
                "red_flags": " | ".join(nlp_result.get("red_flags", []))
            }
            if text:
                db_update["transcript"] = text
            threading.Thread(target=gsheet_db.update_youtube_row, args=(video_id, db_update)).start()
        except Exception as e:
            print(f"Failed to sync NLP to DB: {e}")

    return jsonify({
        "trust_index": trust_index,
        "report": report,
        "phase_outputs": {
            "phase1_stats":   stats,
            "phase3_nlp":     {
                "manipulation_score": manip_score / 100.0,
                "virality_score": virality_score,
                "claim_analysis": nlp_result.get("claim_analysis", []),
                "red_flags": nlp_result.get("red_flags", []),
                "transcript": text
            },
            "phase5_graph":   graph_result,
        },
    })

# ─────────────────────────────────────────────
# CHROME EXTENSION ENDPOINT
# ─────────────────────────────────────────────
processing_videos = set()

@app.route("/api/extension/analyze", methods=["POST"])
def extension_analyze():
    """
    Dedicated endpoint for the Chrome/Brave Extension.
    Takes a URL, extracts ID, checks GSheetDB for a cached result.
    """
    body = request.get_json(force=True) or {}
    url = body.get("url", "")
    title = body.get("title", "Unknown Video (Extension)")
    
    import re
    video_id = ""
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    if match:
        video_id = match.group(1)
        
    if not video_id:
        return jsonify({"error": "Invalid YouTube URL"}), 400
        
    # Check cache first for instant extension demo!
    if gsheet_db:
        try:
            cached_row = gsheet_db.get_youtube_row(video_id)
            if cached_row and cached_row.get("trust_score") and "%" in cached_row.get("trust_score", ""):
                claims_data = cached_row.get("evidence_summary", "[]")
                if not claims_data or claims_data.strip() == "":
                    claims_data = "[]"
                
                parsed_claims = []
                try:
                    parsed_claims = json.loads(claims_data)
                except:
                    pass
                    
                return jsonify({
                    "trust_index": float(cached_row.get("trust_score", "0").replace("%", "")),
                    "virality_score": float(cached_row.get("virality_score", "0").replace("%", "")) / 100,
                    "manipulation_risk": float(cached_row.get("manipulation_score", "0").replace("%", "")) / 100,
                    "claims": parsed_claims
                })
        except Exception as e:
            print(f"Error parsing cached extension data: {e}")
                
    # If not in DB, RUN IT LIVE!
    global processing_videos
    if video_id in processing_videos:
        return jsonify({"error": "Video is already being analyzed in the background. Please wait a minute and try again!"}), 429
        
    print(f"[*] Extension triggered live analysis for: {video_id}")
    processing_videos.add(video_id)
    
    def run_live_analysis_bg(vid, vurl, vtitle):
        try:
            db_views = 0
            db_likes = 0
            db_comments = 0
            title_to_use = vtitle
            
            cached_row = gsheet_db.get_youtube_row(vid) if gsheet_db else None
            
            # 0. Load or initialize DB Row
            if cached_row and cached_row.get("views"):
                db_views = int(cached_row.get("views") or 0)
                db_likes = int(cached_row.get("likes") or 0)
                db_comments = int(cached_row.get("comments") or 0)
                if cached_row.get("title"):
                    title_to_use = cached_row.get("title")
            else:
                try:
                    ydl_opts = {
                        'quiet': True,
                        'skip_download': True,
                        'no_warnings': True,
                        'extract_flat': False,
                        'socket_timeout': 15,
                        'extractor_args': {'youtube': {'player_client': ['ios', 'android']}}
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(vurl, download=False)
                        db_views = int(info.get("view_count") or 0)
                        db_likes = int(info.get("like_count") or 0)
                        db_comments = int(info.get("comment_count") or 0)
                        title_to_use = info.get("title", vtitle)
                        
                        if gsheet_db:
                            gsheet_db.update_youtube_row(vid, {
                                "title": title_to_use,
                                "channel": info.get("uploader"),
                                "views": db_views,
                                "likes": db_likes,
                                "comments": db_comments,
                                "date": info.get("upload_date", ""),
                                "description": info.get("description", "")
                            })
                except Exception as e:
                    print(f"Extension live metadata fetch failed: {e}")
                    # Write placeholder immediately
                    if gsheet_db:
                        try:
                            import datetime
                            gsheet_db.update_youtube_row(vid, {
                                "title": vtitle,
                                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                                "trust_score": "Processing...",
                                "virality_score": "Processing...",
                                "manipulation_score": "Processing..."
                            })
                        except Exception: pass
            
            # 1. Transcript
            text = ""
            if cached_row and cached_row.get("transcript"):
                text = cached_row.get("transcript")
            
            if not text:
                trans_result = transcription_engine.process_youtube(vurl)
                text = trans_result.get("text", "")
                if not text:
                    print(f"[-] Extension Analysis Error: Failed to extract transcript.")
                    if vid in processing_videos: processing_videos.remove(vid)
                    return
                # Update DB with transcript instantly
                if gsheet_db:
                    try:
                        gsheet_db.update_youtube_row(vid, {"transcript": text})
                    except Exception: pass
            
            # 2. NLP
            nlp_result = nlp_engine.analyze_full_spectrum(text)
            evidence_summary = json.dumps(nlp_result.get("claim_analysis", []), ensure_ascii=False)
            
            # 3. Fusion
            report = risk_engine.compute_final_verdict(
                yt_metadata={
                    "view_count": db_views,
                    "like_count": db_likes,
                    "comment_count": db_comments
                },
                social_results={"sources": []}, 
                nlp_results=nlp_result, 
                vision_results={}, 
                graph_results={}
            )
            
            trust_index = 100 - (report.get("composite_score", 0) * 100)
            virality_score = calculate_virality_score({"views": db_views, "likes": db_likes}, nlp_result)
            manip_score = nlp_result.get("manipulation_score", 0) * 100
            
            # 4. Save to DB
            if gsheet_db:
                try:
                    gsheet_db.update_youtube_row(vid, {
                        "evidence_summary": evidence_summary,
                        "trust_score": f"{trust_index:.1f}%",
                        "virality_score": f"{virality_score:.1f}%",
                        "manipulation_score": f"{manip_score:.1f}%",
                        "red_flags": " | ".join(nlp_result.get("red_flags", []))
                    })
                except Exception as e:
                    print(f"Failed to sync final extension run to DB: {e}")
                    
        except Exception as e:
            print(f"[-] Extension Analysis Error: {e}")
            if gsheet_db:
                try:
                    gsheet_db.update_youtube_row(vid, {"trust_score": "Error"})
                except: pass
        finally:
            # Always clean up the lock
            if vid in processing_videos:
                processing_videos.remove(vid)
            print(f"[*] Live analysis complete for {vid}")

    # Start the background thread
    import threading
    threading.Thread(target=run_live_analysis_bg, args=(video_id, url, title)).start()
    
    # Immediately return a status to the extension so it doesn't hang
    return jsonify({"status": "processing", "message": "Analysis started in background"}), 202

# ─────────────────────────────────────────────
# AUTOPILOT ENDPOINTS
# ─────────────────────────────────────────────
@app.route('/api/autopilot/status', methods=['GET'])
def get_autopilot_status():
    status_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "autopilot_status.json")
    if os.path.exists(status_file):
        try:
            with open(status_file, "r") as f:
                return jsonify(json.load(f))
        except:
            pass
    return jsonify({"step": 0, "message": "Autopilot Daemon Offline or Sleeping", "active": False, "data": {}})

@app.route('/api/autopilot/force_start', methods=['POST'])
def force_start_autopilot():
    trigger_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "autopilot_trigger.txt")
    print(f"[*] API Force Start Request Received. Writing trigger file: {trigger_file}")
    try:
        os.makedirs(os.path.dirname(trigger_file), exist_ok=True)
        with open(trigger_file, "w") as f:
            f.write("KICK_START")
        print("[*] Trigger file successfully written.")
        return jsonify({"success": True, "message": "Daemon kicked"})
    except Exception as e:
        print(f"[-] Error writing trigger file: {e}")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
if __name__ == "__main__":
    import logging
    log = logging.getLogger('werkzeug')
    class StatusFilter(logging.Filter):
        def filter(self, record):
            return '/api/autopilot/status' not in record.getMessage()
    log.addFilter(StatusFilter())

    app.run(debug=True, port=5001)
