"""Room CRUD, history, memory, events, commands and chat endpoints."""
import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_room
from app.db.database import get_session
from app.models.entities import Agent, EventLog, MemoryItem, Message, Room, RoomAgent
from app.orchestration.registry import get_controller, peek_controller
from app.schemas.serializers import (
    agent_out,
    decision_out,
    event_out,
    memory_out,
    message_out,
    room_out,
)

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


class RoomCreate(BaseModel):
    name: str


class RoomPatch(BaseModel):
    name: str | None = None


class ChatIn(BaseModel):
    content: str


class CommandIn(BaseModel):
    command: str
    args: str = ""


class AddAgentIn(BaseModel):
    agent_id: str


@router.get("")
async def list_rooms(session: AsyncSession = Depends(get_session)):
    rooms = (await session.execute(sa.select(Room).order_by(Room.created_at))).scalars().all()
    counts = dict(
        (row[0], row[1])
        for row in (
            await session.execute(sa.select(Message.room_id, sa.func.count(Message.id)).group_by(Message.room_id))
        ).all()
    )
    agent_counts = dict(
        (row[0], row[1])
        for row in (await session.execute(sa.select(RoomAgent.room_id, sa.func.count()).group_by(RoomAgent.room_id))).all()
    )
    return {
        "rooms": [
            {**room_out(r), "message_count": counts.get(r.id, 0), "agent_count": agent_counts.get(r.id, 0)}
            for r in rooms
        ]
    }


@router.post("", status_code=201)
async def create_room(body: RoomCreate, session: AsyncSession = Depends(get_session)):
    name = body.name.strip() or "Unnamed Room"
    room = Room(name=name)
    session.add(room)
    await session.flush()
    agents = (await session.execute(sa.select(Agent).where(Agent.active).order_by(Agent.created_at))).scalars().all()
    for i, agent in enumerate(agents):
        session.add(RoomAgent(room_id=room.id, agent_id=agent.id, position=i))
    await session.commit()
    await session.refresh(room)
    return room_out(room)


@router.get("/{room_id}")
async def get_room(room_id: str, session: AsyncSession = Depends(get_session)):
    await require_room(room_id, session)
    controller = await get_controller(room_id)
    return await controller.snapshot()


@router.patch("/{room_id}")
async def patch_room(room_id: str, body: RoomPatch, session: AsyncSession = Depends(get_session)):
    room = await require_room(room_id, session)
    if body.name is not None and body.name.strip():
        room.name = body.name.strip()
        await session.commit()
    return room_out(room)


@router.delete("/{room_id}")
async def delete_room(room_id: str, session: AsyncSession = Depends(get_session)):
    room = await require_room(room_id, session)
    from app.orchestration.registry import invalidate

    await invalidate(room_id)
    await session.delete(room)
    await session.commit()
    return {"ok": True}


@router.post("/{room_id}/reset")
async def reset_room(room_id: str, session: AsyncSession = Depends(get_session)):
    await require_room(room_id, session)
    controller = await get_controller(room_id)
    await controller.reset_room()
    return await controller.snapshot()


@router.get("/{room_id}/messages")
async def get_messages(
    room_id: str, limit: int = 200, session: AsyncSession = Depends(get_session)
):
    await require_room(room_id, session)
    limit = max(1, min(limit, 500))
    rows = (
        await session.execute(
            sa.select(Message, Agent)
            .outerjoin(Agent, Agent.id == Message.agent_id)
            .where(Message.room_id == room_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
    ).all()
    reply_ids = {str(m.reply_to_id) for m, _ in rows if m.reply_to_id}
    replies: dict[str, Message] = {}
    if reply_ids:
        for m in (
            await session.execute(sa.select(Message).where(Message.id.in_(list(reply_ids))))
        ).scalars():
            replies[str(m.id)] = m
    out = [message_out(m, agent, replies.get(str(m.reply_to_id)) if m.reply_to_id else None) for m, agent in reversed(rows)]
    return {"messages": out}


@router.get("/{room_id}/events")
async def get_events(room_id: str, limit: int = 100, session: AsyncSession = Depends(get_session)):
    await require_room(room_id, session)
    limit = max(1, min(limit, 500))
    events = (
        await session.execute(
            sa.select(EventLog)
            .where(EventLog.room_id == room_id)
            .order_by(EventLog.id.desc())
            .limit(limit)
        )
    ).scalars()
    return {"events": [event_out(e) for e in reversed(events.all())]}


@router.get("/{room_id}/memories")
async def get_memories(room_id: str, session: AsyncSession = Depends(get_session)):
    await require_room(room_id, session)
    rows = (
        await session.execute(
            sa.select(MemoryItem)
            .where(MemoryItem.room_id == room_id)
            .order_by(MemoryItem.created_at.desc())
            .limit(100)
        )
    ).scalars()
    return {"memories": [memory_out(m) for m in rows.all()]}


@router.get("/{room_id}/decision")
async def get_decision(room_id: str, session: AsyncSession = Depends(get_session)):
    from app.models.entities import Debate

    await require_room(room_id, session)
    row = (
        await session.execute(
            sa.select(Decision)
            .join(Debate, Debate.id == Decision.debate_id)
            .where(Debate.room_id == room_id)
            .order_by(Decision.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return {"decision": decision_out(row) if row else None}


@router.post("/{room_id}/chat")
async def post_chat(room_id: str, body: ChatIn, session: AsyncSession = Depends(get_session)):
    await require_room(room_id, session)
    controller = await get_controller(room_id)
    await controller.handle_king_text(body.content)
    return {"ok": True}


@router.post("/{room_id}/commands")
async def post_command(room_id: str, body: CommandIn, session: AsyncSession = Depends(get_session)):
    await require_room(room_id, session)
    controller = await get_controller(room_id)
    await controller.dispatch_command(body.command, body.args)
    return {"ok": True}


@router.post("/{room_id}/agents", status_code=201)
async def add_agent_to_room(room_id: str, body: AddAgentIn, session: AsyncSession = Depends(get_session)):
    await require_room(room_id, session)
    agent = await session.get(Agent, body.agent_id)
    if agent is None:
        raise HTTPException(404, "Agent not found")
    existing = (
        await session.execute(
            sa.select(RoomAgent).where(RoomAgent.room_id == room_id, RoomAgent.agent_id == body.agent_id)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "Agent already in room")
    position = (
        await session.execute(sa.select(sa.func.count()).select_from(RoomAgent).where(RoomAgent.room_id == room_id))
    ).scalar_one()
    session.add(RoomAgent(room_id=room_id, agent_id=body.agent_id, position=position))
    await session.commit()
    controller = await get_controller(room_id)
    await controller.load()
    return {"ok": True}


@router.delete("/{room_id}/agents/{agent_id}")
async def remove_agent_from_room(room_id: str, agent_id: str, session: AsyncSession = Depends(get_session)):
    await require_room(room_id, session)
    await session.execute(sa.delete(RoomAgent).where(RoomAgent.room_id == room_id, RoomAgent.agent_id == agent_id))
    await session.commit()
    controller = peek_controller(room_id)
    if controller:
        await controller.load()
    return {"ok": True}
