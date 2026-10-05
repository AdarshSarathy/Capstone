from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_state(self, message: dict):
        # We assume `message` is already a dict, we serialize once
        data = json.dumps(message)
        for connection in self.active_connections:
            try:
                await connection.send_text(data)
            except Exception as e:
                logger.error(f"Error sending message to websocket: {e}")
                self.disconnect(connection)

manager = ConnectionManager()

@router.websocket("/sync")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect much incoming data on this channel, it's mostly for broadcasting.
            # Just keep connection alive
            data = await websocket.receive_text()
            # Handle incoming pings if necessary
    except WebSocketDisconnect:
        manager.disconnect(websocket)
