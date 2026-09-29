"""Room lifecycle tests: create -> inspect -> rename -> delete."""


async def test_create_room_assigns_all_agents(client):
    resp = await client.post("/api/rooms", json={"name": "Strategy Room"})
    assert resp.status_code == 201
    room = resp.json()

    detail = await client.get(f"/api/rooms/{room['id']}")
    snap = detail.json()
    assert snap["room"]["name"] == "Strategy Room"
    assert snap["room"]["state"] == "IDLE"
    assert len(snap["agents"]) == 5
    assert all("status" in a and "stats" in a for a in snap["agents"])


async def test_rename_room(client, seeded_room_id):
    resp = await client.patch(f"/api/rooms/{seeded_room_id}", json={"name": "Renamed Room"})
    assert resp.json()["name"] == "Renamed Room"


async def test_delete_room(client):
    created = await client.post("/api/rooms", json={"name": "Doomed"})
    room_id = created.json()["id"]
    resp = await client.delete(f"/api/rooms/{room_id}")
    assert resp.json()["ok"] is True
    assert (await client.get(f"/api/rooms/{room_id}")).status_code == 404


async def test_room_404(client):
    resp = await client.get("/api/rooms/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
