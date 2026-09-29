"""Realtime WebSocket endpoint: /ws/rooms/{room_id}

Inbound: {"type": "chat", "content": "..."} | {"type": "command", "command": "stop", "args": ""} | {"type": "ping"}
Outbound: bus events forwarded by the room's controller bridge (message_new/delta/complete,
agent_status, room_state, debate_phase, vote_cast, decision, system_notice, error).
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.runtime import get_runtime
from app.orchestration.registry import get_controller

router = APIRouter()


@router.websocket("/ws/rooms/{room_id}")
async def room_ws(websocket: WebSocket, room_id: str):
    rt = get_runtime()
    try:
        controller = await get_controller(room_id)
    except KeyError:
        await websocket.accept()
        await websocket.send_json({"event": "error", "room_id": room_id, "data": {"message": "Room not found"}})
        await websocket.close(code=4404)
        return

    await rt.ws.connect(room_id, websocket)
    try:
        # Initial sync so late joiners see current state.
        await websocket.send_json(
            {
                "event": "room_state",
                "room_id": room_id,
                "data": {"state": controller.room.state if controller.room else "IDLE"},
            }
        )
        for runtime in controller.runtimes.values():
            await websocket.send_json(
                {
                    "event": "agent_status",
                    "room_id": room_id,
                    "data": {
                        "agent_id": runtime.profile.id,
                        "name": runtime.profile.name,
                        "status": runtime.status,
                        "silenced": runtime.profile.silenced,
                    },
                }
            )
        while True:
            data = await websocket.receive_json()
            mtype = data.get("type")
            if mtype == "chat":
                await controller.handle_king_text(str(data.get("content", "")))
            elif mtype == "command":
                command = str(data.get("command", "help")).strip().lstrip("/")
                args = str(data.get("args", ""))
                await controller.handle_king_text(f"/{command} {args}".strip())
            elif mtype == "ping":
                await websocket.send_json({"event": "pong", "room_id": room_id, "data": {}})
            else:
                await websocket.send_json(
                    {"event": "error", "room_id": room_id, "data": {"message": f"unknown type {mtype}"}}
                )
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        rt.ws.disconnect(room_id, websocket)
        raise
    finally:
        rt.ws.disconnect(room_id, websocket)
