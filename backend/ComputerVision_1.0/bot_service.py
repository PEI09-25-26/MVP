from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
import random

app = FastAPI(title="Bot IA Service", version="1.0")

# Estrutura de dados
RANKS = ["2", "3", "4", "5", "6", "Q", "J", "K", "7", "A"]
SUITS = ["♣", "♦", "♥", "♠"]
RANK_VALUES = {"2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "Q": 2, "J": 3, "K": 4, "7": 10, "A": 11}

# Armazenamento dos bots
bots: Dict[int, "Bot"] = {}


class Bot:
    def __init__(self, player_id: int):
        self.player_id = player_id
        self.cards: List[int] = []  # IDs das cartas (0-39)
        self.trump_suit: Optional[str] = None
    
    def get_card_suit(self, card_id: int) -> str:
        return SUITS[card_id // 10]
    
    def get_card_rank(self, card_id: int) -> str:
        return RANKS[card_id % 10]
    
    def get_card_name(self, card_id: int) -> str:
        return f"{self.get_card_rank(card_id)}{self.get_card_suit(card_id)}"
    
    def get_card_value(self, card_id: int) -> int:
        rank = self.get_card_rank(card_id)
        return RANK_VALUES[rank]
    
    def has_suit(self, suit: str) -> bool:
        for card_id in self.cards:
            if self.get_card_suit(card_id) == suit:
                return True
        return False
    
    def get_cards_of_suit(self, suit: str) -> List[int]:
        return [c for c in self.cards if self.get_card_suit(c) == suit]
    
    def choose_card(self, round_suit: Optional[str], cards_played: List[int], is_first_round: bool, is_dealer: bool) -> int:
        """
        Escolhe a melhor carta a jogar seguindo as regras da Sueca.
        Estratégia: jogar a carta mais baixa válida, ou a mais alta se puder ganhar.
        """
        valid_cards = []
        
        if round_suit is None:
            # Bot é o primeiro a jogar - pode jogar qualquer carta
            # Exceto: na 1ª rodada, só o dealer pode jogar trunfo
            if is_first_round and not is_dealer:
                valid_cards = [c for c in self.cards if self.get_card_suit(c) != self.trump_suit]
                if not valid_cards:  # Se só tem trunfos, pode jogar
                    valid_cards = self.cards.copy()
            else:
                valid_cards = self.cards.copy()
        else:
            # Tem de seguir o naipe se tiver
            cards_of_suit = self.get_cards_of_suit(round_suit)
            if cards_of_suit:
                valid_cards = cards_of_suit
            else:
                # Não tem o naipe - pode jogar qualquer carta
                valid_cards = self.cards.copy()
        
        if not valid_cards:
            raise ValueError("Bot não tem cartas válidas para jogar!")
        
        # Estratégia simples: jogar a carta de menor valor
        # TODO: Implementar estratégia mais inteligente
        valid_cards.sort(key=lambda c: self.get_card_value(c))
        chosen = valid_cards[0]
        
        return chosen
    
    def play_card(self, card_id: int) -> int:
        """Remove a carta da mão e retorna o índice (1-10)"""
        if card_id not in self.cards:
            raise ValueError(f"Bot não tem a carta {card_id}")
        
        index = self.cards.index(card_id) + 1  # 1-indexed
        self.cards.remove(card_id)
        return index


# DTOs
class CreateBotRequest(BaseModel):
    player_id: int


class DealCardsRequest(BaseModel):
    cards: List[int]
    trump_suit: str


class PlayRequest(BaseModel):
    round_suit: Optional[str] = None
    cards_played: List[int] = []
    is_first_round: bool = False
    is_dealer: bool = False


class PlayResponse(BaseModel):
    card_id: int
    card_index: int
    card_name: str
    remaining_cards: int


class BotHandResponse(BaseModel):
    player_id: int
    cards: List[dict]
    trump_suit: Optional[str]


# Endpoints
@app.post("/bot/create/{player_id}")
def create_bot(player_id: int):
    """Cria um bot para a posição específica"""
    if player_id < 1 or player_id > 4:
        raise HTTPException(status_code=400, detail="Player ID deve ser entre 1 e 4")
    
    bots[player_id] = Bot(player_id)
    print(f"[BOT] Bot criado para jogador {player_id}")
    return {"success": True, "message": f"Bot criado para posição {player_id}"}


@app.post("/bot/{player_id}/deal")
def deal_cards(player_id: int, request: DealCardsRequest):
    """Distribui cartas ao bot"""
    if player_id not in bots:
        raise HTTPException(status_code=404, detail=f"Bot {player_id} não existe")
    
    bot = bots[player_id]
    bot.cards = request.cards.copy()
    bot.trump_suit = request.trump_suit
    
    cards_names = [bot.get_card_name(c) for c in bot.cards]
    print(f"[BOT] Jogador {player_id} recebeu cartas: {cards_names}")
    print(f"[BOT] Trunfo: {request.trump_suit}")
    
    return {
        "success": True,
        "message": f"Bot {player_id} recebeu {len(request.cards)} cartas",
        "cards": cards_names
    }


@app.post("/bot/{player_id}/play", response_model=PlayResponse)
def play_card(player_id: int, request: PlayRequest):
    """Bot escolhe e joga uma carta"""
    if player_id not in bots:
        raise HTTPException(status_code=404, detail=f"Bot {player_id} não existe")
    
    bot = bots[player_id]
    
    if not bot.cards:
        raise HTTPException(status_code=400, detail="Bot não tem cartas para jogar")
    
    # Escolher carta
    card_id = bot.choose_card(
        round_suit=request.round_suit,
        cards_played=request.cards_played,
        is_first_round=request.is_first_round,
        is_dealer=request.is_dealer
    )
    
    # Jogar carta (remove da mão)
    card_index = bot.play_card(card_id)
    card_name = bot.get_card_name(card_id)
    
    print(f"[BOT] Jogador {player_id} jogou carta {card_index}: {card_name}")
    
    return PlayResponse(
        card_id=card_id,
        card_index=card_index,
        card_name=card_name,
        remaining_cards=len(bot.cards)
    )


@app.get("/bot/{player_id}/hand", response_model=BotHandResponse)
def get_hand(player_id: int):
    """Ver cartas do bot (para debug)"""
    if player_id not in bots:
        raise HTTPException(status_code=404, detail=f"Bot {player_id} não existe")
    
    bot = bots[player_id]
    cards_info = []
    for i, card_id in enumerate(bot.cards):
        cards_info.append({
            "index": i + 1,
            "card_id": card_id,
            "name": bot.get_card_name(card_id)
        })
    
    return BotHandResponse(
        player_id=player_id,
        cards=cards_info,
        trump_suit=bot.trump_suit
    )


@app.delete("/bot/{player_id}")
def remove_bot(player_id: int):
    """Remove um bot"""
    if player_id in bots:
        del bots[player_id]
        return {"success": True, "message": f"Bot {player_id} removido"}
    return {"success": False, "message": f"Bot {player_id} não existe"}


@app.post("/bot/reset")
def reset_bots():
    """Remove todos os bots"""
    bots.clear()
    return {"success": True, "message": "Todos os bots removidos"}


@app.get("/health")
def health():
    return {"status": "ok", "bots_active": list(bots.keys())}
