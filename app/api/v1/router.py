from fastapi import APIRouter

from app.api.v1.endpoints.game import router as game_router
from app.api.v1.endpoints.health import router as health_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(game_router, prefix="/game", tags=["game"])
