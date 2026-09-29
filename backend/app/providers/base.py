"""LLM provider abstraction. Agents depend on this interface only, never on a vendor SDK."""
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


class ProviderError(Exception):
    """Raised for timeout / rate-limit / auth / malformed-response failures."""


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMProvider(ABC):
    name: str = "base"
    live: bool = True  # False when running as a fallback without credentials

    @abstractmethod
    async def stream(
        self, messages: list[ChatMessage], *, temperature: float = 0.7, max_tokens: int = 1024
    ) -> AsyncIterator[str]:
        """Yield incremental text chunks."""

    async def generate(
        self, messages: list[ChatMessage], *, temperature: float = 0.7, max_tokens: int = 1024
    ) -> str:
        parts: list[str] = []
        async for chunk in self.stream(messages, temperature=temperature, max_tokens=max_tokens):
            parts.append(chunk)
        return "".join(parts)


async def with_timeout(aw, seconds: float, provider_name: str):
    try:
        return await asyncio.wait_for(aw, timeout=seconds)
    except asyncio.TimeoutError as exc:
        raise ProviderError(f"{provider_name} timeout after {seconds}s") from exc
