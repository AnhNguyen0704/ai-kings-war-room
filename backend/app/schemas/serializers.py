"""Pydantic-free serializers for API payloads (keeps response shapes in one place)."""
from typing import Any

from app.models.entities import Agent, Decision, EventLog, MemoryItem, Message, Room


def room_out(room: Room) -> dict:
    return {
        "id": str(room.id),
        "name": room.name,
        "state": room.state,
        "created_at": room.created_at.isoformat() if room.created_at else "",
    }


def agent_out(agent: Agent) -> dict:
    return {
        "id": str(agent.id),
        "name": agent.name,
        "icon": agent.icon,
        "color": agent.color,
        "provider": agent.provider,
        "model": agent.model,
        "role": agent.role,
        "personality": agent.personality or [],
        "system_prompt": agent.system_prompt or "",
        "behavior": agent.behavior or {},
        "capabilities": agent.capabilities or [],
        "tools": agent.tools or [],
        "memory_enabled": agent.memory_enabled,
        "active": agent.active,
        "created_at": agent.created_at.isoformat() if agent.created_at else "",
    }


def message_out(msg: Message, agent: Agent | None = None, reply_to: Message | None = None) -> dict:
    sender_names = {"king": "👑 The King", "system": "SYSTEM", "judge": "⚖ JUDGE"}
    if msg.sender_type == "agent" and agent:
        sender_name = agent.name
        color = agent.color
        role = (agent.role or "").replace("_", " ").title()
    else:
        sender_name = sender_names.get(msg.sender_type, "AGENT")
        color = "#f5c542" if msg.sender_type in ("king", "judge") else "#64748b"
        role = ""
    return {
        "id": str(msg.id),
        "room_id": str(msg.room_id),
        "debate_id": str(msg.debate_id) if msg.debate_id else None,
        "sender_type": msg.sender_type,
        "agent_id": str(msg.agent_id) if msg.agent_id else None,
        "sender_name": sender_name,
        "agent_color": color,
        "agent_role": role,
        "message_type": msg.message_type,
        "content": msg.content,
        "reply_to_id": str(msg.reply_to_id) if msg.reply_to_id else None,
        "reply_to": (
            {"id": str(reply_to.id), "sender_name": (reply_to.meta or {}).get("sender_name", "agent")}
            if reply_to
            else None
        ),
        "round": msg.round,
        "meta": msg.meta or {},
        "created_at": msg.created_at.isoformat() if msg.created_at else "",
    }


def decision_out(decision: Decision) -> dict:
    reasoning = decision.reasoning or ""
    return {
        "id": str(decision.id),
        "debate_id": str(decision.debate_id),
        "decision": decision.decision,
        "reasoning": reasoning if isinstance(reasoning, list) else [l for l in reasoning.split("\n") if l.strip()],
        "confidence": decision.confidence,
        "open_questions": decision.open_questions or [],
        "dissenting_views": decision.dissenting_views or [],
        "created_at": decision.created_at.isoformat() if decision.created_at else "",
    }


def memory_out(m: MemoryItem) -> dict:
    return {
        "id": str(m.id),
        "kind": m.kind,
        "agent_id": str(m.agent_id) if m.agent_id else None,
        "content": m.content,
        "importance": m.importance,
        "created_at": m.created_at.isoformat() if m.created_at else "",
    }


def event_out(e: EventLog) -> dict:
    return {
        "id": e.id,
        "room_id": str(e.room_id),
        "agent_id": str(e.agent_id) if e.agent_id else None,
        "event_type": e.event_type,
        "payload": e.payload or {},
        "created_at": e.created_at.isoformat() if e.created_at else "",
    }


def any_out(obj: Any) -> Any:  # pragma: no cover - convenience for typing
    return obj
