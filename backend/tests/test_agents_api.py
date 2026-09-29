"""Agent CRUD + seed tests."""


async def test_seed_agents_exist(client):
    resp = await client.get("/api/agents")
    names = {a["name"] for a in resp.json()["agents"]}
    assert {"GPT", "Claude", "Gemini", "Grok", "Kimi"} <= names


async def test_create_and_patch_agent(client):
    resp = await client.post(
        "/api/agents",
        json={"name": "Nova", "provider": "mock", "role": "scout", "personality": ["bold"]},
    )
    assert resp.status_code == 201
    agent = resp.json()
    assert agent["name"] == "Nova"

    patch = await client.patch(f"/api/agents/{agent['id']}", json={"role": "navigator"})
    assert patch.json()["role"] == "navigator"


async def test_duplicate_agent_name_conflict(client):
    resp = await client.post("/api/agents", json={"name": "GPT"})
    assert resp.status_code == 409


async def test_delete_agent(client):
    created = await client.post("/api/agents", json={"name": "Temp"})
    resp = await client.delete(f"/api/agents/{created.json()['id']}")
    assert resp.json()["ok"] is True
    missing = await client.get(f"/api/agents/{created.json()['id']}")
    assert missing.status_code == 404
