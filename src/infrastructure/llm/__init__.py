"""LLM service — Ollama chat + embeddings via httpx.

Uses httpx async for non-blocking IO.  Tracks token usage for observability.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

from src.core.config import get_settings

logger = structlog.get_logger(__name__)


class OllamaLLMService:
    """Self-hosted LLM calls via Ollama REST API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.ollama_base_url
        self._chat_model = settings.ollama_chat_model
        self._embed_model = settings.ollama_embed_model
        self._timeout = settings.ollama_timeout

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.1,
        format_json: bool = False,
    ) -> dict[str, Any]:
        """Send chat completion request. Returns full Ollama response dict."""
        model = model or self._chat_model
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if format_json:
            payload["format"] = "json"

        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
        elapsed_ms = (time.perf_counter() - start) * 1000

        data = resp.json()
        data["_latency_ms"] = elapsed_ms
        data["_model"] = model

        logger.info(
            "ollama_chat_completed",
            model=model,
            latency_ms=round(elapsed_ms, 1),
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
        )
        return data

    async def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        model = model or self._embed_model
        embeddings: list[list[float]] = []

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for text_item in texts:
                payload = {"model": model, "input": text_item}
                resp = await client.post(f"{self._base_url}/api/embed", json=payload)
                resp.raise_for_status()
                data = resp.json()
                # Ollama returns {"embeddings": [[...]]} 
                embs = data.get("embeddings", [])
                if embs:
                    embeddings.append(embs[0])
                else:
                    embeddings.append([0.0] * 768)

        logger.info("ollama_embeddings_generated", count=len(embeddings), model=model)
        return embeddings

    async def is_available(self) -> bool:
        """Check if Ollama is responding."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """List available models."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []
