"""Google Gemini REST provider (generateContent, SSE streaming)."""
import json
from typing import AsyncIterator

import httpx

from app.providers.base import ChatMessage, LLMProvider, ProviderError

_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GoogleProvider(LLMProvider):
    def __init__(self, model: str, api_key: str) -> None:
        self.name = "google"
        self.model = model
        self.api_key = api_key

    @property
    def live(self) -> bool:
        return bool(self.api_key)

    def _build(self, messages: list[ChatMessage], temperature: float, max_tokens: int) -> dict:
        system_parts = [m.content for m in messages if m.role == "system"]
        contents = [
            {"role": m.role if m.role in ("user", "assistant", "model") else "user", "parts": [{"text": m.content}]}
            for m in messages
            if m.role != "system"
        ]
        payload: dict = {
            "contents": contents or [{"role": "user", "parts": [{"text": ""}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        return payload

    async def stream(
        self, messages: list[ChatMessage], *, temperature: float = 0.7, max_tokens: int = 1024
    ) -> AsyncIterator[str]:
        action = "streamGenerateContent?alt=sse&key="
        url = f"{_BASE}/models/{self.model}:{action}{self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30, read=300)) as client:
                async with client.stream("POST", url, json=self._build(messages, temperature, max_tokens)) as resp:
                    if resp.status_code != 200:
                        body = (await resp.aread())[:400].decode("utf-8", "ignore")
                        raise ProviderError(f"google HTTP {resp.status_code}: {body}")
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        try:
                            event = json.loads(line[5:].strip())
                        except json.JSONDecodeError:
                            continue
                        for candidate in event.get("candidates", []):
                            for part in candidate.get("content", {}).get("parts", []):
                                text = part.get("text")
                                if text:
                                    yield text
        except httpx.HTTPError as exc:
            raise ProviderError(f"google connection error: {exc}") from exc
