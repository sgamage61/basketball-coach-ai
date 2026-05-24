"""
Integration tests for the game endpoints.
"""

import pytest
from httpx import AsyncClient

from tests.conftest import make_game_state_payload


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "timestamp" in body


@pytest.mark.asyncio
async def test_update_game_state(client: AsyncClient) -> None:
    payload = make_game_state_payload("TEST-GAME-001")
    response = await client.post("/api/v1/game/update", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["game_id"] == "TEST-GAME-001"
    assert body["home_team"] == "Golden State Warriors"
    assert body["home_score"] == 58
    assert body["away_score"] == 61


@pytest.mark.asyncio
async def test_get_game_state_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/game/state/NONEXISTENT-GAME")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_game_state_after_update(client: AsyncClient) -> None:
    game_id = "TEST-GAME-002"
    payload = make_game_state_payload(game_id)

    # Create
    create_resp = await client.post("/api/v1/game/update", json=payload)
    assert create_resp.status_code == 200

    # Retrieve
    get_resp = await client.get(f"/api/v1/game/state/{game_id}")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["game_id"] == game_id


@pytest.mark.asyncio
async def test_update_game_state_invalid_payload(client: AsyncClient) -> None:
    response = await client.post("/api/v1/game/update", json={"game_id": ""})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_timeout_game_not_found(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/game/timeout",
        json={
            "game_id": "GHOST-GAME",
            "team": "home",
            "quarter": 4,
            "time_remaining": "2:00",
        },
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_timeout_generates_recommendation(client: AsyncClient) -> None:
    game_id = "TEST-TIMEOUT-GAME"
    # Seed game state first
    await client.post("/api/v1/game/update", json=make_game_state_payload(game_id))

    response = await client.post(
        "/api/v1/game/timeout",
        json={
            "game_id": game_id,
            "team": "home",
            "quarter": 3,
            "time_remaining": "4:32",
            "reason": "momentum shift",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["game_id"] == game_id
    assert "primary_recommendation" in body
    assert 0.0 <= body["confidence_score"] <= 1.0
    assert "reasoning" in body
    assert isinstance(body["agent_traces"], list)
    assert len(body["agent_traces"]) == 4  # All four agents ran
