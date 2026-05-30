from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GameState(Base):
    """Persisted snapshot of a live game's state."""

    __tablename__ = "game_states"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    game_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    home_team: Mapped[str] = mapped_column(String(100), nullable=False)
    away_team: Mapped[str] = mapped_column(String(100), nullable=False)
    home_score: Mapped[int] = mapped_column(Integer, default=0)
    away_score: Mapped[int] = mapped_column(Integer, default=0)
    quarter: Mapped[int] = mapped_column(Integer, default=1)
    time_remaining: Mapped[str] = mapped_column(String(10), default="12:00")
    possession: Mapped[str | None] = mapped_column(String(10), nullable=True)
    shot_clock: Mapped[int] = mapped_column(Integer, default=24)
    home_fouls: Mapped[int] = mapped_column(Integer, default=0)
    away_fouls: Mapped[int] = mapped_column(Integer, default=0)
    home_timeouts: Mapped[int] = mapped_column(Integer, default=7)
    away_timeouts: Mapped[int] = mapped_column(Integer, default=7)
    # JSON blob for player stats, recent plays, and any extension data
    game_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<GameState game_id={self.game_id!r} "
            f"{self.home_team} {self.home_score}-{self.away_score} {self.away_team}>"
        )


class RecommendationLog(Base):
    """Audit trail of every AI recommendation generated during a timeout."""

    __tablename__ = "recommendation_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    game_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    requesting_team: Mapped[str] = mapped_column(String(10), nullable=False)
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    time_remaining: Mapped[str] = mapped_column(String(10), nullable=False)
    confidence_score: Mapped[float] = mapped_column(default=0.0)
    primary_recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    full_response: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    processing_time_ms: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<RecommendationLog game_id={self.game_id!r} "
            f"team={self.requesting_team!r} confidence={self.confidence_score:.2f}>"
        )
