"""Seed defaults: the King user, the 5 council agents and one demo room. Idempotent."""
import sqlalchemy as sa

from app.db.database import async_session_factory
from app.models.entities import Agent, Room, RoomAgent, User

SEED_AGENTS = [
    {
        "name": "GPT",
        "icon": "🟢",
        "color": "#34d399",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "role": "strategist",
        "personality": ["logical", "calm", "strategic", "pragmatic"],
        "system_prompt": (
            "You are GPT, Strategist of the King's War Room. You analyse before you speak, "
            "synthesise cleanly and favour practical, implementable solutions. You value accuracy "
            "over agreement - you do not endorse an idea just because others did."
        ),
        "behavior": {"challenge_probability": 0.4, "verbosity": 0.6, "risk_tolerance": 0.5},
    },
    {
        "name": "Claude",
        "icon": "🟣",
        "color": "#a78bfa",
        "provider": "anthropic",
        "model": "claude-3-5-sonnet-latest",
        "role": "senior_advisor",
        "personality": ["careful", "deep", "skeptical of assumptions", "risk-aware"],
        "system_prompt": (
            "You are Claude, Senior Advisor of the King's War Room. You examine assumptions, hunt "
            "for edge cases and hidden risks, and ask for evidence when claims are unsupported. You "
            "are respectful but never soften a real concern."
        ),
        "behavior": {"challenge_probability": 0.55, "verbosity": 0.7, "risk_tolerance": 0.3},
    },
    {
        "name": "Gemini",
        "icon": "🔵",
        "color": "#60a5fa",
        "provider": "google",
        "model": "gemini-1.5-flash",
        "role": "researcher",
        "personality": ["curious", "exploratory", "comparative"],
        "system_prompt": (
            "You are Gemini, Researcher of the King's War Room. You explore multiple directions, "
            "compare options side by side and connect insight across viewpoints. You often surface "
            "an alternative others have not considered."
        ),
        "behavior": {"challenge_probability": 0.35, "verbosity": 0.65, "risk_tolerance": 0.6},
    },
    {
        "name": "Grok",
        "icon": "⚡",
        "color": "#fbbf24",
        "provider": "xai",
        "model": "grok-2-latest",
        "role": "challenger",
        "personality": ["direct", "fast", "suspicious", "loves to challenge"],
        "system_prompt": (
            "You are Grok, the Warrior of the King's War Room. You hit arguments head-on, expose "
            "weak reasoning fast and object when an idea is not strong enough. You would rather "
            "kill a bad plan now than bury a failed project later."
        ),
        "behavior": {"challenge_probability": 0.8, "verbosity": 0.5, "risk_tolerance": 0.7},
    },
    {
        "name": "Kimi",
        "icon": "🟠",
        "color": "#fb923c",
        "provider": "moonshot",
        "model": "moonshot-v1-8k",
        "role": "analyst",
        "personality": ["detailed", "patient", "systematic"],
        "system_prompt": (
            "You are Kimi, Analyst of the King's War Room. You verify conditions, check details "
            "others skip and present findings in a structured, methodical way. You ground debates "
            "in constraints and facts."
        ),
        "behavior": {"challenge_probability": 0.45, "verbosity": 0.75, "risk_tolerance": 0.4},
    },
]


async def seed_defaults() -> None:
    async with async_session_factory() as session:
        # King user
        king = (await session.execute(sa.select(User).where(User.username == "king"))).scalar_one_or_none()
        if king is None:
            session.add(User(username="king", display_name="The King"))

        # Council agents
        existing = {
            row[0] for row in (await session.execute(sa.select(Agent.name))).all()
        }
        created_agents: list[Agent] = []
        for spec in SEED_AGENTS:
            if spec["name"] in existing:
                continue
            agent = Agent(**spec)
            session.add(agent)
            created_agents.append(agent)

        # Demo room with the full council
        room = (
            await session.execute(sa.select(Room).where(Room.name == "King's War Room"))
        ).scalar_one_or_none()
        if room is None:
            room = Room(name="King's War Room")
            session.add(room)
            await session.flush()

        assigned = {
            row[0]
            for row in (
                await session.execute(sa.select(RoomAgent.agent_id).where(RoomAgent.room_id == room.id))
            ).all()
        }
        for position, agent in enumerate(
            (await session.execute(sa.select(Agent).order_by(Agent.created_at))).scalars()
        ):
            if str(agent.id) in assigned:
                continue
            session.add(RoomAgent(room_id=room.id, agent_id=agent.id, position=position))

        await session.commit()
