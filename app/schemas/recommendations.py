from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Priority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MatchupAdvantage(StrEnum):
    FAVORABLE = "favorable"
    UNFAVORABLE = "unfavorable"
    NEUTRAL = "neutral"


class StrategyAdjustment(BaseModel):
    category: str = Field(..., description="offense | defense | lineup | pace | special")
    recommendation: str
    priority: Priority
    rationale: str
    estimated_impact: str = ""


class KeyMatchup(BaseModel):
    player_name: str
    opponent_name: str
    advantage: MatchupAdvantage
    notes: str
    suggested_action: str = ""


class AnalyticsSummary(BaseModel):
    scoring_run: str = ""
    momentum_team: str | None = None
    hot_players: list[str] = Field(default_factory=list)
    cold_players: list[str] = Field(default_factory=list)
    defensive_vulnerabilities: list[str] = Field(default_factory=list)
    offensive_opportunities: list[str] = Field(default_factory=list)
    pace_rating: str = ""
    three_point_differential: int = 0
    paint_scoring_differential: int = 0
    turnover_differential: int = 0
    rebounding_differential: int = 0


class AgentTrace(BaseModel):
    """Internal: captures per-agent performance for observability."""

    agent_name: str
    success: bool
    processing_time_ms: float
    error: str | None = None


class RecommendationResponse(BaseModel):
    game_id: str
    requesting_team: str
    quarter: int
    time_remaining: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    primary_recommendation: str
    alternative_recommendations: list[str] = Field(default_factory=list)
    reasoning: str
    analytics_summary: AnalyticsSummary
    strategy_adjustments: list[StrategyAdjustment] = Field(default_factory=list)
    key_matchups: list[KeyMatchup] = Field(default_factory=list)
    agent_traces: list[AgentTrace] = Field(default_factory=list)
    generated_at: datetime
    total_processing_time_ms: float = 0.0
