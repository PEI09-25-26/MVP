class CardMapper:
    """This class is responsible for mapping the cards id (0-39) to it's corresponding suit and rank. """
    SUITS = ["♣", "♦", "♥", "♠"]
    RANKS = ["2", "3", "4", "5", "6", "Q", "J", "K", "7", "A"]
    SUITSIZE = 10
    RANK_VALUES = {
        "2": 0,
        "3": 0,
        "4": 0,
        "5": 0,
        "6": 0,
        "Q": 2,
        "J": 3,
        "K": 4,
        "7": 10,
        "A": 11,
    }

    @staticmethod
    def get_card_suit(card_id):
        """Returns a card's suit, given it's id. """
        suit_index = int(card_id) // CardMapper.SUITSIZE
        return CardMapper.SUITS[suit_index]

    @staticmethod
    def get_card_rank(card_id):
        """Returns a card's rank, given it's id. """
        rank_index = int(card_id) % CardMapper.SUITSIZE
        return CardMapper.RANKS[rank_index]

    @staticmethod
    def get_card(card_id):
        """Returns a formatted card in a string, given it's id. """
        return f"{CardMapper.get_card_rank(card_id)}{CardMapper.get_card_suit(card_id)}"

    @staticmethod
    def get_card_points(card_id):
        """Returns a card's value, given it's id. """
        rank = CardMapper.get_card_rank(card_id)
        return CardMapper.RANK_VALUES[rank]
