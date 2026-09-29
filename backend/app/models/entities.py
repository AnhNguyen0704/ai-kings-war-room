"""SQLAlchemy entities. Timestamps are UTC; JSON columns hold flexible payloads."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), default="The King")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(32), default="IDLE", index=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Agent(Base):
    """Global agent definition (persona + provider binding). Assigned to rooms via room_agents."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    icon: Mapped[str] = mapped_column(String(16), default="🤖")
    color: Mapped[str] = mapped_column(String(16), default="#38bdf8")
    provider: Mapped[str] = mapped_column(String(32), default="auto")
    model: Mapped[str] = mapped_column(String(128), default="")
    role: Mapped[str] = mapped_column(String(64), default="advisor")
    personality: Mapped[list] = mapped_column(JSON, default=list)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    behavior: Mapped[dict] = mapped_column(JSON, default=dict)
    capabilities: Mapped[list] = mapped_column(JSON, default=list)
    tools: Mapped[list] = mapped_column(JSON, default=list)
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RoomAgent(Base):
    __tablename__ = "room_agents"

    room_id: Mapped[str] = mapped_column(String(36), ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    silenced: Mapped[bool] = mapped_column(Boolean, default=False)


class Debate(Base):
    __tablename__ = "debates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(String(36), ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    task: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(16), default="full")  # full | quick
    phase: Mapped[str] = mapped_column(String(32), default="proposals")
    round: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)  # active|completed|stopped|error
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_room_created", "room_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(String(36), ForeignKey("rooms.id", ondelete="CASCADE"))
    debate_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("debates.id", ondelete="SET NULL"), nullable=True)
    sender_type: Mapped[str] = mapped_column(String(16))  # king | agent | system | judge
    agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    message_type: Mapped[str] = mapped_column(String(16), default="observation")
    content: Mapped[str] = mapped_column(Text, default="")
    reply_to_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    round: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Vote(Base):
    __tablename__ = "votes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    debate_id: Mapped[str] = mapped_column(String(36), ForeignKey("debates.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[str] = mapped_column(String(36), ForeignKey("agents.id", ondelete="CASCADE"))
    choice: Mapped[str] = mapped_column(String(128))  # agent name or "abstain"
    rationale: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    debate_id: Mapped[str] = mapped_column(String(36), ForeignKey("debates.id", ondelete="CASCADE"), unique=True)
    decision: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    open_questions: Mapped[list] = mapped_column(JSON, default=list)
    dissenting_views: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(String(36), ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    debate_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("debates.id", ondelete="SET NULL"), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|running|completed|stopped
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MemoryItem(Base):
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(String(36), ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), default="shared")  # shared | agent_long
    content: Mapped[str] = mapped_column(Text)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EventLog(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_room_created", "room_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[str] = mapped_column(String(36), ForeignKey("rooms.id", ondelete="CASCADE"))
    agent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
