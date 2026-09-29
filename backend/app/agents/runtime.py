"""Agent Runtime: one live instance per agent in a room.

Owns the agent's profile, resolved provider, status and stats. Runs a streaming
turn (persist + broadcast) or a structured vote, with full error isolation -
a failing agent never kills the room.
"""
import asyncio
from dataclasses import dataclass, field

from app.agents.profile import AgentProfile
from app.agents.prompts import build_system_prompt, build_turn_prompt, parse_vote
from app.core.runtime import get_runtime
from app.db.database import async_session_factory
from app.events.types import AgentStatus, EventType
from app.models.entities import Message
from app.providers.base import ChatMessage, LLMProvider, ProviderError


@dataclass
class TurnContext:
    room_id: str
    debate_id: str | None
    task: str
    round: int
    transcript: list[dict]
    memory_bullets: list[str] = field(default_factory=list)
    kind: str = "proposal"          # proposal | challenge | rebuttal | agreement | observation | answer
    message_type: str = "proposal"
    target_name: str | None = None
    target_agent_id: str | None = None
    reply_to_id: str | None = None


@dataclass
class VoteResult:
    choice: str
    rationale: str


class AgentRuntime:
    def __init__(self, profile: AgentProfile, provider: LLMProvider, resolved_label: str) -> None:
        self.profile = profile
        self.provider = provider
        self.resolved_label = resolved_label
        self.status: str = AgentStatus.IDLE
        self.last_message_id: str | None = None
        self.last_out_type: str | None = None

    # ------------------------------------------------------------------ helpers

    def _emit(self, room_id: str, event_type: str, data: dict) -> None:
        get_runtime().bus.publish(room_id, {"event": event_type, "room_id": room_id, "data": data})

    def _status_payload(self, status: str) -> dict:
        return {
            "agent_id": self.profile.id,
            "name": self.profile.name,
            "status": status,
            "silenced": self.profile.silenced,
        }

    def set_status(self, room_id: str, status: str) -> None:
        self.status = status
        self._emit(room_id, EventType.AGENT_STATUS, self._status_payload(status))

    # ------------------------------------------------------------------- turns

    async def turn(self, ctx: TurnContext) -> None:
        """Run one streaming speaking turn. Raises on failure; caller isolates errors."""
        self.set_status(ctx.room_id, AgentStatus.THINKING)

        # 1. Persist an empty message so the UI has a stable id to stream into.
        meta: dict = {"resolved_provider": self.resolved_label}
        if ctx.target_agent_id:
            meta["target_agent_id"] = ctx.target_agent_id
        if ctx.target_name:
            meta["target_name"] = ctx.target_name
        async with async_session_factory() as session:
            msg = Message(
                room_id=ctx.room_id,
                debate_id=ctx.debate_id,
                sender_type="agent",
                agent_id=self.profile.id,
                message_type=ctx.message_type,
                content="",
                reply_to_id=ctx.reply_to_id,
                round=ctx.round,
                meta=meta,
            )
            session.add(msg)
            await session.commit()
            await session.refresh(msg)
            message_id = str(msg.id)

        self._emit(
            ctx.room_id,
            EventType.MESSAGE_NEW,
            {
                "id": message_id,
                "sender_type": "agent",
                "agent_id": self.profile.id,
                "sender_name": self.profile.name,
                "agent_color": self.profile.color,
                "agent_role": self.profile.role_title,
                "message_type": ctx.message_type,
                "content": "",
                "reply_to_id": ctx.reply_to_id,
                "meta": meta,
                "created_at": "",
                "streaming": True,
            },
        )

        # 2. Build prompt and stream token chunks.
        self.set_status(ctx.room_id, AgentStatus.SPEAKING)
        user_prompt = build_turn_prompt(
            self.profile,
            task=ctx.task,
            transcript=ctx.transcript,
            memory_bullets=ctx.memory_bullets,
            instruction=self._instruction_text(ctx),
            target_name=ctx.target_name,
            include_mock_hint=self.provider.name == "mock",
            mock_hint={
                "kind": ctx.kind,
                "agent": self.profile.name,
                "role": self.profile.role_title,
                "target": ctx.target_name or "",
                "task": ctx.task,
            },
        )
        messages = [
            ChatMessage(role="system", content=build_system_prompt(self.profile)),
            ChatMessage(role="user", content=user_prompt),
        ]

        rt = get_runtime()
        buffer: list[str] = []

        async def _run_stream() -> None:
            async for chunk in self.provider.stream(messages, temperature=self._temperature()):
                buffer.append(chunk)
                self._emit(ctx.room_id, EventType.MESSAGE_DELTA, {"id": message_id, "delta": chunk})

        try:
            await asyncio.wait_for(_run_stream(), timeout=rt.settings.agent_turn_timeout)
        except asyncio.TimeoutError as exc:
            raise ProviderError(f"{self.profile.provider} timeout after {rt.settings.agent_turn_timeout}s") from exc

        content = "".join(buffer).strip() or "(no response)"
        async with async_session_factory() as session:
            obj = await session.get(Message, message_id)
            if obj:
                obj.content = content
                await session.commit()

        self._emit(
            ctx.room_id,
            EventType.MESSAGE_COMPLETE,
            {
                "id": message_id,
                "content": content,
                "message_type": ctx.message_type,
                "agent_id": self.profile.id,
                "meta": meta,
            },
        )
        self.last_message_id = message_id
        self.last_out_type = ctx.message_type
        self.profile.messages += 1
        if ctx.message_type == "challenge":
            self.profile.challenges += 1
        if ctx.message_type == "agreement":
            self.profile.agreements += 1
        self.set_status(ctx.room_id, AgentStatus.IDLE)

    async def vote(self, ctx: TurnContext, candidates: list[str]) -> VoteResult:
        """Structured voting turn (no streaming broadcast)."""
        self.set_status(ctx.room_id, AgentStatus.THINKING)
        prompt = build_turn_prompt(
            self.profile,
            task=ctx.task,
            transcript=ctx.transcript,
            memory_bullets=ctx.memory_bullets,
            instruction="Vote for the advisor whose proposal survived the debate best. "
            "Reply exactly:\nVOTE: <advisor name or abstain>\nRATIONALE: <one sentence>",
            include_mock_hint=self.provider.name == "mock",
            mock_hint={
                "kind": "vote",
                "agent": self.profile.name,
                "role": self.profile.role_title,
                "task": ctx.task,
                "candidates": candidates,
            },
        )
        messages = [
            ChatMessage(role="system", content=build_system_prompt(self.profile)),
            ChatMessage(role="user", content=prompt),
        ]
        rt = get_runtime()
        try:
            raw = await asyncio.wait_for(
                self.provider.generate(messages, temperature=0.2, max_tokens=200),
                timeout=rt.settings.agent_turn_timeout,
            )
        except asyncio.TimeoutError as exc:
            raise ProviderError(f"{self.profile.provider} timeout during vote") from exc

        choice, rationale = parse_vote(raw)
        if choice.lower() not in [c.lower() for c in candidates] and choice.lower() != "abstain":
            choice = "abstain"
        self.set_status(ctx.room_id, AgentStatus.IDLE)
        return VoteResult(choice=choice, rationale=rationale)

    # ------------------------------------------------------------------ config

    def _temperature(self) -> float:
        verbosity = float(self.profile.behavior.get("verbosity", 0.6))
        return min(1.0, 0.3 + verbosity * 0.5)

    def _instruction_text(self, ctx: TurnContext) -> str:
        target = f" Direct your message at {ctx.target_name}." if ctx.target_name else ""
        return {
            "proposal": "Present your initial proposal for the task. State your core recommendation and why."
            + target,
            "challenge": "Challenge the weakest point of the target's argument. Be direct and specific." + target,
            "rebuttal": "Defend your position against the challenge. Concede what is fair, refute what is not."
            + target,
            "agreement": "State your agreement and what should be recorded as the shared conclusion." + target,
            "observation": "Add a new angle or missing consideration that nobody has raised yet." + target,
            "answer": "Answer the King's question directly, in your role's voice." + target,
        }.get(ctx.kind, "Contribute to the council discussion." + target)
