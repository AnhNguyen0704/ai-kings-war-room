"""Debate lifecycle tests - the core orchestration guarantee: a plain King message
must produce proposals -> discussion -> votes -> judge -> final report."""
import asyncio

import pytest


async def _poll_until(client, room_id: str, predicate, timeout_s: float = 30.0):
    elapsed = 0.0
    while elapsed < timeout_s:
        messages = (await client.get(f"/api/rooms/{room_id}/messages")).json()["messages"]
        if predicate(messages):
            return messages
        await asyncio.sleep(0.1)
        elapsed += 0.1
    return messages  # last snapshot for assertion failure diagnostics


async def _snapshot(client, room_id: str):
    return (await client.get(f"/api/rooms/{room_id}")).json()


async def test_full_debate_lifecycle(client, seeded_room_id):
    sent = await client.post(f"/api/rooms/{seeded_room_id}/chat", json={"content": "PostgreSQL hay MongoDB?"})
    assert sent.status_code == 200

    messages = await _poll_until(
        client, seeded_room_id, lambda ms: any(m["message_type"] == "final" for m in ms), timeout_s=30
    )
    types = [m["message_type"] for m in messages]

    snap = await _snapshot(client, seeded_room_id)
    assert snap["room"]["state"] == "COMPLETED"

    # proposals from all 5 agents
    assert types.count("proposal") == 5
    # discussion happened
    assert any(t in types for t in ("challenge", "rebuttal", "observation", "agreement"))
    # votes from all 5 agents
    assert types.count("vote") == 5
    # judge final report exists with structured meta
    final = next(m for m in messages if m["message_type"] == "final")
    assert final["sender_type"] == "judge"
    decision_meta = final["meta"].get("decision")
    assert decision_meta and decision_meta.get("decision")
    assert 0 <= float(decision_meta.get("confidence", 0)) <= 1

    # structured decision persisted
    assert snap["decision"] is not None
    assert snap["decision"]["decision"]

    # reply chain: at least one message references another
    assert any(m["reply_to_id"] for m in messages)

    # shared memory written (spec section 15)
    memories = (await client.get(f"/api/rooms/{seeded_room_id}/memories")).json()["memories"]
    assert any(m["kind"] == "shared" and m["content"].startswith("Decision:") for m in memories)

    # event log for debugging populated (spec section 25)
    events = (await client.get(f"/api/rooms/{seeded_room_id}/events")).json()["events"]
    assert any(e["event_type"] == "debate_phase" for e in events)


async def test_quick_ask_skips_debate(client, seeded_room_id):
    await client.post(f"/api/rooms/{seeded_room_id}/chat", json={"content": "/ask Kien truc nao nhe?"})
    messages = await _poll_until(
        client, seeded_room_id, lambda ms: sum(1 for m in ms if m["message_type"] == "answer") >= 5
    )
    types = [m["message_type"] for m in messages]
    assert "final" not in types
    assert "vote" not in types
    assert sum(1 for t in types if t == "answer") == 5


async def test_stop_stops_debate(client, seeded_room_id):
    await client.post(
        f"/api/rooms/{seeded_room_id}/chat", json={"content": "Thiet ke kien truc Multi-Agent day du"}
    )
    await asyncio.sleep(0.15)  # let the debate start
    stopped = await client.post(f"/api/rooms/{seeded_room_id}/commands", json={"command": "stop"})
    assert stopped.status_code == 200

    async def _stopped():
        snap = await _snapshot(client, seeded_room_id)
        return snap["room"]["state"] in ("STOPPED", "COMPLETED")

    for _ in range(100):
        if await _stopped():
            break
        await asyncio.sleep(0.1)
    assert await _stopped()


async def test_only_one_debate_at_a_time(client, seeded_room_id):
    await client.post(f"/api/rooms/{seeded_room_id}/chat", json={"content": "Nhiem vu 1"})
    await asyncio.sleep(0.1)
    await client.post(f"/api/rooms/{seeded_room_id}/chat", json={"content": "Nhiem vu 2"})
    messages = await _poll_until(client, seeded_room_id, lambda ms: any(m["message_type"] == "system" and "already in session" in m["content"] for m in ms))
    assert any("already in session" in m["content"] for m in messages)
    # cleanup: stop the debate so teardown is clean
    await client.post(f"/api/rooms/{seeded_room_id}/commands", json={"command": "stop"})
    await asyncio.sleep(0.2)


async def test_debate_survives_silenced_agent(client, seeded_room_id):
    await client.post(f"/api/rooms/{seeded_room_id}/commands", json={"command": "silence", "args": "Grok"})
    await client.post(f"/api/rooms/{seeded_room_id}/chat", json={"content": "Ruby hay Python?"})
    messages = await _poll_until(client, seeded_room_id, lambda ms: any(m["message_type"] == "final" for m in ms))
    assert types_ok(messages)


def types_ok(messages) -> bool:
    senders_of_proposals = {m["sender_name"] for m in messages if m["message_type"] == "proposal"}
    return len(senders_of_proposals) == 4  # Grok silenced
