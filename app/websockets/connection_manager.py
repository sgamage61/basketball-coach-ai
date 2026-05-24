import asyncio
import json
from typing import Any

from fastapi import WebSocket

from app.core.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections grouped by game_id.

    Thread-safety note: FastAPI runs in a single-threaded async event loop,
    so plain dict mutation here is safe — no locks needed.
    """

    def __init__(self) -> None:
        # game_id -> set of active WebSocket connections
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, game_id: str) -> None:
        await websocket.accept()
        if game_id not in self._connections:
            self._connections[game_id] = set()
        self._connections[game_id].add(websocket)
        logger.info("WebSocket connected", game_id=game_id, total=len(self._connections[game_id]))

    def disconnect(self, websocket: WebSocket, game_id: str) -> None:
        if game_id in self._connections:
            self._connections[game_id].discard(websocket)
            if not self._connections[game_id]:
                del self._connections[game_id]
        logger.info("WebSocket disconnected", game_id=game_id)

    async def broadcast(self, game_id: str, message: dict[str, Any]) -> None:
        """Send a message to all subscribers of a game."""
        sockets = self._connections.get(game_id, set()).copy()
        if not sockets:
            return

        payload = json.dumps(message, default=str)
        results = await asyncio.gather(
            *[ws.send_text(payload) for ws in sockets],
            return_exceptions=True,
        )

        # Clean up broken connections silently
        for ws, result in zip(sockets, results):
            if isinstance(result, Exception):
                logger.warning("WebSocket send failed — removing connection", game_id=game_id)
                self._connections.get(game_id, set()).discard(ws)

    async def send_personal(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        await websocket.send_text(json.dumps(message, default=str))

    @property
    def active_games(self) -> list[str]:
        return list(self._connections.keys())

    def connection_count(self, game_id: str) -> int:
        return len(self._connections.get(game_id, set()))


# Module-level singleton shared across the app
manager = ConnectionManager()
