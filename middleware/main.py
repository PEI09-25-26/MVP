from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional
import asyncio
import requests
import websockets
import json

from models import CardDetection, ScanEvent
from backend_client import BackendClient

# ---------- App ----------

app = FastAPI(title="CV Middleware", version="0.1")

backend = BackendClient(base_url="http://localhost:8080")

# CV Service URLs
CV_SERVICE_URL = "http://localhost:8001"
CV_SERVICE_WS_URL = "ws://localhost:8001"

# Active WebSocket connections
active_connections: dict[str, WebSocket] = {}
cv_connections: dict[str, websockets.WebSocketClientProtocol] = {}


# ---------- API DTOs ----------

class CardDetectionDTO(BaseModel):
    rank: str
    suit: str
    confidence: float


class ScanEventDTO(BaseModel):
    source: str
    success: bool
    message: str
    detection: Optional[CardDetectionDTO] = None


class StartGameRequest(BaseModel):
    playerName: str
    roomId: Optional[str] = None


class StartGameResponse(BaseModel):
    success: bool
    message: str
    gameId: str


# ---------- Routes ----------

@app.post("/game/start")
async def start_game(request: StartGameRequest):
    """
    Starts a new game with computer vision.
    Initializes the CV service.
    """
    try:
        # Call CV service to start detection
        response = requests.post(
            f"{CV_SERVICE_URL}/cv/start",
            json={"game_id": request.roomId or "default"},
            timeout=5
        )
        
        if response.status_code == 200:
            return StartGameResponse(
                success=True,
                message="Game started successfully",
                gameId=request.roomId or "default"
            )
        else:
            return StartGameResponse(
                success=False,
                message=f"Failed to start CV service: {response.text}",
                gameId=""
            )
    except requests.RequestException as e:
        print(f"[Middleware] Error starting CV service: {e}")
        return StartGameResponse(
            success=False,
            message=f"CV service unavailable: {str(e)}",
            gameId=""
        )


@app.websocket("/ws/camera/{game_id}")
async def websocket_camera(websocket: WebSocket, game_id: str):
    """
    WebSocket endpoint to receive camera frames from mobile app.
    Forwards frames to CV service via WebSocket for continuous processing.
    """
    await websocket.accept()
    active_connections[game_id] = websocket
    print(f"[Middleware] Mobile WebSocket connected for game: {game_id}")
    
    # Connect to CV Service via WebSocket
    cv_ws = None
    try:
        cv_ws = await websockets.connect(f"{CV_SERVICE_WS_URL}/cv/stream/{game_id}")
        cv_connections[game_id] = cv_ws
        print(f"[Middleware] Connected to CV Service WebSocket for game: {game_id}")
        
        # Create task to receive detections from CV service
        async def receive_from_cv():
            try:
                async for message in cv_ws:
                    # Forward CV detections back to mobile
                    data = json.loads(message)
                    if data.get("success") and data.get("detection"):
                        await websocket.send_json(data)
                        print(f"[Middleware] Forwarded detection to mobile: {data['detection']}")
            except Exception as e:
                print(f"[Middleware] Error receiving from CV: {e}")
        
        # Start receiving task
        receive_task = asyncio.create_task(receive_from_cv())
        
        # Forward frames from mobile to CV service
        while True:
            # Receive base64 encoded frame from mobile
            frame_data = await websocket.receive_text()
            
            # Forward frame to CV service via WebSocket
            await cv_ws.send(frame_data)
                
    except WebSocketDisconnect:
        print(f"[Middleware] Mobile WebSocket disconnected for game: {game_id}")
    except Exception as e:
        print(f"[Middleware] WebSocket error: {e}")
    finally:
        # Cleanup
        if game_id in active_connections:
            del active_connections[game_id]
        if cv_ws:
            await cv_ws.close()
        if game_id in cv_connections:
            del cv_connections[game_id]
        print(f"[Middleware] Cleaned up connections for game: {game_id}")


@app.post("/scan")
def receive_scan(event: ScanEventDTO):
    """
    Receives a card detection event and forwards it to the backend.
    """
    if not event.detection:
        return {
            "success": False,
            "message": "no card detected",
            "detection": event.detection.dict() if event.detection else None
        }

    detection = CardDetection(
        rank=event.detection.rank,
        suit=event.detection.suit,
        confidence=event.detection.confidence
    )

    backend_response = backend.send_card(detection)

    if backend_response is None:
        return {
            "success": False,
            "message": "backend unavailable",
            "detection": detection.to_json()
        }

    return {
        "success": True,
        "message": "card forwarded",
        "backend_response": backend_response,
        "detection": detection.to_json()
    }
