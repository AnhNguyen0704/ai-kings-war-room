"""Agent profile: the portable persona/config object agents run on (see spec section 6)."""
from dataclasses import dataclass, field

from app.models.entities import Agent


@dataclass
class AgentProfile:
    id: str
    name: str
    icon: str = "🤖"
    color: str = "#38bdf8"
    provider: str = "auto"
    model: str = ""
    role: str = "advisor"
    personality: list[str] = field(default_factory=list)
    system_prompt: str = ""
    behavior: dict = field(default_factory=dict)
    memory_enabled: bool = True
    active: bool = True
    silenced: bool = False
    # stats (mutable at runtime)
    messages: int = 0
    challenges: int = 0
    agreements: int = 0

    @classmethod
    def from_entity(cls, agent: Agent, silenced: bool = False) -> "AgentProfile":
        return cls(
            id=str(agent.id),
            name=agent.name,
            icon=agent.icon,
            color=agent.color,
            provider=agent.provider,
            model=agent.model,
            role=agent.role,
            personality=list(agent.personality or []),
            system_prompt=agent.system_prompt or "",
            behavior=dict(agent.behavior or {}),
            memory_enabled=agent.memory_enabled,
            active=agent.active,
            silenced=silenced,
        )

    @property
    def role_title(self) -> str:
        return (self.role or "advisor").replace("_", " ").title()

    @property
    def challenge_probability(self) -> float:
        return float(self.behavior.get("challenge_probability", 0.5))
