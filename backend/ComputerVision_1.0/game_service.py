from fastapi import FastAPI
from pydantic import BaseModel
import requests
from typing import Optional, List, Dict
from card_mapper import CardMapper
from referee import Referee
import threading
import random

app = FastAPI(title="Card Game Backend")
ref = Referee()

MIDDLEWARE_URL = "http://localhost:8000/game/state"
MIDDLEWARE_ROUND_END_URL = "http://localhost:8000/game/round_end"
BOT_SERVICE_URL = "http://localhost:8003"

# Game constants
MAX_ROUNDS = 4  # 4 rondas por jogo
MAX_RODADAS = 10  # 10 rodadas por ronda
current_round = 1  # Ronda atual (1-4)
current_hand = 0

# Bot management
bot_players: Dict[int, bool] = {}  # {player_id: is_bot}
used_cards: List[int] = []  # Cartas já distribuídas nesta ronda

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
    global ref, current_round, bot_players, used_cards
    ref = Referee()
    current_round = 1
    bot_players = {}
    used_cards = []
    # Reset bots
    try:
        requests.post(f"{BOT_SERVICE_URL}/bot/reset", timeout=1)
    except:
        pass
    return {"success": True, "message": "Game reset"}


# ========== BOT MANAGEMENT ==========

@app.post("/player/{player_id}/set_bot")
def set_player_as_bot(player_id: int):
    """Marca um jogador como bot"""
    global bot_players
    if player_id < 1 or player_id > 4:
        return {"success": False, "message": "Player ID deve ser entre 1 e 4"}
    
    bot_players[player_id] = True
    
    # Criar bot no bot_service
    try:
        response = requests.post(f"{BOT_SERVICE_URL}/bot/create/{player_id}", timeout=2)
        if response.status_code == 200:
            print(f"[GAME] Player {player_id} é agora um bot")
            return {"success": True, "message": f"Player {player_id} é agora um bot"}
    except Exception as e:
        print(f"[WARN] Failed to create bot: {e}")
    
    return {"success": True, "message": f"Player {player_id} marcado como bot (offline)"}


@app.post("/player/{player_id}/remove_bot")
def remove_player_bot(player_id: int):
    """Remove bot de um jogador"""
    global bot_players
    if player_id in bot_players:
        del bot_players[player_id]
        try:
            requests.delete(f"{BOT_SERVICE_URL}/bot/{player_id}", timeout=1)
        except:
            pass
    return {"success": True, "message": f"Bot removido do player {player_id}"}


@app.get("/players/bots")
def get_bot_players():
    """Lista jogadores que são bots"""
    return {"bots": list(bot_players.keys())}


@app.post("/bot/deal_cards")
def deal_cards_to_bots():
    """Distribui 10 cartas aleatórias a cada bot após o trunfo ser definido"""
    global used_cards
    
    if not ref.trump_set:
        return {"success": False, "message": "Trunfo ainda não foi definido"}
    
    # Adicionar carta de trunfo às usadas
    used_cards = [ref.trump]
    
    results = {}
    for player_id in bot_players.keys():
        # Gerar 10 cartas aleatórias não usadas
        available = [i for i in range(40) if i not in used_cards]
        bot_cards = random.sample(available, min(10, len(available)))
        used_cards.extend(bot_cards)
        
        # Enviar cartas ao bot
        try:
            response = requests.post(
                f"{BOT_SERVICE_URL}/bot/{player_id}/deal",
                json={"cards": bot_cards, "trump_suit": ref.trump_suit},
                timeout=2
            )
            if response.status_code == 200:
                cards_names = [CardMapper.get_card(c) for c in bot_cards]
                results[player_id] = {"success": True, "cards": cards_names}
                print(f"[GAME] Bot {player_id} recebeu: {cards_names}")
        except Exception as e:
            results[player_id] = {"success": False, "error": str(e)}
    
    return {"success": True, "bots_dealt": results}


@app.post("/bot/{player_id}/request_play")
def request_bot_play(player_id: int, round_suit: Optional[str] = None):
    """Pede ao bot para jogar uma carta"""
    if player_id not in bot_players:
        return {"success": False, "message": f"Player {player_id} não é um bot"}
    
    is_first_round = ref.rounds_played == 0
    # O dealer é sempre o jogador 4
    is_dealer = player_id == 4
    
    try:
        response = requests.post(
            f"{BOT_SERVICE_URL}/bot/{player_id}/play",
            json={
                "round_suit": round_suit,
                "cards_played": list(ref.round_vector),
                "is_first_round": is_first_round,
                "is_dealer": is_dealer
            },
            timeout=2
        )
        
        if response.status_code == 200:
            data = response.json()
            card_id = data["card_id"]
            card_name = data["card_name"]
            card_index = data["card_index"]
            
            # Injetar carta no jogo
            ref.inject_card(card_id)
            
            print(f"[GAME] Bot {player_id} jogou carta {card_index}: {card_name}")
            
            return {
                "success": True,
                "card_id": card_id,
                "card_name": card_name,
                "card_index": card_index,
                "player_id": player_id
            }
    except Exception as e:
        print(f"[ERROR] Failed to get bot play: {e}")
        return {"success": False, "message": str(e)}
    
    return {"success": False, "message": "Bot failed to play"}


@app.get("/game/current_turn")
def get_current_turn():
    """Retorna de quem é a vez de jogar"""
    current_player = ref.current_player
    cards_in_round = len(ref.card_queue)
    
    # Calcular quem deve jogar agora
    turn_player = ((current_player + cards_in_round - 1) % 4) + 1
    is_bot = turn_player in bot_players
    
    return {
        "current_player": turn_player,
        "is_bot": is_bot,
        "cards_in_round": cards_in_round,
        "rounds_played": ref.rounds_played
    }


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
    global current_hand
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
        
        # Se há bots, distribuir cartas (mas NÃO iniciar reconhecimento ainda)
        if bot_players:
            print("[DEBUG] Distribuindo cartas aos bots...")
            bot_result = deal_cards_to_bots()
            print("[DEBUG] ⏸️  Aguardando que jogador pressione botão para mostrar cartas ao bot")
            
            # Notificar middleware que as cartas foram distribuídas
            try:
                requests.post(
                    f"{MIDDLEWARE_URL.replace('/game/state', '/game/bot_cards_dealt_notification')}",
                    json=bot_result,
                    timeout=1
                )
            except Exception as e:
                print(f"[WARN] Failed to notify bot cards dealt: {e}")
        
        return {
            "success": True,
            "message": "Trump card set",
            "round_number": current_round,
            "has_bots": len(bot_players) > 0
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
        
        # Verificar se o próximo jogador (início da próxima rodada) é um bot
        if not round_ended and ref.current_player in bot_players:
            print(f"[DEBUG] Próximo a jogar (início de rodada) é bot ({ref.current_player}), acionando...")
            try:
                # Chamar diretamente ao invés de HTTP request
                bot_result = request_bot_play(ref.current_player, None)
                
                if bot_result.get("success"):
                    print(f"[DEBUG] ✅ Bot {ref.current_player} jogou automaticamente: {bot_result.get('card_name')}")
                    # Notificar middleware
                    try:
                        requests.post(
                            f"{MIDDLEWARE_URL.replace('/game/state', '/game/bot_played_notification')}",
                            json=bot_result,
                            timeout=1
                        )
                    except:
                        pass
                        
            except Exception as e:
                print(f"[WARN] Failed to trigger bot play after round: {e}")
        
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

    # Verificar se o próximo jogador é um bot e acionar automaticamente
    next_player = ((ref.current_player + len(ref.card_queue) - 1) % 4) + 1
    if next_player in bot_players and len(ref.card_queue) < 4:
        print(f"[DEBUG] Próximo jogador é bot ({next_player}), acionando jogada automática...")
        # Acionar bot automaticamente DIRETAMENTE (não via middleware para evitar loop)
        try:
            # Obter naipe da primeira carta da rodada (se houver)
            round_suit = None
            if ref.card_queue:
                first_card_id = ref.card_queue[0]
                # Extrair naipe do card_id (o naipe está nos últimos 2 bits)
                suit_idx = first_card_id % 4
                suit_map = ["♣", "♦", "♥", "♠"]
                round_suit = suit_map[suit_idx]
            
            # Chamar diretamente a função local ao invés de fazer HTTP request
            bot_result = request_bot_play(next_player, round_suit)
            
            if bot_result.get("success"):
                print(f"[DEBUG] ✅ Bot {next_player} jogou automaticamente: {bot_result.get('card_name')}")
                # Notificar middleware sobre a jogada do bot
                try:
                    requests.post(
                        f"{MIDDLEWARE_URL.replace('/game/state', '/game/bot_played_notification')}",
                        json=bot_result,
                        timeout=1
                    )
                except:
                    pass
            else:
                print(f"[WARN] Bot {next_player} falhou ao jogar: {bot_result.get('message')}")
                
        except Exception as e:
            print(f"[WARN] Failed to trigger bot play: {e}")
    
    return {
        "success": True,
        "message": "Card queued",
        "current_player": current_hand,
        "queue_size": len(ref.card_queue),
        "next_player": next_player,
        "next_is_bot": next_player in bot_players
    }