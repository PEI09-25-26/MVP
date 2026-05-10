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

    @POST("game/confirm_trick_clear/{gameId}")
    suspend fun confirmTrickClear(@Path("gameId") gameId: String): ActionResponse

    //get de arbitragem
}
