"""Async database engine + session factory. SQLite for zero-config dev, PostgreSQL via DATABASE_URL."""
from pathlib import Path
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _build_engine():
    url = get_settings().database_url
    kwargs: dict = {"future": True}
    if url.startswith("sqlite"):
        from sqlalchemy.pool import NullPool

        kwargs["connect_args"] = {"timeout": 30}
        kwargs["poolclass"] = NullPool  # connections must not outlive an event loop (tests / reload)
    return create_async_engine(url, **kwargs)


engine = _build_engine()
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Dev convenience: create schema directly. Production (docker) uses Alembic instead."""
    url = get_settings().database_url
    if url.startswith("sqlite"):
        db_path = url.split("///")[-1]
        parent = Path(db_path).parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
    # Import models so metadata is populated.
    import app.models.entities  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
