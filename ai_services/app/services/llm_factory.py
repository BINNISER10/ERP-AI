"""Multi-provider LLM factory for the Nexus AI assistant."""
import json
import logging
import os
import re
from abc import ABC, abstractmethod

import google.generativeai as genai
import httpx
import openai
import requests

from app.config import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when an LLM provider cannot generate a response."""


class BaseLLM(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a text response from the given prompt."""


class GeminiLLM(BaseLLM):
    def __init__(self, api_key: str, model: str | None = None):
        self.api_key = api_key
        self.model = model or settings.gemini_model
        genai.configure(api_key=api_key)

    def generate(self, prompt: str) -> str:
        try:
            model = genai.GenerativeModel(model_name=self.model)
            response = model.generate_content(prompt)
            return response.text or ""
        except Exception as exc:
            msg = str(exc)
            if "API_KEY_INVALID" in msg or "PERMISSION_DENIED" in msg:
                raise LLMError("GEMINI_AUTH_ERROR: مفتاح Gemini غير صالح أو منتهي الصلاحية") from exc
            if "QUOTA_EXCEEDED" in msg or "RESOURCE_EXHAUSTED" in msg:
                raise LLMError("GEMINI_QUOTA_ERROR: تجاوزت الحد المسموح من طلبات Gemini") from exc
            raise LLMError(f"GEMINI_ERROR: {msg}") from exc


class OpenAILLM(BaseLLM):
    def __init__(self, api_key: str, model: str | None = None, base_url: str | None = None):
        self.api_key = api_key
        self.model = model or settings.openai_model
        self.base_url = base_url

    def generate(self, prompt: str) -> str:
        try:
            client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                timeout=settings.request_timeout,
            )
            return response.choices[0].message.content or ""
        except openai.AuthenticationError as exc:
            raise LLMError("OPENAI_AUTH_ERROR: مفتاح OpenAI غير صالح") from exc
        except openai.RateLimitError as exc:
            raise LLMError("OPENAI_QUOTA_ERROR: تجاوزت الحد المسموح من طلبات OpenAI") from exc
        except Exception as exc:
            raise LLMError(f"OPENAI_ERROR: {exc}") from exc


class DeepSeekLLM(BaseLLM):
    def __init__(self, api_key: str, model: str | None = None):
        self.api_key = api_key
        self.model = model or settings.deepseek_model

    def generate(self, prompt: str) -> str:
        # DeepSeek uses the OpenAI-compatible API.
        return OpenAILLM(
            api_key=self.api_key,
            model=self.model,
            base_url="https://api.deepseek.com/v1",
        ).generate(prompt)


class OllamaLLM(BaseLLM):
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(self, prompt: str) -> str:
        try:
            url = f"{self.base_url}/api/generate"
            response = requests.post(
                url,
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=settings.request_timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except requests.ConnectionError as exc:
            raise LLMError("OLLAMA_CONNECTION_ERROR: لا يمكن الاتصال بخدمة Ollama") from exc
        except Exception as exc:
            raise LLMError(f"OLLAMA_ERROR: {exc}") from exc


async def _ollama_healthy() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            return response.status_code == 200
    except Exception:
        return False


def get_llm(provider: str | None = None) -> BaseLLM:
    """Return an LLM instance based on the requested or configured provider."""
    name = (provider or settings.ai_provider or "auto").lower()

    if name == "auto":
        # Priority: gemini -> openai -> deepseek -> ollama
        if settings.gemini_api_key:
            return GeminiLLM(settings.gemini_api_key, settings.gemini_model)
        if settings.openai_api_key:
            return OpenAILLM(settings.openai_api_key, settings.openai_model, settings.openai_base_url)
        if settings.deepseek_api_key:
            return DeepSeekLLM(settings.deepseek_api_key, settings.deepseek_model)
        return OllamaLLM(settings.ollama_base_url, settings.ollama_model)

    if name == "gemini":
        if not settings.gemini_api_key:
            raise LLMError("GEMINI_API_KEY not configured")
        return GeminiLLM(settings.gemini_api_key, settings.gemini_model)

    if name == "openai":
        if not settings.openai_api_key:
            raise LLMError("OPENAI_API_KEY not configured")
        return OpenAILLM(settings.openai_api_key, settings.openai_model, settings.openai_base_url)

    if name == "deepseek":
        if not settings.deepseek_api_key:
            raise LLMError("DEEPSEEK_API_KEY not configured")
        return DeepSeekLLM(settings.deepseek_api_key, settings.deepseek_model)

    if name == "ollama":
        return OllamaLLM(settings.ollama_base_url, settings.ollama_model)

    raise LLMError(f"Unknown AI provider: {name}")


def extract_json(text: str) -> dict | list:
    """Extract a JSON object or array from an LLM response, forgiving markdown fences."""
    text = text.strip()
    # Remove markdown code fences if present.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    # Find the first JSON object or array.
    match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise LLMError(f"AI returned invalid JSON: {exc}") from exc
    raise LLMError("AI did not return any JSON")


def generate_json(prompt: str, provider: str | None = None) -> dict | list:
    """Generate a JSON response from the LLM and parse it."""
    llm = get_llm(provider)
    text = llm.generate(prompt)
    return extract_json(text)
