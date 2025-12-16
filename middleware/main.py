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
from frontend_client import FrontendClient
#from qrcode_generator import generate_qr_code

# ---------- App ----------

app = FastAPI(title="CV Middleware", version="0.1")

backend = BackendClient(base_url="http://localhost:8002")
frontend = FrontendClient(base_url="http://localhost:8003")

latest_state: dict = {}

# Service URLs
CV_SERVICE_URL = "http://localhost:8001"
CV_SERVICE_WS_URL = "ws://localhost:8001"
GAME_SERVICE_URL = "http://localhost:8002"
BOT_SERVICE_URL = "http://localhost:8003"

#Device url
#DEVICE_SERVICE_URL = subprocess.getoutput("ifconfig | grep -A 1 \"en0\" | grep \"inet \" | awk '{print $2}'")

#Device url as QR code
#generate_qr_code(f"http://{DEVICE_SERVICE_URL}:8000")

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


class AddBotRequest(BaseModel):
    player_id: int


class BotPlayResponse(BaseModel):
    success: bool
    card_id: Optional[int] = None
    card_name: Optional[str] = None
    card_index: Optional[int] = None
    player_id: Optional[int] = None
    message: Optional[str] = None


# ---------- Routes ----------

@app.post("/game/state")
def receive_state(state: dict):
    global latest_state
    latest_state = state
    # State is now pushed via WebSocket connections
    return {"ok": True}

@app.get("/game/state")
def get_state():
    return latest_state

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


# ========== BOT ENDPOINTS ==========

@app.post("/game/add_bot/{player_id}")
async def add_bot(player_id: int):
    """Adiciona um bot na posição especificada"""
    try:
        response = requests.post(
            f"{GAME_SERVICE_URL}/player/{player_id}/set_bot",
            timeout=5
        )
        if response.status_code == 200:
            # Notificar frontend via WebSocket
            for game_id, ws in active_connections.items():
                try:
                    message = {
                        "type": "bot_added",
                        "player_id": player_id
                    }
                    await ws.send_text(json.dumps(message))
                except:
                    pass
            return response.json()
        return {"success": False, "message": "Failed to add bot"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.delete("/game/remove_bot/{player_id}")
async def remove_bot(player_id: int):
    """Remove um bot da posição especificada"""
    try:
        response = requests.post(
            f"{GAME_SERVICE_URL}/player/{player_id}/remove_bot",
            timeout=5
        )
        return response.json() if response.status_code == 200 else {"success": False}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/game/bots")
def get_bots():
    """Lista todos os bots ativos"""
    try:
        response = requests.get(f"{GAME_SERVICE_URL}/players/bots", timeout=5)
        return response.json() if response.status_code == 200 else {"bots": []}
    except:
        return {"bots": []}


@app.post("/game/deal_bot_cards")
async def deal_bot_cards():
    """Distribui cartas aos bots após o trunfo ser definido"""
    try:
        response = requests.post(f"{GAME_SERVICE_URL}/bot/deal_cards", timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Notificar frontend sobre cartas distribuídas
            for game_id, ws in active_connections.items():
                try:
                    message = {
                        "type": "bot_cards_dealt",
                        "bots": data.get("bots_dealt", {})
                    }
                    await ws.send_text(json.dumps(message))
                except:
                    pass
            return data
        return {"success": False, "message": "Failed to deal cards"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/game/bot_cards_dealt_notification")
async def bot_cards_dealt_notification(data: dict):
    """Recebe notificação do game_service que as cartas foram distribuídas aos bots"""
    try:
        print(f"[Middleware] 🎴 Cartas distribuídas aos bots: {data.get('bots_dealt', {}).keys()}")
        
        # Notificar frontend
        for game_id, ws in active_connections.items():
            try:
                message = {
                    "type": "bot_cards_dealt",
                    "bots": data.get("bots_dealt", {})
                }
                await ws.send_text(json.dumps(message))
                print(f"[Middleware] ✅ Notificação de cartas distribuídas enviada ao frontend")
            except Exception as e:
                print(f"[ERROR] Failed to notify frontend: {e}")
        
        return {"success": True}
    except Exception as e:
        print(f"[ERROR] bot_cards_dealt_notification failed: {e}")
        return {"success": False, "message": str(e)}


@app.post("/game/bot_play/{player_id}")
async def request_bot_play(player_id: int, round_suit: Optional[str] = None):
    """Pede ao bot para jogar"""
    try:
        response = requests.post(
            f"{GAME_SERVICE_URL}/bot/{player_id}/request_play",
            params={"round_suit": round_suit} if round_suit else {},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                # Notificar frontend sobre jogada do bot
                for game_id, ws in active_connections.items():
                    try:
                        message = {
                            "type": "bot_played",
                            "player_id": player_id,
                            "card_id": data["card_id"],
                            "card_name": data["card_name"],
                            "card_index": data["card_index"]
                        }
                        await ws.send_text(json.dumps(message))
                    except:
                        pass
            return data
        return {"success": False, "message": "Bot play failed"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/game/bot_played_notification")
async def bot_played_notification(data: dict):
    """Recebe notificação do game_service que um bot jogou"""
    try:
        print(f"[Middleware] 🤖 Bot {data.get('player_id')} jogou: {data.get('card_name')}")
        
        # Notificar frontend
        for game_id, ws in active_connections.items():
            try:
                message = {
                    "type": "bot_played",
                    "player_id": data.get("player_id"),
                    "card_id": data.get("card_id"),
                    "card_name": data.get("card_name"),
                    "card_index": data.get("card_index")
                }
                await ws.send_text(json.dumps(message))
                print(f"[Middleware] ✅ Notificação de jogada do bot enviada ao frontend")
            except Exception as e:
                print(f"[ERROR] Failed to notify frontend: {e}")
        
        return {"success": True}
    except Exception as e:
        print(f"[ERROR] bot_played_notification failed: {e}")
        return {"success": False, "message": str(e)}


@app.get("/game/current_turn")
def get_current_turn():
    """Retorna de quem é a vez de jogar"""
    try:
        response = requests.get(f"{GAME_SERVICE_URL}/game/current_turn", timeout=5)
        return response.json() if response.status_code == 200 else {"error": "Failed"}
    except Exception as e:
        return {"error": str(e)}


@app.post("/game/bot_recognition_start")
async def bot_recognition_start(data: dict):
    """Inicia o reconhecimento de cartas do bot pelo CV - MANUAL"""
    try:
        bot_ids = data.get("bots", [])
        print(f"[Middleware] 🤖 Iniciando reconhecimento de cartas para bots: {bot_ids}")
        
        # IMPORTANTE: Primeiro fazer reset completo do CV para limpar o trunfo
        for game_id, cv_ws in cv_connections.items():
            try:
                # Passo 1: Reset completo
                reset_command = {
                    "action": "reset_cards"
                }
                await cv_ws.send(json.dumps(reset_command))
                print(f"[Middleware] 🔄 CV reset enviado")
                
                # Aguardar um pouco para garantir que o reset foi processado
                await asyncio.sleep(0.3)
                
                # Passo 2: Iniciar modo de reconhecimento do bot
                command = {
                    "action": "start_bot_recognition",
                    "player_id": bot_ids[0] if bot_ids else None
                }
                await cv_ws.send(json.dumps(command))
                print(f"[Middleware] ✅ Modo de reconhecimento do bot iniciado")
            except Exception as e:
                print(f"[ERROR] Failed to send bot recognition start to CV: {e}")
        
        # Notificar frontend para mostrar interface de reconhecimento
        for game_id, ws in active_connections.items():
            try:
                message = {
                    "type": "bot_recognition_start",
                    "bot_ids": bot_ids
                }
                await ws.send_text(json.dumps(message))
            except Exception as e:
                print(f"[ERROR] Failed to send bot_recognition_start: {e}")
        
        return {"success": True}
    except Exception as e:
        print(f"[ERROR] bot_recognition_start failed: {e}")
        return {"success": False, "message": str(e)}


@app.post("/game/bot_card_recognized")
async def bot_card_recognized(data: dict):
    """Notifica que uma carta do bot foi reconhecida pelo CV"""
    try:
        card_number = data.get("card_number")  # 1 a 10
        card_id = data.get("card_id")
        player_id = data.get("player_id")
        
        print(f"[DEBUG] Bot {player_id} - Carta {card_number} reconhecida: {card_id}")
        
        # Notificar frontend para mostrar número na carta
        for game_id, ws in active_connections.items():
            try:
                message = {
                    "type": "bot_card_recognized",
                    "player_id": player_id,
                    "card_number": card_number,
                    "card_id": card_id
                }
                await ws.send_text(json.dumps(message))
            except Exception as e:
                print(f"[ERROR] Failed to send bot_card_recognized: {e}")
        
        return {"success": True}
    except Exception as e:
        print(f"[ERROR] bot_card_recognized failed: {e}")
        return {"success": False, "message": str(e)}


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
            
            # Verificar se o primeiro jogador é um bot e acionar automaticamente
            try:
                turn_response = requests.get(f"{GAME_SERVICE_URL}/game/current_turn", timeout=2)
                if turn_response.status_code == 200:
                    turn_data = turn_response.json()
                    if turn_data.get("is_bot"):
                        player_id = turn_data.get("current_player")
                        print(f"[Middleware] 🤖 Primeiro jogador é bot ({player_id}), acionando...")
                        # Aguardar um pouco para garantir que tudo está pronto
                        await asyncio.sleep(0.5)
                        await request_bot_play(player_id, None)
            except Exception as e:
                print(f"[Middleware] Error checking/triggering initial bot: {e}")
            
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
                    
                    # Check if it's a bot recognition message
                    if data.get("type") == "bot_card_recognized":
                        print(f"[Middleware] 🤖 Bot card recognized: {data['card_number']}/10 - {data['card_id']}")
                        # Forward to frontend via /game/bot_card_recognized endpoint
                        try:
                            await bot_card_recognized({
                                "card_number": data["card_number"],
                                "card_id": data["card_id"],
                                "player_id": data["player_id"]
                            })
                        except Exception as e:
                            print(f"[Middleware] Error forwarding bot card: {e}")
                        continue
                    
                    elif data.get("type") == "bot_recognition_complete":
                        print(f"[Middleware] 🤖 Bot recognition complete!")
                        # Notify frontend
                        for ws in active_connections.values():
                            try:
                                await ws.send_json({
                                    "type": "bot_recognition_complete",
                                    "player_id": data["player_id"]
                                })
                            except:
                                pass
                        continue
                    
                    # Normal card detection
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
