package com.example.MVP

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.example.MVP.models.CreateRoomRequest
import com.example.MVP.models.StartGameRequest
import com.example.MVP.network.RetrofitClient
import com.example.MVP.models.JoinRoomRequest
import kotlinx.coroutines.launch

class MainMenuActivity : AppCompatActivity() {

    private var selectedBotPosition: Int? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main_menu_mvp)

        val inputName = findViewById<EditText>(R.id.inputName)
        val inputRoom = findViewById<EditText>(R.id.inputRoom)
        val btnJoin = findViewById<Button>(R.id.btnJoin)
        val btnVision = findViewById<Button>(R.id.btnVision)
        val btnAddBot = findViewById<Button>(R.id.btnAddBot)
        val txtBotStatus = findViewById<TextView>(R.id.txtBotStatus)

        btnJoin.setOnClickListener {
            val name = inputName.text.toString().ifBlank { "Player${(1000..9999).random()}" }
            val roomId = inputRoom.text.toString().ifBlank { null }

            lifecycleScope.launch {
                try {
                    if (roomId != null){
                        val resp = RetrofitClient.api.joinRoom(JoinRoomRequest(name, roomId))
                        if (resp.success) {
                            val intent = Intent(this@MainMenuActivity, RoomActivity::class.java)
                            intent.putExtra("roomId", resp.roomId)
                            intent.putExtra("playerId", resp.playerId)
                            startActivity(intent)
                        } else {
                            Toast.makeText(
                                this@MainMenuActivity,
                                "Erro a entrar: ${resp}",
                                Toast.LENGTH_LONG
                            ).show()
                        }
                    } else {
                        val resp = RetrofitClient.api.createRoom(CreateRoomRequest(name))
                        if (resp.success) {
                            val intent = Intent(this@MainMenuActivity, RoomActivity::class.java)
                            intent.putExtra("roomId", resp.roomId)
                            intent.putExtra("playerId", resp.playerId)
                            startActivity(intent)
                        } else {
                            Toast.makeText(
                                this@MainMenuActivity,
                                "Erro a entrar: ${resp}",
                                Toast.LENGTH_LONG
                            ).show()
                        }
                    }
                } catch (e: Exception) {
                    e.printStackTrace()
                    Toast.makeText(this@MainMenuActivity, "Erro de rede: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }

        btnVision.setOnClickListener {
            val name = inputName.text.toString().ifBlank { "Player${(1000..9999).random()}" }
            val roomId = inputRoom.text.toString().ifBlank { null }

            lifecycleScope.launch {
                try {
                    // Call middleware to start the game with CV
                    val response = RetrofitClient.api.startGame(
                        StartGameRequest(playerName = name, roomId = roomId)
                    )
                    
                    if (response.success) {
                        Toast.makeText(
                            this@MainMenuActivity,
                            "Vision AI Started!",
                            Toast.LENGTH_SHORT
                        ).show()
                        
                        // Open VisionActivity
                        val intent = Intent(this@MainMenuActivity, VisionActivity::class.java)
                        intent.putExtra("playerName", name)
                        intent.putExtra("roomId", response.gameId)
                        startActivity(intent)
                    } else {
                        Toast.makeText(
                            this@MainMenuActivity,
                            "Failed to start: ${response.message}",
                            Toast.LENGTH_LONG
                        ).show()
                    }
                } catch (e: retrofit2.HttpException) {
                    e.printStackTrace()
                    Toast.makeText(
                        this@MainMenuActivity,
                        "Erro HTTP: ${e.code()} - ${e.message()}",
                        Toast.LENGTH_LONG
                    ).show()
                } catch (e: java.net.ConnectException) {
                    e.printStackTrace()
                    Toast.makeText(
                        this@MainMenuActivity,
                        "Não foi possível conectar ao servidor. Verifique se o middleware está a correr.",
                        Toast.LENGTH_LONG
                    ).show()
                } catch (e: Exception) {
                    e.printStackTrace()
                    Toast.makeText(
                        this@MainMenuActivity,
                        "Erro: ${e.javaClass.simpleName} - ${e.message}",
                        Toast.LENGTH_LONG
                    ).show()
                }
            }
        }

        // Bot button logic
        btnAddBot.setOnClickListener {
            showBotPositionDialog(txtBotStatus)
        }
    }

    private fun showBotPositionDialog(txtBotStatus: TextView) {
        val positions = arrayOf("Jogador 2", "Jogador 3", "Jogador 4")
        val positionIds = arrayOf(2, 3, 4)
        
        AlertDialog.Builder(this)
            .setTitle("🤖 Escolher posição do Bot")
            .setItems(positions) { _, which ->
                val playerId = positionIds[which]
                addBot(playerId, txtBotStatus)
            }
            .setNegativeButton("Cancelar", null)
            .show()
    }

    private fun addBot(playerId: Int, txtBotStatus: TextView) {
        lifecycleScope.launch {
            try {
                val response = RetrofitClient.api.addBot(playerId)
                if (response.success) {
                    selectedBotPosition = playerId
                    txtBotStatus.text = "🤖 Bot ativo: Jogador $playerId"
                    Toast.makeText(
                        this@MainMenuActivity,
                        "Bot adicionado na posição $playerId",
                        Toast.LENGTH_SHORT
                    ).show()
                } else {
                    Toast.makeText(
                        this@MainMenuActivity,
                        "Erro: ${response.message}",
                        Toast.LENGTH_LONG
                    ).show()
                }
            } catch (e: Exception) {
                e.printStackTrace()
                Toast.makeText(
                    this@MainMenuActivity,
                    "Erro ao adicionar bot: ${e.message}",
                    Toast.LENGTH_LONG
                ).show()
            }
        }
    }
}
