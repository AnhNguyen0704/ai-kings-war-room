"""Provider abstraction tests: mock behaviour, parsing helpers, manager fallback."""
import json

from app.agents.prompts import extract_json, parse_vote
from app.providers.base import ChatMessage
from app.providers.manager import ProviderManager
from app.providers.mock import MockProvider


async def test_mock_generate_returns_text():
    provider = MockProvider()
    text = await provider.generate([ChatMessage(role="user", content="hello")])
    assert isinstance(text, str) and len(text) > 20


async def test_mock_stream_yields_words():
    provider = MockProvider()
    chunks = [c async for c in provider.stream([ChatMessage(role="user", content="hello")])]
    assert len(chunks) > 5
    assert "".join(chunks).strip()


def test_mock_judge_hint_returns_valid_json():
    provider = MockProvider()
    hint = json.dumps({"kind": "judge", "agent": "JUDGE", "task": "chon database", "candidates": ["GPT", "Kimi"]})
    msg = ChatMessage(role="user", content=f"[MOCK-HINT]\n{hint}\n[/MOCK-HINT]")
    raw = provider._compose([msg])
    decision = extract_json(raw)
    assert decision is not None
    assert "decision" in decision
    assert isinstance(decision["reasoning"], list)
    assert 0 <= float(decision["confidence"]) <= 1


def test_mock_vote_hint_parses():
    provider = MockProvider()
    hint = json.dumps({"kind": "vote", "agent": "GPT", "task": "t", "candidates": ["Claude", "Kimi"]})
    msg = ChatMessage(role="user", content=f"[MOCK-HINT]\n{hint}\n[/MOCK-HINT]")
    raw = provider._compose([msg])
    choice, rationale = parse_vote(raw)
    assert choice in ("Claude", "Kimi")
    assert rationale.strip()


def test_parse_vote_formats():
    assert parse_vote("VOTE: GPT\nRATIONALE: strong case") == ("GPT", "strong case")
    assert parse_vote("garbage")[0] == "abstain"


def test_extract_json_fenced_and_embedded():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('blabla {"a": {"b": 2}} blabla') == {"a": {"b": 2}}
    assert extract_json("no json here") is None


def test_manager_falls_back_to_mock_without_keys():
    manager = ProviderManager()
    resolved = manager.resolve("openai", "gpt-4o")
    assert isinstance(resolved, MockProvider)
    assert resolved.fallback_from == "openai"
    auto = manager.resolve("auto", "")
    assert isinstance(auto, MockProvider)
    judge = manager.resolve_judge()
    assert isinstance(judge, MockProvider)
    assert all(item["live"] is False for item in manager.status() if item["kind"] == "llm")
