from card_mapper import CardMapper

class Referee:
    def __init__(self):
        self.trump_card = None
        self.cards_played = []

    def get_lead_suit(self):
        if not self.cards_played:
            return None
        return CardMapper.get_card_suit(self.cards_played[0])

    def assure_card_can_be_played(self, card):
        card_suit = CardMapper.get_card_suit(card)
        lead_suit = self.get_lead_suit()
        trump_suit = CardMapper.get_card_suit(self.trump_card)

        if lead_suit is None or card_suit == lead_suit or card_suit == trump_suit:
            self.cards_played.append(card)
            return True

        return False

    def run(self):
        self.trump_card = int(input("Enter the trump card: "))
        print(f"Trump card set to: {self.trump_card}\n")

        for i in range(4):
            card = int(input(f"Enter card {i + 1}: "))
            if self.assure_card_can_be_played(card):
                print(f"Card {card} accepted.\n")
            else:
                print(f"Card {card} is invalid! Exiting.")
                return False

        print("All cards played successfully!")
        return True


if __name__ == "__main__":
    referee = Referee()
    result = referee.run()
    print("Result:", result)
