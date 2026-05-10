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
import time

# ---------- App ----------

app = FastAPI(title="Computer Vision Service", version="1.0")

# ---------- Global State ----------

detector: Optional[CardDetector] = None
classifier: Optional[CardClassifier] = None
# Legacy compatibility placeholders (corner pipeline disabled).
classifier_rank: Optional[CardClassifier] = None
classifier_suit: Optional[CardClassifier] = None
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


def normalize_rank_label(rank_label: str) -> str:
    rank_map = {
        "Ace": "A",
        "11": "J",
        "12": "Q",
        "13": "K"
    }
    return rank_map.get(rank_label, rank_label)


def extract_symbol_patch(flat_card: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> Optional[np.ndarray]:
    """
    Extracts one symbol (rank or suit) from a fixed corner region of a flattened card.
    Returns a 3-channel 28x40 patch compatible with the corner dataset style.
    """
    if flat_card is None or flat_card.size == 0:
        return None

    h, w = flat_card.shape[:2]
    x1 = max(0, min(x1, w - 1))
    x2 = max(1, min(x2, w))
    y1 = max(0, min(y1, h - 1))
    y2 = max(1, min(y2, h))

    if x2 <= x1 or y2 <= y1:
        return None

    region = flat_card[y1:y2, x1:x2]
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)

    _, bin_img = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    fg = cv2.bitwise_not(bin_img)

    contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        cnt = max(contours, key=cv2.contourArea)
        x, y, cw, ch = cv2.boundingRect(cnt)
        if cw > 2 and ch > 2:
            pad = 2
            xs = max(0, x - pad)
            ys = max(0, y - pad)
            xe = min(gray.shape[1], x + cw + pad)
            ye = min(gray.shape[0], y + ch + pad)
            symbol = gray[ys:ye, xs:xe]
        else:
            symbol = gray
    else:
        symbol = gray

    symbol = cv2.resize(symbol, (28, 40), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(symbol, cv2.COLOR_GRAY2BGR)


def classify_corner_card(flat_card: np.ndarray):
    """
    Classifies rank and suit from corner symbols of a normalized 200x280 card.
    Tries 4 rotations to handle cards arriving upside-down or sideways.
    Returns rank, suit, confidence.
    """
    if classifier_rank is None or classifier_suit is None:
        return None, None, 0.0

    candidates = [
        flat_card,
        cv2.rotate(flat_card, cv2.ROTATE_90_CLOCKWISE),
        cv2.rotate(flat_card, cv2.ROTATE_180),
        cv2.rotate(flat_card, cv2.ROTATE_90_COUNTERCLOCKWISE),
    ]

    best_rank = None
    best_suit = None
    best_conf = 0.0

    for candidate in candidates:
        # Regions tuned for normalized card output from opencv.py (200x280).
        rank_patch = extract_symbol_patch(candidate, x1=4, y1=5, x2=62, y2=95)
        suit_patch = extract_symbol_patch(candidate, x1=4, y1=85, x2=62, y2=175)

        if rank_patch is None or suit_patch is None:
            continue

        rank_label, rank_conf = classifier_rank.classify(rank_patch, require_min_conf=False)
        suit_label, suit_conf = classifier_suit.classify(suit_patch, require_min_conf=False)

        if not rank_label or not suit_label:
            continue

        conf = min(rank_conf, suit_conf)
        if conf > best_conf:
            best_rank = normalize_rank_label(rank_label)
            best_suit = suit_label
            best_conf = conf

    # Gate final output after choosing the best orientation.
    if best_rank is None or best_suit is None or best_conf < 0.50:
        return None, None, 0.0

    return best_rank, best_suit, best_conf


# ---------- Exclusion Zone Helpers ----------

def corners_to_bbox(corners):
    """
    Convert 4-corner points to an axis-aligned bounding box (x, y, w, h).
    corners: array of shape (4, 1, 2) or (4, 2)
    """
    pts = np.array(corners).reshape(-1, 2)
    x_min, y_min = pts.min(axis=0)
    x_max, y_max = pts.max(axis=0)
    return (float(x_min), float(y_min), float(x_max - x_min), float(y_max - y_min))


def bbox_iou(box_a, box_b):
    """
    Compute Intersection over Union between two bboxes (x, y, w, h).
    Returns IoU value [0, 1].
    """
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b

    # Intersection
    ix1 = max(ax, bx)
    iy1 = max(ay, by)
    ix2 = min(ax + aw, bx + bw)
    iy2 = min(ay + ah, by + bh)

    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0

    inter_area = (ix2 - ix1) * (iy2 - iy1)
    area_a = aw * ah
    area_b = bw * bh
    union_area = area_a + area_b - inter_area

    if union_area <= 0:
        return 0.0

    return inter_area / union_area


def bbox_overlap_ratio(box_new, box_existing):
    """
    What percentage of box_new is covered by box_existing.
    """
    ax, ay, aw, ah = box_new
    bx, by, bw, bh = box_existing

    ix1 = max(ax, bx)
    iy1 = max(ay, by)
    ix2 = min(ax + aw, bx + bw)
    iy2 = min(ay + ah, by + bh)

    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0

    inter_area = (ix2 - ix1) * (iy2 - iy1)
    area_new = aw * ah
    if area_new <= 0:
        return 0.0

    return inter_area / area_new


# Overlap threshold: if a new card's bbox overlaps >= this with any exclusion zone, skip it
EXCLUSION_OVERLAP_THRESHOLD = 0.40


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
        
        # Legacy mode: use only the combined card classifier.
        model_path = "./runs/classify/sueca_cards_classifier/weights/best.pt"

        if os.path.exists(model_path):
            print(f"[CV Service] Combined model found: {model_path}")
            classifier = CardClassifier(model_path=model_path)
            print("[CV Service] Combined classifier initialized successfully")
        else:
            print("[CV Service] No YOLO model found. Only detection will be available.")
            classifier = None
        
        # Track this game
        active_games[request.game_id] = {
            "last_labels": {},
            "sent_labels": set(),
            "exclusion_zones": [],  # list of bboxes (x, y, w, h)
            "paused_until": 0       # timestamp until which detection is paused
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
            "sent_labels": set(),
            "exclusion_zones": [],
            "paused_until": 0
        }
    
    game_state = active_games[game_id]
    last_labels = game_state["last_labels"]
    sent_labels = game_state["sent_labels"]
    exclusion_zones = game_state["exclusion_zones"]
    
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
                        delay = command.get("delay", 3)  # seconds to pause detection
                        full = command.get("full", False)  # full=True only at new game
                        print(f"[CV Service] 🔄 Reset command - pausing {delay}s (full={full})")
                        game_state["paused_until"] = time.time() + delay
                        last_labels.clear()
                        exclusion_zones.clear()
                        if full:
                            sent_labels.clear()
                            print(f"[CV Service] Full reset: sent_labels cleared")
                        await websocket.send_json({
                            "success": True,
                            "message": "cards_reset",
                            "paused_seconds": delay
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
            
            # Skip detection while paused (cards being removed from table)
            if time.time() < game_state["paused_until"]:
                continue

            # Detect cards using OpenCV
            flatten_cards, img_result, four_corners_set = detector.detect_cards_from_frame(frame)
            
            # Classify cards if combined classifier is available
            if flatten_cards and classifier:
                for i, flat_card in enumerate(flatten_cards):
                    # --- Exclusion zone check ---
                    if i < len(four_corners_set):
                        card_bbox = corners_to_bbox(four_corners_set[i])
                        # Check if this card's position overlaps with any exclusion zone
                        skip = False
                        for zone in exclusion_zones:
                            overlap = bbox_overlap_ratio(card_bbox, zone)
                            if overlap >= EXCLUSION_OVERLAP_THRESHOLD:
                                skip = True
                                break
                        if skip:
                            continue  # Skip classification entirely
                    # --- End exclusion zone check ---

                    class_label, conf = classifier.classify(flat_card)

                    rank = None
                    suit = None
                    if class_label:
                        rank, suit = parse_label(class_label)

                    card_key = f"{rank}_{suit}" if rank and suit else None
                    label_str = f"{rank} of {suit} ({conf:.2f})" if rank and suit else "Unknown"
                    
                    prev_label = last_labels.get(i)
                    if prev_label != label_str and card_key:
                        print(f"[CV Service] Card {i}: {label_str}")
                        last_labels[i] = label_str
                        
                        # Only report new detections
                        if card_key not in sent_labels:
                            # Register exclusion zone for this card
                            if i < len(four_corners_set):
                                card_bbox = corners_to_bbox(four_corners_set[i])
                                exclusion_zones.append(card_bbox)
                                print(f"[CV Service] 🔒 Exclusion zone added: {card_bbox}")

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
                            sent_labels.add(card_key)
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
