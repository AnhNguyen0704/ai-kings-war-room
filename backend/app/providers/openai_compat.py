"""OpenAI-compatible REST provider (used for OpenAI, xAI Grok, Moonshot Kimi).
No vendor SDK - plain httpx + SSE parsing, so all adapters stay uniform and light."""
import json
from typing import AsyncIterator

import httpx

from app.core.logging import get_logger
from app.providers.base import ChatMessage, LLMProvider, ProviderError

logger = get_logger("providers")


class OpenAICompatProvider(LLMProvider):
    def __init__(self, name: str, model: str, api_key: str, base_url: str) -> None:
        self.name = name
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.live = bool(api_key)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _payload(self, messages: list[ChatMessage], temperature: float, max_tokens: int, stream: bool) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

    async def stream(
        self, messages: list[ChatMessage], *, temperature: float = 0.7, max_tokens: int = 1024
    ) -> AsyncIterator[str]:
        url = f"{self.base_url}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30, read=300)) as client:
                async with client.stream(
                    "POST", url, headers=self._headers(), json=self._payload(messages, temperature, max_tokens, True)
                ) as resp:
                    if resp.status_code != 200:
                        body = (await resp.aread())[:400].decode("utf-8", "ignore")
                        raise ProviderError(f"{self.name} HTTP {resp.status_code}: {body}")
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        delta = (chunk.get("choices") or [{}])[0].get("delta", {})
                        text = delta.get("content")
                        if text:
                            yield text
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.name} connection error: {exc}") from exc
