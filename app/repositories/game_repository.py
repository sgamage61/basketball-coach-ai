from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.game import GameState, RecommendationLog
from app.schemas.game import GameStateUpdate

logger = get_logger(__name__)


class GameRepository:
    """Data-access layer for GameState and RecommendationLog persistence."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ─── GameState ────────────────────────────────────────────────────────────

    async def get_by_game_id(self, game_id: str) -> GameState | None:
        result = await self._db.execute(
            select(GameState).where(GameState.game_id == game_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, payload: GameStateUpdate) -> GameState:
        existing = await self.get_by_game_id(payload.game_id)

        game_data = {
            "home_players": [p.model_dump() for p in payload.home_players],
            "away_players": [p.model_dump() for p in payload.away_players],
            "recent_plays": [p.model_dump() for p in payload.recent_plays],
        }

        if existing:
            await self._db.execute(
                update(GameState)
                .where(GameState.game_id == payload.game_id)
                .values(
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
                    game_data=game_data,
                )
            )
            await self._db.refresh(existing)
            logger.debug("GameState updated", game_id=payload.game_id)
            return existing

        record = GameState(
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
            game_data=game_data,
        )
        self._db.add(record)
        await self._db.flush()
        logger.debug("GameState created", game_id=payload.game_id)
        return record

    # ─── RecommendationLog ────────────────────────────────────────────────────

    async def log_recommendation(self, payload: dict) -> RecommendationLog:
        record = RecommendationLog(
            game_id=payload["game_id"],
            requesting_team=payload["requesting_team"],
            quarter=payload["quarter"],
            time_remaining=payload["time_remaining"],
            confidence_score=payload.get("confidence_score", 0.0),
            primary_recommendation=payload.get("primary_recommendation", ""),
            reasoning=payload.get("reasoning", ""),
            full_response=payload,
            processing_time_ms=payload.get("total_processing_time_ms", 0.0),
        )
        self._db.add(record)
        await self._db.flush()
        return record
