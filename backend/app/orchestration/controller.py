"""RoomController: the live state of one room.

Owns agent runtimes, the running debate task, command handling, event emission
(persisted to the events table for the debug log) and the bus->websocket bridge.
"""
import asyncio
import json

import sqlalchemy as sa

from app.agents.profile import AgentProfile
from app.agents.runtime import AgentRuntime, TurnContext
from app.core.logging import get_logger
from app.core.runtime import get_runtime
from app.db.database import async_session_factory
from app.events.bus import make_event
from app.events.types import DebatePhase, EventType, MessageTypes, RoomState
from app.models.entities import (
    Agent,
    Debate,
    Decision,
    EventLog,
    MemoryItem,
    Message,
    Room,
    RoomAgent,
    Task,
    Vote,
)
from app.orchestration.commands import COMMAND_HELP, parse_command
from app.orchestration.debate_engine import DebateEngine

logger = get_logger("controller")


class RoomController:
    def __init__(self, room_id: str) -> None:
        self.room_id = room_id
        self.room: Room | None = None
        self.runtimes: dict[str, AgentRuntime] = {}
        self.order: list[str] = []
        self.stop_event = asyncio.Event()
        self.debate_task: asyncio.Task | None = None
        self.current_engine: DebateEngine | None = None
        self.current_debate_id: str | None = None
        self.force_request: str | None = None  # "vote" | "judge"
        self._bridge_task: asyncio.Task | None = None
        self._bridge_queue = None

    # ------------------------------------------------------------------ setup

    async def load(self) -> None:
        async with async_session_factory() as session:
            self.room = await session.get(Room, self.room_id)
            if self.room is None:
                raise KeyError(f"room {self.room_id} not found")
            rows = (
                await session.execute(
                    sa.select(RoomAgent, Agent)
                    .join(Agent, Agent.id == RoomAgent.agent_id)
                    .where(RoomAgent.room_id == self.room_id)
                    .order_by(RoomAgent.position)
                )
            ).all()
        rt = get_runtime()
        self.runtimes = {}
        self.order = []
        for room_agent, agent in rows:
            profile = AgentProfile.from_entity(agent, silenced=room_agent.silenced)
            provider = rt.providers.resolve(profile.provider, profile.model)
            self.runtimes[profile.id] = AgentRuntime(profile, provider, provider.name)
            self.order.append(profile.id)

    def start_bridge(self) -> None:
        """Forward every bus event for this room to all connected websockets."""
        rt = get_runtime()
        self._bridge_queue = rt.bus.subscribe(self.room_id)

        async def _bridge() -> None:
            try:
                while True:
                    evt = await self._bridge_queue.get()
                    await rt.ws.send_to_room(self.room_id, evt)
            except asyncio.CancelledError:
                pass
            finally:
                rt.bus.unsubscribe(self.room_id, self._bridge_queue)

        self._bridge_task = asyncio.create_task(_bridge(), name=f"bridge:{self.room_id}")

    async def shutdown(self) -> None:
        self.stop_event.set()
        if self.debate_task and not self.debate_task.done():
            self.debate_task.cancel()
            try:
                await self.debate_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._bridge_task:
            self._bridge_task.cancel()
            try:
                await self._bridge_task
            except asyncio.CancelledError:
                pass

    # ------------------------------------------------------------------ emit

    def emit(self, event_type: str, data: dict, persist: bool = True) -> None:
        rt = get_runtime()
        evt = make_event(event_type, self.room_id, data)
        rt.bus.publish(self.room_id, evt)
        if persist and event_type != EventType.MESSAGE_DELTA:
            asyncio.create_task(self._persist_event(event_type, data))

    async def _persist_event(self, event_type: str, data: dict) -> None:
        try:
            async with async_session_factory() as session:
                session.add(
                    EventLog(
                        room_id=self.room_id,
                        agent_id=data.get("agent_id"),
                        event_type=event_type,
                        payload=json.loads(json.dumps(data, ensure_ascii=False, default=str)),
                    )
                )
                await session.commit()
        except Exception:  # noqa: BLE001 - the debug log must never break the flow
            logger.exception("failed to persist event %s", event_type)

    async def set_room_state(self, state: str) -> None:
        async with async_session_factory() as session:
            room = await session.get(Room, self.room_id)
            if room:
                room.state = state
                await session.commit()
        if self.room:
            self.room.state = state
        self.emit(EventType.ROOM_STATE, {"state": state})

    async def set_debate_phase(self, debate_id: str, phase: str, round_no: int) -> None:
        async with async_session_factory() as session:
            debate = await session.get(Debate, debate_id)
            if debate:
                debate.phase = phase
                debate.round = round_no
                await session.commit()
        self.emit(
            EventType.DEBATE_PHASE,
            {"debate_id": debate_id, "phase": phase, "round": round_no},
        )

    async def system_message(self, content: str, message_type: str = MessageTypes.SYSTEM) -> None:
        async with async_session_factory() as session:
            msg = Message(room_id=self.room_id, sender_type="system", message_type=message_type, content=content)
            session.add(msg)
            await session.commit()
            await session.refresh(msg)
            payload = self._message_payload(msg)
        self.emit(EventType.MESSAGE_NEW, payload, persist=False)

    def _message_payload(self, msg: Message) -> dict:
        return {
            "id": str(msg.id),
            "sender_type": msg.sender_type,
            "agent_id": str(msg.agent_id) if msg.agent_id else None,
            "sender_name": {"king": "👑 The King", "system": "SYSTEM", "judge": "⚖ JUDGE"}.get(
                msg.sender_type, "AGENT"
            ),
            "agent_color": "#f5c542" if msg.sender_type in ("king", "judge") else "#64748b",
            "agent_role": "",
            "message_type": msg.message_type,
            "content": msg.content,
            "reply_to_id": str(msg.reply_to_id) if msg.reply_to_id else None,
            "meta": msg.meta or {},
            "created_at": msg.created_at.isoformat() if msg.created_at else "",
            "streaming": False,
        }

    # ------------------------------------------------------------- data reads

    async def get_transcript(self, limit: int | None = None) -> list[dict]:
        limit = limit or get_runtime().settings.transcript_window
        async with async_session_factory() as session:
            rows = (
                await session.execute(
                    sa.select(Message, Agent)
                    .outerjoin(Agent, Agent.id == Message.agent_id)
                    .where(Message.room_id == self.room_id)
                    .order_by(Message.created_at.desc(), Message.id.desc())
                    .limit(limit)
                )
            ).all()
        out = []
        for msg, agent in reversed(rows):
            sender = agent.name if agent else {"king": "The King", "system": "SYSTEM", "judge": "JUDGE"}.get(
                msg.sender_type, "AGENT"
            )
            out.append(
                {
                    "id": str(msg.id),
                    "sender_name": sender,
                    "sender_type": msg.sender_type,
                    "message_type": msg.message_type,
                    "content": msg.content,
                }
            )
        return out

    async def get_memory_bullets(self) -> list[str]:
        async with async_session_factory() as session:
            rows = (
                await session.execute(
                    sa.select(MemoryItem)
                    .where(MemoryItem.room_id == self.room_id)
                    .order_by(MemoryItem.created_at.desc())
                    .limit(10)
                )
            ).scalars()
            return [m.content for m in reversed(rows.all())]

    # ------------------------------------------------------------ king input

    async def handle_king_text(self, content: str) -> None:
        content = (content or "").strip()
        if not content:
            return
        cmd = parse_command(content)
        message_type = MessageTypes.COMMAND if cmd.name != "chat" else MessageTypes.TASK
        async with async_session_factory() as session:
            msg = Message(room_id=self.room_id, sender_type="king", message_type=message_type, content=content)
            session.add(msg)
            await session.commit()
            await session.refresh(msg)
            payload = self._message_payload(msg)
        self.emit(EventType.MESSAGE_NEW, payload, persist=False)
        await self.dispatch_command(cmd.name, cmd.args)

    async def dispatch_command(self, name: str, args: str) -> None:
        if name in ("chat", "debate"):
            await self.start_debate(args, mode="full")
        elif name == "ask":
            await self.start_debate(args, mode="quick")
        elif name == "assign":
            await self._assign(args)
        elif name == "stop":
            await self.stop_debate(by_king=True)
        elif name == "vote":
            await self._force("vote")
        elif name == "judge":
            await self._force("judge")
        elif name == "silence":
            await self._set_silenced(args, True)
        elif name == "activate":
            await self._set_silenced(args, False)
        elif name == "add-agent":
            await self._add_agent(args)
        elif name == "remove-agent":
            await self._remove_agent(args)
        elif name == "reset":
            await self.reset_room()
        elif name == "memory":
            await self.show_memory()
        elif name == "help":
            await self.system_message(COMMAND_HELP)
        else:  # pragma: no cover
            await self.system_message(f"Unknown command: /{name}")

    async def _force(self, what: str) -> None:
        if self.debate_task and not self.debate_task.done() and self.current_engine:
            self.force_request = what
            await self.system_message(f"⚖ The King requested {what.upper()} — the council will comply.")
        else:
            await self.system_message("No active debate. Start one with /debate <task>.")

    def consume_force(self, options: tuple[str, ...]) -> bool:
        if self.force_request in options:
            self.force_request = None
            return True
        return False

    async def _assign(self, args: str) -> None:
        """Assign a task: '/assign Kimi analyse X' targets one agent, otherwise the whole council."""
        parts = args.split(maxsplit=1)
        target = None
        active = self.active_runtimes()
        if parts and parts[0].lower() in [rt.profile.name.lower() for rt in active]:
            target = next(rt for rt in active if rt.profile.name.lower() == parts[0].lower())
            task_text = parts[1] if len(parts) > 1 else "Report your view on the current situation."
        else:
            task_text = args
        if not task_text.strip():
            await self.system_message("Usage: /assign [agent] <task>")
            return
        async with async_session_factory() as session:
            session.add(Task(room_id=self.room_id, content=task_text, status="running"))
            await session.commit()
        targets = [target] if target else active
        for rt in targets:
            ctx = TurnContext(
                room_id=self.room_id,
                debate_id=None,
                task=task_text,
                round=0,
                transcript=await self.get_transcript(),
                memory_bullets=await self.get_memory_bullets(),
                kind="answer",
                message_type=MessageTypes.ANSWER,
            )
            await self._run_turn_isolated(rt, ctx)

    # ------------------------------------------------------------- debate ops

    async def start_debate(self, task: str, mode: str = "full") -> None:
        task = (task or "").strip()
        if not task:
            await self.system_message("Give the council a task: /debate <task>  (or just type it).")
            return
        if self.debate_task and not self.debate_task.done():
            await self.system_message("A debate is already in session. Use /stop first.")
            return
        if not self.active_runtimes():
            await self.system_message("No active agents in this room. Add one with /add-agent <name>.")
            return

        self.stop_event.clear()
        self.force_request = None
        async with async_session_factory() as session:
            debate = Debate(room_id=self.room_id, task=task, mode=mode)
            session.add(debate)
            await session.flush()
            session.add(Task(room_id=self.room_id, debate_id=debate.id, content=task, status="running"))
            await session.commit()
            await session.refresh(debate)
            debate_id = str(debate.id)

        self.current_debate_id = debate_id
        engine = DebateEngine(self)
        self.current_engine = engine
        await self.set_room_state(RoomState.DISCUSSING)
        self.emit(EventType.SYSTEM_NOTICE, {"notice": f"Debate started ({mode}): {task}"})
        logger.info("debate started room=%s debate=%s mode=%s", self.room_id, debate_id, mode)
        self.debate_task = asyncio.create_task(engine.run(debate_id, task, mode), name=f"debate:{debate_id}")

    async def stop_debate(self, by_king: bool = True) -> None:
        if not self.debate_task or self.debate_task.done():
            if by_king:
                await self.system_message("No debate is running.")
            return
        self.stop_event.set()
        try:
            await asyncio.wait_for(asyncio.shield(self.debate_task), timeout=6)
        except (asyncio.TimeoutError, asyncio.CancelledError, Exception):  # noqa: BLE001
            self.debate_task.cancel()
            try:
                await self.debate_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        if by_king:
            await self.system_message("⏹ Debate stopped by the King.")
            await self.set_room_state(RoomState.STOPPED)

    async def reset_room(self) -> None:
        await self.stop_debate(by_king=False)
        async with async_session_factory() as session:
            debate_ids = sa.select(Debate.id).where(Debate.room_id == self.room_id)
            await session.execute(sa.delete(Decision).where(Decision.debate_id.in_(debate_ids)))
            await session.execute(sa.delete(Vote).where(Vote.debate_id.in_(debate_ids)))
            for table in (MemoryItem, Message, Task, Debate):
                await session.execute(sa.delete(table).where(table.room_id == self.room_id))
            await session.execute(sa.update(Room).where(Room.id == self.room_id).values(state=RoomState.IDLE))
            await session.commit()
        await self.load()
        await self.set_room_state(RoomState.IDLE)
        await self.system_message("♻ Room reset. Memory cleared. The council stands ready.")

    async def show_memory(self) -> None:
        bullets = await self.get_memory_bullets()
        if bullets:
            await self.system_message("🧠 Council memory:\n" + "\n".join(f"- {b}" for b in bullets))
        else:
            await self.system_message("🧠 Council memory is empty. Win a debate first.")

    # ---------------------------------------------------------- agent actions

    def active_runtimes(self) -> list[AgentRuntime]:
        return [
            self.runtimes[aid]
            for aid in self.order
            if aid in self.runtimes
            and self.runtimes[aid].profile.active
            and not self.runtimes[aid].profile.silenced
        ]

    async def _set_silenced(self, name: str, silenced: bool) -> None:
        runtime = self._find_runtime(name)
        if runtime is None:
            await self.system_message(f"Agent not found: {name}")
            return
        runtime.profile.silenced = silenced
        async with async_session_factory() as session:
            await session.execute(
                sa.update(RoomAgent)
                .where(RoomAgent.room_id == self.room_id, RoomAgent.agent_id == runtime.profile.id)
                .values(silenced=silenced)
            )
            await session.commit()
        runtime.set_status(self.room_id, "offline" if silenced else "idle")
        await self.system_message(f"{'🔇 Silenced' if silenced else '🔊 Activated'}: {runtime.profile.name}")

    def _find_runtime(self, name: str) -> AgentRuntime | None:
        name = (name or "").strip().lower()
        for rt in self.runtimes.values():
            if rt.profile.name.lower() == name:
                return rt
        for rt in self.runtimes.values():
            if rt.profile.id == name or rt.profile.name.lower().startswith(name):
                return rt
        return None

    async def _add_agent(self, name: str) -> None:
        name = (name or "").strip()
        if not name:
            await self.system_message("Usage: /add-agent <name>")
            return
        async with async_session_factory() as session:
            agent = Agent(
                name=name,
                provider="auto",
                role="advisor",
                icon="🛡",
                color="#94a3b8",
                personality=["loyal to the King"],
                system_prompt=f"You are {name}, an advisor in the King's War Room.",
            )
            session.add(agent)
            await session.flush()
            session.add(RoomAgent(room_id=self.room_id, agent_id=agent.id, position=len(self.order)))
            await session.commit()
        await self.load()
        await self.system_message(f"➕ Agent {name} joined the council (provider: auto).")

    async def _remove_agent(self, name: str) -> None:
        runtime = self._find_runtime(name)
        if runtime is None:
            await self.system_message(f"Agent not found: {name}")
            return
        async with async_session_factory() as session:
            await session.execute(
                sa.delete(RoomAgent).where(
                    RoomAgent.room_id == self.room_id, RoomAgent.agent_id == runtime.profile.id
                )
            )
            await session.commit()
        await self.load()
        await self.system_message(f"➖ Agent {name} left the council.")

    async def _run_turn_isolated(self, runtime: AgentRuntime, ctx: TurnContext) -> None:
        """One agent failing must never kill the room (spec section 19)."""
        try:
            await runtime.turn(ctx)
        except Exception as exc:  # noqa: BLE001
            logger.warning("agent turn failed room=%s agent=%s: %s", self.room_id, runtime.profile.name, exc)
            runtime.set_status(self.room_id, "error")
            await self.system_message(f"⚠ {runtime.profile.name} — {exc}")

    # --------------------------------------------------------------- snapshots

    async def snapshot(self) -> dict:
        from app.schemas.serializers import decision_out

        async with async_session_factory() as session:
            room = await session.get(Room, self.room_id)
            pairs = (
                await session.execute(
                    sa.select(RoomAgent, Agent)
                    .join(Agent, Agent.id == RoomAgent.agent_id)
                    .where(RoomAgent.room_id == self.room_id)
                    .order_by(RoomAgent.position)
                )
            ).all()
            msg_counts = dict(
                (row[0], row[1])
                for row in (
                    await session.execute(
                        sa.select(Message.agent_id, sa.func.count(Message.id))
                        .where(Message.room_id == self.room_id, Message.agent_id.isnot(None))
                        .group_by(Message.agent_id)
                    )
                ).all()
            )
            typed_counts = (
                await session.execute(
                    sa.select(Message.agent_id, Message.message_type, sa.func.count(Message.id))
                    .where(Message.room_id == self.room_id, Message.agent_id.isnot(None))
                    .group_by(Message.agent_id, Message.message_type)
                )
            ).all()
            per_type: dict[tuple, int] = {(row[0], row[1]): row[2] for row in typed_counts}
            decision_row = (
                await session.execute(
                    sa.select(Decision)
                    .join(Debate, Debate.id == Decision.debate_id)
                    .where(Debate.room_id == self.room_id)
                    .order_by(Decision.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            total = (
                await session.execute(sa.select(sa.func.count(Message.id)).where(Message.room_id == self.room_id))
            ).scalar_one()

        agent_views = []
        for room_agent, agent in pairs:
            aid = str(agent.id)
            runtime = self.runtimes.get(aid)
            profile = AgentProfile.from_entity(agent, silenced=room_agent.silenced)
            provider = get_runtime().providers.resolve(profile.provider, profile.model)
            agent_views.append(
                {
                    "id": aid,
                    "name": agent.name,
                    "icon": agent.icon,
                    "color": agent.color,
                    "role": agent.role,
                    "role_title": profile.role_title,
                    "personality": agent.personality or [],
                    "system_prompt": agent.system_prompt,
                    "behavior": agent.behavior or {},
                    "provider": agent.provider,
                    "model": agent.model,
                    "resolved_provider": provider.name,
                    "memory_enabled": agent.memory_enabled,
                    "active": agent.active,
                    "silenced": room_agent.silenced,
                    "status": runtime.status if runtime else "offline",
                    "stats": {
                        "messages": msg_counts.get(agent.id, 0),
                        "challenges": per_type.get((agent.id, "challenge"), 0),
                        "agreements": per_type.get((agent.id, "agreement"), 0),
                    },
                }
            )
        debate_active = bool(self.debate_task and not self.debate_task.done())
        return {
            "room": {
                "id": str(room.id),
                "name": room.name,
                "state": room.state,
                "created_at": room.created_at.isoformat(),
            },
            "agents": agent_views,
            "message_count": total,
            "decision": decision_out(decision_row) if decision_row else None,
            "debate": {"active": debate_active, "phase": None, "round": 0},
        }
