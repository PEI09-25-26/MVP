from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
from card_mapper import CardMapper
from referee import Referee

app = FastAPI(title="Card Game Backend")
ref = Referee()

class CardDTO(BaseModel):
    rank: str
    suit: str
    confidence: Optional[float] = None

@app.get("/state")
def get_state():
    return ref.state()

@app.post("/reset")
def reset_game():
    global ref
    ref = Referee()
    return {"success": True, "message": "Game reset"}

@app.post("/card")
def receive_card(card: CardDTO):
    print(f"[DEBUG] Received card: {card.rank} {card.suit}")
    try:
        rank_index = CardMapper.RANKS.index(card.rank)
        suit_index = CardMapper.SUITS.index(card.suit)
        card_id = suit_index * CardMapper.SUITSIZE + rank_index
    except ValueError:
        print("[DEBUG] Invalid card!")
        return {"success": False, "message": "Invalid card"}

    ref.inject_card(card_id)
    print(f"[DEBUG] Card injected. Queue size: {len(ref.card_queue)}")

    if not ref.trump_set:
        print("[DEBUG] Setting trump...")
        ref.set_trump()
        print(f"[DEBUG] Trump now: {CardMapper.get_card(ref.trump)} (suit: {ref.trump_suit})")
        return {
            "success": True,
            "message": "Trump card set"
        }

    if len(ref.card_queue) >= 4:
        print("[DEBUG] Enough cards for a round, playing round...")
        round_ok = ref.play_round()
        print(f"[REFEREE] Round played. Team 1 points: {ref.team1_points}, Team 2 points: {ref.team2_points}")
        if not round_ok:
            return {
                "success": False,
                "message": "Round failed (renuncia or invalid play)"
            }
        return {
            "success": True,
            "message": "Round played",
            "team1_points": ref.team1_points,
            "team2_points": ref.team2_points
        }

    return {
        "success": True,
        "message": "Card queued",
        "queue_size": len(ref.card_queue)
    }