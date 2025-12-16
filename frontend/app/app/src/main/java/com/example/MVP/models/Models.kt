package com.example.MVP.models

data class JoinRoomRequest(val playerName: String, val roomId: String)
data class JoinRoomResponse(val success: Boolean, val playerId: String, val roomId: String)

data class PlayCardRequest(val playerId: String, val roomId: String, val card: Card)
data class ActionResponse(val success: Boolean, val message: String?)

data class Card(
    val id: String,
    val suit: String,
    val value: String,
    val imageUrl: String? = null
)

data class Player(val id: String, val name: String)

data class RoomState(
    val roomId: String,
    val players: List<Player>,
    val gameStarted: Boolean,
    val gameState: GameState? = null
)

data class GameState(
    val currentPlayerId: String,
    val hands: Map<String, List<Card>>, // playerId -> hand
    val table: List<Card>, // cards on table in current trick
    val scores: Map<String, Int>
)

data class CreateRoomRequest(val playerName: String)
data class CreateRoomResponse(val success: Boolean, val playerId: String, val roomId: String)

data class StartGameRequest(val playerName: String, val roomId: String?)
data class StartGameResponse(val success: Boolean, val message: String, val gameId: String)

// Bot models
data class BotResponse(val success: Boolean, val message: String? = null)
data class BotsListResponse(val bots: List<Int>)
data class BotRecognitionRequest(val bots: List<Int>)
data class BotPlayResponse(
    val success: Boolean,
    val card_id: Int? = null,
    val card_name: String? = null,
    val card_index: Int? = null,
    val player_id: Int? = null,
    val message: String? = null
)