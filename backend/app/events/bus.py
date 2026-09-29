"""Event bus abstraction. In-memory implementation for single-process runs,
Redis pub/sub implementation for multi-process deployments (set REDIS_URL)."""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

from app.core.logging import get_logger

logger = get_logger("events")

DEFAULT_ROOM = "__global__"


def make_event(event_type: str, room_id: str, payload: dict) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event": event_type,
        "room_id": room_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "data": payload,
    }


class EventBus:
    """Fan-out pub/sub scoped by room. publish() is safe to call from anywhere."""

    async def start(self) -> None:  # pragma: no cover - interface
        pass

    async def stop(self) -> None:  # pragma: no cover - interface
        pass

    def publish(self, room_id: str, event: dict) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def subscribe(self, room_id: str) -> asyncio.Queue:  # pragma: no cover - interface
        raise NotImplementedError

    def unsubscribe(self, room_id: str, queue: asyncio.Queue) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class InMemoryEventBus(EventBus):
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = {}

    def publish(self, room_id: str, event: dict) -> None:
        for q in list(self._subs.get(room_id, set())):
            q.put_nowait(event)

    def subscribe(self, room_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.setdefault(room_id, set()).add(q)
        return q

    def unsubscribe(self, room_id: str, queue: asyncio.Queue) -> None:
        subs = self._subs.get(room_id)
        if subs:
            subs.discard(queue)
            if not subs:
                self._subs.pop(room_id, None)


class RedisEventBus(EventBus):
    """Room-scoped Redis pub/sub. One background listener feeds local subscriber queues."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis = None
        self._listener_task: asyncio.Task | None = None
        self._subs: dict[str, set[asyncio.Queue]] = {}
        self._channel_prefix = "warroom:room:"

    async def start(self) -> None:
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
        self._listener_task = asyncio.create_task(self._listen(), name="redis-event-listener")
        logger.info("RedisEventBus started url=%s", self._redis_url)

    async def stop(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
        if self._redis:
            await self._redis.aclose()

    def _channel(self, room_id: str) -> str:
        return f"{self._channel_prefix}{room_id}"

    def publish(self, room_id: str, event: dict) -> None:
        if self._redis is None:
            return
        asyncio.ensure_future(self._redis.publish(self._channel(room_id), json.dumps(event, ensure_ascii=False)))

    def subscribe(self, room_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.setdefault(room_id, set()).add(q)
        return q

    def unsubscribe(self, room_id: str, queue: asyncio.Queue) -> None:
        subs = self._subs.get(room_id)
        if subs:
            subs.discard(queue)

    async def _listen(self) -> None:
        pubsub = self._redis.pubsub()
        await pubsub.psubscribe(f"{self._channel_prefix}*")
        async for msg in pubsub.listen():
            if msg is None or msg.get("type") not in ("pmessage", "message"):
                continue
            try:
                event = json.loads(msg["data"])
                room_id = event.get("room_id", "")
            except (json.JSONDecodeError, KeyError):
                continue
            for q in list(self._subs.get(room_id, set())):
                q.put_nowait(event)
