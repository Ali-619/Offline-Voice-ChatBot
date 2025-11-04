"""Expose service singletons but import them lazily with safe fallbacks.

This avoids hard import-time failures when optional dependencies (torch, openai, etc.)
are not installed during development or syntax checks.
"""
import logging

logger = logging.getLogger(__name__)

def _import_service(name: str):
	try:
		module = __import__(f"app.services.{name}", fromlist=[name])
		return getattr(module, f"{name}")
	except Exception as e:
		logger.warning("Could not import service %s: %s", name, e)
		return None

# Try to import; if not available the variables will be None and callers should handle it.
stt_service = _import_service("stt_service")
llm_service = _import_service("llm_service")
tts_service = _import_service("tts_service")

__all__ = ["stt_service", "llm_service", "tts_service"]
