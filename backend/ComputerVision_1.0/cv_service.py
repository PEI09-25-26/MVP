from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, List
import cv2
import numpy as np
import base64
from io import BytesIO
from PIL import Image
import asyncio
import json

from opencv import CardDetector
from yolo import CardClassifier
from card_mapper import CardMapper
import os

# ---------- App ----------

app = FastAPI(title="Computer Vision Service", version="1.0")

# ---------- Global State ----------

detector: Optional[CardDetector] = None
classifier: Optional[CardClassifier] = None
active_games: dict = {}


# ---------- Models ----------

class StartCVRequest(BaseModel):
    game_id: str


class ProcessFrameRequest(BaseModel):
    frame_base64: str
    game_id: str


class CardDetectionResult(BaseModel):
    rank: str
    suit: str
    confidence: float
    position: int  # index of the card detected


class ProcessFrameResponse(BaseModel):
    success: bool
    message: str
    detections: List[CardDetectionResult] = []


# ---------- Helper Functions ----------

def parse_label(label: str):
    """
    Converts YOLO label like 'Kc' or '10h' to rank and suit.
    """
    if len(label) < 2:
        return None, None
    rank = label[:-1]
    suit_char = label[-1].lower()
    suit_map = {
        "c": "Clubs",
        "d": "Diamonds",
        "h": "Hearts",
        "s": "Spades"
    }
    suit = suit_map.get(suit_char, "Unknown")
    return rank, suit


def base64_to_image(base64_string: str) -> Optional[np.ndarray]:
    """
    Converts a base64 string to OpenCV image (numpy array).
    """
    try:
        # Decode base64
        img_data = base64.b64decode(base64_string)
        
        # Convert to PIL Image
        pil_image = Image.open(BytesIO(img_data))
        
        # Convert to OpenCV format (BGR)
        opencv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        
        return opencv_image
    except Exception as e:
        print(f"[CV Service] Error converting base64 to image: {e}")
        return None


# ---------- Endpoints ----------

@app.post("/cv/start")
async def start_cv_service(request: StartCVRequest):
    """
    Initializes the CV service with detector and classifier.
    """
    global detector, classifier
    
    try:
        # Initialize detector
        detector = CardDetector(debug=False, min_area=10000)
        
        # Find YOLO model
        model_path = None
        runs_path = "./runs/classify/sueca_cards_classifier/weights/best.pt"
        if os.path.exists(runs_path):
            model_path = runs_path
            print(f"[CV Service] YOLO model found: {model_path}")

        # Initialize classifier if model found
        if model_path is not None and os.path.exists(model_path):
            classifier = CardClassifier(model_path=model_path)
            print("[CV Service] Classifier initialized successfully")
        else:
            print("[CV Service] No YOLO model found. Only detection will be available.")
            classifier = None
        
        # Track this game
        active_games[request.game_id] = {
            "last_labels": {},
            "sent_labels": set()
        }
        
        return {
            "success": True,
            "message": "CV service started successfully",
            "has_classifier": classifier is not None
        }
        
    except Exception as e:
        print(f"[CV Service] Error starting service: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/cv/stream/{game_id}")
async def cv_stream(websocket: WebSocket, game_id: str):
    """
    WebSocket endpoint to receive continuous video stream and process cards.
    """
    global detector, classifier
    
    await websocket.accept()
    print(f"[CV Service] WebSocket connected for game: {game_id}")
    
    if detector is None:
        await websocket.send_json({"error": "CV service not initialized. Call /cv/start first."})
        await websocket.close()
        return
    
    # Get or create game state
    if game_id not in active_games:
        active_games[game_id] = {
            "last_labels": {},
            "sent_labels": set()
        }
    
    game_state = active_games[game_id]
    last_labels = game_state["last_labels"]
    sent_labels = game_state["sent_labels"]
    
    frame_count = 0
    
    try:
        while True:
            # Receive message from websocket
            message = await websocket.receive_text()
            
            # Check if it's a command (JSON) or frame data (base64)
            if message.startswith("{"):
                # It's a command
                try:
                    command = json.loads(message)
                    if command.get("action") == "reset_cards":
                        print(f"[CV Service] 🔄 Received reset command - clearing card history")
                        sent_labels.clear()
                        last_labels.clear()
                        await websocket.send_json({
                            "success": True,
                            "message": "cards_reset"
                        })
                        continue
                except json.JSONDecodeError:
                    pass  # Not a valid JSON, treat as frame
            
            # It's a base64 frame
            frame_base64 = message
            frame_count += 1
            
            # Convert base64 to image
            frame = base64_to_image(frame_base64)
            if frame is None:
                continue
            
            # Detect cards using OpenCV
            flatten_cards, img_result, four_corners_set = detector.detect_cards_from_frame(frame)
            
            # Classify cards if classifier is available
            if flatten_cards and classifier:
                for i, flat_card in enumerate(flatten_cards):
                    class_label, conf = classifier.classify(flat_card)
                    label_str = f"{class_label} ({conf:.2f})" if class_label else "Unknown"
                    
                    prev_label = last_labels.get(i)
                    if prev_label != label_str and class_label:
                        print(f"[CV Service] Card {i}: {label_str}")
                        last_labels[i] = label_str
                        
                        # Only report new detections
                        if class_label not in sent_labels:
                            rank, suit = parse_label(class_label)
                            if rank and suit:
                                # Send detection back to middleware
                                detection = {
                                    "rank": rank,
                                    "suit": suit,
                                    "confidence": conf,
                                    "position": i
                                }
                                await websocket.send_json({
                                    "success": True,
                                    "detection": detection
                                })
                                sent_labels.add(class_label)
                                print(f"[CV Service] ✓ New card detected: {rank} of {suit} (confidence: {conf:.2%})")
            
            # Log progress every 30 frames
            if frame_count % 30 == 0:
                cards_sent = len(sent_labels)
                
    except WebSocketDisconnect:
        print(f"[CV Service] WebSocket disconnected for game: {game_id}")
    except Exception as e:
        print(f"[CV Service] Error in WebSocket stream: {e}")
        await websocket.close()


@app.post("/cv/stop")
async def stop_cv_service(game_id: str):
    """
    Stops CV service for a specific game.
    """
    if game_id in active_games:
        del active_games[game_id]
        return {"success": True, "message": "CV service stopped"}
    return {"success": False, "message": "Game not found"}


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {
        "status": "healthy",
        "detector_loaded": detector is not None,
        "classifier_loaded": classifier is not None,
        "active_games": len(active_games)
    }
