from card_mapper import CardMapper
import random


SUITS = ["♣", "♦", "♥", "♠"]

class Referee:
    def __init__(self):
        self.players = {"player1":[True,True,True,True],
                        "player2":[True,True,True,True],
                        "player3":[True,True,True,True],
                        "player4":[True,True,True,True]
                        }
        self.trump=None
        self.trump_suit=None
        self.trump_was_played = False
        self.round_vector = []
        self.team1_points = 0
        self.team2_points = 0
        self.team1_victories = 0
        self.team2_victories = 0
                
    def receive_card(self):
        card = input("card:")
        return card

    def round(self, first_player):
        for _ in range(10):
            if _==0:
                self.get_trump()
            for i in range(4):
                card_number = self.receive_card()
                self.round_vector.append(card_number)
                if card_number == self.trump:
                    self.trump_was_played = True
                card_suit = CardMapper.get_card_suit(card_number)
                this_player = i + first_player
                if this_player%4 != 0:
                    this_player = this_player%4
                else :
                    this_player = 4
                player = str("player"+str(this_player))
                card_suit_index = SUITS.index(card_suit)
                if self.players.get(player)[card_suit_index]== False:
                    print("RENUNCIA -> A equipa adversária vence 4 jogos!\n")
                    if this_player%2 ==0:
                        self.team1_victories +=4
                    else:
                        self.team2_victories +=4
                    return False
                if i == 0:
                    round_suit = card_suit
                    print(player, card_suit, round_suit, "\n")
                    round_suit_index = SUITS.index(round_suit)
                elif 0<i<3: 
                    print(player, card_suit, round_suit, "\n")
                    if card_suit != round_suit:
                        print("Já não tenho\n")
                        self.players[player][round_suit_index]=False
                else:
                    print(player, card_suit, round_suit, "\n")
                    if card_suit != round_suit:
                        if round_suit == self.trump_suit:
                            if self.trump_was_played == False:
                                print("RENUNCIA -> A equipa adversária vence 4 jogos!\n")
                                if this_player%2 ==0:
                                    self.team1_victories +=4
                                else:
                                    self.team2_victories +=4
                                return False
                        print("Já não tenho\n")
                        self.players[player][round_suit_index]=False
            winner = self.determine_round_winner(round_suit)
            self.get_round_sum(winner)
            self.reset_round()
            first_player = winner + first_player
            if first_player%4!=0:
                first_player = first_player%4
            else:
                first_player = 4
        self.get_game_winner()
        return True
    
    def game(self):
        while True:
            for i in range(4):
                first_player = i+1
                self.reset_players()
                self.round(first_player)
                print(f"Score: Team 1 - {self.team1_victories} | Team 2 - {self.team2_victories}\n")



    def reset_players(self):
        self.players = {"player1":[True,True,True,True],
                        "player2":[True,True,True,True],
                        "player3":[True,True,True,True],
                        "player4":[True,True,True,True]
                        }
        self.trump_was_played = False
        self.trump=None
        self.trump_suit=None
        self.team1_points = 0
        self.team2_points = 0

    def reset_round(self):
        self.round_vector = []
        
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


r = Referee()
r.game()