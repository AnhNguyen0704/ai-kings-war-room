"""Prompt construction for agent turns, votes and judging. Provider-agnostic."""
import json

from app.agents.profile import AgentProfile
from app.events.types import MessageTypes

SYSTEM_SUFFIX = (
    "You are an AI advisor in the King's War Room council. Address other advisors by name when "
    "referring to their arguments. Be concise (max ~120 words unless asked otherwise). Respond in "
    "the same language the King uses. Never break character, never mention being an AI model."
)


def build_system_prompt(profile: AgentProfile) -> str:
    parts = [profile.system_prompt.strip() or f"You are {profile.name}, a trusted advisor of the King."]
    if profile.personality:
        parts.append("Your personality: " + ", ".join(profile.personality) + ".")
    parts.append(f"Your role in the council: {profile.role_title}.")
    parts.append(SYSTEM_SUFFIX)
    return "\n\n".join(parts)


def format_transcript(entries: list[dict]) -> str:
    if not entries:
        return "(the council has not spoken yet)"
    lines = []
    for e in entries:
        sender = e.get("sender_name", "?")
        mtype = e.get("message_type", "message")
        content = (e.get("content") or "").strip()
        if content:
            lines.append(f"{sender} ({mtype}): {content}")
    return "\n".join(lines) or "(empty)"


def build_turn_prompt(
    profile: AgentProfile,
    *,
    task: str,
    transcript: list[dict],
    memory_bullets: list[str],
    instruction: str,
    target_name: str | None = None,
    include_mock_hint: bool = False,
    mock_hint: dict | None = None,
) -> str:
    parts = [f"[TASK]\n{task}"]
    if memory_bullets:
        parts.append("[COUNCIL MEMORY]\n" + "\n".join(f"- {b}" for b in memory_bullets))
    parts.append("[COUNCIL TRANSCRIPT (oldest first)]\n" + format_transcript(transcript))
    if target_name:
        parts.append(f"[TARGET] You are replying to {target_name}.")
    parts.append(f"[YOUR INSTRUCTION]\n{instruction}\nRespond with your message content only.")
    if include_mock_hint and mock_hint is not None:
        import json as _json

        parts.append("[MOCK-HINT]\n" + _json.dumps(mock_hint, ensure_ascii=False) + "\n[/MOCK-HINT]")
    return "\n\n".join(parts)


VOTE_INSTRUCTION = (
    "Vote for the advisor whose proposal survived the debate best. Reply exactly in this format:\n"
    "VOTE: <advisor name or abstain>\nRATIONALE: <one sentence>"
)

JUDGE_INSTRUCTION = (
    "Evaluate the debate on correctness, reasoning quality, evidence, feasibility, complexity, risk "
    "and consistency. Do NOT simply follow the majority vote. Synthesize the strongest combined "
    "position. Reply with ONLY a JSON object:\n"
    '{"decision": str, "reasoning": [str, ...], "confidence": float, '
    '"open_questions": [str, ...], "dissenting_views": [{"agent": str, "view": str}] }'
)


def parse_vote(text: str) -> tuple[str, str]:
    choice, rationale = "abstain", (text or "").strip()[:200]
    upper = (text or "").upper()
    idx = upper.find("VOTE:")
    if idx >= 0:
        rest = (text or "")[idx + 5 :]
        nl = rest.find("\n")
        choice = rest[: nl if nl >= 0 else len(rest)].strip().strip("*").strip() or "abstain"
        r_idx = rest.upper().find("RATIONALE:")
        if r_idx >= 0:
            rationale = rest[r_idx + 10 :].strip()
    return choice[:64], rationale


def extract_json(text: str) -> dict | None:
    """Extract the first balanced JSON object from arbitrary LLM output."""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    start = cleaned.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def message_type_for_kind(kind: str) -> str:
    return {
        "proposal": MessageTypes.PROPOSAL,
        "challenge": MessageTypes.CHALLENGE,
        "rebuttal": MessageTypes.REBUTTAL,
        "agreement": MessageTypes.AGREEMENT,
        "observation": MessageTypes.OBSERVATION,
        "answer": MessageTypes.ANSWER,
    }.get(kind, MessageTypes.OBSERVATION)
