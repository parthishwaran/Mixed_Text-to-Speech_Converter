<div align="center">

# Mixed Language TTS (Tamil + English)

Convert mixed Tamil and English text into natural speech with **4 TTS engine options**: Azure (premium), Google Cloud (premium), Edge TTS (free), and gTTS (free). The app auto-detects language segments, intelligently selects the best available engine, stitches audio seamlessly, and shows real-time progress.

</div>

## ✨ Features

- Mixed-language detection (Tamil + English) per word/segment
- **Smart TTS Engine Selection**: Automatic fallback cascade (Azure → Google → Edge → gTTS)
- **Premium Options**: Azure Cognitive Services & Google Cloud TTS (optional)
- **Free Options**: Edge TTS & gTTS (work out-of-the-box, no API keys needed)
- Real-time progress indicator (0–100%) during conversion
- Upload .txt or .docx or paste text directly
- Outputs a single MP3 with smooth concatenation
- Tanglish support (Tamil words written in English script)

## 🧱 Tech Stack

- **Backend**: Python, Flask, Flask-CORS, asyncio, pydub, langdetect, python-docx
- **TTS Engines**: 
	- Azure Cognitive Services (optional, premium)
	- Google Cloud Text-to-Speech (optional, premium)
	- Edge TTS (free, included)
	- gTTS (free, included)
- Frontend: Vanilla HTML/CSS/JS
- System dependency: ffmpeg (for pydub to process MP3)

## 🎤 TTS Engine Comparison

| Engine | Quality | Cost | Setup |
|--------|---------|------|-------|
| **Azure** | ⭐⭐⭐⭐⭐ Best | Free tier: 500K chars/month | Requires API key |
| **Google** | ⭐⭐⭐⭐ Excellent | Free tier: 1M chars/month | Requires credentials |
| **Edge TTS** | ⭐⭐⭐ Good | Free unlimited | No setup needed ✅ |
| **gTTS** | ⭐⭐ Basic | Free unlimited | No setup needed ✅ |

**Default mode**: Uses Edge TTS (good quality, free, no configuration)

See [TTS_COMPARISON.md](TTS_COMPARISON.md) for detailed comparison and [SETUP_GUIDE.md](SETUP_GUIDE.md) for premium engine setup.

## 📦 Project Structure

```
mixed_tts/
├── backend/
│   └── main.py          # Flask API (sync + async endpoints with progress)
├── frontend/
│   ├── index.html       # UI
│   ├── index.css        # Styles (includes progress bar)
│   └── index.js         # Calls async API, polls progress, downloads MP3
├── start.sh             # Start server + open frontend
├── stop.sh              # Stop server
├── requirements.txt     # Python deps (see below)
└── venv/                # Virtual environment (local)
```

## 🚀 Quick Start

Recommended (one command):

```bash
cd /home/parthishwaran/Desktop/cu/mixed_tts
./start.sh
```

This will:
- Activate the virtual environment
- Start the Flask backend on http://127.0.0.1:5000
- Open the frontend in your browser

Stop the server:

```bash
./stop.sh
```

Manual start (alternative):

```bash
cd /home/parthishwaran/Desktop/cu/mixed_tts
source venv/bin/activate
python backend/main.py

# In another terminal
xdg-open frontend/index.html
```

## 🧑‍💻 Using the App

1. Paste mixed Tamil/English text or upload a .txt/.docx file
2. Click "Convert to Speech"
3. Watch the progress percent + bar update until 100%
4. Play or download the resulting MP3

Example mixed text:

```
Hello! வணக்கம். This is a mixed language example.
இது ஒரு கலப்பு மொழி உதாரணம். How are you? நலமாக இருக்கிறீர்களா?
```

## 🔌 API (for automation)

Health:

```bash
curl -s http://127.0.0.1:5000/health
```

Start async conversion (text or file):

```bash
# Text
curl -s -X POST -F "text=Hello வணக்கம்" http://127.0.0.1:5000/convert_async

# File
curl -s -X POST -F "file=@sample.txt" http://127.0.0.1:5000/convert_async
```

Poll progress:

```bash
curl -s http://127.0.0.1:5000/progress/<job_id>
# → { "status": "running|finished|error", "percent": 0-100, "message": "..." }
```

Download result (when finished):

```bash
curl -s -o output.mp3 http://127.0.0.1:5000/download/<job_id>
```

Synchronous (legacy) endpoint:

```bash
curl -X POST -F "text=Hello" http://127.0.0.1:5000/convert -o out.mp3
```

## 📋 Requirements

Python dependencies (see `requirements.txt`):

- Flask==2.3.3
- Flask-CORS==4.0.0
- asgiref==3.7.2             # for async view support
- gTTS==2.3.2                # Tamil (and can fallback for English)
- edge-tts==6.1.5            # English
- pydub==0.25.1
- langdetect==1.0.9
- python-docx==1.1.0
- requests==2.31.0

System dependency:

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

## 🛠️ Troubleshooting

- Port 5000 already in use
	- Find and stop: `lsof -ti:5000 | xargs kill -9`
- ImportError (missing packages)
	- `source venv/bin/activate && pip install -r requirements.txt`
- Long conversions timeout in the browser
	- Use the async flow (frontend already uses it) which polls `/progress/<job_id>`
- Edge TTS requires internet connectivity
	- Ensure your machine can reach external network


