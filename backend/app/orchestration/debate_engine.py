"""Debate Engine: drives the full council flow.

    TASK -> PROPOSALS -> DISCUSSION (challenge/rebuttal/refine) -> VOTING
         -> JUDGE -> SYNTHESIS -> FINAL REPORT

The orchestrator decides who speaks, who challenges whom, when consensus is
reached and when to hand over to the Judge. The King can stop, force a vote or
force judging at any time. A failing agent never aborts the debate.
"""
import asyncio
import random

import sqlalchemy as sa

from app.agents.judge import JudgeService
from app.agents.runtime import AgentRuntime, TurnContext
from app.core.logging import get_logger
from app.core.runtime import get_runtime
from app.db.database import async_session_factory
from app.events.types import AgentStatus, DebatePhase, EventType, MessageTypes, RoomState
from app.models.entities import Debate, Decision, MemoryItem, Message, Vote

logger = get_logger("debate")


class DebateStopped(Exception):
    pass


class DebateEngine:
    def __init__(self, controller) -> None:  # controller: RoomController
        self.c = controller
        self.rng = random.Random(str(controller.room_id))
        self.last_messages: dict[str, dict] = {}          # agent_id -> {id, type}
        self.pending_challenges: dict[str, str] = {}      # challenged_id -> challenger_id
        self.votes: list[dict] = []

    # ------------------------------------------------------------------ flow

    async def run(self, debate_id: str, task: str, mode: str) -> None:
        try:
            self._check_stop()
            await self._phase_proposals(debate_id, task, mode)
            if mode == "full":
                if not self.c.consume_force(("judge",)):
                    self._check_stop()
                    await self._phase_discussion(debate_id, task)
                    if not self.c.consume_force(("judge",)):
                        self._check_stop()
                        await self._phase_voting(debate_id, task)
                self._check_stop()
                await self._phase_judging(debate_id, task)
                self._check_stop()
                await self._phase_synthesis(debate_id, task)
            else:
                await self.c.system_message("💬 Quick answers delivered.")
            await self._finish_debate(debate_id, status="completed")
            if mode != "full":
                await self.c.set_room_state(RoomState.COMPLETED)
        except DebateStopped:
            await self._finish_debate(debate_id, status="stopped")
            await self.c.set_room_state(RoomState.STOPPED)
        except asyncio.CancelledError:
            await self._finish_debate(debate_id, status="stopped")
            await self.c.set_room_state(RoomState.STOPPED)
            raise
        except Exception as exc:  # noqa: BLE001 - the room must survive any engine error
            logger.exception("debate failed room=%s debate=%s", self.c.room_id, debate_id)
            await self._finish_debate(debate_id, status="error")
            await self.c.set_room_state(RoomState.ERROR)
            await self.c.system_message(f"⚠ Debate error: {exc}")
            await self._emit_error(str(exc))
        finally:
            self.c.current_debate_id = None

    def _check_stop(self) -> None:
        if self.c.stop_event.is_set():
            raise DebateStopped()

    def _emit_error(self, message: str) -> None:
        self.c.emit(EventType.ERROR, {"message": message})

    # --------------------------------------------------------------- phases

    async def _phase_proposals(self, debate_id: str, task: str, mode: str = "full") -> None:
        await self.c.set_debate_phase(debate_id, DebatePhase.PROPOSALS, 0)
        quick = mode == "quick"
        for rt in self.c.active_runtimes():
            self._check_stop()
            ctx = TurnContext(
                room_id=self.c.room_id,
                debate_id=debate_id,
                task=task,
                round=0,
                transcript=await self.c.get_transcript(),
                memory_bullets=await self.c.get_memory_bullets(),
                kind="answer" if quick else "proposal",
                message_type=MessageTypes.ANSWER if quick else MessageTypes.PROPOSAL,
            )
            await self._run_turn(rt, ctx)

    async def _phase_discussion(self, debate_id: str, task: str) -> None:
        rounds = get_runtime().settings.discussion_rounds
        await self.c.set_room_state(RoomState.DEBATING)
        for round_no in range(1, rounds + 1):
            self._check_stop()
            await self.c.set_debate_phase(debate_id, DebatePhase.DISCUSSION, round_no)
            for rt in self.c.active_runtimes():
                self._check_stop()
                if self.c.consume_force(("vote", "judge")):
                    return
                kind, target = self._decide_turn(rt, round_no)
                reply_to = target.last_message_id if target else None
                ctx = TurnContext(
                    room_id=self.c.room_id,
                    debate_id=debate_id,
                    task=task,
                    round=round_no,
                    transcript=await self.c.get_transcript(),
                    memory_bullets=await self.c.get_memory_bullets(),
                    kind=kind,
                    message_type=kind,
                    target_name=target.profile.name if target else None,
                    target_agent_id=target.profile.id if target else None,
                    reply_to_id=reply_to,
                )
                await self._run_turn(rt, ctx)
            if self._consensus_reached():
                await self.c.system_message("🤝 Consensus reached — the council agrees.")
                return

    def _decide_turn(self, rt: AgentRuntime, round_no: int) -> tuple[str, AgentRuntime | None]:
        """Orchestrator decides who says what to whom (spec section 8)."""
        others = [o for o in self.c.active_runtimes() if o.profile.id != rt.profile.id]

        # A pending challenge against this agent -> rebuttal.
        challenger_id = self.pending_challenges.pop(rt.profile.id, None)
        if challenger_id and challenger_id in [o.profile.id for o in others]:
            return "rebuttal", self.c.runtimes[challenger_id]

        # Behaviour-driven challenge.
        if others and self.rng.random() < rt.profile.challenge_probability:
            speakers = [o for o in others if o.last_message_id]
            if speakers:
                return "challenge", self.rng.choice(speakers)

        # Later rounds: converge or observe.
        if round_no > 1:
            proposal_authors = [
                o for o in others if self.last_messages.get(o.profile.id, {}).get("type") == MessageTypes.PROPOSAL
            ]
            if proposal_authors:
                return "agreement", proposal_authors[0]
            if others:
                return "observation", others[0]
        return "observation", (others[-1] if others else None)

    def _consensus_reached(self) -> bool:
        active = self.c.active_runtimes()
        return bool(active) and all(rt.last_out_type == MessageTypes.AGREEMENT for rt in active)

    async def _phase_voting(self, debate_id: str, task: str) -> None:
        await self.c.set_room_state(RoomState.VOTING)
        await self.c.set_debate_phase(debate_id, DebatePhase.VOTING, 0)
        candidates = [rt.profile.name for rt in self.c.active_runtimes()]
        for rt in self.c.active_runtimes():
            self._check_stop()
            ctx = TurnContext(
                room_id=self.c.room_id,
                debate_id=debate_id,
                task=task,
                round=0,
                transcript=await self.c.get_transcript(),
                memory_bullets=await self.c.get_memory_bullets(),
                kind="vote",
                message_type=MessageTypes.VOTE,
            )
            try:
                result = await rt.vote(ctx, candidates)
            except Exception as exc:  # noqa: BLE001
                logger.warning("vote failed agent=%s: %s", rt.profile.name, exc)
                rt.set_status(self.c.room_id, AgentStatus.ERROR)
                result = None
                await self.c.system_message(f"⚠ {rt.profile.name} — vote failed: {exc}")
            choice = result.choice if result else "abstain"
            rationale = result.rationale if result else "could not vote"
            async with async_session_factory() as session:
                session.add(Vote(debate_id=debate_id, agent_id=rt.profile.id, choice=choice, rationale=rationale))
                await session.commit()
            self.votes.append({"agent": rt.profile.name, "choice": choice, "rationale": rationale})
            content = f"🗳 VOTE: {choice}\nRATIONALE: {rationale}"
            await self._post_agent_message(rt, debate_id, MessageTypes.VOTE, content)
            self.c.emit(
                EventType.VOTE_CAST,
                {"agent": rt.profile.name, "agent_id": rt.profile.id, "choice": choice, "rationale": rationale},
            )

    async def _phase_judging(self, debate_id: str, task: str) -> None:
        await self.c.set_room_state(RoomState.JUDGING)
        await self.c.set_debate_phase(debate_id, DebatePhase.JUDGING, 0)
        transcript = await self.c.get_transcript(limit=60)
        decision = await JudgeService().synthesize(
            task=task,
            transcript=transcript,
            votes=self.votes,
            memory_bullets=await self.c.get_memory_bullets(),
        )
        async with async_session_factory() as session:
            session.add(
                Decision(
                    debate_id=debate_id,
                    decision=decision.get("decision", ""),
                    reasoning=decision.get("reasoning") if isinstance(decision.get("reasoning"), str)
                    else "\n".join(decision.get("reasoning") or []),
                    confidence=float(decision.get("confidence", 0.5)),
                    open_questions=decision.get("open_questions") or [],
                    dissenting_views=decision.get("dissenting_views") or [],
                )
            )
            await session.commit()
        self.c.emit(EventType.DECISION, {"debate_id": debate_id, "decision": _jsonable(decision)})

    async def _phase_synthesis(self, debate_id: str, task: str) -> None:
        await self.c.set_debate_phase(debate_id, DebatePhase.SYNTHESIS, 0)
        async with async_session_factory() as session:
            decision_row = (
                await session.execute(
                    sa.select(Decision).where(Decision.debate_id == debate_id).order_by(Decision.created_at.desc())
                )
            ).scalars().first()
        decision = {
            "decision": decision_row.decision,
            "reasoning": [line for line in (decision_row.reasoning or "").split("\n") if line.strip()],
            "confidence": decision_row.confidence,
            "open_questions": decision_row.open_questions or [],
            "dissenting_views": decision_row.dissenting_views or [],
        }
        content = _format_final_report(decision)
        meta = {"decision": _jsonable(decision)}
        # Flip state before the report lands so pollers never see a dangling final message.
        await self.c.set_room_state(RoomState.COMPLETED)
        async with async_session_factory() as session:
            msg = Message(
                room_id=self.c.room_id,
                debate_id=debate_id,
                sender_type="judge",
                message_type=MessageTypes.FINAL,
                content=content,
                meta=meta,
            )
            session.add(msg)
            await session.commit()
            await session.refresh(msg)
            payload = self.c._message_payload(msg)
        self.c.emit(EventType.MESSAGE_NEW, payload, persist=False)

        # Shared room memory (spec section 15).
        dissent = "; ".join(
            f"{d.get('agent', '?')} preferred: {d.get('view', '')}" for d in decision["dissenting_views"]
        )
        bullets = [
            f"Decision: {decision['decision']}",
            f"Reason: {' '.join(decision['reasoning'][:2])}" if decision["reasoning"] else "Reason: see final report",
        ]
        if dissent:
            bullets.append(f"Dissent: {dissent}")
        async with async_session_factory() as session:
            for b in bullets:
                session.add(MemoryItem(room_id=self.c.room_id, kind="shared", content=b, importance=0.9))
            await session.commit()
        await self.c.system_message("🏁 Debate complete. The final report awaits the King's decision.")

    # -------------------------------------------------------------- helpers

    async def _run_turn(self, rt: AgentRuntime, ctx: TurnContext) -> None:
        try:
            await rt.turn(ctx)
            self.last_messages[rt.profile.id] = {"id": rt.last_message_id, "type": ctx.message_type}
            if ctx.kind == "challenge" and ctx.target_agent_id:
                self.pending_challenges[ctx.target_agent_id] = rt.profile.id
        except Exception as exc:  # noqa: BLE001 - isolate agent failures
            logger.warning("agent turn failed room=%s agent=%s: %s", self.c.room_id, rt.profile.name, exc)
            rt.set_status(self.c.room_id, AgentStatus.ERROR)
            await self.c.system_message(f"⚠ {rt.profile.name} — {exc}")

    async def _post_agent_message(self, rt: AgentRuntime, debate_id: str, message_type: str, content: str) -> None:
        async with async_session_factory() as session:
            msg = Message(
                room_id=self.c.room_id,
                debate_id=debate_id,
                sender_type="agent",
                agent_id=rt.profile.id,
                message_type=message_type,
                content=content,
            )
            session.add(msg)
            await session.commit()
            await session.refresh(msg)
            payload = self.c._message_payload(msg)
            payload["agent_color"] = rt.profile.color
            payload["agent_role"] = rt.profile.role_title
        self.c.emit(EventType.MESSAGE_NEW, payload, persist=False)

    async def _finish_debate(self, debate_id: str, status: str) -> None:
        async with async_session_factory() as session:
            debate = await session.get(Debate, debate_id)
            if debate:
                debate.status = status
                from datetime import datetime, timezone

                debate.ended_at = datetime.now(timezone.utc)
                await session.commit()
        self.c.emit(
            EventType.DEBATE_PHASE,
            {"debate_id": debate_id, "phase": DebatePhase.DONE, "round": 0, "status": status},
        )
        logger.info("debate %s finished status=%s", debate_id, status)


def _jsonable(obj) -> dict:
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, float):
        return round(obj, 4)
    return obj


def _format_final_report(d: dict) -> str:
    lines = [
        "🏁 FINAL REPORT",
        "",
        "📌 DECISION",
        d.get("decision", "—"),
        "",
    ]
    reasoning = d.get("reasoning") or []
    if reasoning:
        lines.append("🧠 REASONING")
        if isinstance(reasoning, str):
            reasoning = [reasoning]
        lines += [f"- {r}" for r in reasoning]
        lines.append("")
    lines.append(f"📊 CONFIDENCE: {int(float(d.get('confidence', 0.5)) * 100)}%")
    oq = d.get("open_questions") or []
    lines.append("")
    lines.append("❓ OPEN QUESTIONS")
    lines += [f"- {q}" for q in oq] or ["- (none — the council closed all open threads)"]
    dv = d.get("dissenting_views") or []
    lines.append("")
    lines.append("⚡ DISSENTING VIEWS")
    if dv:
        lines += [f"- {v.get('agent', '?')}: {v.get('view', '')}" for v in dv]
    else:
        lines.append("- None recorded — consensus reached.")
    lines.append("")
    lines.append("👑 The final word belongs to the King.")
    return "\n".join(lines)
