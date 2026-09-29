"""King's command tests: silence/activate, add/remove agent, reset, memory."""


async def _snapshot(client, room_id: str):
    return (await client.get(f"/api/rooms/{room_id}")).json()


async def test_silence_and_activate(client, seeded_room_id):
    resp = await client.post(
        f"/api/rooms/{seeded_room_id}/commands", json={"command": "silence", "args": "Grok"}
    )
    assert resp.status_code == 200
    snap = await _snapshot(client, seeded_room_id)
    grok = next(a for a in snap["agents"] if a["name"] == "Grok")
    assert grok["silenced"] is True

    await client.post(f"/api/rooms/{seeded_room_id}/commands", json={"command": "activate", "args": "Grok"})
    snap = await _snapshot(client, seeded_room_id)
    assert next(a for a in snap["agents"] if a["name"] == "Grok")["silenced"] is False


async def test_add_and_remove_agent(client, seeded_room_id):
    await client.post(f"/api/rooms/{seeded_room_id}/commands", json={"command": "add-agent", "args": "Nova"})
    snap = await _snapshot(client, seeded_room_id)
    assert any(a["name"] == "Nova" for a in snap["agents"])

    await client.post(f"/api/rooms/{seeded_room_id}/commands", json={"command": "remove-agent", "args": "Nova"})
    snap = await _snapshot(client, seeded_room_id)
    assert not any(a["name"] == "Nova" for a in snap["agents"])


async def test_reset_clears_room(client, seeded_room_id):
    await client.post(f"/api/rooms/{seeded_room_id}/chat", json={"content": "/ask ping?"})
    for _ in range(100):
        snap = await _snapshot(client, seeded_room_id)
        if snap["room"]["state"] == "COMPLETED":
            break
        await asyncio_sleep()
    resp = await client.post(f"/api/rooms/{seeded_room_id}/reset")
    snap = resp.json()
    assert snap["room"]["state"] == "IDLE"
    memories = (await client.get(f"/api/rooms/{seeded_room_id}/memories")).json()["memories"]
    assert memories == []
    messages = (await client.get(f"/api/rooms/{seeded_room_id}/messages")).json()["messages"]
    # only the reset system notice remains
    assert len(messages) == 1 and messages[0]["sender_type"] == "system"


async def test_memory_command_reports_empty(client, seeded_room_id):
    await client.post(f"/api/rooms/{seeded_room_id}/commands", json={"command": "memory"})
    messages = (await client.get(f"/api/rooms/{seeded_room_id}/messages")).json()["messages"]
    assert any("memory is empty" in m["content"] for m in messages)


async def test_help_command(client, seeded_room_id):
    await client.post(f"/api/rooms/{seeded_room_id}/commands", json={"command": "help"})
    messages = (await client.get(f"/api/rooms/{seeded_room_id}/messages")).json()["messages"]
    assert any("commands" in m["content"] for m in messages)


async def asyncio_sleep():
    await __import__("asyncio").sleep(0.1)
