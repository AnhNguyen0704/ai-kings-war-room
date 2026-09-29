"""WebSocket connection manager: tracks sockets per room, broadcasts JSON events."""
import json

from fastapi import WebSocket

from app.core.logging import get_logger

logger = get_logger("ws")


class WSManager:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = {}

    async def connect(self, room_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._rooms.setdefault(room_id, set()).add(ws)
        logger.debug("ws connect room=%s sockets=%d", room_id, len(self._rooms[room_id]))

    def disconnect(self, room_id: str, ws: WebSocket) -> None:
        sockets = self._rooms.get(room_id)
        if sockets:
            sockets.discard(ws)
            if not sockets:
                self._rooms.pop(room_id, None)

    def connection_count(self, room_id: str | None = None) -> int:
        if room_id:
            return len(self._rooms.get(room_id, set()))
        return sum(len(s) for s in self._rooms.values())

    async def send_to_room(self, room_id: str, payload: dict) -> None:
        text = json.dumps(payload, ensure_ascii=False, default=str)
        for ws in list(self._rooms.get(room_id, set())):
            try:
                await ws.send_text(text)
            except Exception:
                self.disconnect(room_id, ws)
