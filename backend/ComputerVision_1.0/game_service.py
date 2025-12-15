from fastapi import FastAPI
from pydantic import BaseModel
import requests
from typing import Optional
from card_mapper import CardMapper
from referee import Referee
import threading

app = FastAPI(title="Card Game Backend")
ref = Referee()

MIDDLEWARE_URL = "http://localhost:8000/game/state"
MIDDLEWARE_ROUND_END_URL = "http://localhost:8000/game/round_end"

# Game constants
MAX_ROUNDS = 4  # 4 rondas por jogo
MAX_RODADAS = 10  # 10 rodadas por ronda
current_round = 1  # Ronda atual (1-4)
current_hand = 0

class CardDTO(BaseModel):
    rank: str
    suit: str
    confidence: Optional[float] = None

@app.get("/state")
def get_state():
    return ref.state()

def send_state_to_middleware(ref):
    try:
        requests.post(MIDDLEWARE_URL, json=ref.state(), timeout=0.2)
        print("[SYNC] State pushed to middleware")
    except requests.exceptions.RequestException as e:
        print(f"[WARN] State sync failed: {e}")

def push_state(ref):
    threading.Thread(
        target=send_state_to_middleware,
        args=(ref,),
        daemon=True
    ).start()

@app.post("/reset")
def reset_game():
    global ref, current_round
    ref = Referee()
    current_round = 1
    return {"success": True, "message": "Game reset"}

@app.post("/new_round")
def new_round():
    """Inicia uma nova ronda (reset do referee mas mantém victories)"""
    global ref, current_round
    team1_vict = ref.team1_victories
    team2_vict = ref.team2_victories
    ref = Referee()
    ref.team1_victories = team1_vict
    ref.team2_victories = team2_vict
    current_round += 1
    return {
        "success": True, 
        "message": f"Nova ronda {current_round} iniciada",
        "round": current_round
    }

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
        push_state(ref)
        return {
            "success": True,
            "message": "Trump card set"
        }

    current_hand += 1

    if len(ref.card_queue) >= 4:
        current_hand = 0
        print("[DEBUG] Enough cards for a round, playing round...")
        round_ok = ref.play_round()
        print(f"[REFEREE] Round played. Team 1 points: {ref.team1_points}, Team 2 points: {ref.team2_points}")
        
        # Verificar se a ronda acabou (10 rodadas ou rendição)
        round_ended = False
        winner_team = None
        winner_points = 0
        
        if not round_ok:
            # Rendição - a ronda acaba imediatamente
            round_ended = True
            if ref.team1_victories > ref.team2_victories:
                winner_team = 1
                winner_points = ref.team1_victories
            else:
                winner_team = 2
                winner_points = ref.team2_victories
            print(f"[RONDA] Acabou por rendição! Equipa {winner_team} ganhou com {winner_points} pontos")
        elif ref.rounds_played >= MAX_RODADAS:
            # 10 rodadas completadas
            round_ended = True
            if ref.team1_points > ref.team2_points:
                winner_team = 1
                winner_points = ref.team1_points
            else:
                winner_team = 2
                winner_points = ref.team2_points
            print(f"[RONDA] Acabou após 10 rodadas! Equipa {winner_team} ganhou com {winner_points} pontos")
        
        if round_ended:
            # Notificar middleware sobre fim de ronda
            try:
                round_data = {
                    "round_number": current_round,
                    "winner_team": winner_team,
                    "winner_points": winner_points,
                    "team1_points": ref.team1_points,
                    "team2_points": ref.team2_points,
                    "game_ended": current_round >= MAX_ROUNDS
                }
                requests.post(MIDDLEWARE_ROUND_END_URL, json=round_data, timeout=1)
                print(f"[SYNC] Round end notification sent to middleware")
            except Exception as e:
                print(f"[WARN] Failed to notify middleware: {e}")
        
        push_state(ref)
        
        if not round_ok:
            return {
                "success": False,
                "message": "Round failed (renuncia or invalid play)",
                "round_ended": round_ended,
                "winner_team": winner_team,
                "winner_points": winner_points
            }
        return {
            "success": True,
            "message": "Round played",
            "team1_points": ref.team1_points,
            "team2_points": ref.team2_points,
            "rounds_played": ref.rounds_played,
            "round_ended": round_ended,
            "winner_team": winner_team,
            "winner_points": winner_points
        }

    return {
        "success": True,
        "message": "Card queued",
        "current_player": current_hand,
        "queue_size": len(ref.card_queue)
    }