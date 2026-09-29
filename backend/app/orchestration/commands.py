"""King's command parser: /ask /debate /assign /vote /judge /stop /add-agent
/remove-agent /silence /activate /reset /memory. Buttons in the UI call the
same handler via POST /api/rooms/{id}/commands."""
from dataclasses import dataclass


@dataclass
class ParsedCommand:
    name: str          # "chat" when the text is a plain task/question
    args: str


def parse_command(text: str) -> ParsedCommand:
    text = (text or "").strip()
    if not text.startswith("/"):
        return ParsedCommand(name="chat", args=text)
    parts = text[1:].split(maxsplit=1)
    name = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""
    known = {
        "ask", "debate", "assign", "vote", "judge", "stop", "add-agent", "remove-agent",
        "silence", "activate", "reset", "memory", "help",
    }
    if name not in known:
        return ParsedCommand(name="chat", args=text)
    return ParsedCommand(name=name, args=args)


COMMAND_HELP = (
    "King's commands: /ask <question> - quick answers | /debate <task> - full debate | "
    "/vote - force voting | /judge - force judging | /stop - stop the debate | "
    "/silence <agent> | /activate <agent> | /add-agent <name> | /remove-agent <name> | "
    "/reset - wipe room | /memory - show council memory"
)
