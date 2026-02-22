"""
Ollama REST API client for CodeGuard.

Thin wrapper for local LLM inference via Ollama.
Supports both streaming and non-streaming generation.
"""

from typing import Generator, Optional

import requests
from rich.console import Console

from config.settings import settings

console = Console()

# Default model as per architecture spec
DEFAULT_MODEL = "qwen2.5-coder:7b-instruct-q4_K_M"
OLLAMA_BASE_URL = "http://localhost:11434"


class OllamaClient:
    """Client for the Ollama local LLM server."""

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: int = 300,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.session = requests.Session()

    def is_healthy(self) -> bool:
        """Check if Ollama is running and the model is available."""
        try:
            resp = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code != 200:
                return False
            models = resp.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            # Check if our model (or a prefix of it) is available
            return any(
                self.model in name or name.startswith(self.model.split(":")[0])
                for name in model_names
            )
        except Exception:
            return False

    def list_models(self) -> list[str]:
        """List all locally available models."""
        try:
            resp = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            return [m.get("name", "") for m in models]
        except Exception as e:
            console.print(f"[red]Failed to list models: {e}[/red]")
            return []

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        temperature: float = 0.1,
        stream: bool = False,
    ) -> str | Generator[str, None, None]:
        """
        Generate a response from the LLM.

        Args:
            prompt: The user prompt / full review prompt.
            system_prompt: System-level instructions.
            model: Override model (defaults to self.model).
            temperature: Sampling temperature (0.1 for deterministic reviews).
            stream: If True, returns a generator yielding tokens.

        Returns:
            Complete response string, or generator of token strings if streaming.
        """
        target_model = model or self.model

        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_ctx": 8192,  # Context window
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        if stream:
            return self._stream_generate(payload)
        else:
            return self._blocking_generate(payload)

    def _blocking_generate(self, payload: dict) -> str:
        """Non-streaming generation — wait for full response."""
        payload["stream"] = False
        try:
            resp = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
        except requests.exceptions.Timeout:
            return "⚠️ **Review timed out.** The diff may be too large. Try a smaller PR or increase the timeout."
        except requests.exceptions.ConnectionError:
            return "❌ **Cannot connect to Ollama.** Make sure Ollama is running: `ollama serve`"
        except Exception as e:
            return f"❌ **LLM Error:** {e}"

    def _stream_generate(self, payload: dict) -> Generator[str, None, None]:
        """Streaming generation — yield tokens as they arrive."""
        payload["stream"] = True
        try:
            resp = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
                stream=True,
            )
            resp.raise_for_status()

            for line in resp.iter_lines():
                if line:
                    import json
                    data = json.loads(line)
                    token = data.get("response", "")
                    if token:
                        yield token
                    if data.get("done", False):
                        break
        except requests.exceptions.ConnectionError:
            yield "❌ **Cannot connect to Ollama.** Make sure Ollama is running: `ollama serve`"
        except Exception as e:
            yield f"❌ **LLM Error:** {e}"


# Module-level convenience instance
ollama_client = OllamaClient()
