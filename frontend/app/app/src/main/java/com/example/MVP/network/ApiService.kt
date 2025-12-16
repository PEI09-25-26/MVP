package com.example.MVP.network

import com.example.MVP.models.*
import retrofit2.http.*

interface ApiService {
    @POST("joinRoom")
    suspend fun joinRoom(@Body body: JoinRoomRequest): JoinRoomResponse

    @GET("room/{id}/state")
    suspend fun getRoomState(@Path("id") roomId: String): RoomState

    @POST("playCard")
    suspend fun playCard(@Body body: PlayCardRequest): ActionResponse

    @POST("createRoom")
    suspend fun createRoom(@Body body: CreateRoomRequest): CreateRoomResponse

    //post de visão de camara
    @POST("playCardVision")
    suspend fun playCardVision(
        @Body imageBase64: String
    ): List<Card>
    
    @POST("game/start")
    suspend fun startGame(@Body body: StartGameRequest): StartGameResponse
    
    @POST("game/ready/{gameId}")
    suspend fun startGameReady(@Path("gameId") gameId: String): StartGameResponse
    
    @POST("game/new_round/{gameId}")
    suspend fun startNewRound(@Path("gameId") gameId: String): StartGameResponse

    // Bot endpoints
    @POST("game/add_bot/{playerId}")
    suspend fun addBot(@Path("playerId") playerId: Int): BotResponse
    
    @DELETE("game/remove_bot/{playerId}")
    suspend fun removeBot(@Path("playerId") playerId: Int): BotResponse
    
    @GET("game/bots")
    suspend fun getBots(): BotsListResponse
    
    @POST("game/deal_bot_cards")
    suspend fun dealBotCards(): BotResponse
    
    @POST("game/bot_recognition_start")
    suspend fun startBotRecognition(@Body request: BotRecognitionRequest): BotResponse
    
    @POST("game/bot_play/{playerId}")
    suspend fun requestBotPlay(
        @Path("playerId") playerId: Int,
        @Query("round_suit") roundSuit: String? = null
    ): BotPlayResponse

    //get de arbitragem
}
