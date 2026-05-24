from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Dict, Optional
import base64
from io import BytesIO
from PIL import Image
import cv2
import numpy as np
import json
import os
import time

from yolo import CornerYoloDetector


app = FastAPI(title="Computer Vision Service", version="2.0")


detector: Optional[CornerYoloDetector] = None
active_games: Dict[str, Dict] = {}
MAX_CARDS_PER_TRICK = 4


class StartCVRequest(BaseModel):
    game_id: str


def parse_label(label: str):
    if len(label) < 2:
        return None, None

    rank = label[:-1]
    suit_char = label[-1].lower()
    suit_map = {
        "c": "Clubs",
        "d": "Diamonds",
        "h": "Hearts",
        "s": "Spades",
    }
    suit = suit_map.get(suit_char)
    if suit is None:
        return None, None

    return rank, suit


def bbox_overlap_ratio(box_new, box_existing):
    ax1, ay1, ax2, ay2 = box_new
    bx1, by1, bx2, by2 = box_existing

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0

    inter_area = (ix2 - ix1) * (iy2 - iy1)
    area_new = (ax2 - ax1) * (ay2 - ay1)
    if area_new <= 0:
        return 0.0

    return inter_area / area_new


def base64_to_image(base64_string: str):
    try:
        img_data = base64.b64decode(base64_string)
        pil_image = Image.open(BytesIO(img_data)).convert("RGB")
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    except Exception as exc:
        print(f"[CV2] Failed to decode frame: {exc}")
        return None


def resolve_model_path() -> Optional[str]:
    env_path = os.getenv("CV2_MODEL_PATH")
    candidates = []
    if env_path:
        candidates.append(env_path)

    candidates.extend(
        [
            "./runs/archive3_final/weights/best.pt",
            "./runs/detect/corner_cards/weights/best.pt",
            "./runs/detect/train/weights/best.pt",
            "../ComputerVision_1.0/runs/detect/train/weights/best.pt",
        ]
    )

    for path in candidates:
        if os.path.exists(path):
            return path
    return None


EXCLUSION_OVERLAP_THRESHOLD = 0.40


def should_accept_card(rank: str, suit: str, confidence: float) -> bool:
    """
    Selectively filter cards based on rank and confidence.
    - Cards 8, 9, 10: Never accepted (not used in Sueca)
    - Aces: Accepted if confidence >= 0.5 (difficult to recognize)
    - Others: Accepted if confidence >= 0.8 (normal threshold)
    """
    # Never accept 8, 9, 10
    if rank in ("8", "9", "10"):
        return False
    
    # Aces need lower confidence (they're hard to detect)
    if rank == "A":
        return confidence >= 0.5
    
    # All other cards need 0.8 confidence
    return confidence >= 0.8


@app.post("/cv/start")
async def start_cv_service(request: StartCVRequest):
    global detector

    try:
        model_path = resolve_model_path()
        if model_path is None:
            raise HTTPException(
                status_code=500,
                detail=(
                    "No detection model found. Set CV2_MODEL_PATH or place a model in "
                    "runs/detect/.../best.pt"
                ),
            )

        detector = CornerYoloDetector(model_path=model_path)

        active_games[request.game_id] = {
            "sent_labels": set(),
            "exclusion_zones": [],
            "paused_until": 0,
            "trick_count": 0,
            "trick_locked": False,
            "frame_consistency": {},
        }

        return {
            "success": True,
            "message": "CV 2.0 service started successfully",
            "model_path": model_path,
        }
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[CV2] Error starting service: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.websocket("/cv/stream/{game_id}")
async def cv_stream(websocket: WebSocket, game_id: str):
    global detector

    await websocket.accept()
    print(f"[CV2] WebSocket connected for game: {game_id}")

    if detector is None:
        await websocket.send_json({"error": "CV service not initialized. Call /cv/start first."})
        await websocket.close()
        return

    if game_id not in active_games:
        active_games[game_id] = {
            "sent_labels": set(),
            "exclusion_zones": [],
            "paused_until": 0,
            "trick_count": 0,
            "trick_locked": False,
            "frame_consistency": {},
        }

    game_state = active_games[game_id]
    sent_labels = game_state["sent_labels"]
    exclusion_zones = game_state["exclusion_zones"]
    frame_consistency = game_state["frame_consistency"]

    try:
        while True:
            message = await websocket.receive_text()

            if message.startswith("{"):
                try:
                    command = json.loads(message)
                    if command.get("action") == "reset_cards":
                        delay = command.get("delay", 3)
                        full = command.get("full", False)
                        game_state["paused_until"] = time.time() + delay
                        exclusion_zones.clear()
                        frame_consistency.clear()
                        game_state["trick_count"] = 0
                        game_state["trick_locked"] = False
                        if full:
                            sent_labels.clear()
                        await websocket.send_json(
                            {
                                "success": True,
                                "message": "cards_reset",
                                "paused_seconds": delay,
                            }
                        )
                        continue
                except json.JSONDecodeError:
                    pass

            frame = base64_to_image(message)
            if frame is None:
                continue

            if time.time() < game_state["paused_until"]:
                continue

            # After 4 cards in a trick, ignore all detections until reset_cards arrives.
            if game_state["trick_locked"]:
                continue

            detections = detector.detect(frame)
            
            # Clean up frame_consistency for positions that no longer exist
            positions_to_remove = [pos for pos in frame_consistency if pos >= len(detections)]
            for pos in positions_to_remove:
                del frame_consistency[pos]
            
            for i, det in enumerate(detections):
                bbox = det["bbox"]

                skip = False
                for zone in exclusion_zones:
                    overlap = bbox_overlap_ratio(bbox, zone)
                    if overlap >= EXCLUSION_OVERLAP_THRESHOLD:
                        skip = True
                        break
                if skip:
                    continue

                rank, suit = parse_label(det["label"])
                if rank is None or suit is None:
                    continue

                # Apply selective confidence filtering
                if not should_accept_card(rank, suit, det["confidence"]):
                    continue

                card_key = f"{rank}_{suit}"
                label_str = f"{rank} of {suit}"
                
                # Consecutive frames validation
                if i not in frame_consistency:
                    frame_consistency[i] = {
                        "label": label_str,
                        "count": 1,
                        "card_key": card_key
                    }
                else:
                    prev_consistency = frame_consistency[i]
                    if prev_consistency["label"] == label_str and card_key:
                        prev_consistency["count"] += 1
                        
                        if prev_consistency["count"] == 3 and card_key not in sent_labels:
                            sent_labels.add(card_key)
                            exclusion_zones.append(tuple(bbox))
                            game_state["trick_count"] += 1

                            with open("cartas_detetadas.txt", "a",encoding="utf-8") as f:
                                f.write(f"{rank} {suit} .\n")

                            detection = {
                                "rank": rank,
                                "suit": suit,
                                "confidence": det["confidence"],
                                "position": i,
                            }
                            await websocket.send_json({"success": True, "detection": detection})

                            if game_state["trick_count"] >= MAX_CARDS_PER_TRICK:
                                game_state["trick_locked"] = True
                                break
                    else:
                        frame_consistency[i] = {
                            "label": label_str,
                            "count": 1,
                            "card_key": card_key
                        }

    except WebSocketDisconnect:
        print(f"[CV2] WebSocket disconnected for game: {game_id}")
    except Exception as exc:
        print(f"[CV2] Error in WebSocket stream: {exc}")
        await websocket.close()


@app.post("/cv/stop")
async def stop_cv_service(game_id: str):
    if game_id in active_games:
        del active_games[game_id]
        return {"success": True, "message": "CV service stopped"}
    return {"success": False, "message": "Game not found"}


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "detector_loaded": detector is not None,
        "active_games": len(active_games),
        "version": "2.0",
    }
