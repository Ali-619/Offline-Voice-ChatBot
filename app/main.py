import os
import io
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, RedirectResponse
from pydantic import BaseModel
import tempfile

from .history import history
from .services import stt_service, llm_service, tts_service

app = FastAPI(title="Langchain-like Chat with STT/TTS")

# store the last STT uploaded temp file path for debugging (optional, restricted)
last_stt_saved_path: str | None = None

@app.get("/")
async def root():
    """Redirect root to the static web UI."""
    return RedirectResponse(url="/static/index.html")

# Compute static directory relative to this file so mounting works when running from project root
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATIC_DIR = os.path.join(BASE_DIR, "web")

from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class ChatRequest(BaseModel):
    text: str
    session_id: str | None = None
    tts: bool = False

@app.post("/api/stt")
async def stt_endpoint(audio: UploadFile = File(...)):
    # save to a temporary file
    suffix = os.path.splitext(audio.filename)[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        data = await audio.read()
        tmp.write(data)
        tmp_path = tmp.name
    # record last saved path for quick debugging endpoint
    global last_stt_saved_path
    last_stt_saved_path = tmp_path
    try:
        transcription = stt_service.transcribe_file(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    # return diagnostic info to help debugging client recording issues
    file_size = None
    try:
        file_size = os.path.getsize(tmp_path)
    except Exception:
        file_size = None
    return {"text": transcription, "file_size": file_size, "file_path": tmp_path}


@app.get('/api/last_stt')
async def get_last_stt():
    """Return the last saved STT temp file path and size (restricted to project or temp dir).

    Use this for local debugging; it helps find the most recent file that was uploaded via /api/stt.
    """
    if not last_stt_saved_path:
        raise HTTPException(status_code=404, detail='no stt file recorded yet')

    abs_path = os.path.abspath(last_stt_saved_path)
    allowed_dirs = [BASE_DIR, tempfile.gettempdir()]
    allowed = any(abs_path.startswith(os.path.abspath(d) + os.sep) or abs_path == os.path.abspath(d) for d in allowed_dirs)
    if not allowed:
        raise HTTPException(status_code=403, detail='recorded path not allowed')

    size = None
    try:
        size = os.path.getsize(abs_path)
    except Exception:
        size = None

    return {"file_path": abs_path, "file_size": size}


class DebugTranscribeRequest(BaseModel):
    path: str


@app.post("/api/debug_transcribe")
async def debug_transcribe(req: DebugTranscribeRequest):
    """Safely transcribe a local file path for debugging and return verbose JSON.

    POST JSON: { "path": "C:\\...\\recording.wav" }
    """
    path = req.path
    if not path:
        raise HTTPException(status_code=400, detail="path is required")

    abs_path = os.path.abspath(path)
    allowed_dirs = [BASE_DIR, tempfile.gettempdir()]
    allowed = any(abs_path.startswith(os.path.abspath(d) + os.sep) or abs_path == os.path.abspath(d) for d in allowed_dirs)
    if not allowed:
        raise HTTPException(status_code=403, detail="path not allowed; must be inside project directory or temp dir")

    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="file not found")

    try:
        res = stt_service.transcribe_file_verbose(abs_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # include file info
    try:
        res["file_path"] = abs_path
        res["file_size"] = os.path.getsize(abs_path)
    except Exception:
        pass
    return res


@app.post('/api/debug_transcribe_last')
async def debug_transcribe_last():
    """Transcribe the most recent uploaded STT temp file and return verbose result.

    This is a convenience for debugging: it reads the last path recorded by /api/stt
    and runs the verbose transcription on it.
    """
    if not last_stt_saved_path:
        raise HTTPException(status_code=404, detail='no stt file recorded yet')
    abs_path = os.path.abspath(last_stt_saved_path)
    allowed_dirs = [BASE_DIR, tempfile.gettempdir()]
    allowed = any(abs_path.startswith(os.path.abspath(d) + os.sep) or abs_path == os.path.abspath(d) for d in allowed_dirs)
    if not allowed:
        raise HTTPException(status_code=403, detail='recorded path not allowed')
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail='file not found')
    try:
        res = stt_service.transcribe_file_verbose(abs_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    try:
        res["file_path"] = abs_path
        res["file_size"] = os.path.getsize(abs_path)
    except Exception:
        pass
    return res

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    sid = req.session_id or history.new_session()
    history.append(sid, "user", req.text)
    assistant_text = llm_service.generate(req.text, history.get(sid))
    history.append(sid, "assistant", assistant_text)

    result = {"session_id": sid, "assistant": assistant_text}

    if req.tts:
        audio_bytes = tts_service.synthesize(assistant_text)
        return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/mpeg")

    return result

@app.get("/api/tts")
async def tts_endpoint(text: str):
    audio_bytes = tts_service.synthesize(text)
    return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/mpeg")

@app.get("/api/history")
async def get_history(session_id: str | None = None):
    if session_id is None:
        return {"sessions": list(history.sessions.keys())}
    return {"session_id": session_id, "history": history.get(session_id)}

@app.get("/api/ping")
async def ping():
    return {"status": "ok"} 











