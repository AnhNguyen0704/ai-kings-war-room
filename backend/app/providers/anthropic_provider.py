"""Anthropic Claude REST provider (Messages API, SSE streaming)."""
import json
from typing import AsyncIterator

import httpx

from app.providers.base import ChatMessage, LLMProvider, ProviderError

_API_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str, api_key: str) -> None:
        self.name = "anthropic"
        self.model = model
        self.api_key = api_key

    @property
    def live(self) -> bool:
        return bool(self.api_key)

    async def stream(
        self, messages: list[ChatMessage], *, temperature: float = 0.7, max_tokens: int = 1024
    ) -> AsyncIterator[str]:
        system_parts = [m.content for m in messages if m.role == "system"]
        turns = [
            {"role": m.role if m.role in ("user", "assistant") else "user", "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]
        payload: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": turns or [{"role": "user", "content": ""}],
            "stream": True,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": _API_VERSION,
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30, read=300)) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as resp:
                    if resp.status_code != 200:
                        body = (await resp.aread())[:400].decode("utf-8", "ignore")
                        raise ProviderError(f"anthropic HTTP {resp.status_code}: {body}")
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        try:
                            event = json.loads(line[5:].strip())
                        except json.JSONDecodeError:
                            continue
                        if event.get("type") == "content_block_delta":
                            text = event.get("delta", {}).get("text")
                            if text:
                                yield text
                        elif event.get("type") == "error":
                            raise ProviderError(f"anthropic stream error: {event}")
        except httpx.HTTPError as exc:
            raise ProviderError(f"anthropic connection error: {exc}") from exc
