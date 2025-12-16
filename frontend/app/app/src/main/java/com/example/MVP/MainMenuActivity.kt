package com.example.MVP

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.example.MVP.models.CreateRoomRequest
import com.example.MVP.models.StartGameRequest
import com.example.MVP.network.RetrofitClient
import com.example.MVP.models.JoinRoomRequest
import kotlinx.coroutines.launch

class MainMenuActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main_menu_mvp)

        val inputName = findViewById<EditText>(R.id.inputName)
        val inputRoom = findViewById<EditText>(R.id.inputRoom)
        val btnJoin = findViewById<Button>(R.id.btnJoin)
        val btnVision = findViewById<Button>(R.id.btnVision)

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
    }
}
