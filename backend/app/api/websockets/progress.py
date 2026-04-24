from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from typing import Dict, List
import json

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import ProgressEvent


class ConnectionManager:
    def __init__(self):
        # project_id -> list of active connections
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, project_id: str):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
        self.active_connections[project_id].append(websocket)
        # Replay persisted history so a client joining mid-job (or after the
        # server restarted, or after the job already finished) sees the full
        # step timeline. The worker writes every event to `progress_events`;
        # this query is the single source of truth for past events.
        db = SessionLocal()
        try:
            events = (
                db.query(ProgressEvent)
                .filter(ProgressEvent.project_id == project_id)
                .order_by(ProgressEvent.seq.asc())
                .all()
            )
            for ev in events:
                try:
                    await websocket.send_text(json.dumps({
                        "project_id": ev.project_id,
                        "status": ev.status,
                        "step": ev.step,
                        "time_elapsed": ev.time_elapsed,
                        "error": ev.error,
                    }))
                except Exception:
                    pass
        finally:
            db.close()

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
        if project_id in self.active_connections:
            for connection in self.active_connections[project_id]:
                try:
                    await connection.send_text(message_str)
                except Exception:
                    pass

    async def close_project(self, project_id: str) -> None:
        """Close every WS still subscribed to ``project_id`` and drop the slot.

        Called when a project is permanently deleted so clients stop waiting
        for events that will never arrive and the in-memory map does not leak.
        """
        conns = self.active_connections.pop(project_id, [])
        for ws in conns:
            try:
                await ws.close(code=1000, reason="project_deleted")
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
