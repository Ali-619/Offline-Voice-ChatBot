import os
import io
import tempfile

PREFERRED_TTS = os.getenv("PREFERRED_TTS", "gtts")


class TTSService:
    def __init__(self):
        self.engine = PREFERRED_TTS.lower()
        # try to import Coqui TTS if requested
        self.coqui_available = False
        if self.engine == "coqui":
            try:
                from TTS.api import TTS  # type: ignore
                self.TTS = TTS
                self.coqui_available = True
            except Exception:
                self.coqui_available = False

    def synthesize(self, text: str) -> bytes:
        """Return MP3 bytes of the synthesized text.

        Uses Coqui TTS if available and configured; otherwise uses gTTS.
        """
        if self.engine == "coqui" and self.coqui_available:
            # Use Coqui TTS to synthesize to file then read as bytes
            tts = self.TTS()
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                path = tmp.name
            tts.tts_to_file(text=text, file_path=path)
            with open(path, "rb") as f:
                data = f.read()
            return data

        # fallback: gTTS
        try:
            from gtts import gTTS
            mp3_fp = io.BytesIO()
            tts = gTTS(text)
            tts.write_to_fp(mp3_fp)
            mp3_fp.seek(0)
            return mp3_fp.read()
        except Exception as e:
            raise RuntimeError("No TTS available: " + str(e))


tts_service = TTSService()
