"""Process-wide runtime state (wired once at startup, shared by API + WebSocket layers)."""
from dataclasses import dataclass

from app.core.config import Settings
from app.events.bus import EventBus
from app.providers.manager import ProviderManager
from app.websocket.manager import WSManager


@dataclass
class Runtime:
    settings: Settings
    bus: EventBus
    ws: WSManager
    providers: ProviderManager


_runtime: Runtime | None = None


def init_runtime(settings: Settings, bus: EventBus, ws: WSManager, providers: ProviderManager) -> Runtime:
    global _runtime
    _runtime = Runtime(settings=settings, bus=bus, ws=ws, providers=providers)
    return _runtime


def get_runtime() -> Runtime:
    if _runtime is None:
        raise RuntimeError("Runtime not initialised. App startup has not run.")
    return _runtime
