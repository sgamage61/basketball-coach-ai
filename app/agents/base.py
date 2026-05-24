import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger


@dataclass
class AgentContext:
    """Shared context object passed through the agent pipeline."""

    game_id: str
    requesting_team: str
    game_state: dict[str, Any]
    # Accumulates outputs from upstream agents so downstream agents can read them
    pipeline_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Standardised return value from every agent."""

    agent_name: str
    success: bool
    data: dict[str, Any]
    error: str | None = None
    processing_time_ms: float = 0.0


class BaseAgent(ABC):
    """
    Abstract base for all pipeline agents.

    Subclasses implement `run()`.  The `__call__` entry-point handles timing,
    error catching, and logging so agents stay focused on their domain logic.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.logger = get_logger(f"agent.{name}")

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResult:
        ...

    async def __call__(self, context: AgentContext) -> AgentResult:
        start = time.perf_counter()
        self.logger.info("Agent started", game_id=context.game_id)
        try:
            result = await self.run(context)
            result.processing_time_ms = (time.perf_counter() - start) * 1000
            self.logger.info(
                "Agent finished",
                game_id=context.game_id,
                success=result.success,
                ms=round(result.processing_time_ms, 1),
            )
            return result
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            self.logger.error("Agent failed", game_id=context.game_id, error=str(exc))
            return AgentResult(
                agent_name=self.name,
                success=False,
                data={},
                error=str(exc),
                processing_time_ms=elapsed,
            )
