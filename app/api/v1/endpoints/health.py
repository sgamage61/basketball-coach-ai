from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import Settings, get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    environment: str
    version: str
    timestamp: datetime


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """Returns service health status. Used by load balancers and container orchestration."""
    return HealthResponse(
        status="ok",
        environment=settings.app_env,
        version="0.1.0",
        timestamp=datetime.now(timezone.utc),
    )
