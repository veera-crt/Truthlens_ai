import os
import json
import time
import requests

STATUS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "autopilot_status.json")

def update_status(step, message, active=True, data=None):
    status = {
        "step": step,
        "message": message,
        "active": active,
        "data": data or {},
        "timestamp": time.time()
    }
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f)
    print(f"[{time.strftime('%H:%M:%S')}] [AUTOPILOT] Step {step}: {message}")

def run_pipeline():
    try:
        base_url = "http://127.0.0.1:5001"
        
        # Step 1: Fetch Trending Video
        update_status(1, "Connecting to backend and fetching trending videos...")
        time.sleep(2) # Visual delay for UI
        
        # Gracefully handle backend startup delay
        max_retries = 8
        res = None
        for attempt in range(max_retries):
            try:
                res = requests.get(f"{base_url}/api/youtube/trending?category=trending", timeout=30)
                break
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries - 1:
                    print(f"[*] Flask backend is still starting up (port 5001 connection refused). Retrying in 5 seconds... ({attempt + 1}/{max_retries})")
                    time.sleep(5)
                else:
                    raise Exception(f"Could not connect to Flask backend at {base_url} after multiple attempts: {e}")
        
        if not res or not res.ok: raise Exception("Failed to fetch trending videos from backend")
        
        videos = res.json()
        if not videos: raise Exception("No trending videos found")
        
        top_video = videos[0]
        video_id = top_video.get("video_id")
        if not video_id: raise Exception("Trending video object is missing 'video_id' key")
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        update_status(1, f"Found trending video: {top_video.get('title')}", data={"video_id": video_id, "title": top_video.get('title')})
        time.sleep(3)
        
        # Step 2: Acquire Metadata
        update_status(2, f"Extracting deep metadata for {video_id}...", data={"video_id": video_id, "title": top_video.get('title')})
        res = requests.post(f"{base_url}/api/youtube/analyze", json={"video_id": video_id}, timeout=60)
        if not res.ok: raise Exception("Metadata extraction failed")
        time.sleep(3)
        
        # Step 3: Transcription
        update_status(3, "Downloading & transcribing audio/visual streams...", data={"video_id": video_id, "title": top_video.get('title')})
        res = requests.post(f"{base_url}/api/youtube/transcript", json={"url": video_url}, timeout=120)
        if not res.ok: raise Exception("Transcription failed")
        
        transcript_data = res.json()
        text = transcript_data.get("text", "")
        if not text: raise Exception("Transcript returned empty text")
        time.sleep(3)
        
        # Step 4: NLP Engine & Trust
        update_status(4, "Running TruthLens NLP & Graph Intelligence...", data={"video_id": video_id, "title": top_video.get('title')})
        res = requests.post(f"{base_url}/api/trust/full", json={"video_id": video_id, "text": text}, timeout=120)
        if not res.ok: raise Exception("NLP Trust analysis failed")
        time.sleep(3)
        
        # Step 5: Complete
        update_status(5, "Database Synchronized. Autopilot Cycle Complete!", active=False, data={"video_id": video_id, "title": top_video.get('title')})
        return True
        
    except Exception as e:
        update_status(-1, f"Autopilot Error: {str(e)}", active=False)
        return False

if __name__ == "__main__":
    print("=======================================")
    print("   TRUTHLENS AUTOPILOT DAEMON ACTIVATED  ")
    print("=======================================")
    while True:
        print("\n[*] Starting new Autopilot sequence...")
        update_status(0, "Initializing Autopilot Sequence...", active=True)
        time.sleep(2) # Small 2 sec sleep before starting as requested
        success = run_pipeline()
        
        trigger_path = os.path.join(os.path.dirname(STATUS_FILE), "autopilot_trigger.txt")
        if success:
            print("[*] Cycle complete. Sleeping for 6 hours before fetching next video...")
            update_status(0, "Sleeping for 6 hours before next cycle...", active=False)
            sleep_seconds = 6 * 3600
        else:
            print("[!] Cycle failed with error. Waiting for manual kick-start or retrying in 5 minutes...")
            # Do NOT overwrite the status file so that the error banner persists on the dashboard!
            sleep_seconds = 300
            
        waited = 0
        while waited < sleep_seconds:
            if os.path.exists(trigger_path):
                try:
                    os.remove(trigger_path)
                except Exception as del_err:
                    print(f"[-] Error removing trigger file: {del_err}")
                print("\n[*] Manual Kick-Start Received! Waking up early...")
                break
            time.sleep(2)
            waited += 2
