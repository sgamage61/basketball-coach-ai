import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.core.redis import get_redis
from app.websockets.connection_manager import manager

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/ws/game/{game_id}")
async def game_websocket(websocket: WebSocket, game_id: str) -> None:
    """
    WebSocket endpoint for real-time game updates.

    Clients connect here to receive push notifications whenever:
    - Game state changes  (POST /game/update)
    - A timeout recommendation is generated  (POST /game/timeout)
    - Any other game event is published to the Redis channel

    Protocol (server → client):
        {"type": "connected",      "game_id": "...", "timestamp": "..."}
        {"type": "state_update",   "game_id": "...", "timestamp": "..."}
        {"type": "recommendation", "game_id": "...", "data": {...}}
        {"type": "ping",           "timestamp": "..."}

    Protocol (client → server):
        {"type": "ping"}   — keepalive; server echoes a pong
    """
    await manager.connect(websocket, game_id)
    await manager.send_personal(
        websocket,
        {
            "type": "connected",
            "game_id": game_id,
            "message": f"Subscribed to game {game_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    redis_task = asyncio.create_task(_redis_listener(websocket, game_id))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if msg.get("type") == "ping":
                await manager.send_personal(
                    websocket,
                    {"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()},
                )

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected", game_id=game_id)
    finally:
        redis_task.cancel()
        manager.disconnect(websocket, game_id)


async def _redis_listener(websocket: WebSocket, game_id: str) -> None:
    """Subscribes to the Redis pub/sub channel and forwards events to the client."""
    redis = await get_redis()
    pubsub = redis.pubsub()
    channel = f"game_updates:{game_id}"
    await pubsub.subscribe(channel)
    logger.debug("Redis pubsub subscribed", channel=channel)

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                data = json.loads(message["data"])
            except (json.JSONDecodeError, TypeError):
                continue
            await manager.send_personal(websocket, data)
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
