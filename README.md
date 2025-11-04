# Voice Chat App  Local-only

A minimal local voice chat application: records audio in the browser, sends it to a local FastAPI server for STT (Whisper), generates replies with a local LLM (GGUF/ctransformers or compatible HF model), and returns TTS audio.

Quick start (Windows PowerShell)

1) Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2) Install Python dependencies

```powershell
pip install -r requirements.txt
```

3) Install Whisper (required for STT) and ffmpeg (recommended)

```powershell
pip install -U openai-whisper
# Install ffmpeg separately on Windows and add to PATH if you want broader codec support.
```

4) Place your local LLM model and configure environment variable

Put your GGUF or HF model in the project `models` folder. Example path used by the project:

```
<project-root>/models/mistral-7b.gguf
```

Then set the environment variable (PowerShell):

```powershell
#$env:LOCAL_MODEL_PATH should point to the model file or folder
$env:LOCAL_MODEL_PATH = Join-Path (Get-Location) 'models\\mistral-7b.gguf'
```

5) Run the server and open the UI

```powershell
uvicorn app.main:app --reload --port 8000
```

Open the frontend at: http://127.0.0.1:8000/static/index.html

Useful debug endpoints
- `POST /api/stt`  upload audio (used by the frontend)
- `GET /api/last_stt`  returns last saved STT temp file (for debugging)
- `POST /api/debug_transcribe_last`  transcribe the last saved STT file and return detailed JSON

 
