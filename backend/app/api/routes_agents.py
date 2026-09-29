"""Global agent CRUD (persona + provider binding)."""
import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.models.entities import Agent, RoomAgent
from app.orchestration.registry import peek_controller
from app.schemas.serializers import agent_out

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentCreate(BaseModel):
    name: str
    icon: str = "🤖"
    color: str = "#38bdf8"
    provider: str = "auto"
    model: str = ""
    role: str = "advisor"
    personality: list[str] = Field(default_factory=list)
    system_prompt: str = ""
    behavior: dict = Field(default_factory=dict)
    memory_enabled: bool = True
    active: bool = True


class AgentPatch(AgentCreate):
    name: str | None = None  # type: ignore[assignment]
    role: str | None = None  # type: ignore[assignment]


async def _invalidate_for_agent(agent_id: str, session: AsyncSession) -> None:
    """Reload controllers of rooms containing this agent (skip rooms mid-debate)."""
    room_ids = (
        await session.execute(sa.select(RoomAgent.room_id).where(RoomAgent.agent_id == agent_id))
    ).scalars().all()
    for rid in room_ids:
        controller = peek_controller(rid)
        if controller and (controller.debate_task is None or controller.debate_task.done()):
            await controller.load()


@router.get("")
async def list_agents(session: AsyncSession = Depends(get_session)):
    agents = (await session.execute(sa.select(Agent).order_by(Agent.created_at))).scalars().all()
    return {"agents": [agent_out(a) for a in agents]}


@router.post("", status_code=201)
async def create_agent(body: AgentCreate, session: AsyncSession = Depends(get_session)):
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "name is required")
    exists = (await session.execute(sa.select(Agent).where(Agent.name == name))).scalar_one_or_none()
    if exists:
        raise HTTPException(409, f"Agent '{name}' already exists")
    agent = Agent(**body.model_dump())
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return agent_out(agent)


@router.get("/{agent_id}")
async def get_agent(agent_id: str, session: AsyncSession = Depends(get_session)):
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(404, "Agent not found")
    return agent_out(agent)


@router.patch("/{agent_id}")
async def patch_agent(agent_id: str, body: AgentPatch, session: AsyncSession = Depends(get_session)):
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(404, "Agent not found")
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(agent, key, value)
    await session.commit()
    await session.refresh(agent)
    await _invalidate_for_agent(agent_id, session)
    return agent_out(agent)


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, session: AsyncSession = Depends(get_session)):
    agent = await session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(404, "Agent not found")
    await session.execute(sa.delete(RoomAgent).where(RoomAgent.agent_id == agent_id))
    await session.delete(agent)
    await session.commit()
    await _invalidate_for_agent(agent_id, session)
    return {"ok": True}
