"""
LLM client for CodeGuard.

Supports two providers:
  - Ollama (local, default): Free, private, runs on your machine
  - Groq (cloud): Free tier, fast inference, for cloud deployment

Use get_llm_client() factory to get the right client based on settings.
"""

import json
from typing import Generator, Optional

import requests
from rich.console import Console

from config.settings import settings

console = Console()

# ── Ollama (Local) ──

DEFAULT_OLLAMA_MODEL = "qwen2.5-coder:7b-instruct-q4_K_M"
OLLAMA_BASE_URL = "http://localhost:11434"


class OllamaClient:
    """Client for the Ollama local LLM server."""

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = DEFAULT_OLLAMA_MODEL,
        timeout: int = 300,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.session = requests.Session()
        self.provider = "ollama"

    def is_healthy(self) -> bool:
        """Check if Ollama is running and the model is available."""
        try:
            resp = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code != 200:
                return False
            models = resp.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
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
        """Generate a response from the local LLM."""
        target_model = model or self.model

        payload = {
            "model": target_model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_ctx": 8192,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        if stream:
            return self._stream_generate(payload)
        else:
            return self._blocking_generate(payload)

    def _blocking_generate(self, payload: dict) -> str:
        """Non-streaming generation."""
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


# ── Groq (Cloud) ──

class GroqClient:
    """Client for the Groq cloud LLM API (OpenAI-compatible)."""

    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
        timeout: int = 120,
    ):
        self.api_key = api_key or settings.groq_api_key
        self.model = model or settings.groq_model
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
        self.provider = "groq"

    def is_healthy(self) -> bool:
        """Check if Groq API is reachable and key is valid."""
        try:
            resp = self.session.get(
                "https://api.groq.com/openai/v1/models",
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        """List available Groq models."""
        try:
            resp = self.session.get(
                "https://api.groq.com/openai/v1/models",
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return [m["id"] for m in data.get("data", [])]
        except Exception as e:
            console.print(f"[red]Failed to list Groq models: {e}[/red]")
            return []

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        temperature: float = 0.1,
        stream: bool = False,
    ) -> str | Generator[str, None, None]:
        """Generate a response from the Groq cloud LLM."""
        target_model = model or self.model

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4096,
            "stream": stream,
        }

        if stream:
            return self._stream_generate(payload)
        else:
            return self._blocking_generate(payload)

    def _blocking_generate(self, payload: dict) -> str:
        """Non-streaming generation via Groq API."""
        payload["stream"] = False
        try:
            resp = self.session.post(
                self.GROQ_API_URL,
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout:
            return "⚠️ **Review timed out.** Try a smaller PR."
        except requests.exceptions.ConnectionError:
            return "❌ **Cannot connect to Groq API.** Check your internet connection."
        except Exception as e:
            return f"❌ **Groq LLM Error:** {e}"

    def _stream_generate(self, payload: dict) -> Generator[str, None, None]:
        """Streaming generation via Groq API (SSE)."""
        payload["stream"] = True
        try:
            resp = self.session.post(
                self.GROQ_API_URL,
                json=payload,
                timeout=self.timeout,
                stream=True,
            )
            resp.raise_for_status()

            for line in resp.iter_lines():
                if line:
                    line_str = line.decode("utf-8")
                    if line_str.startswith("data: "):
                        data_str = line_str[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0].get("delta", {})
                            token = delta.get("content", "")
                            if token:
                                yield token
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
        except Exception as e:
            yield f"❌ **Groq LLM Error:** {e}"


# ── Factory ──

def get_llm_client() -> OllamaClient | GroqClient:
    """
    Return the appropriate LLM client based on settings.

    Auto-detects: if GROQ_API_KEY is set, use Groq.
    Otherwise, fall back to Ollama.
    """
    provider = settings.llm_provider.lower()

    if provider == "groq" or (settings.groq_api_key and provider != "ollama"):
        console.print("  [cyan]🌐 Using Groq cloud LLM[/cyan]")
        return GroqClient()
    else:
        console.print("  [cyan]🏠 Using Ollama local LLM[/cyan]")
        return OllamaClient()


# Module-level convenience instance
llm_client = get_llm_client()
