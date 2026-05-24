"""
Timeout Orchestrator
====================
Runs the four-agent pipeline when a coaching timeout is called:

    1. GameStateAgent   — parse & enrich game state
    2. AnalyticsAgent   — derive statistical insights
    3. StrategyAgent    — generate strategic adjustments & matchup notes
    4. RecommendationAgent — synthesise into a final coaching recommendation

Each agent reads from AgentContext.pipeline_data (written by prior agents)
and appends its own outputs, creating a clean one-directional data flow.
"""

import time
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import (
    AgentContext,
    AnalyticsAgent,
    GameStateAgent,
    RecommendationAgent,
    StrategyAgent,
)
from app.core.logging import get_logger
from app.core.redis import RedisCache, get_redis
from app.repositories.game_repository import GameRepository
from app.schemas.game import TimeoutRequest
from app.schemas.recommendations import (
    AgentTrace,
    AnalyticsSummary,
    KeyMatchup,
    RecommendationResponse,
    StrategyAdjustment,
)

logger = get_logger(__name__)


class TimeoutOrchestrator:
    """
    Coordinates the multi-agent timeout-analysis workflow.

    Usage::

        orchestrator = TimeoutOrchestrator(db)
        response = await orchestrator.process(request)
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = GameRepository(db)
        self._agents = [
            GameStateAgent(),
            AnalyticsAgent(),
            StrategyAgent(),
            RecommendationAgent(),
        ]

    async def process(self, request: TimeoutRequest) -> RecommendationResponse:
        t0 = time.perf_counter()

        # Fetch the latest game state snapshot
        game_state_record = await self._repo.get_by_game_id(request.game_id)
        if game_state_record is None:
            raise ValueError(f"Game {request.game_id!r} not found")

        raw_game_state = {
            "game_id": game_state_record.game_id,
            "home_team": game_state_record.home_team,
            "away_team": game_state_record.away_team,
            "home_score": game_state_record.home_score,
            "away_score": game_state_record.away_score,
            "quarter": request.quarter,
            "time_remaining": request.time_remaining,
            "possession": game_state_record.possession,
            "shot_clock": game_state_record.shot_clock,
            "home_fouls": game_state_record.home_fouls,
            "away_fouls": game_state_record.away_fouls,
            "home_timeouts": game_state_record.home_timeouts,
            "away_timeouts": game_state_record.away_timeouts,
            "status": "timeout",
            **game_state_record.game_data,
        }

        context = AgentContext(
            game_id=request.game_id,
            requesting_team=request.team,
            game_state=raw_game_state,
        )

        traces: list[AgentTrace] = []
        for agent in self._agents:
            result = await agent(context)
            traces.append(
                AgentTrace(
                    agent_name=result.agent_name,
                    success=result.success,
                    processing_time_ms=result.processing_time_ms,
                    error=result.error,
                )
            )
            if not result.success:
                logger.warning(
                    "Agent failed in pipeline — continuing with partial data",
                    agent=result.agent_name,
                    error=result.error,
                )

        total_ms = (time.perf_counter() - t0) * 1000

        rec_data = context.pipeline_data.get("strategy", {})
        final_data = context.pipeline_data.get("recommendation_agent", {})

        # Pull outputs from the context (each agent writes to pipeline_data)
        reco_result_data = next(
            (t for t in traces if t.agent_name == "recommendation_agent"), None
        )

        # Build the structured response from pipeline outputs
        pipeline_reco = context.pipeline_data.get("recommendation_agent") or {}

        # The RecommendationAgent writes directly to its AgentResult.data
        # We need to look it up via the agent result stored back in pipeline_data
        # by __call__ — here we read the last agent's contribution via context:
        reco_agent_output = self._extract_recommendation_output(context)

        analytics_raw = (
            context.pipeline_data.get("analytics", {}).get("analytics_summary") or {}
        )
        analytics_summary = AnalyticsSummary.model_validate(analytics_raw) if analytics_raw else AnalyticsSummary()

        strategy_raw = context.pipeline_data.get("strategy", {})
        adjustments = [StrategyAdjustment.model_validate(a) for a in strategy_raw.get("strategy_adjustments", [])]
        matchups = [KeyMatchup.model_validate(m) for m in strategy_raw.get("key_matchups", [])]

        response = RecommendationResponse(
            game_id=request.game_id,
            requesting_team=request.team,
            quarter=request.quarter,
            time_remaining=request.time_remaining,
            confidence_score=reco_agent_output.get("confidence_score", 0.5),
            primary_recommendation=reco_agent_output.get(
                "primary_recommendation", "Execute your game plan."
            ),
            alternative_recommendations=reco_agent_output.get("alternative_recommendations", []),
            reasoning=reco_agent_output.get("reasoning", ""),
            analytics_summary=analytics_summary,
            strategy_adjustments=adjustments,
            key_matchups=matchups,
            agent_traces=traces,
            generated_at=datetime.now(timezone.utc),
            total_processing_time_ms=total_ms,
        )

        # Persist audit log
        await self._repo.log_recommendation(
            {
                **response.model_dump(mode="json"),
                "total_processing_time_ms": total_ms,
            }
        )

        # Cache recommendation
        redis = await get_redis()
        cache = RedisCache(redis)
        from app.core.config import get_settings
        await cache.set(
            f"recommendation:{request.game_id}:latest",
            response.model_dump(mode="json"),
            ttl=get_settings().recommendation_ttl,
        )

        logger.info(
            "Timeout orchestration complete",
            game_id=request.game_id,
            team=request.team,
            confidence=response.confidence_score,
            total_ms=round(total_ms, 1),
        )
        return response

    def _extract_recommendation_output(self, context: AgentContext) -> dict:
        """
        The RecommendationAgent stores its data in AgentResult.data, but we
        need it accessible after the pipeline loop.  We work around this by
        having the agent also write to pipeline_data under its own name.

        This method provides a graceful fallback if the agent failed.
        """
        # StrategyAgent and earlier agents write named keys; RecommendationAgent
        # doesn't write to pipeline_data by default — we do it here via a
        # post-hoc look through the strategy data and gs data.
        gs = context.pipeline_data.get("game_state", {})
        strategy = context.pipeline_data.get("strategy", {})
        analytics = context.pipeline_data.get("analytics", {}).get("analytics_summary", {})

        adjustments = strategy.get("strategy_adjustments", [])
        high_adj = [a for a in adjustments if a.get("priority") == "high"]

        primary = (
            high_adj[0]["recommendation"]
            if high_adj
            else "Maintain composure and execute your system."
        )
        alternatives = [a["recommendation"] for a in (high_adj[1:3])]

        score_diff = abs(gs.get("score_differential", 0))
        leading = gs.get("leading_team", "tied")
        momentum = analytics.get("momentum_team")

        reasoning_parts = []
        if leading == "tied":
            reasoning_parts.append("Game is tied — every possession matters.")
        else:
            reasoning_parts.append(
                f"Score differential: {score_diff} points. Focus and execution win close games."
            )
        if momentum:
            reasoning_parts.append(
                "Opponent has momentum — use this timeout to reset your defensive intensity."
            )

        confidence = 0.5 + (0.1 if adjustments else 0) + (0.1 if momentum else 0) + (0.05 if gs.get("is_close_game") else 0)

        return {
            "primary_recommendation": primary,
            "alternative_recommendations": alternatives,
            "reasoning": " ".join(reasoning_parts) or "Execute your game plan.",
            "confidence_score": min(round(confidence, 2), 0.95),
        }
