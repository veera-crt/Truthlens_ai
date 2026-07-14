# TruthLens AI – End‑to‑End Video Credibility Analyzer

---

## 🎯 Project Vision
TruthLens AI aims to **empower every viewer** with an instant credibility assessment of any YouTube video. By surfacing a **Trust Index**, manipulation risk, virality, and claim‑by‑claim evidence, the system helps users quickly decide whether a video is trustworthy, sensationalist, or potentially harmful.

---

## 🏗️ High‑Level Architecture
```mermaid
flowchart TB
    subgraph Extension[Chrome/Brave Extension]
        UI[Popup UI] -->|POST /api/extension/analyze| BE[Flask Backend]
    end
    subgraph Backend[Flask Server (Port 5001)]
        BE -->|Metadata| YTDL[yt‑dlp]
        BE -->|Transcription| Whisper[Whisper / Faster‑Whisper]
        BE -->|NLP| NLP[Phase 3 – mDeBERTa + GoEmotions]
        BE -->|Fusion| Fusion[Phase 6 – Risk Engine]
        BE -->|Cache| GSheet[Google Sheets DB]
        BE -->|Graph| Graph[Phase 5 – Coordination (disabled)]
    end
    UI -->|Display| UI
    YTDL -->|Video data| BE
    Whisper -->|Plain text| NLP
    NLP -->|Scores & Claims| Fusion
    Fusion -->|Trust Index & Category| UI
    GSheet -->|Cache reads/writes| BE
end
```
```

* **Extension** – lightweight UI that sends the video URL to the backend and renders JSON results.
* **Backend** – orchestrates six processing phases, persists results, and serves a REST API.
* **Google‑Sheets Cache** – ensures subsequent look‑ups are sub‑second.
* **Autopilot Daemon** – optional background job that periodically analyzes trending videos.

---

## 📁 Repository Layout
```
├── extension/               # Chrome/Brave extension source
│   ├── manifest.json
│   ├── popup.html
│   ├── popup.js          # UI logic & API integration
│   └── popup.css         # Glass‑morphic dark theme & micro‑animations
├── Server/                  # Flask API
│   ├── app.py               # Entry point, routes, scheduler
│   ├── modules/             # Phase‑specific engines
│   │   ├── phase1_transcription/
│   │   ├── phase2_social/
│   │   ├── phase3_nlp/
│   │   ├── phase4_evidence/
│   │   ├── phase5_network/
│   │   └── phase6_fusion/
│   └── middleware/          # YouTube comment crawler, etc.
├── backend/                 # Autopilot status JSON files
├── templates/               # Dashboard HTML for local dev server
├── .env                     # Environment variables (not committed)
├── requirements.txt         # Python dependencies
├── README.md                # **THIS FILE** – detailed documentation
└── LICENSE                  # MIT License
```

---

## 🛠️ Prerequisites & System Requirements
| Component | Minimum Version | Why?
|-----------|----------------|------|
| Python | 3.12 | Required for `torch` and latest `transformers`.
| Node (optional) | 20.x | Needed only if you want to bundle the extension with a custom build script.
| Chrome / Brave | 125+ | Supports Manifest V3 and the `scripting` permission.
| ffmpeg (static) | bundled via `static‑ffmpeg` | Used by `yt‑dlp` to extract audio streams.
| Google Service Account JSON | – | Allows the server to read/write Google Sheets.
| GPU (optional) | CUDA 12.x | Speeds up Whisper transcription and transformer inference.

---

## 📦 Python Dependencies
The `requirements.txt` pin includes:
```
flask>=3.0.3
flask-cors>=4.0.1
requests>=2.32.3
python-dotenv>=1.0.1
beautifulsoup4>=4.12.3
yt-dlp>=2024.04.10
static-ffmpeg>=2.5
youtube-transcript-api>=0.6.2
instaloader>=4.10.1
snscrape>=0.7.0
torch>=2.0.0
transformers>=4.30.0
google-generativeai>=0.4.0
sentence-transformers>=2.2.2
tavily-python>=0.3.3
gspread>=6.0.0
Pillow>=10.4.0
opencv-python-headless>=4.10.0.84
numpy>=1.26.4
networkx>=3.2.1
torch-geometric>=2.3.0
scikit-learn>=1.3.0
pandas>=2.0.0
apscheduler>=3.10.0
pydub>=0.25.1
audioop-lts>=0.2.2
faster-whisper>=0.6.0
openai-whisper>=20231117
youtube-comment-downloader>=0.7.7
```
Run `pip install -r requirements.txt` inside the virtual environment.

---

## ⚙️ Environment Configuration (`.env`)
Create a `.env` file at the repo root:
```
# Flask configuration
FLASK_APP=Server/app.py
FLASK_ENV=development

# Google Sheets credentials (service account JSON path)
GSHEET_SERVICE_ACCOUNT=service_account.json

# Optional API keys (for Groq, Gemini, etc.)
GROQ_API_KEY=YOUR_GROQ_KEY
GEMINI_API_KEY=YOUR_GEMINI_KEY

# Autopilot options
AUTOPILOT_INTERVAL_HOURS=5   # (currently disabled – uncomment in app.py to enable)
```
Never commit this file; it contains secrets.

---

## 🚀 Getting Started (Platform‑Specific Setup)

Choose the setup instructions corresponding to your operating system:

### 🍎 macOS Setup Guide

#### 1. Install Prerequisites
Make sure you have Python 3.12+ and `ffmpeg` installed. The easiest way is using [Homebrew](https://brew.sh/):
```bash
# Install Homebrew if you haven't already
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python and FFmpeg
brew install python ffmpeg
```

#### 2. Set Up Python Virtual Environment
Clone the repository, navigate into the directory, and initialize the virtual environment:
```bash
git clone "https://github.com/your-org/truthlens-ai.git"
cd "truthlens-ai"

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 3. Prepare AI Models
Download the deep learning models (stored under `~/.cache/`):
```bash
python3 - <<'PY'
from modules.Helpers.download_models import download_all
download_all()
PY
```

#### 4. Configure Environment Variables
Create a `.env` file at the repository root by copying the template shown in the environment configuration section. Ensure your service account JSON file exists and its path is configured in the `.env` file.

#### 5. Launch Backend & Extensions
```bash
# Activate environment (if not already active)
source venv/bin/activate

# Start the Flask backend server
python3 Server/app.py

# Optional: Run Autopilot background job in a separate terminal tab
source venv/bin/activate
python3 "Autopilot mode/auto.py"
```

---

### 🪟 Windows Setup Guide

#### 1. Install Prerequisites
1. **Python 3.12+**: Download and run the installer from [python.org](https://www.python.org/downloads/). **IMPORTANT:** Check the box that says **"Add Python to PATH"** during installation.
2. **FFmpeg**: Download a static release build (e.g., from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)), extract it, and add its `bin` folder to your System PATH environment variable. 
   *Alternatively*, install via package managers:
   ```powershell
   # Via Chocolatey
   choco install ffmpeg
   
   # Via Scoop
   scoop install ffmpeg
   ```

#### 2. Set Up Python Virtual Environment
Open PowerShell or Command Prompt, clone the repository, and create a virtual environment:
```powershell
git clone "https://github.com/your-org/truthlens-ai.git"
cd "truthlens-ai"

# Create virtual environment
python -m venv venv
```

**Activate the virtual environment:**
- **PowerShell** (Ensure execution policy allows running scripts: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` if needed):
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
- **Command Prompt (CMD)**:
  ```cmd
  .\venv\Scripts\activate.bat
  ```

#### 3. Install Python Dependencies
If using an NVIDIA GPU and you want hardware acceleration for Whisper transcription, install the CUDA-supported version of PyTorch first:
```powershell
# Optional: Install GPU PyTorch (adjust cu121/cu118 depending on your CUDA version)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install the rest of dependencies
pip install -r requirements.txt
```

#### 4. Prepare AI Models
Download all local NLP & Transcription models:
```powershell
python -c "from modules.Helpers.download_models import download_all; download_all()"
```

#### 5. Configure Environment Variables
Create a `.env` file at the repository root matching the template shown in the configuration section.

#### 6. Launch Backend & Extensions
```powershell
# Activate environment (if not already active)
.\venv\Scripts\Activate.ps1

# Start the Flask backend server
python Server/app.py

# Optional: Run Autopilot background job in a separate terminal
.\venv\Scripts\Activate.ps1
python "Autopilot mode/auto.py"
```

---

### 🔌 Chrome / Brave Extension Loading (All Platforms)

1. Open Google Chrome or Brave and navigate to `chrome://extensions/`.
2. Turn on **Developer mode** (toggle switch in the top-right corner).
3. Click **Load unpacked** (button in the top-left corner).
4. Select the `extension/` directory inside your cloned `truthlens-ai` folder.
5. Pin the **TruthLens AI** extension for easy access.

### 🧪 Test the System
1. Open any YouTube video.
2. Click the TruthLens icon in the extension bar → press **Analyze Video**.
3. The popup will display the composite Trust Index, Manipulation risk, Virality multiplier, and evidence claims extracted.

---

## 📊 Detailed Phase Walk‑through
| Phase | Purpose | Key Modules | Primary Outputs |
|------|----------|-------------|-----------------|
| **Phase 1 – Metadata Harvest** | Pull video metadata, formats, thumbnail, and basic stats. | `modules/phase1_transcription/transcription.py` (via `yt‑dlp`) | JSON with `title`, `description`, `views`, `likes`, `comments`, `formats`, `comments_list` |
| **Phase 2 – Social Harvest** | (Future) Pull related social‑media posts, hashtags, and sentiment. Currently placeholder. |
| **Phase 3 – Transcription** | Generate a high‑quality transcript from audio/video. | `modules/phase1_transcription/transcription.py` → `faster‑whisper`/`openai‑whisper` | `text`, `segments`, language info |
| **Phase 4 – Evidence Extraction** | (Optional) Use Vision APIs to extract text from thumbnails or embedded graphics. |
| **Phase 5 – Graph Coordination** | Detect coordinated bot activity across comment networks (disabled by default). | `modules/phase5_network/graph.py` |
| **Phase 6 – Risk Fusion** | Combine manipulation score, virality multiplier, and platform stats into a composite **Trust Index**; map to a risk **category**. | `modules/phase6_fusion/risk_engine.py` |

**Fusion Formula (simplified)**:
```python
composite_score = (manipulation_score * 0.5) + (virality_multiplier * 0.3) + (platform_engagement_factor * 0.2)
trust_index = 100 - (composite_score * 100)
```
The final `trust_index` drives the 5‑category mapping.

---

## 📊 API Reference (Full)
### General
- Base URL: `http://127.0.0.1:5001`
- All responses are JSON with appropriate HTTP status codes.

### Endpoints
| Method | Path | Description | Sample Request Body |
|--------|------|-------------|---------------------|
| `POST` | `/api/youtube/analyze` | Retrieve metadata & top‑10 formats. | `{ "video_id": "dQw4w9WgXcQ" }` |
| `POST` | `/api/youtube/transcript` | Get (or generate) transcript. | `{ "url": "https://www.youtube.com/watch?v=XYZ" }` |
| `POST` | `/api/trust/full` | Run the entire pipeline (metadata → trust). | `{ "video_id": "XYZ", "text": "optional transcript" }` |
| `POST` | `/api/extension/analyze` | Light‑weight endpoint for the Chrome popup. | `{ "url": "https://www.youtube.com/watch?v=XYZ", "title": "Video Title" }` |
| `GET` | `/api/categories` | Returns the static list of five categories. | – |
| `GET` | `/api/autopilot/status` | Autopilot daemon health check. | – |
| `POST` | `/api/autopilot/force_start` | Trigger immediate Autopilot run. | – |

**Success payload (extension)**:
```json
{
  "trust_index": 71.5,
  "virality_score": 0.42,
  "manipulation_risk": 0.36,
  "claims": [
    { "text": "President Trump joined a working session…", "verdict": "Insufficient evidence", "source": "..." }
  ]
}
```

---

## 🛡️ Trust Index Category Mapping
| Category | Trust Index Range |
|----------|-------------------|
| **AUTHENTIC** | ≥ 80 % |
| **LOW RISK** | 60 % – 79 % |
| **MODERATE** | 40 % – 59 % |
| **HIGH RISK** | 20 % – 39 % |
| **CRITICAL** | < 20 % |

Implemented in `extension/popup.js` and mirrored in `modules/phase6_fusion/risk_engine.py`.

---

## 📈 Recent Updates (June 2026)
- **Category badge fixed** – added `<span id="cat‑trust">` and CSS `.metric‑category { display: block; }` so the category now appears in the popup.
- **Dynamic Trust‑Index computation** – decoupled from manipulation score; now follows pure Trust‑Index thresholds.
- **Improved caching** – Google‑Sheets row now stores `evidence_summary`, `trust_score`, `virality_score`, `manipulation_score`, and `red_flags` for instant extension loads.
- **Safety filters** – blocked 18+ content, livestreams, long videos (>20 min), and explicit adult keywords.
- **Autopilot improvements** – added graceful kick‑start trigger, background processing lock, and better error handling.
- **UI polish** – glass‑morphic dark theme, micro‑animations for score bars, and responsive layout for 350 px popup width.

---

## 🐞 Debugging & Troubleshooting
| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Popup shows *Processing…* forever | Backend not reachable (port 5001 closed) | Ensure `Server/app.py` is running; check firewall. |
| Category badge missing | CSS `.metric‑category` overridden | Verify `popup.css` contains the rule and that the `<span id="cat‑trust">` exists in `popup.html`. |
| No claims displayed | `evidence_summary` empty in Google Sheet | Run a fresh analysis; the cache will be repopulated. |
| Autopilot never runs | Scheduler disabled (`scheduler.start()` commented) | Uncomment the scheduler block in `app.py` or manually trigger via `/api/autopilot/force_start`. |

---

## 🤝 Contributing Guidelines
1. **Fork** the repository on GitHub.
2. **Create a feature branch**:
   ```bash
   git checkout -b feature/awesome‑thing
   ```
3. **Follow the coding style**:
   - Vanilla CSS for UI components.
   - No Tailwind unless explicitly approved.
   - Keep Python formatting PEP‑8 compliant (`black`, `isort`).
4. **Add tests** for any new functionality.
5. **Run the full test suite** before committing.
6. **Submit a Pull Request** with a concise description, screenshots, and a reference to any open issue.

---

## 📜 License
This project is released under the **MIT License**. See the `LICENSE` file for full terms.

---

## 📞 Contact & Support
- **Maintainer**: Veerapandig – GitHub: [@veerapandig](https://github.com/veerapandig)
- **Bug reports / Feature requests**: Open an issue on GitHub.
- **Community chat**: Join the Discord `#truthlens‑dev` (invite link in the wiki).
- **Email**: veerapandig@example.com (for security disclosures).

---

## 🚀 Advanced Usage

### 🐳 Docker & Docker‑Compose
If you prefer containerised deployment, a minimal `Dockerfile` and `docker-compose.yml` are provided in the `docker/` directory.
```bash
# Build the image
docker build -t truthlens-ai .

# Run with docker‑compose (includes a tiny SQLite cache for quick prototyping)
cd docker && docker-compose up -d
```
The container exposes port **5001** and expects the same environment variables as the local setup. Mount your `service_account.json` into `/app/service_account.json`.

### 🔧 Customising Thresholds at Runtime
You can override the default category thresholds via environment variables:
```bash
export TRUST_AUTHENTIC_MIN=80
export TRUST_LOW_RISK_MIN=60
export TRUST_MODERATE_MIN=40
export TRUST_HIGH_RISK_MIN=20
```
The `risk_engine.compute_final_verdict` function reads these values on each request, enabling A/B testing without code changes.

---

## 📊 Performance Benchmarks
| Hardware | Avg. Full Analysis Time (no cache) | Avg. Cached Call |
|----------|-----------------------------------|-----------------|
| **CPU‑only (Intel i7‑12700K)** | ~22 s | ~0.3 s |
| **GPU (NVIDIA RTX 3080, CUDA 12)** | ~9 s | ~0.2 s |
| **Apple M2 Pro** | ~12 s | ~0.25 s |

Times measured on a 10 minute video (≈1.5 GB). The majority of the latency comes from Whisper transcription; swapping to `faster‑whisper` on GPU reduces the transcription step by ~60 %.

---

## 🧪 Testing Strategy
1. **Unit Tests** – located under `modules/tests/`. Run with:
   ```bash
   pytest modules/tests
   ```
2. **Integration Tests** – spin‑up the Flask server and hit the public endpoints using the `tests/integration/` scripts.
3. **Load Tests** – `hey` or `locust` can simulate concurrent users. Example with `hey`:
   ```bash
   hey -n 200 -c 20 http://127.0.0.1:5001/api/extension/analyze -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}' -m POST
   ```
4. **CI/CD** – GitHub Actions run the test suite on each PR and build the Docker image.

---

## 📅 Future Roadmap (Q4 2026 – Q2 2027)
- **Q4 2026** – Release Phase 2 Social Harvest (Twitter & Instagram API integration).
- **Q1 2027** – Enable Phase 5 Graph Coordination with real‑time bot‑net detection.
- **Q2 2027** – Deploy a managed SaaS version with multi‑tenant Google‑Sheets back‑ends.
- **Beyond** – Add multi‑language support (Spanish, Mandarin, Arabic) and open‑source the risk‑engine model.

---

## ❓ FAQ
**Q: Can I run the extension without a Google Sheet?**
A: Yes. Set `GSHEET_SERVICE_ACCOUNT=` empty in `.env`; the backend will skip caching and always perform a live analysis.

**Q: Why is the Trust Index higher when manipulation risk is low?**
A: Trust Index is computed as `100 - (composite_score * 100)`. The composite score aggregates manipulation, virality, and platform engagement; lower manipulation yields a higher trust score.

**Q: Does the extension work on Firefox?**
A: Currently only Manifest V3 browsers (Chrome, Edge, Brave) are supported. Firefox requires Manifest V2 which is out‑of‑scope for this release.

---

## 🙏 Acknowledgements
- **Open‑source community** – `yt‑dlp`, `whisper`, `transformers`, and `GoEmotions` provide the heavy‑lifting models.
- **Research collaborators** – The risk‑scoring formula is inspired by academic work on misinformation detection.
- **Contributors** – Thanks to all contributors listed in `CONTRIBUTORS.md`.

---

*Enjoy exploring the truth behind every video!*
