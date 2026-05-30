# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## FastAPI Startup Rule

Whenever you provide a command to start the FastAPI server, always include the --reload flag.

Use:
uvicorn main:app --reload

Never suggest running uvicorn without --reload in development.

## Dev Instructions

The FastAPI server is always running using:
uvicorn main:app --reload

Assume all code changes are automatically reloaded by the server.
Do not suggest manually restarting the server.

## Commands

```bash
# Run the API (reload mode). This should
uvicorn app.main:app --reload          # or: serve  (console script → app.main:run)

# Start a Celery worker (consumes the game_events queue)
celery -A app.workers.game_worker worker --loglevel=info -Q game_events

# Tests (pytest-cov + asyncio auto-mode are pre-configured in pyproject.toml)
pytest                                  # full suite with coverage
pytest tests/test_game.py -v            # single file
pytest tests/test_game.py::test_name    # single test

# Lint / format / type-check
ruff check . [--fix]
ruff format .
mypy app/                               # strict mode + pydantic plugin

# Migrations
alembic revision --autogenerate -m "msg"
alembic upgrade head
alembic downgrade -1

# Local infra only (Postgres + Redis), then run the app on the host
docker compose up postgres redis -d
# Full stack (api + worker + postgres + redis):
docker compose up --build && docker compose exec api alembic upgrade head
```

**Tests require a live Postgres** at the `basketball_coach_test` database (see `TEST_DB_URL` in `tests/conftest.py`). `conftest.py` creates/drops all tables per session and overrides the `get_db` dependency with a rollback-per-test session — tests never commit. Start Postgres with `docker compose up postgres -d` before running.

## Architecture

Async FastAPI backend that converts live basketball game state into structured coaching recommendations. Strictly layered with one-directional dependencies:

```
HTTP / WebSocket → api/ (routing + DI) → services/ + agents/ → repositories/ → models/ → DB
```

- **The repository boundary is enforced.** Only `app/repositories/` touches the ORM. Services and the orchestrator go through `GameRepository` — do not import models directly elsewhere.
- **`OpenAIService` is the single LLM chokepoint.** Swap providers there; agents/services must not import the OpenAI SDK directly.
- **Unit of work per request.** `get_db()` (`app/core/database.py`) commits on success / rolls back on exception. Repository methods use `flush()`, never `commit()` — the dependency owns the transaction. The engine adapts pool args for SQLite (local dev) vs Postgres (prod).
- **Config** is a `@lru_cache` singleton (`app/core/config.py`), env-driven via pydantic-settings. `/docs`, `/redoc`, `/openapi.json` are only mounted when `APP_DEBUG=true`.

### The timeout agent pipeline (the core feature)

`POST /api/v1/game/timeout` runs a four-stage pipeline orchestrated by `TimeoutOrchestrator` (`app/services/timeout_orchestrator.py`):

```
GameStateAgent → AnalyticsAgent → StrategyAgent → RecommendationAgent
```

Agents follow a **blackboard pattern**: each reads from and writes to the shared mutable `AgentContext.pipeline_data` dict under a named key (`"game_state"`, `"analytics"`, `"strategy"`). `BaseAgent.__call__` (`app/agents/base.py`) wraps every agent with timing, error capture, and logging — an agent that throws returns a failed `AgentResult` instead of crashing the pipeline, and the orchestrator continues with partial data. Per-agent `AgentTrace`s are surfaced in the API response for observability.

**Current agents are deterministic rule engines, not LLM calls** — `OpenAIService` exists but is not yet wired into the timeout pipeline.

To add an agent: extend `BaseAgent`, implement `async run()`, write outputs to `context.pipeline_data["<name>"]`, and insert it into `self._agents` in `TimeoutOrchestrator.__init__`.

`RecommendationAgent` is the terminal agent: it writes its synthesised output to `pipeline_data["recommendation_agent"]`, and `TimeoutOrchestrator` reads that key directly to build the `RecommendationResponse` (falling back to schema defaults only if the agent failed and never wrote its key). Keep this contract — the orchestrator no longer re-derives the recommendation itself.

### Real-time (WebSocket + Redis pub/sub)

Cross-process fan-out scales via **Redis pub/sub**, not the in-memory registry. `POST /game/update` publishes to channel `game_updates:{game_id}`; each WebSocket connection runs a background listener (`_redis_listener` in `app/websockets/game_socket.py`) subscribed to that channel and forwards messages to its client. `ConnectionManager` is an in-memory singleton (`game_id → set[WebSocket]`) used only for local delivery — so multiple API replicas stay in sync without sticky sessions.

### Caching

`GameService` is cache-first: `get_game_state` reads Redis (`game_state:{id}`) then DB-with-backfill; `update_game_state` invalidates the key. Recommendations are cached at `recommendation:{game_id}:latest`. TTLs come from settings (`GAME_STATE_TTL`, `RECOMMENDATION_TTL`).

### Data model

`GameState` is a hybrid table: query-relevant fields (scores, clock, fouls, timeouts) are columns; nested `home_players`/`away_players`/`recent_plays` live in a `game_data` JSON blob. `RecommendationLog` is an append-only audit trail storing the full response as JSON.

### Background workers

`app/workers/game_worker.py` defines Celery tasks (`process_game_snapshot`, `generate_halftime_report`, `notify_coaching_staff`) with routing/retry config — but the bodies are **stubs (`TODO`)** and nothing currently enqueues them.

## Conventions

- Python 3.12, mypy `strict = true`, ruff line-length 100. `ANN101`/`ANN102` are ignored.
- Use `structlog` via `get_logger(__name__)` with key-value context (e.g. `logger.info("...", game_id=...)`), not f-strings.
- Pydantic v2 schemas in `app/schemas/` are the I/O contracts; agents re-validate raw dicts against them rather than trusting upstream shape.
