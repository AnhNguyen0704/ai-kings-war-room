"""AI King's War Room - FastAPI application entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_agents, routes_health, routes_rooms, ws
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.runtime import init_runtime
from app.db.database import init_db
from app.db.seed import seed_defaults
from app.events.bus import InMemoryEventBus, RedisEventBus
from app.providers.manager import ProviderManager
from app.websocket.manager import WSManager

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.debug)
    bus = RedisEventBus(settings.redis_url) if settings.redis_url else InMemoryEventBus()
    await bus.start()
    init_runtime(settings=settings, bus=bus, ws=WSManager(), providers=ProviderManager(settings))
    await init_db()
    await seed_defaults()
    logger.info("AI King's War Room backend ready (bus=%s)", type(bus).__name__)
    yield
    await bus.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(routes_health.router)
    app.include_router(routes_rooms.router)
    app.include_router(routes_agents.router)
    app.include_router(ws.router)
    return app


app = create_app()


async def setup_for_tests() -> FastAPI:
    """Initialise DB + runtime state without running the server (used by the test suite)."""
    settings = get_settings()
    configure_logging(False)
    bus = InMemoryEventBus()
    await bus.start()
    init_runtime(settings=settings, bus=bus, ws=WSManager(), providers=ProviderManager(settings))
    await init_db()
    await seed_defaults()
    return app
