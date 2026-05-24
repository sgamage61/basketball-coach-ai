import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import RedisCache, get_redis
from app.repositories.game_repository import GameRepository
from app.schemas.game import GameStateResponse, GameStateUpdate

logger = get_logger(__name__)
settings = get_settings()

_CACHE_PREFIX = "game_state:"


class GameService:
    """Business logic layer for game state management."""

    def __init__(self, db: AsyncSession) -> None:
        self._repo = GameRepository(db)

    async def update_game_state(self, payload: GameStateUpdate) -> GameStateResponse:
        """Persist updated game state to DB and invalidate cache."""
        record = await self._repo.upsert(payload)

        # Invalidate Redis cache so next read fetches fresh data
        redis = await get_redis()
        cache = RedisCache(redis)
        await cache.delete(f"{_CACHE_PREFIX}{payload.game_id}")

        # Publish update event for WebSocket subscribers
        await cache.publish(
            f"game_updates:{payload.game_id}",
            {"type": "state_update", "game_id": payload.game_id},
        )

        logger.info("Game state updated", game_id=payload.game_id)
        return self._to_response(record, payload)

    async def get_game_state(self, game_id: str) -> GameStateResponse | None:
        """Return game state — cache-first, then DB."""
        redis = await get_redis()
        cache = RedisCache(redis)
        cached = await cache.get(f"{_CACHE_PREFIX}{game_id}")
        if cached:
            logger.debug("Game state cache hit", game_id=game_id)
            return GameStateResponse.model_validate(cached)

        record = await self._repo.get_by_game_id(game_id)
        if record is None:
            return None

        game_data = record.game_data or {}
        response = GameStateResponse(
            game_id=record.game_id,
            home_team=record.home_team,
            away_team=record.away_team,
            home_score=record.home_score,
            away_score=record.away_score,
            quarter=record.quarter,
            time_remaining=record.time_remaining,
            possession=record.possession,
            shot_clock=record.shot_clock,
            home_fouls=record.home_fouls,
            away_fouls=record.away_fouls,
            home_timeouts=record.home_timeouts,
            away_timeouts=record.away_timeouts,
            status=record.status,
            home_players=game_data.get("home_players", []),
            away_players=game_data.get("away_players", []),
            recent_plays=game_data.get("recent_plays", []),
            updated_at=record.updated_at,
        )

        await cache.set(
            f"{_CACHE_PREFIX}{game_id}",
            json.loads(response.model_dump_json()),
            ttl=settings.game_state_ttl,
        )
        return response

    def _to_response(self, record: object, payload: GameStateUpdate) -> GameStateResponse:
        from datetime import datetime, timezone
        return GameStateResponse(
            game_id=payload.game_id,
            home_team=payload.home_team,
            away_team=payload.away_team,
            home_score=payload.home_score,
            away_score=payload.away_score,
            quarter=payload.quarter,
            time_remaining=payload.time_remaining,
            possession=payload.possession,
            shot_clock=payload.shot_clock,
            home_fouls=payload.home_fouls,
            away_fouls=payload.away_fouls,
            home_timeouts=payload.home_timeouts,
            away_timeouts=payload.away_timeouts,
            status=payload.status,
            home_players=payload.home_players,
            away_players=payload.away_players,
            recent_plays=payload.recent_plays,
            updated_at=datetime.now(timezone.utc),
        )
