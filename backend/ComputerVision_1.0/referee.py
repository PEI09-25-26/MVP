from card_mapper import CardMapper
from collections import deque
import random


SUITS = ["♣", "♦", "♥", "♠"]

class Referee:
    def __init__(self):
        self.card_queue = deque()
        self.players = {"player1":[True,True,True,True],
                        "player2":[True,True,True,True],
                        "player3":[True,True,True,True],
                        "player4":[True,True,True,True]
                        }
        self.trump_set = False
        self.current_player = 1
        self.trump=None
        self.trump_suit=None
        self.trump_was_played = False
        self.round_vector = []
        self.rounds_played = 0
        self.team1_points = 0
        self.team2_points = 0
        self.team1_victories = 0
        self.team2_victories = 0
        self.first_player=0

    
    def state(self):
        return {
            "trump_set": self.trump_set,
            "trump": CardMapper.get_card(self.trump) if self.trump else None,
            "trump_suit": self.trump_suit,
            "queue_size": len(self.card_queue),
            "rounds_played": self.rounds_played,
            "current_player": self.current_player,
            "team1_points": self.team1_points,
            "team2_points": self.team2_points,
            "team1_victories": self.team1_victories,
            "team2_victories": self.team2_victories,
            "new_game": self.rounds_played == 0
        }

    def receive_card(self):
        if not self.card_queue:
            raise RuntimeError("No card available")
        return self.card_queue.popleft()

    def inject_card(self, card_id: int):
        self.card_queue.append(card_id)

    def set_trump(self):
        self.trump = self.receive_card()
        self.trump_suit = CardMapper.get_card_suit(self.trump)
        self.trump_set = True
        print(f"Trump set to {CardMapper.get_card(self.trump)}")

    def play_round(self):
        self.rounds_played += 1
        for i in range(4):
            card_number = self.receive_card()
            self.round_vector.append(card_number)

            if card_number == self.trump:
                self.trump_was_played = True
                print("[DEBUG] Trump was played this round!")

            card_suit = CardMapper.get_card_suit(card_number)
            card_suit_index = SUITS.index(card_suit)
            this_player = self.current_player + i
            this_player = ((this_player - 1) % 4) + 1
            player = f"player{this_player}"

            if i == 0:
                round_suit = card_suit
                round_suit_index = SUITS.index(round_suit)
            else:
                if not self.players[player][card_suit_index]:
                    print("[RENUNCIA] AN ILLEGAL PLAY HAS BEEN MADE!!")
                    if this_player % 2 != 0:
                        self.team1_victories += 4
                    else:
                        self.team2_victories += 4
                    self.reset_players()
                    return False
                if card_suit != round_suit:
                    self.players[player][round_suit_index] = False
                    if (self.first_player + 3) % 4 == 0:
                        last = 4
                    else:
                        last = (self.first_player + 3) % 4

                    if not self.trump_was_played and card_suit == self.trump_suit and this_player==last:
                        print("[RENUNCIA] AN ILLEGAL PLAY HAS BEEN MADE!!")
                        if this_player % 2 != 0:
                            self.team1_victories += 4
                        else:
                            self.team2_victories += 4
                        self.reset_players()
                        return False

        winner = self.determine_round_winner(round_suit)
        self.get_round_sum(winner)

        self.current_player = winner+1

        self.reset_round()
        return True

    def reset_players(self):
        self.players = {"player1":[True,True,True,True],
                        "player2":[True,True,True,True],
                        "player3":[True,True,True,True],
                        "player4":[True,True,True,True]
                        }
        self.round_vector = []
        self.trump_was_played = False
        self.trump=None
        self.trump_suit=None
        self.trump_set=False
        self.rounds_played = 0
        self.card_queue.clear()
        if self.first_player == 4:
            self.first_player = 0
        else:
            self.first_player += 1
        self.current_player = self.first_player +1
        print("[DEBUG] PLAYERS RESET")

    def reset_round(self):
        self.round_vector = []
        self.trump_was_played = False
        if self.rounds_played == 10:
            self.get_game_winner()
        
    def get_trump(self):
        self.trump = self.receive_card()
        self.trump_suit = CardMapper.get_card_suit(self.trump)

    def determine_round_winner(self, suit):
        round_trumps = [c for c in self.round_vector if CardMapper.get_card_suit(c) == self.trump_suit]
        if round_trumps:
            winner = max(round_trumps)
            winner_index = self.round_vector.index(winner)
            return winner_index

        winner = max(c for c in self.round_vector if CardMapper.get_card_suit(c) == suit)
        winner_index = self.round_vector.index(winner)
        return winner_index

    def get_round_sum(self, winner):
        """Returns the sum of the cards that were played this round. """
        round_sum = sum((CardMapper.get_card_points(card_number)) for card_number in self.round_vector)
        print(self.round_vector)
        if winner%2 == 0:
            self.team1_points += round_sum
        else:
            self.team2_points += round_sum
        print(f"Round winner: Player {winner+1} | Round points: {round_sum}\n")

    def get_game_winner(self):
        if self.team1_points > self.team2_points:
            if self.team2_points >= 30:
                self.team1_victories += 1
                print("Team 1 wins the game!")
            elif self.team2_points > 0:
                self.team1_victories += 2
                print("Team 1 wins the game and team 2 didn't make 30 points (Team 1 +2 victories)!")
            else:
                self.team1_victories += 4
                print("Team 1 wins the game and team 2 made no points (Team 1 +4 victories)!")
        elif self.team2_points > self.team1_points:
            if self.team1_points >= 30:
                self.team2_victories += 1
                print("Team 2 wins the game!")
            elif self.team1_points > 0:
                self.team2_victories += 2
                print("Team 2 wins the game and team 1 didn't make 30 points (Team 2 +2 victories)!")
            else:
                self.team2_victories += 4
                print("Team 2 wins the game and team 1 made no points (Team 2 +4 victories)!")
        self.reset_players()
