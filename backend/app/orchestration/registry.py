"""Room controller registry: one live RoomController per room, created on demand."""
import asyncio

from app.core.runtime import get_runtime
from app.orchestration.controller import RoomController

_controllers: dict[str, RoomController] = {}
_lock = asyncio.Lock()


async def get_controller(room_id: str) -> RoomController:
    async with _lock:
        controller = _controllers.get(room_id)
        if controller is None:
            controller = RoomController(room_id)
            await controller.load()
            _controllers[room_id] = controller
            controller.start_bridge()
        return controller


def peek_controller(room_id: str) -> RoomController | None:
    return _controllers.get(room_id)


async def invalidate(room_id: str) -> None:
    """Drop the cached controller (e.g. after agent edits or room reset)."""
    async with _lock:
        controller = _controllers.pop(room_id, None)
    if controller:
        await controller.shutdown()


async def reset_all() -> None:
    """Used by tests to avoid cross-event-loop state."""
    async with _lock:
        controllers = list(_controllers.values())
        _controllers.clear()
    for c in controllers:
        await c.shutdown()
