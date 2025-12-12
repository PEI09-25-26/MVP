package com.example.MVP

import android.os.Bundle
import android.widget.GridLayout
import android.widget.ImageView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.example.MVP.models.Card
import com.example.MVP.network.RetrofitClient
import com.example.MVP.models.PlayCardRequest
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class GameActivity : AppCompatActivity() {

    private lateinit var roomId: String
    private lateinit var playerId: String

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_game_mvp)

        roomId = intent.getStringExtra("roomId") ?: ""
        playerId = intent.getStringExtra("playerId") ?: ""

        findViewById<ImageView>(R.id.backButton).setOnClickListener { finish() }

        startPolling()
    }

    private fun startPolling() {
        lifecycleScope.launch {
            while (true) {
                try {
                    val state = RetrofitClient.api.getRoomState(roomId)
                    renderState(state.gameState)
                } catch (e: Exception) {
                    e.printStackTrace()
                }
                delay(900)
            }
        }
    }

    private fun renderState(gameState: com.example.MVP.models.GameState?) {
        val grid = findViewById<GridLayout>(R.id.playerHand)
        grid.removeAllViews()
        if (gameState == null) return

        val hand = gameState.hands[playerId] ?: emptyList()
        for (card in hand) {
            val iv = ImageView(this)
            val size = resources.getDimensionPixelSize(R.dimen.card_size)
            val lp = GridLayout.LayoutParams()
            lp.width = size
            lp.height = size
            lp.setMargins(8,8,8,8)
            iv.layoutParams = lp
            iv.setImageResource(R.drawable.card_back) // temporário: trocar por imagens reais/content loader
            iv.setOnClickListener {
                playCard(card)
            }
            grid.addView(iv)
        }
    }

    private fun playCard(card: Card) {
        lifecycleScope.launch {
            try {
                val resp = RetrofitClient.api.playCard(PlayCardRequest(playerId, roomId, card))
                if (!resp.success) Toast.makeText(this@GameActivity, "Erro: ${resp.message}", Toast.LENGTH_SHORT).show()
            } catch (e: Exception) {
                Toast.makeText(this@GameActivity, "Erro: ${e.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }
}
