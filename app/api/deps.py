"""
FastAPI dependency injection providers.

Import these into endpoint modules via `Depends(...)`.
"""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import RedisCache, get_redis
from app.services.game_service import GameService
from app.services.openai_service import OpenAIService
from app.services.timeout_orchestrator import TimeoutOrchestrator


async def get_game_service(
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[GameService, None]:
    yield GameService(db)


async def get_timeout_orchestrator(
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerator[TimeoutOrchestrator, None]:
    yield TimeoutOrchestrator(db)


async def get_openai_service() -> OpenAIService:
    return OpenAIService()


async def get_cache() -> AsyncGenerator[RedisCache, None]:
    redis = await get_redis()
    yield RedisCache(redis)
