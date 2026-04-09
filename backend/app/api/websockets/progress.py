from collections import deque
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from typing import Dict, List
import json

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
        while True:
            # The client doesn't need to send anything, but we need to listen for connection closed events.
            data = await websocket.receive_text()
            # Could process incoming messages if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket, project_id)
