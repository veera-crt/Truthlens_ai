import os
import re
import sys
import json
import shutil
from pathlib import Path
import yt_dlp

try:
    # pyrefly: ignore [missing-import]
    from youtube_transcript_api import YouTubeTranscriptApi
    HAS_YTA = True
except ImportError:
    HAS_YTA = False

# Add video-analyzer-main to path so we can import its modules
# Calculate project root from this file's location (.../modules/phase1_transcription/transcription.py -> root)
_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(_root_dir, "video-analyzer-main"))
# pyrefly: ignore [missing-import]
from video_analyzer.audio_processor import AudioProcessor
# pyrefly: ignore [missing-import]
from video_analyzer.config import Config
# pyrefly: ignore [missing-import]
from video_analyzer.frame import VideoProcessor
# pyrefly: ignore [missing-import]
from video_analyzer.prompt import PromptLoader
# pyrefly: ignore [missing-import]
from video_analyzer.analyzer import VideoAnalyzer
# pyrefly: ignore [missing-import]
from video_analyzer.clients.ollama import OllamaClient

class TranscriptionEngine:
    def __init__(self, model_size="base"):
        print(f"[*] Initializing TruthLens Deep Transcription Engine (Audio + Visual Fallback)...")
        self.model_size = model_size
        self.temp_dir = Path("temp_audio")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # We initialize AudioProcessor from video-analyzer-main
        self.audio_processor = AudioProcessor(model_size_or_path=self.model_size)

    def get_video_id(self, url):
        """Extracts video ID from various YouTube URL formats using robust regex."""
        match = re.search(r"(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]{11})", url)
        return match.group(1) if match else "video"

    def download_audio(self, url, video_id):
        """Downloads ONLY the audio using yt-dlp to save bandwidth/time."""
        output_path = self.temp_dir / f"{video_id}.mp3"
        if output_path.exists() and output_path.stat().st_size > 1000:
            print(f"[*] Found cached Deep Audio for {video_id}. Skipping yt-dlp download!")
            return output_path
            
        print(f"[*] Downloading Deep Audio for {video_id}...")
        
        # pyrefly: ignore [missing-import]
        from static_ffmpeg import run
        ffmpeg_path, _ = run.get_or_fetch_platform_executables_else_raise()
        ffmpeg_dir = os.path.dirname(ffmpeg_path)
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'ffmpeg_location': ffmpeg_dir,
            'outtmpl': str(self.temp_dir / f"{video_id}.%(ext)s"),
            'quiet': True,
            'source_address': '0.0.0.0', 
            'nocheckcertificate': True,
            'noplaylist': True,
            'nopart': True, # Disable .part files to prevent rename race condition errors
            'overwrites': True, # Always overwrite to prevent HTTP 416 errors
            'continuedl': False, # Never try to resume to prevent HTTP 416 errors
            'extractor_args': {'youtube': {'player_client': ['ios', 'android']}}
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        return output_path

    def download_video(self, url, video_id):
        """Downloads the full MP4 video for visual frame analysis."""
        output_path = self.temp_dir / f"{video_id}.mp4"
        if output_path.exists() and output_path.stat().st_size > 1000:
            print(f"[*] Found cached Full Video for {video_id}. Skipping yt-dlp download!")
            return output_path
            
        print(f"[*] Downloading Full Video for {video_id} (Visual Analysis Fallback)...")
        
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4/best',
            'outtmpl': str(self.temp_dir / f"{video_id}.%(ext)s"),
            'quiet': True,
            'nocheckcertificate': True,
            'noplaylist': True,
            'extractor_args': {'youtube': {'player_client': ['ios', 'android']}}
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        return output_path

    def analyze_video_frames(self, video_path, transcript_text=None, url=None):
        """Runs the video-analyzer-main pipeline using OpenRouter, falling back to local Ollama."""
        print(f"[*] Running Deep Visual Frame Analysis using OpenRouter (fallback to local Ollama if needed)...")
        
        # Determine video_id from video_path filename for concurrent safety
        video_id = Path(video_path).stem
        output_dir = self.temp_dir / "frames_out" / video_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Fetch YouTube Metadata & Comments for context
        video_title = "Unknown Title"
        video_description_meta = "No description available."
        comments_list = []
        
        if url:
            try:
                print(f"[*] Fetching YouTube metadata for fallback context from {url}...")
                ydl_opts = {
                    'quiet': True,
                    'skip_download': True,
                    'no_warnings': True,
                    'extract_flat': False,
                    'socket_timeout': 10,
                    'extractor_args': {'youtube': {'player_client': ['ios', 'android']}}
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    video_title = info.get("title", "Unknown Title")
                    video_description_meta = info.get("description", "No description available.")
                    if video_description_meta:
                        video_description_meta = video_description_meta[:1000]
            except Exception as meta_err:
                print(f"[-] Failed to fetch YouTube metadata: {meta_err}")
                
            try:
                print("[*] Fetching top comments for fallback context...")
                # pyrefly: ignore [missing-import]
                from youtube_comment_downloader import YoutubeCommentDownloader
                downloader = YoutubeCommentDownloader()
                comment_iter = downloader.get_comments_from_url(url, sort_by=0)
                count = 0
                for c in comment_iter:
                    text = c.get("text", "")
                    if text:
                        comments_list.append(text)
                        count += 1
                        if count >= 10:  # Get top 10 comments
                            break
            except Exception as comm_err:
                print(f"[-] Failed to fetch comments: {comm_err}")

        # Construct a rich metadata block to help the vision model synthesize the context
        metadata_text = f"YOUTUBE VIDEO CONTEXT (Use this to understand the event, title, location, and claims):\n" \
                        f"Video Title: {video_title}\n" \
                        f"Video Description: {video_description_meta}\n"
        if comments_list:
            comments_str = "\n".join([f"- {c}" for c in comments_list])
            metadata_text += f"Top User Comments:\n{comments_str}\n"
        if transcript_text:
            metadata_text += f"\nWhisper Audio Transcript (highly unreliable/noisy):\n{transcript_text}\n"

        # 2. Extract keyframes from the video
        v_main = os.path.join(_root_dir, "video-analyzer-main")
        config = Config(os.path.join(v_main, "video_analyzer/config"))
        prompt_loader = PromptLoader(
            config.get("prompt_dir", os.path.join(v_main, "video_analyzer/prompts")),
            config.get("prompts", [])
        )
        
        processor = VideoProcessor(video_path, output_dir, "llama3.2-vision")
        # Extract keyframes dynamically based on video length
        frames = processor.extract_keyframes(frames_per_minute=15)
        
        video_description = None
        
        # 3. Try OpenRouter First
        try:
            print("[*] Attempting Visual Frame Analysis using OpenRouter (llama-3.2-11b-vision-instruct)...")
            # pyrefly: ignore [missing-import]
            from video_analyzer.clients.generic_openai_api import GenericOpenAIAPIClient
            
            client = GenericOpenAIAPIClient(
                api_key=os.getenv("OPENROUTER_API_KEY", ""),
                api_url="https://openrouter.ai/api/v1"
            )
            model = "meta-llama/llama-3.2-11b-vision-instruct"
            
            analyzer = VideoAnalyzer(client, model, prompt_loader, temperature=0.2)
            frame_analyses = []
            for frame in frames:
                analysis = analyzer.analyze_frame(frame)
                frame_analyses.append(analysis)
                
            class DummyTranscript:
                def __init__(self, text):
                    self.text = text
            
            dummy_transcript = DummyTranscript(metadata_text)
            
            # Set a custom prompt specifically for the final synthesis step to get a clean report
            analyzer.user_prompt = (
                "Analyze the video frames along with the provided YouTube metadata (Title, Description, Comments). "
                "Reconstruct a clear, structured analysis containing:\n"
                "1. VIDEO TITLE & LOCATION: Identify/infer the event title and the location/place where the event is happening (infer from visual cues, description, or comments).\n"
                "2. VISUAL ANALYSIS: Describe what is physically happening in the frames chronologically.\n"
                "3. KEY CLAIMS & COMMENTS CONTEXT: Extract key claims being made in the video or the user comments (e.g., statements that can be verified/fact-checked).\n"
                "Format the output strictly using these headers:\n"
                "### VIDEO TITLE & LOCATION\n"
                "...\n"
                "### VISUAL ANALYSIS\n"
                "...\n"
                "### KEY CLAIMS & COMMENTS CONTEXT\n"
                "..."
            )
            video_description = analyzer.reconstruct_video(frame_analyses, frames, transcript=dummy_transcript)
            print("[+] OpenRouter Visual Frame Analysis Successful!")
            
        except Exception as openrouter_err:
            print(f"[-] OpenRouter failed: {openrouter_err}")
            print("[*] Falling back to local Ollama (llama3.2-vision) visual frame analysis...")
            
            try:
                client = OllamaClient("http://localhost:11434")
                model = "llama3.2-vision"
                
                analyzer = VideoAnalyzer(client, model, prompt_loader, temperature=0.2)
                frame_analyses = []
                for frame in frames:
                    analysis = analyzer.analyze_frame(frame)
                    frame_analyses.append(analysis)
                    
                class DummyTranscript:
                    def __init__(self, text):
                        self.text = text
                
                dummy_transcript = DummyTranscript(metadata_text)
                
                # Set a custom prompt specifically for the final synthesis step to get a clean report
                analyzer.user_prompt = (
                    "Analyze the video frames along with the provided YouTube metadata (Title, Description, Comments). "
                    "Reconstruct a clear, structured analysis containing:\n"
                    "1. VIDEO TITLE & LOCATION: Identify/infer the event title and the location/place where the event is happening (infer from visual cues, description, or comments).\n"
                    "2. VISUAL ANALYSIS: Describe what is physically happening in the frames chronologically.\n"
                    "3. KEY CLAIMS & COMMENTS CONTEXT: Extract key claims being made in the video or the user comments (e.g., statements that can be verified/fact-checked).\n"
                    "Format the output strictly using these headers:\n"
                    "### VIDEO TITLE & LOCATION\n"
                    "...\n"
                    "### VISUAL ANALYSIS\n"
                    "...\n"
                    "### KEY CLAIMS & COMMENTS CONTEXT\n"
                    "..."
                )
                video_description = analyzer.reconstruct_video(frame_analyses, frames, transcript=dummy_transcript)
                print("[+] Local Ollama Visual Frame Analysis Successful!")
            except Exception as ollama_err:
                print(f"[-] Local Ollama also failed: {ollama_err}")
                video_description = {"response": f"Visual analysis failed. OpenRouter error: {openrouter_err}. Local Ollama error: {ollama_err}."}
        
        # Cleanup extracted frames for this specific video
        if output_dir.exists():
            shutil.rmtree(output_dir)
            
        return video_description

    def save_transcript_locally(self, text):
        """Saves the final transcript to a text file for local review."""
        try:
            with open("transcript.txt", "w", encoding="utf-8") as f:
                f.write(text)
            print("[*] Transcript saved to transcript.txt")
        except Exception as e:
            print(f"[-] Failed to save transcript.txt: {e}")

    def is_transcript_meaningful(self, text):
        """Uses local LLM to verify if the transcript actually contains meaningful human speech."""
        try:
            client = OllamaClient()
            prompt = (
                "Evaluate the following text. Determine if it contains meaningful, coherent human speech. "
                "The text can be in any language (e.g., Telugu, English, Hindi, etc). "
                "If it is mostly junk, repetitive letters (e.g. l-l-l-l), or random noise without meaning, "
                "reply ONLY with the word 'NO'. If it contains actual meaningful sentences, reply ONLY with 'YES'.\n\n"
                f"Text:\n{text[:2000]}"
            )
            response = client.generate(prompt=prompt, model="llama3.2-vision", temperature=0.1)
            reply = response.get("response", "").strip().upper()
            return "YES" in reply
        except Exception as e:
            print(f"[-] LLM validation error: {e}")
            return True

    def get_youtube_api_transcript(self, video_id):
        if not HAS_YTA:
            print("[-] youtube-transcript-api package is not installed. Skipping direct transcript fetch.")
            return None
        print("[*] Attempting to fetch transcript directly via youtube-transcript-api...")
        try:
            # We must instantiate the API class in this specific library version
            ytt_api = YouTubeTranscriptApi()
            languages = ['ta', 'en', 'en-IN', 'en-US', 'en-GB', 'te', 'hi', 'kn', 'ml', 'mr', 'bn', 'gu', 'ur', 'pa', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ar', 'ja', 'ko', 'zh', 'zh-Hans', 'zh-Hant']
            
            fetched_transcript = ytt_api.fetch(video_id, languages=languages)
            
            if fetched_transcript:
                print(f"[*] Found transcript directly via YouTube API!")
                text_lines = []
                for snippet in fetched_transcript:
                    if isinstance(snippet, dict):
                        text_lines.append(snippet.get('text', ''))
                    elif hasattr(snippet, 'text'):
                        text_lines.append(snippet.text)
                    elif hasattr(snippet, 'get'):
                        text_lines.append(snippet.get('text', ''))
                    else:
                        try:
                            text_lines.append(snippet.text)
                        except AttributeError:
                            text_lines.append(str(snippet))
                
                final_text = " ".join(text_lines).replace("\n", " ")
                
                # Cleanup if FetchedTranscriptSnippet pattern leaked in
                if "FetchedTranscriptSnippet" in final_text:
                    final_text = re.sub(r"FetchedTranscriptSnippet\(text=(['\"])(.*?)\1,\s*start=.*?,?\s*duration=.*?\)", r"\2", final_text)
                
                return final_text
        except Exception as e:
            print(f"[-] YouTube API transcript fetch failed: {e}")
            return None

    def process_youtube(self, url):
        """New Pipeline: YouTube API transcript -> Audio Fallback -> Visual Analyzer Fallback."""
        video_id = self.get_video_id(url)
        
        transcript_text = ""
        result = None
        
        # 1. Try YouTube API transcript
        transcript_text = self.get_youtube_api_transcript(video_id)
        if transcript_text and len(transcript_text.strip()) > 50:
            print("[*] Validating YouTube API transcript meaning with LLM...")
            if self.is_transcript_meaningful(transcript_text):
                print("[+] YouTube API Transcript is valid. Skipping audio/visual fallback.")
                result = {
                    "method": "YouTube API Transcript",
                    "language": "en",
                    "language_probability": 1.0,
                    "segments": [],
                    "text": transcript_text
                }
            else:
                print("[-] YouTube API Transcript is garbage/insufficient. Triggering audio fallback...")
                transcript_text = None
        elif transcript_text:
            print("[-] YouTube API Transcript is too short (<50 chars). Triggering audio fallback...")
            transcript_text = None
        
        # 2. If no API transcript, download audio and Whisper
        if not result:
            print("[*] No valid YouTube API transcript found. Proceeding to Audio Download & Whisper Transcription...")
            audio_path = None
            try:
                audio_path = self.download_audio(url, video_id)
                transcript = self.audio_processor.transcribe(audio_path)
                
                if transcript and transcript.text and len(transcript.text.strip()) > 50:
                    print("[*] Validating audio transcript meaning with LLM...")
                    if self.is_transcript_meaningful(transcript.text):
                        print("[+] Whisper Audio Transcription Successful!")
                        transcript_text = transcript.text
                        result = {
                            "method": "Whisper Audio Analyzer",
                            "language": getattr(transcript, "language", "en"),
                            "language_probability": 1.0,
                            "segments": getattr(transcript, "segments", []),
                            "text": transcript_text
                        }
                    else:
                        print("[-] Transcript deemed not meaningful by LLM. Triggering visual fallback...")
                else:
                    print("[!] Audio transcript insufficient (<50 chars). Proceeding to Visual Fallback...")
            except Exception as e:
                print(f"[-] Audio Transcription Error: {e}")
            finally:
                pass # Retain the audio file in temp_audio for future caching!

        # 3. Visual Fallback if both yt-dlp and audio fail
        if not result:
            print("[*] Audio/Text failed. Running Video Analyzer Fallback on video frames...")
            video_path = None
            try:
                video_path = self.download_video(url, video_id)
                if video_path and video_path.exists():
                    video_desc = self.analyze_video_frames(video_path, url=url)
                    
                    final_text = video_desc.get("response", "Visual analysis failed.")
                    
                    result = {
                        "method": "Visual Frame Analyzer (Fallback)",
                        "language": "en",
                        "language_probability": 1.0,
                        "segments": [],
                        "text": f"[VISUAL TRANSCRIPT RECONSTRUCTION]\n{final_text}"
                    }
                else:
                    result = {"error": "Video download failed."}
            except Exception as e:
                print(f"[-] Video Analyzer Error: {e}")
            finally:
                pass # Retain the video file in temp_audio for future caching!

        # Save locally if successful
        if result and "text" in result:
            self.save_transcript_locally(result["text"])
            
        return result
