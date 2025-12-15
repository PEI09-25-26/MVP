from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional
import asyncio
import requests
import websockets
import json
import threading
import subprocess

from models import CardDetection, ScanEvent
from backend_client import BackendClient
from qrcode_generator import generate_qr_code

# ---------- App ----------

app = FastAPI(title="CV Middleware", version="0.1")

backend = BackendClient(base_url="http://localhost:8002")

# Service URLs
CV_SERVICE_URL = "http://localhost:8001"
CV_SERVICE_WS_URL = "ws://localhost:8001"
GAME_SERVICE_URL = "http://localhost:8002"

#Device url
DEVICE_SERVICE_URL = subprocess.getoutput("ip route get 1.1.1.1 | awk '{print $7}'")

#Device url as QR code
generate_qr_code(f"http://{DEVICE_SERVICE_URL}:8000")

# Active WebSocket connections
active_connections: dict[str, WebSocket] = {}
cv_connections: dict[str, websockets.WebSocketClientProtocol] = {}

# Suit name to symbol mapping for Game Service
SUIT_SYMBOLS = {
    "Clubs": "♣",
    "Diamonds": "♦",
    "Hearts": "♥",
    "Spades": "♠"
}


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


class RoundEndData(BaseModel):
    round_number: int
    winner_team: int
    winner_points: int
    team1_points: int
    team2_points: int
    game_ended: bool


# ---------- Routes ----------

@app.post("/game/round_end")
async def round_end(data: RoundEndData):
    """
    Recebe notificação de fim de ronda do game_service.
    Envia para o frontend via WebSocket.
    """
    print(f"[MIDDLEWARE] Ronda {data.round_number} acabou! Equipa {data.winner_team} ganhou com {data.winner_points} pontos")
    
    # Enviar para todos os clientes conectados
    for game_id, ws in active_connections.items():
        try:
            message = {
                "type": "round_end",
                "round_number": data.round_number,
                "winner_team": data.winner_team,
                "winner_points": data.winner_points,
                "team1_points": data.team1_points,
                "team2_points": data.team2_points,
                "game_ended": data.game_ended
            }
            await ws.send_text(json.dumps(message))
            print(f"[MIDDLEWARE] Round end notification sent to game {game_id}")
        except Exception as e:
            print(f"[MIDDLEWARE] Failed to send round end to {game_id}: {e}")
    
    return {"success": True}

@app.post("/game/new_round/{game_id}")
async def new_round(game_id: str):
    """
    Inicia uma nova ronda: reset do CV e notifica game_service.
    """
    try:
        # 1. Reset CV service
        reset_message = {"action": "reset_cards"}
        if game_id in cv_connections:
            cv_ws = cv_connections[game_id]
            await cv_ws.send(json.dumps(reset_message))
            print(f"[MIDDLEWARE] CV reset command sent for game {game_id}")
        
        # 2. Notificar game service para iniciar nova ronda
        response = requests.post(f"{GAME_SERVICE_URL}/new_round", timeout=5)
        if response.status_code == 200:
            return {"success": True, "message": "Nova ronda iniciada"}
        else:
            return {"success": False, "message": "Erro ao iniciar nova ronda"}
    except Exception as e:
        print(f"[MIDDLEWARE] Error starting new round: {e}")
        return {"success": False, "message": str(e)}

@app.post("/game/start")
async def start_game(request: StartGameRequest):
    """
    Starts a new game with computer vision.
    Initializes the CV service.
    """
    try:
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


@app.post("/game/ready/{game_id}")
async def game_ready(game_id: str):
    """
    Called when player is ready to start playing (after removing trump card).
    Resets CV card history.
    """
    if game_id in cv_connections:
        cv_ws = cv_connections[game_id]
        try:
            reset_command = json.dumps({"action": "reset_cards"})
            await cv_ws.send(reset_command)
            print(f"[Middleware] 🎮 Game started for {game_id} - CV history reset")
            return {"success": True, "message": "Game started, ready for cards"}
        except Exception as e:
            print(f"[Middleware] Error resetting CV: {e}")
            return {"success": False, "message": str(e)}
    else:
        return {"success": False, "message": "Game not found"}


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
                    # Parse detection from CV
                    data = json.loads(message)
                    if data.get("success") and data.get("detection"):
                        detection = data["detection"]
                        print(f"[Middleware] Received detection from CV: {detection}")
                        
                        # Send to Game Service (Referee)
                        try:
                            # Convert suit name to symbol for Game Service
                            suit_symbol = SUIT_SYMBOLS.get(detection["suit"], detection["suit"])
                            
                            game_response = requests.post(
                                f"{GAME_SERVICE_URL}/card",
                                json={
                                    "rank": detection["rank"],
                                    "suit": suit_symbol,  # Use symbol instead of name
                                    "confidence": detection.get("confidence", 1.0)
                                },
                                timeout=2
                            )
                            if game_response.status_code == 200:
                                game_result = game_response.json()
                                print(f"[Middleware] ✓ Game Service response: {game_result}")
                                
                                # Check if trump was just set
                                if game_result.get("message") == "Trump card set":
                                    print(f"[Middleware] 🃏 Trump set! Waiting for player to start game...")
                                
                                # Forward both CV detection and game state to mobile
                                combined_data = {
                                    "success": True,
                                    "detection": detection,
                                    "game_state": game_result
                                }
                                await websocket.send_json(combined_data)
                            else:
                                print(f"[Middleware] ✗ Game Service HTTP {game_response.status_code}: {game_response.text}")
                                # Still forward CV detection to mobile
                                await websocket.send_json(data)
                        except requests.exceptions.ConnectionError as e:
                            print(f"[Middleware] ✗ Game Service not running at {GAME_SERVICE_URL}: {e}")
                            # Still forward CV detection to mobile
                            await websocket.send_json(data)
                        except requests.RequestException as e:
                            print(f"[Middleware] ✗ Error sending to Game Service: {e}")
                            # Still forward CV detection to mobile
                            await websocket.send_json(data)
                        
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
