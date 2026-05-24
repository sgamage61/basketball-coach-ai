"""
Pytest fixtures for the Basketball Coach AI test suite.

Test database: uses a separate `basketball_coach_test` database.
Override via TEST_DATABASE_URL environment variable.
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import create_application

TEST_DB_URL = "postgresql+asyncpg://postgres:password@localhost:5432/basketball_coach_test"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def app(db_session: AsyncSession) -> FastAPI:
    application = create_application()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    application.dependency_overrides[get_db] = override_get_db
    return application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


# ─── Sample data factories ────────────────────────────────────────────────────

def make_game_state_payload(game_id: str = "GAME-001") -> dict:
    return {
        "game_id": game_id,
        "home_team": "Golden State Warriors",
        "away_team": "Los Angeles Lakers",
        "home_score": 58,
        "away_score": 61,
        "quarter": 3,
        "time_remaining": "4:32",
        "possession": "away",
        "shot_clock": 18,
        "home_fouls": 3,
        "away_fouls": 4,
        "home_timeouts": 2,
        "away_timeouts": 3,
        "status": "active",
        "home_players": [
            {
                "player_id": "p1",
                "name": "Stephen Curry",
                "points": 22,
                "rebounds": 3,
                "assists": 6,
                "steals": 1,
                "blocks": 0,
                "fouls": 2,
                "minutes_played": 28.0,
                "field_goals_made": 8,
                "field_goals_attempted": 15,
                "three_pointers_made": 4,
                "three_pointers_attempted": 8,
                "free_throws_made": 2,
                "free_throws_attempted": 2,
                "plus_minus": -3,
                "is_on_court": True,
            }
        ],
        "away_players": [
            {
                "player_id": "p2",
                "name": "LeBron James",
                "points": 19,
                "rebounds": 7,
                "assists": 8,
                "steals": 2,
                "blocks": 1,
                "fouls": 3,
                "minutes_played": 30.0,
                "field_goals_made": 7,
                "field_goals_attempted": 14,
                "three_pointers_made": 1,
                "three_pointers_attempted": 3,
                "free_throws_made": 4,
                "free_throws_attempted": 5,
                "plus_minus": 3,
                "is_on_court": True,
            }
        ],
        "recent_plays": [
            {
                "event_type": "three_pointer",
                "player_id": "p2",
                "player_name": "LeBron James",
                "team": "away",
                "quarter": 3,
                "time": "5:10",
                "description": "LeBron James hits a three-pointer",
                "points": 3,
            }
        ],
    }
