# 👑 AI King's War Room

A realtime multi-agent council: you are the King, LLM agents (GPT, Claude, Gemini, Grok, Kimi) are your advisors. They propose, challenge, rebut, vote — and a Judge synthesises the final report. The final word is always yours.

Runs **end-to-end with zero API keys** via a built-in Mock Provider; add real keys and the same agents call real models. Architecture is provider-agnostic — no vendor logic is hard-coded.

---

## 1. Architecture

```
User (King)
   │  React + Vite + Tailwind + Zustand
   ▼
Frontend  ──REST──►  FastAPI (api/)          ──► PostgreSQL / SQLite
   │                    │
   └──WebSocket──►  RoomController (orchestration/)
                        ├─ Command Router    (/debate /ask /stop /vote /judge …)
                        ├─ Agent Runtimes    (agents/)   one per agent per room
                        ├─ Debate Engine     proposals → discussion → voting → judge
                        ├─ Judge/Synthesizer (agents/judge.py)
                        ├─ Provider Manager  (providers/) adapter per vendor + mock
                        └─ Event Bus (events/)  in-memory or Redis pub/sub
                              │
                              └──► WebSocket Manager ──► every connected client
```

Core principles: separation of concerns, provider abstraction (agents never touch vendor SDKs), event-driven realtime, full error isolation (one failing agent never kills a room), everything persisted (messages, votes, decisions, events, memory).

Details: [docs/architecture.md](docs/architecture.md) · [agent-system](docs/agent-system.md) · [debate-engine](docs/debate-engine.md) · [websocket](docs/websocket.md) · [provider-system](docs/provider-system.md)

## 2. Installation

```bash
# backend (Python 3.11+)
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# frontend (Node 18+)
cd ../frontend
npm install
```

## 3. Environment variables

Copy `.env.example` → `.env` (backend dir or repo root). All keys optional — missing keys fall back to the Mock Provider:

| Variable | Meaning |
|---|---|
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` / `XAI_API_KEY` / `MOONSHOT_API_KEY` | LLM provider keys |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/warroom.db` (dev) or `postgresql+asyncpg://…` |
| `REDIS_URL` | empty = in-memory bus; `redis://…` for multi-process |
| `JUDGE_PROVIDER` / `JUDGE_MODEL` | `auto` uses first live provider |
| `DISCUSSION_ROUNDS`, `AGENT_TURN_TIMEOUT`, `TRANSCRIPT_WINDOW` | debate tuning |
| `MOCK_THINK_DELAY`, `MOCK_TOKEN_DELAY` | mock pacing (0 for tests) |

## 4. Running locally

```bash
# terminal 1 — backend on :8000 (creates DB + seeds 5 agents + demo room)
cd backend && uvicorn app.main:app --reload

# terminal 2 — frontend on :5173 (proxies /api and /ws to :8000)
cd frontend && npm run dev
```

Open http://localhost:5173 → enter **King's War Room** → type a task → watch the council debate in realtime.

## 5. Docker

```bash
cp .env.example .env   # optional: fill real API keys
docker compose up --build
```

Services: `frontend` (nginx, :8080) → `backend` (:8000) → `db` (Postgres 16) + `redis` 7. Backend runs `alembic upgrade head` on boot. Open http://localhost:8080.

## 6. Creating agents

```bash
curl -X POST localhost:8000/api/agents -H 'Content-Type: application/json' -d '{
  "name": "Nova", "provider": "openai", "model": "gpt-4o-mini",
  "role": "scout", "personality": ["bold", "fast"],
  "system_prompt": "You are Nova…",
  "behavior": {"challenge_probability": 0.6, "verbosity": 0.5, "risk_tolerance": 0.7}
}'
```

Or at runtime: `/add-agent Nova` (provider `auto`), then edit via `PATCH /api/agents/{id}`. The Agent Card in the UI (click an agent) shows persona, provider, stats.

## 7. Creating rooms

```bash
curl -X POST localhost:8000/api/rooms -H 'Content-Type: application/json' -d '{"name": "Strategy Room"}'
```

New rooms automatically seat every active agent. Add/remove per-room via `POST /api/rooms/{id}/agents` and `DELETE /api/rooms/{id}/agents/{agent_id}`, or `/silence <name>` / `/activate <name>` to mute temporarily.

## 8. Adding an LLM provider

1. Implement `app/providers/base.py::LLMProvider` (`stream()` yielding text chunks).
2. Register it in `app/providers/manager.py` (a `_build` branch + env key in `config.py`).
3. Point any agent at it: `provider: "yourprovider"`. No other code changes — agents only know the interface.

See [docs/provider-system.md](docs/provider-system.md).

## 9. Debate flow

```
TASK → PROPOSALS (each agent) → DISCUSSION (challenge/rebuttal/observe, N rounds,
behaviour-driven) → VOTING → JUDGE (independent synthesis, JSON verdict) →
FINAL REPORT (decision, reasoning, confidence, open questions, dissent) → shared memory
```

The King can `/stop` anytime, force `/vote` or `/judge`, or use `/ask` for quick answers without a full debate. The Judge only *recommends* — authority stays with the King. Details: [docs/debate-engine.md](docs/debate-engine.md).

## 10. API documentation

Interactive: http://localhost:8000/docs (OpenAPI/Swagger). Summary:

| Method & path | Purpose |
|---|---|
| `GET /api/health`, `GET /api/providers` | health, provider/judge status |
| `GET/POST /api/rooms`, `GET/PATCH/DELETE /api/rooms/{id}` | room CRUD |
| `GET /api/rooms/{id}/messages · /events · /memories · /decision` | history & observability |
| `POST /api/rooms/{id}/chat` | send King text (plain task or `/command`) |
| `POST /api/rooms/{id}/commands` | buttons/commands: debate/stop/vote/judge/silence/… |
| `POST /api/rooms/{id}/reset` | wipe room |
| `GET/POST/PATCH/DELETE /api/agents` | agent CRUD |
| `WS /ws/rooms/{id}` | realtime events (see docs/websocket.md) |

### Commands

```
/ask <q>  /debate <task>  /assign [agent] <task>  /vote  /judge  /stop
/add-agent <n>  /remove-agent <n>  /silence <n>  /activate <n>  /reset  /memory  /help
```

## 11. Tests

```bash
cd backend && python -m pytest tests/ -q     # 28 tests: debate lifecycle, commands,
                                             # providers, rooms, agents, WebSocket E2E
```

## Project structure

```
ai-kings-war-room/
├── backend/app/
│   ├── api/            REST routes + WebSocket endpoint
│   ├── agents/         AgentProfile, AgentRuntime, prompts, Judge
│   ├── orchestration/  RoomController, DebateEngine, commands, registry
│   ├── providers/      LLMProvider base + openai/anthropic/google/xai/moonshot/mock
│   ├── events/         event bus (in-memory / Redis) + event types
│   ├── memory/         (memory via MemoryItem; see docs)
│   ├── models/         SQLAlchemy entities      ├── schemas/  serializers
│   ├── core/           config, runtime, logging ├── websocket/ WS manager
│   └── db/             engine, seed
├── backend/migrations/ Alembic
├── frontend/src/       components/ pages/ stores/ services/ types/
├── docker/             Dockerfiles
├── docker-compose.yml  · .env.example · docs/
```
