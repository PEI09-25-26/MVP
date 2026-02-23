package com.example.MVP

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.example.MVP.models.Player
import com.example.MVP.models.RoomState
import com.example.MVP.network.RetrofitClient
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class RoomActivity : AppCompatActivity() {

    private var pollingJob: Job? = null
    private lateinit var roomId: String
    private lateinit var playerId: String

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_room_mvp)

        roomId = intent.getStringExtra("roomId") ?: "SALA_LOCAL"
        playerId = intent.getStringExtra("playerId") ?: "ID_LOCAL"

        val txtRoom = findViewById<TextView>(R.id.txtRoom)
        val recycler = findViewById<RecyclerView>(R.id.recyclerPlayers)
        val btnStart = findViewById<Button>(R.id.btnStart)
        val btnBack = findViewById<ImageView>(R.id.backButton)

        txtRoom.text = "Sala: $roomId"
        recycler.layoutManager = LinearLayoutManager(this)

        btnBack.setOnClickListener { finish() }

        if (roomId == "SALA_LOCAL") {
            // Modo Mock: Adicionar jogadores fictícios
            val dummyPlayers = listOf(
                Player("ID_LOCAL", "Tu (Local)"),
                Player("2", "Parceiro Bot"),
                Player("3", "Adversário 1"),
                Player("4", "Adversário 2")
            )
            recycler.adapter = PlayersAdapter(dummyPlayers)
            btnStart.text = "Começar (Mock)"
        }

        btnStart.setOnClickListener {
            if (roomId == "SALA_LOCAL") {
                goToGameMock()
            } else {
                lifecycleScope.launch {
                    try {
                        val state = RetrofitClient.api.getRoomState(roomId)
                        if (state.gameStarted) {
                            goToGame(state)
                        } else {
                            Toast.makeText(this@RoomActivity, "Aguardando jogadores...", Toast.LENGTH_SHORT).show()
                        }
                    } catch (e: Exception) {
                        Toast.makeText(this@RoomActivity, "Servidor offline. Iniciando modo Mock...", Toast.LENGTH_SHORT).show()
                        goToGameMock()
                    }
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        if (roomId != "SALA_LOCAL") {
            startPolling()
        }
    }

    override fun onPause() {
        super.onPause()
        pollingJob?.cancel()
    }

    private fun startPolling() {
        pollingJob = lifecycleScope.launch {
            while (true) {
                try {
                    val state = RetrofitClient.api.getRoomState(roomId)
                    updateUI(state)
                    if (state.gameStarted && state.gameState != null) {
                        goToGame(state)
                        break
                    }
                } catch (e: Exception) {
                    e.printStackTrace()
                }
                delay(1000)
            }
        }
    }

    private fun updateUI(state: RoomState) {
        val recycler = findViewById<RecyclerView>(R.id.recyclerPlayers)
        recycler.adapter = PlayersAdapter(state.players)
    }

    private fun goToGame(state: RoomState) {
        val intent = Intent(this, GameActivity::class.java)
        intent.putExtra("roomId", state.roomId)
        intent.putExtra("playerId", playerId)
        startActivity(intent)
        finish()
    }

    private fun goToGameMock() {
        val intent = Intent(this, GameActivity::class.java)
        intent.putExtra("roomId", "SALA_LOCAL")
        intent.putExtra("playerId", "ID_LOCAL")
        startActivity(intent)
        finish()
    }
}