from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_game_service, get_timeout_orchestrator
from app.core.logging import get_logger
from app.schemas.game import GameStateResponse, GameStateUpdate, TimeoutRequest
from app.schemas.recommendations import RecommendationResponse
from app.services.game_service import GameService
from app.services.timeout_orchestrator import TimeoutOrchestrator

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/update",
    response_model=GameStateResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest live game state update",
)
async def update_game_state(
    payload: GameStateUpdate,
    service: GameService = Depends(get_game_service),
) -> GameStateResponse:
    """
    Called by the live game ingestion pipeline whenever the game state changes.
    Creates or updates the stored game state and broadcasts a WebSocket event.
    """
    logger.info("Game state update received", game_id=payload.game_id)
    return await service.update_game_state(payload)


@router.post(
    "/timeout",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger AI coaching recommendation on timeout",
)
async def call_timeout(
    request: TimeoutRequest,
    orchestrator: TimeoutOrchestrator = Depends(get_timeout_orchestrator),
) -> RecommendationResponse:
    """
    Initiates the four-agent AI pipeline:
    GameStateAgent → AnalyticsAgent → StrategyAgent → RecommendationAgent

    Returns a structured coaching recommendation with confidence score,
    strategic adjustments, key matchup notes, and full reasoning.
    """
    logger.info(
        "Timeout triggered",
        game_id=request.game_id,
        team=request.team,
        quarter=request.quarter,
        time=request.time_remaining,
    )
    try:
        return await orchestrator.process(request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/state/{game_id}",
    response_model=GameStateResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve current game state",
)
async def get_game_state(
    game_id: str,
    service: GameService = Depends(get_game_service),
) -> GameStateResponse:
    """Returns the latest cached/persisted game state for the given game_id."""
    state = await service.get_game_state(game_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game '{game_id}' not found",
        )
    return state
