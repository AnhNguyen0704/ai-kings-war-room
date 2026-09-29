"""Judge / Synthesizer service.

The Judge evaluates the whole debate (not just the vote count) and proposes a
synthesis. It NEVER overrides the King's authority - output is a recommendation.
"""
from app.agents.prompts import JUDGE_INSTRUCTION, extract_json, format_transcript
from app.core.runtime import get_runtime
from app.providers.base import ChatMessage

_JUDGE_SYSTEM = (
    "You are the Judge of the King's War Room. You are neutral, rigorous and fair. "
    "You weigh correctness, reasoning quality, evidence, feasibility, complexity, risk and "
    "consistency. You synthesize the council's strongest position into a clear recommendation "
    "for the King, who always holds final authority."
)


class JudgeService:
    def synthesize_sync_safe(self) -> None:  # pragma: no cover - placeholder for symmetry
        pass

    async def synthesize(
        self,
        *,
        task: str,
        transcript: list[dict],
        votes: list[dict],
        memory_bullets: list[str],
    ) -> dict:
        rt = get_runtime()
        provider = rt.providers.resolve_judge()
        vote_summary = (
            "\n".join(f"- {v['agent']} voted for {v['choice']}: {v['rationale']}" for v in votes)
            or "(no votes recorded)"
        )
        user_prompt = (
            f"[TASK]\n{task}\n\n"
            f"[COUNCIL TRANSCRIPT (oldest first)]\n{format_transcript(transcript)}\n\n"
            f"[VOTES]\n{vote_summary}\n\n"
            + (f"[COUNCIL MEMORY]\n" + "\n".join(f"- {b}" for b in memory_bullets) + "\n\n" if memory_bullets else "")
            + f"[YOUR INSTRUCTION]\n{JUDGE_INSTRUCTION}"
        )
        if provider.name == "mock":
            import json as _json

            candidates = list(dict.fromkeys([v["choice"] for v in votes if v["choice"] not in ("abstain", "")]))
            user_prompt += (
                "\n\n[MOCK-HINT]\n"
                + _json.dumps(
                    {"kind": "judge", "agent": "JUDGE", "role": "Judge", "task": task, "candidates": candidates},
                    ensure_ascii=False,
                )
                + "\n[/MOCK-HINT]"
            )
        messages = [
            ChatMessage(role="system", content=_JUDGE_SYSTEM),
            ChatMessage(role="user", content=user_prompt),
        ]
        try:
            raw = await provider.generate(messages, temperature=0.3, max_tokens=900)
        except Exception:
            raise
        decision = extract_json(raw)
        if not decision or "decision" not in decision:
            decision = {
                "decision": raw.strip()[:800] or "No synthesis produced.",
                "reasoning": [],
                "confidence": 0.5,
                "open_questions": [],
                "dissenting_views": [],
            }
        decision.setdefault("reasoning", [])
        decision.setdefault("confidence", 0.5)
        decision.setdefault("open_questions", [])
        decision.setdefault("dissenting_views", [])
        decision["_judge"] = provider.name
        return decision
