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