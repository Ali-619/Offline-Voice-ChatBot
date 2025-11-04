Project overview — Voice Chat App (local-only)
============================================

Purpose
-------
This repository implements a local voice-chat prototype: browser records audio, sends it to a FastAPI backend for STT (Whisper), the backend uses a local LLM to generate replies, and the app can synthesize TTS audio for responses. The project is wired for local-only operation (no external inference APIs).

Top-level layout
----------------
- `app/` — Python backend package (FastAPI server).
  - `__init__.py` — package marker.
  - `main.py` — FastAPI app and endpoints (STT upload, chat, TTS, debug endpoints, static file mount). Key endpoints:
    - `POST /api/stt` — accepts uploaded audio file, saves to a temp file, calls STT service, returns `{ text, file_size, file_path }` for debugging.
    - `POST /api/chat` — accepts user text, appends to history, calls LLM service, returns assistant text; optionally streams TTS audio.
    - `GET /api/tts` — returns synthesized audio for given text.
    - `GET /api/last_stt` — returns last saved STT temp file path (restricted to project/temp dir).
    - `POST /api/debug_transcribe` and `/api/debug_transcribe_last` — verbose transcription helpers that return structured JSON (segments, audio_info, errors).

- `app/services/` — service implementations.
  - `llm_service.py` — local LLM loader and generator. The code prefers a local GGUF or HF-format model and uses `ctransformers` when available for GGUF files. It is configured CPU-only by default (gpu_layers=0). The service exposes a `generate(prompt, history)` function used by the chat endpoint.
  - `stt_service.py` — local STT using the `whisper` Python package. It now attempts to load whisper at service init (cached), exposes `transcribe_file(path)` for compatibility and `transcribe_file_verbose(path)` returning structured diagnostics: text, language, segments, file_size, model_loaded, error, and `audio_info` (if WAV). A small WAV inspector detects channels, sample rate, duration and RMS/peak.
  - `tts_service.py` — TTS implementation. Default light-weight option uses `gTTS` or a local TTS backend (Coqui) if available. It exports a `synthesize(text)` function returning audio bytes.

- `app/history.py` — small in-memory history manager for sessions. It stores per-session messages and exposes `new_session()`, `append(session_id, role, text)`, and `get(session_id)`.

- `web/` — frontend static files served at `/static`.
  - `index.html` — UI for recording, text input, buttons and message history. Minimal, professional layout.
  - `main.js` — client logic: MediaRecorder usage, client-side WebM→WAV conversion, upload to `/api/stt`, call `/api/chat`, and play TTS. The client contains a lightweight client-side RMS check (for silent recordings) and no longer auto-plays or displays the raw recording.

- `requirements.txt` — Python dependency list. Contains FastAPI, uvicorn, whisper, and recommended local inference libs; `ctransformers` is used for GGUF support where specified.

- `README.md` — short run instructions (virtualenv, deps, model path, run uvicorn). Keep this minimal per repo owner request.

Model files and formats
-----------------------
- GGUF (recommended for Mistral GGUF builds): `ctransformers` can load `.gguf` files efficiently on CPU.
- HF / Transformers checkpoints: optionally supported by `transformers` + `torch` but heavy; not required if using GGUF.
- Where to put your model: project `models/` folder. Example env var: `LOCAL_MODEL_PATH` points to the model file/folder.

STT (Whisper)
--------------
- We use the `openai-whisper` Python package for local transcription. The service caches the loaded model to avoid repeated downloads/cold-starts. The project includes debug endpoints that return detailed transcription JSON (segments, language, error) and a WAV inspector that reports duration, sample rate, channels, RMS dB, and peak.
- ffmpeg: recommended on the host for broader codec support; the client converts WebM → WAV to reduce host dependency.

TTS (Coqui/gTTS)
-----------------
- The default TTS is a light local option (gTTS or an installed Coqui TTS) depending on availability. The `tts_service` module will try Coqui first if present, otherwise fallback to gTTS or a simple offline synthesizer. Synthesized audio is returned as bytes for the frontend to play.

History format
--------------
- `history` stores a simple list of items per session in memory: each item is `{ role: 'user'|'assistant'|'system', text: str, timestamp?: float }`. It's easy to swap to persistent storage (file, SQLite) if needed.

Debugging & common problems
---------------------------
- STT empty transcription: check `/api/debug_transcribe_last` — it returns `model_loaded`, `audio_info` (rms_db, duration), `segments` and `error`. If `rms_db` is very low (e.g. -100 dB) the recording is silent or mic is blocked. Client-side RMS helps (client logs) and client now warns before upload.
- ffmpeg not found: install ffmpeg and add to PATH.
- Model loading: if the LLM falls back to echo responses, server logs will show model-load errors; ensure `LOCAL_MODEL_PATH` is correct and required runtime libs (`ctransformers` or `transformers`/`torch`) are installed.

Run & test (quick)
-------------------
1. Create venv and install deps:
```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
pip install -U openai-whisper
# optionally install ctransformers for GGUF: pip install ctransformers
```
2. Set model path and run server:
```powershell
$env:LOCAL_MODEL_PATH = Join-Path (Get-Location) 'models\\mistral-7b.gguf'
uvicorn app.main:app --reload --port 8000
```
3. Open `http://127.0.0.1:8000/static/index.html` and test recording.

Security notes
--------------
- Debug endpoints that accept file paths are restricted to the project directory and the system temp directory to limit exposure. Do not expose this server publicly without proper auth.

Next steps (suggested)
----------------------
- Add a small smoke-test script that checks for model files and runs a tiny generation to validate local LLM.
- Persist history to disk/DB for auditability.
- Add an admin-only UI panel to show model and STT/TTS status.

If you want, I can expand any section above into deeper docs (e.g., a full TTS options comparison, step-by-step ffmpeg install on Windows, or a smoke-test script) — tell me which one to expand.
