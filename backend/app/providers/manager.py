"""Provider Manager: maps (provider, model) -> LLMProvider instance.

If an API key is missing the manager transparently returns a MockProvider so the
platform stays fully functional; the resolved provider name is surfaced to the UI.
"""
from app.core.config import Settings, get_settings
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.base import LLMProvider
from app.providers.google_provider import GoogleProvider
from app.providers.mock import MockProvider
from app.providers.openai_compat import OpenAICompatProvider

_OPENAI_COMPAT = {
    "openai": ("https://api.openai.com/v1", "openai_api_key"),
    "xai": ("https://api.x.ai/v1", "xai_api_key"),
    "moonshot": ("https://api.moonshot.cn/v1", "moonshot_api_key"),
}


class ProviderManager:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._cache: dict[tuple[str, str], LLMProvider] = {}

    def _build(self, provider: str, model: str) -> LLMProvider:
        s = self.settings
        if provider == "mock":
            return MockProvider(model=model or "mock-1")
        if provider in _OPENAI_COMPAT:
            base_url, key_field = _OPENAI_COMPAT[provider]
            return OpenAICompatProvider(name=provider, model=model, api_key=getattr(s, key_field), base_url=base_url)
        if provider == "anthropic":
            return AnthropicProvider(model=model, api_key=s.anthropic_api_key)
        if provider == "google":
            return GoogleProvider(model=model, api_key=s.google_api_key)
        return MockProvider(model=model or "mock-1", fallback_from=provider)

    def resolve(self, provider: str, model: str) -> LLMProvider:
        """provider='auto' or missing key -> best-effort live provider, else Mock."""
        key = (provider, model)
        if key in self._cache:
            return self._cache[key]

        effective = provider
        effective_model = model
        if provider == "auto":
            effective = next(
                (p for p in ["openai", "anthropic", "google", "xai", "moonshot"] if self._build(p, "").live),
                "mock",
            )
            effective_model = model or self.settings.provider_default_models.get(effective, "")
        elif not model:
            effective_model = self.settings.provider_default_models.get(provider, "")

        built = self._build(effective, effective_model)
        if not built.live:
            built = MockProvider(model=effective_model or "mock-1", fallback_from=provider)
        self._cache[key] = built
        return built

    def resolve_judge(self) -> LLMProvider:
        s = self.settings
        if s.judge_provider != "auto":
            model = s.judge_model or s.provider_default_models.get(s.judge_provider, "")
            built = self._build(s.judge_provider, model)
            return built if built.live else MockProvider(model=model, fallback_from=s.judge_provider)
        for p in ["openai", "anthropic", "google", "xai", "moonshot"]:
            if self._build(p, "").live:
                model = s.judge_model or s.provider_default_models.get(p, "")
                return self._build(p, model)
        return MockProvider(model="mock-judge")

    def judge_label(self) -> str:
        provider = self.resolve_judge()
        return f"{provider.name}:{getattr(provider, 'model', '')}"

    def status(self) -> list[dict]:
        out = [{"name": "mock", "live": True, "kind": "mock"}]
        for p in ["openai", "anthropic", "google", "xai", "moonshot"]:
            out.append({"name": p, "live": self._build(p, "").live, "kind": "llm"})
        return out
