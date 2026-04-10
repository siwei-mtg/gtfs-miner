from collections import deque
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from typing import Dict, List
import json

from app.core.config import settings

class ConnectionManager:
    def __init__(self):
        # project_id -> list of active connections
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # project_id -> recent messages (for replay on late connect)
        self._history: Dict[str, deque] = {}

    async def connect(self, websocket: WebSocket, project_id: str):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
        self.active_connections[project_id].append(websocket)
        # Replay any messages the client missed before connecting
        if project_id in self._history:
            for msg_str in self._history[project_id]:
                try:
                    await websocket.send_text(msg_str)
                except Exception:
                    pass

    def disconnect(self, websocket: WebSocket, project_id: str):
        if project_id in self.active_connections:
            if websocket in self.active_connections[project_id]:
                self.active_connections[project_id].remove(websocket)
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast_to_project(self, project_id: str, message: dict):
        message_str = json.dumps(message)
        # Store in history so late-connecting clients can catch up
        if project_id not in self._history:
            self._history[project_id] = deque(maxlen=20)
        self._history[project_id].append(message_str)

        if project_id in self.active_connections:
            for connection in self.active_connections[project_id]:
                try:
                    await connection.send_text(message_str)
                except Exception:
                    pass

manager = ConnectionManager()

router = APIRouter()

@router.websocket("/{project_id}/ws")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    await manager.connect(websocket, project_id)
    try:
        if settings.REDIS_URL:
            # Celery mode: subscribe to Redis pub/sub channel and forward to WS
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.REDIS_URL)
            pubsub = r.pubsub()
            await pubsub.subscribe(f"progress:{project_id}")
            try:
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        data_str = message["data"].decode()
                        await websocket.send_text(data_str)
                        if json.loads(data_str).get("status") in ("completed", "failed"):
                            break
            except WebSocketDisconnect:
                pass
            finally:
                await pubsub.unsubscribe(f"progress:{project_id}")
                await r.aclose()
        else:
            # BackgroundTasks mode (dev/test — no Redis): just keep connection alive
            while True:
                await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, project_id)
