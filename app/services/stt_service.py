import os
import logging

logger = logging.getLogger(__name__)


class STTService:
    def __init__(self):
        # Try to import and load the whisper model once at service init to avoid
        # repeated downloads and long per-request startup delays. If whisper is
        # not installed the object will still be created but methods will raise
        # a clear error when used.
        self.model = None
        self.model_name = "small"
        try:
            import whisper
            try:
                # load model eagerly to ensure it's available and report errors early
                self.model = whisper.load_model(self.model_name)
            except Exception as e:
                logger.warning("STT: failed to load whisper model '%s' at init: %s", self.model_name, e)
                self.model = None
        except Exception as e:
            logger.warning("STT: whisper package not available: %s", e)

    def transcribe_file(self, path: str) -> str:
        """Transcribe an audio file using a local whisper installation.

        This implementation no longer uses any hosted API. Install the `whisper` package
        or another local STT backend and ensure it's available in the environment.
        The function logs the input file path and transcription for easier debugging.
        """
        # Use verbose transcription internally but return only text for backward compatibility
        res = self.transcribe_file_verbose(path)
        if res.get("error"):
            raise RuntimeError("Local whisper transcription failed: " + res["error"])
        return res.get("text", "")

    def transcribe_file_verbose(self, path: str) -> dict:
        """Transcribe a file and return a JSON-serializable dict with details.

        Returns keys: text, language, segments (list of {start,end,text}), file_size,
        model_loaded (bool), error (str or null).
        """
        result = {"text": "", "language": None, "segments": [], "file_size": None, "model_loaded": False, "error": None}
        try:
            if not os.path.exists(path):
                raise FileNotFoundError(path)
            size = os.path.getsize(path)
            result["file_size"] = size
            logger.info("STT: transcribing file %s (size=%d bytes)", path, size)

            # Attempt a lightweight audio inspection for WAV files to detect silence/codecs
            try:
                audio_info = self._inspect_wav(path)
                result["audio_info"] = audio_info
            except Exception:
                # non-fatal; continue to transcription
                logger.debug("STT: audio inspection skipped or failed for %s", path)

            # ensure we have a model; if not, try to import & load on demand
            if not self.model:
                try:
                    import whisper
                    self.model = whisper.load_model(self.model_name)
                except Exception as e:
                    logger.exception("STT: failed to import/load whisper model on demand")
                    result["error"] = str(e)
                    return result

            result["model_loaded"] = True
            # perform transcription
            try:
                res = self.model.transcribe(path)
            except Exception as e:
                logger.exception("STT: transcription call failed")
                result["error"] = str(e)
                return result

            text = res.get("text", "")
            result["text"] = text
            result["language"] = res.get("language")
            segments = res.get("segments") or []
            # normalize segments to simple list of dicts
            segs = []
            for s in segments:
                try:
                    segs.append({
                        "start": float(s.get("start", 0)),
                        "end": float(s.get("end", 0)),
                        "text": s.get("text", "").strip(),
                    })
                except Exception:
                    # if segment is a simple string or unexpected shape
                    segs.append({"start": None, "end": None, "text": str(s)})
            result["segments"] = segs
            logger.info("STT: transcription result: %s", repr(text))
            return result
        except Exception as e:
            logger.exception("Local whisper transcription failed (verbose)")
            result["error"] = str(e)
            return result

    def _inspect_wav(self, path: str) -> dict:
        """Return simple WAV file diagnostics: channels, sample_rate, duration, rms_db, peak.

        This uses the standard library `wave` module and does not require external deps.
        Works only for uncompressed WAV (PCM) files.
        """
        info = {"channels": None, "sample_rate": None, "duration": None, "rms_db": None, "peak": None}
        try:
            import wave, struct, math

            with wave.open(path, 'rb') as wf:
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                nframes = wf.getnframes()
                duration = nframes / float(framerate) if framerate else None

                info.update({"channels": channels, "sample_rate": framerate, "duration": duration})

                # Only handle 1 or 2 byte sample widths (8/16-bit). Read in chunks to avoid huge memory.
                max_amp = float((2 ** (8 * sampwidth - 1)) - 1)
                sum_squares = 0.0
                peak = 0.0
                total_samples = 0
                chunk = 1024
                wf.rewind()
                while True:
                    frames = wf.readframes(chunk)
                    if not frames:
                        break
                    # interpret samples
                    if sampwidth == 1:
                        fmt = f"{len(frames)}B"
                        vals = struct.unpack(fmt, frames)
                        # 8-bit WAV is unsigned: convert to signed centered at 128
                        vals = [v - 128 for v in vals]
                    elif sampwidth == 2:
                        fmt = f"<{len(frames)//2}h"
                        vals = struct.unpack(fmt, frames)
                    else:
                        # unsupported width; bail out
                        raise RuntimeError(f"Unsupported sample width: {sampwidth}")

                    # if multi-channel, vals contains interleaved samples
                    for v in vals:
                        total_samples += 1
                        a = float(v)
                        sum_squares += a * a
                        if abs(a) > peak:
                            peak = abs(a)

                if total_samples > 0:
                    rms = math.sqrt(sum_squares / total_samples)
                    # avoid log of zero
                    if rms <= 0:
                        rms_db = float('-inf')
                    else:
                        rms_db = 20.0 * math.log10(rms / max_amp)
                    peak_rel = peak / max_amp if max_amp else None
                else:
                    rms_db = float('-inf')
                    peak_rel = None

                info.update({"rms_db": rms_db, "peak": peak_rel})
                return info
        except Exception as e:
            logger.debug("STT: _inspect_wav failed: %s", e)
            raise


stt_service = STTService()
