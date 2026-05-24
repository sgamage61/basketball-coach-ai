from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class GameStatus(StrEnum):
    ACTIVE = "active"
    TIMEOUT = "timeout"
    HALFTIME = "halftime"
    FINAL = "final"
    SUSPENDED = "suspended"


class Possession(StrEnum):
    HOME = "home"
    AWAY = "away"


# ─── Nested models ────────────────────────────────────────────────────────────


class PlayerStat(BaseModel):
    player_id: str
    name: str
    jersey_number: str = ""
    position: str = ""
    points: int = 0
    rebounds: int = 0
    assists: int = 0
    steals: int = 0
    blocks: int = 0
    turnovers: int = 0
    fouls: int = 0
    minutes_played: float = 0.0
    field_goals_made: int = 0
    field_goals_attempted: int = 0
    three_pointers_made: int = 0
    three_pointers_attempted: int = 0
    free_throws_made: int = 0
    free_throws_attempted: int = 0
    plus_minus: int = 0
    is_on_court: bool = False

    @property
    def fg_percentage(self) -> float:
        if self.field_goals_attempted == 0:
            return 0.0
        return round(self.field_goals_made / self.field_goals_attempted, 3)

    @property
    def three_point_percentage(self) -> float:
        if self.three_pointers_attempted == 0:
            return 0.0
        return round(self.three_pointers_made / self.three_pointers_attempted, 3)


class PlayEvent(BaseModel):
    event_id: str = ""
    event_type: str  # "field_goal", "three_pointer", "free_throw", "turnover", "foul", etc.
    player_id: str | None = None
    player_name: str | None = None
    team: str | None = None  # "home" | "away"
    quarter: int
    time: str
    description: str
    points: int = 0
    x_coordinate: float | None = None
    y_coordinate: float | None = None


# ─── Request models ───────────────────────────────────────────────────────────


class GameStateUpdate(BaseModel):
    """Payload sent by the live game ingestion pipeline to update game state."""

    game_id: str = Field(..., min_length=1, max_length=100)
    home_team: str = Field(..., min_length=1, max_length=100)
    away_team: str = Field(..., min_length=1, max_length=100)
    home_score: int = Field(0, ge=0)
    away_score: int = Field(0, ge=0)
    quarter: int = Field(1, ge=1, le=8)
    time_remaining: str = Field("12:00", pattern=r"^\d{1,2}:\d{2}$")
    possession: Possession | None = None
    shot_clock: int = Field(24, ge=0, le=24)
    home_fouls: int = Field(0, ge=0)
    away_fouls: int = Field(0, ge=0)
    home_timeouts: int = Field(7, ge=0, le=7)
    away_timeouts: int = Field(7, ge=0, le=7)
    status: GameStatus = GameStatus.ACTIVE
    home_players: list[PlayerStat] = Field(default_factory=list)
    away_players: list[PlayerStat] = Field(default_factory=list)
    recent_plays: list[PlayEvent] = Field(default_factory=list)

    @field_validator("home_players", "away_players")
    @classmethod
    def max_fifteen_players(cls, v: list[PlayerStat]) -> list[PlayerStat]:
        if len(v) > 15:
            raise ValueError("A team roster cannot exceed 15 players")
        return v


class TimeoutRequest(BaseModel):
    """Trigger for the AI timeout-analysis workflow."""

    game_id: str = Field(..., min_length=1, max_length=100)
    team: Possession = Field(..., description="Which team is calling the timeout")
    quarter: int = Field(..., ge=1, le=8)
    time_remaining: str = Field(..., pattern=r"^\d{1,2}:\d{2}$")
    reason: str | None = Field(None, max_length=500)


# ─── Response models ──────────────────────────────────────────────────────────


class GameStateResponse(BaseModel):
    game_id: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    quarter: int
    time_remaining: str
    possession: str | None
    shot_clock: int
    home_fouls: int
    away_fouls: int
    home_timeouts: int
    away_timeouts: int
    status: str
    home_players: list[PlayerStat]
    away_players: list[PlayerStat]
    recent_plays: list[PlayEvent]
    updated_at: datetime

    model_config = {"from_attributes": True}
