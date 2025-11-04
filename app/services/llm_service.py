import os
import logging
from typing import List

# Try to import ctransformers for GGUF format support
_HAS_CTRANSFORMERS = False
try:
    from ctransformers import AutoModelForCausalLM
    _HAS_CTRANSFORMERS = True
except Exception:
    pass

logger = logging.getLogger(__name__)


class LLMService:
    """Local LLM service. Loads a local model path (Hugging Face format) and runs generation.

    Controls via environment variables:
    - LOCAL_MODEL_PATH: path or model id to load from (defaults to 'mistralai/Mistral-7B-Instruct')
    - LOCAL_MODEL_DEVICE: 'cpu' or 'cuda' (auto-detected if not set)
    - LOCAL_MAX_NEW_TOKENS: default max new tokens for generation

    If transformers/torch are not installed, generate() falls back to a simple echo.
    """

    def __init__(self):
        self.model_path = os.getenv("LOCAL_MODEL_PATH", "models/mistral-7b.gguf")
        if not os.path.isabs(self.model_path):
            # If path is relative, make it absolute from the project root
            self.model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", self.model_path))
        
        self.max_new_tokens = int(os.getenv("LOCAL_MAX_NEW_TOKENS", "512"))
        self.model = None
        self._ready = False

        if not _HAS_CTRANSFORMERS:
            logger.warning("ctransformers not available — LLM will fallback to echo responses. Install with: pip install ctransformers")
            return

        logger.info(f"Loading local GGUF model: %s", self.model_path)
        try:
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Model file not found: {self.model_path}")

            # Load the GGUF model - uses CPU by default, optimized for inference
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                model_type="mistral",
                context_length=4096,  # Mistral's context window
                gpu_layers=0  # Force CPU as requested
            )
            self._ready = True
            logger.info("Model loaded successfully (CPU)")
        except Exception as e:
            logger.exception("Failed to load GGUF model: %s", e)
            self._ready = False

    def generate(self, prompt: str, history: List[dict] | None = None) -> str:
        """Generate text from prompt + history. Returns assistant text string.

        This keeps the same simple interface as before.
        """
        full_prompt = self._build_prompt(prompt, history)

        if not _HAS_CTRANSFORMERS or not self._ready:
            # fallback simple echo responder
            logger.warning("Local model not available, returning fallback echo response")
            return "Echo: " + prompt

        try:
            # Generate with ctransformers - it handles tokenization internally
            response = self.model(
                full_prompt,
                max_new_tokens=self.max_new_tokens,
                temperature=0.7,
                stop=["user:", "User:", "</s>"],  # Stop at these tokens
                stream=False  # Get complete response
            )
            # ctransformers returns the full response including the prompt
            # try to extract just the assistant's response
            text = response.split("assistant:")[-1].strip()
            return text
        except Exception as e:
            logger.exception("Generation error: %s", e)
            return ""

    def _build_prompt(self, prompt: str, history: List[dict] | None):
        parts = []
        if history:
            for item in history:
                role = item.get("role")
                text = item.get("text")
                parts.append(f"{role}: {text}")
        parts.append("user: " + prompt)
        parts.append("assistant:")
        return "\n".join(parts)


llm_service = LLMService()
