"""WebSocket realtime tests - run against a real uvicorn subprocess so the
protocol (connect sync, chat -> events, ping/pong) is exercised end-to-end."""
import asyncio
import json
import os
import pathlib
import subprocess
import sys
import time

import httpx
import pytest

_BACKEND = pathlib.Path(__file__).resolve().parent.parent
_PORT = 8199
_BASE = f"http://127.0.0.1:{_PORT}"


@pytest.fixture(scope="module")
def server():
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite+aiosqlite:///{(_BACKEND / 'data' / 'ws_test.db').as_posix()}",
        "MOCK_THINK_DELAY": "0.01",
        "MOCK_TOKEN_DELAY": "0",
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(_PORT), "--log-level", "warning"],
        cwd=str(_BACKEND),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(80):
        try:
            if httpx.get(f"{_BASE}/api/health", timeout=1).status_code == 200:
                break
        except Exception:
            time.sleep(0.25)
    else:
        proc.terminate()
        raise RuntimeError("ws test server did not start")
    yield _BASE
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture()
def room_id(server):
    rooms = httpx.get(f"{server}/api/rooms").json()["rooms"]
    return rooms[0]["id"]


async def _recv_events(ws, seconds: float) -> list[dict]:
    events = []
    try:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=seconds)
            events.append(json.loads(raw))
            seconds = 0.5
    except (asyncio.TimeoutError, TimeoutError):
        pass
    return events


async def test_ws_connect_syncs_state(server, room_id):
    import websockets

    async with websockets.connect(f"ws://127.0.0.1:{_PORT}/ws/rooms/{room_id}") as ws:
        first = json.loads(await ws.recv())
        assert first["event"] == "room_state"
        events = await _recv_events(ws, 1.0)
        statuses = [e for e in events if e["event"] == "agent_status"]
        assert len(statuses) >= 5


async def test_ws_ping_pong(server, room_id):
    import websockets

    async with websockets.connect(f"ws://127.0.0.1:{_PORT}/ws/rooms/{room_id}") as ws:
        await ws.recv()  # room_state
        await ws.send(json.dumps({"type": "ping"}))
        for _ in range(15):
            event = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            if event["event"] == "pong":
                break
        else:
            pytest.fail("no pong received")


async def test_ws_chat_streams_and_completes(server, room_id):
    import websockets

    async with websockets.connect(f"ws://127.0.0.1:{_PORT}/ws/rooms/{room_id}") as ws:
        await ws.recv()  # room_state
        await ws.send(json.dumps({"type": "command", "command": "stop", "args": ""}))  # ensure idle
        await asyncio.sleep(0.3)
        await ws.send(json.dumps({"type": "chat", "content": "/ask quick ws question?"}))
        events = []
        for _ in range(400):
            try:
                events.append(json.loads(await asyncio.wait_for(ws.recv(), timeout=20)))
            except (asyncio.TimeoutError, TimeoutError):
                break
            if len(events) > 4000:
                break
    kinds = [e["event"] for e in events]
    assert "message_new" in kinds
    assert "message_delta" in kinds, "streaming deltas must arrive over WS"
    completes = [e for e in events if e["event"] == "message_complete"]
    assert len(completes) >= 5  # five quick answers
