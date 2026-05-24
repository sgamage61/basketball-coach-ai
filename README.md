# Basketball Coach AI

A production-ready **agentic AI basketball coaching backend** built with FastAPI, async SQLAlchemy, Redis, and OpenAI. When a timeout is called, a multi-agent pipeline analyses the live game state and returns structured coaching recommendations with confidence scores, strategic adjustments, and key matchup notes — in real time.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FastAPI Application                         │
│                                                                     │
│  REST API (/api/v1)          WebSocket (/ws/game/{id})              │
│  ├── POST /game/update       └── Real-time broadcast via Redis      │
│  ├── POST /game/timeout           pub/sub                           │
│  └── GET  /game/state/{id}                                          │
│                                                                     │
│  ┌─────────────────── Timeout Agent Pipeline ──────────────────┐   │
│  │  GameStateAgent → AnalyticsAgent → StrategyAgent            │   │
│  │       └──────────────────────────────→ RecommendationAgent  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Services          Repositories       Workers (Celery)              │
│  ├── GameService   └── GameRepository ├── process_game_snapshot    │
│  ├── OpenAIService                    ├── generate_halftime_report  │
│  └── TimeoutOrchestrator              └── notify_coaching_staff     │
└─────────────────────────────────────────────────────────────────────┘
         │                    │                        │
    PostgreSQL              Redis               OpenAI API
```

### Agent Pipeline (Timeout Workflow)

```
Timeout Event
     │
     ▼
GameStateAgent          Parses, validates, enriches game state snapshot
     │  writes → pipeline_data["game_state"]
     ▼
AnalyticsAgent          Derives statistical insights (momentum, hot/cold players,
     │  writes → pipeline_data["analytics"]   differential stats, pace)
     ▼
StrategyAgent           Maps analytics to tactical adjustments & key matchups
     │  writes → pipeline_data["strategy"]
     ▼
RecommendationAgent     Synthesises all data into primary recommendation +
                        confidence score + reasoning
     │
     ▼
RecommendationResponse  Structured JSON returned to API caller + persisted to DB
                        + cached in Redis + broadcast over WebSocket
```

---

## Project Structure

```
basketball-coach-ai/
├── app/
│   ├── main.py                   # FastAPI application factory
│   ├── api/
│   │   ├── deps.py               # Dependency injection providers
│   │   └── v1/
│   │       ├── router.py
│   │       └── endpoints/
│   │           ├── game.py       # POST /game/update|timeout, GET /game/state
│   │           └── health.py     # GET /health
│   ├── agents/
│   │   ├── base.py               # Abstract BaseAgent, AgentContext, AgentResult
│   │   ├── game_state_agent.py
│   │   ├── analytics_agent.py
│   │   ├── strategy_agent.py
│   │   └── recommendation_agent.py
│   ├── core/
│   │   ├── config.py             # Pydantic Settings (env-driven)
│   │   ├── database.py           # Async SQLAlchemy engine & session
│   │   ├── redis.py              # Redis pool + RedisCache helper
│   │   └── logging.py            # Structlog configuration
│   ├── models/
│   │   └── game.py               # SQLAlchemy ORM: GameState, RecommendationLog
│   ├── schemas/
│   │   ├── game.py               # Pydantic I/O schemas
│   │   └── recommendations.py    # RecommendationResponse schema
│   ├── repositories/
│   │   └── game_repository.py    # DB access layer (upsert, log_recommendation)
│   ├── services/
│   │   ├── game_service.py       # Game state business logic + cache management
│   │   ├── openai_service.py     # OpenAI async client abstraction
│   │   └── timeout_orchestrator.py  # Orchestrates the 4-agent pipeline
│   ├── websockets/
│   │   ├── connection_manager.py # WebSocket connection registry
│   │   └── game_socket.py        # /ws/game/{game_id} route + Redis listener
│   └── workers/
│       └── game_worker.py        # Celery tasks (snapshots, reports, notifications)
├── tests/
│   ├── conftest.py               # Fixtures, test DB, sample data factories
│   └── test_game.py              # Integration tests for all endpoints
├── alembic/                      # Database migrations
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## Prerequisites

- Python 3.12+
- Docker & Docker Compose (recommended)
- PostgreSQL 15+ (if running without Docker)
- Redis 7+ (if running without Docker)

---

## Quick Start

### Option A — Docker Compose (recommended)

```bash
# 1. Clone and enter the project
git clone <your-repo-url> basketball-coach-ai
cd basketball-coach-ai

# 2. Copy env file and add your OpenAI key
cp .env.example .env
# Edit .env → set OPENAI_API_KEY

# 3. Start all services
docker compose up --build

# 4. Run database migrations
docker compose exec api alembic upgrade head

# API is live at http://localhost:8000
# Swagger docs at http://localhost:8000/docs  (APP_DEBUG=true)
```

### Option B — Local Development

```bash
# 1. Create virtualenv
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Copy and configure env
cp .env.example .env

# 4. Start infrastructure (PostgreSQL + Redis)
docker compose up postgres redis -d

# 5. Run migrations
alembic upgrade head

# 6. Start the API server
uvicorn app.main:app --reload
```

---

## API Reference

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Service health check |

### Game

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/game/update` | Ingest a live game state update |
| POST | `/api/v1/game/timeout` | Trigger AI timeout analysis |
| GET | `/api/v1/game/state/{game_id}` | Retrieve current game state |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `WS /ws/game/{game_id}` | Subscribe to real-time game events |

#### WebSocket Message Protocol

**Server → Client:**
```json
{ "type": "connected",      "game_id": "...", "timestamp": "..." }
{ "type": "state_update",   "game_id": "...", "timestamp": "..." }
{ "type": "recommendation", "game_id": "...", "data": { ... } }
{ "type": "pong",           "timestamp": "..." }
```

**Client → Server:**
```json
{ "type": "ping" }
```

---

## Example: Timeout Request & Response

**Request:**
```json
POST /api/v1/game/timeout
{
  "game_id": "GAME-2024-GSW-LAL-001",
  "team": "home",
  "quarter": 4,
  "time_remaining": "2:30",
  "reason": "opponent scoring run"
}
```

**Response:**
```json
{
  "game_id": "GAME-2024-GSW-LAL-001",
  "requesting_team": "home",
  "quarter": 4,
  "time_remaining": "2:30",
  "confidence_score": 0.85,
  "primary_recommendation": "Switch to zone defence to disrupt opponent rhythm",
  "alternative_recommendations": [
    "Double-team their primary ball-handler on every possession",
    "Push tempo off defensive rebounds to get easier buckets"
  ],
  "reasoning": "Opponent has a 7-2 scoring run. Your best defender has foul trouble...",
  "analytics_summary": { ... },
  "strategy_adjustments": [ ... ],
  "key_matchups": [ ... ],
  "agent_traces": [
    { "agent_name": "game_state_agent",     "success": true, "processing_time_ms": 2.1 },
    { "agent_name": "analytics_agent",      "success": true, "processing_time_ms": 3.4 },
    { "agent_name": "strategy_agent",       "success": true, "processing_time_ms": 4.8 },
    { "agent_name": "recommendation_agent", "success": true, "processing_time_ms": 1.9 }
  ],
  "total_processing_time_ms": 14.2,
  "generated_at": "2024-11-15T21:43:10.000Z"
}
```

---

## Running Tests

```bash
# All tests with coverage
pytest

# Single file
pytest tests/test_game.py -v

# Watch mode
pytest-watch
```

> Tests require a live PostgreSQL instance at `basketball_coach_test`.  
> Start it with `docker compose up postgres -d` before running tests.

---

## Development Commands

```bash
# Linting
ruff check .

# Auto-fix lint issues
ruff check . --fix

# Type checking
mypy app/

# Format
ruff format .

# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Start Celery worker
celery -A app.workers.game_worker worker --loglevel=info -Q game_events
```

---

## Configuration

All configuration is via environment variables (see `.env.example`).

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `development` | Environment name |
| `APP_DEBUG` | `true` | Enable debug mode, Swagger UI |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async PostgreSQL URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `OPENAI_API_KEY` | — | **Required** for AI recommendations |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model to use |
| `LOG_LEVEL` | `INFO` | Log verbosity |
| `GAME_STATE_TTL` | `3600` | Game state cache TTL (seconds) |
| `RECOMMENDATION_TTL` | `300` | Recommendation cache TTL (seconds) |

---

## Extending the Agent Pipeline

Add a new agent by:

1. Creating `app/agents/my_agent.py` extending `BaseAgent`
2. Implementing `async def run(self, context: AgentContext) -> AgentResult`
3. Writing outputs to `context.pipeline_data["my_agent"]`
4. Inserting it into the `self._agents` list in `TimeoutOrchestrator`

```python
from app.agents.base import AgentContext, AgentResult, BaseAgent

class MyAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("my_agent")

    async def run(self, context: AgentContext) -> AgentResult:
        # Read from prior agents
        game = context.pipeline_data.get("game_state", {})
        # ... compute something ...
        context.pipeline_data["my_agent"] = {"result": "..."}
        return AgentResult(agent_name=self.name, success=True, data={"result": "..."})
```

---

## License

MIT
