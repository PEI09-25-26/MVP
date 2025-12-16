package com.example.MVP

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.appcompat.app.AppCompatActivity
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.LinearLayout
import android.widget.TextView
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch
import android.util.Base64
import android.util.Log
import android.widget.ImageView
import android.widget.Toast
import android.widget.Button
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import okhttp3.*
import com.example.MVP.network.RetrofitClient
import com.example.MVP.models.BotRecognitionRequest
import java.io.ByteArrayOutputStream
import java.util.concurrent.Executors
import androidx.appcompat.app.AlertDialog
import org.json.JSONObject

class VisionActivity : AppCompatActivity() {

    private val executor = Executors.newSingleThreadExecutor()
    private lateinit var webSocket: WebSocket

    private val wsUrl = "ws://10.56.5.35:8000/ws/camera/"  // IP do Mac na rede local
    // For emulator use: "ws://10.0.2.2:8000/ws/camera/"

    private var gameId: String = "default"

    // Views for the cards on the table
    private lateinit var cardNorth: ImageView
    private lateinit var cardWest: ImageView
    private lateinit var cardEast: ImageView
    private lateinit var cardSouth: ImageView
    private lateinit var trumpCard: ImageView

    // Bot cards views
    private lateinit var botCardsSection: LinearLayout
    private lateinit var txtBotStatus: TextView
    private lateinit var botCardViews: Array<ImageView>
    private lateinit var btnShowBotCards: Button
    private var hasBots: Boolean = false
    private var activeBotIds: List<Int> = emptyList()

    // Handler for delayed card reset
    private val handler = Handler(Looper.getMainLooper())
    private var resetRunnable: Runnable? = null
    private var lastWebSocketMessage: String? = null


    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        try {
            setContentView(R.layout.activity_vision_game)

            val btnBack = findViewById<ImageView>(R.id.backButton)
            val btnStartGame = findViewById<Button>(R.id.btnStartGame)
            btnShowBotCards = findViewById(R.id.btnShowBotCards)

            btnBack.setOnClickListener { finish() }
            
            btnShowBotCards.setOnClickListener {
                // Iniciar reconhecimento de cartas do bot
                lifecycleScope.launch {
                    try {
                        val request = BotRecognitionRequest(bots = activeBotIds)
                        val response = RetrofitClient.api.startBotRecognition(request)
                        if (response.success) {
                            btnShowBotCards.visibility = View.GONE
                            Toast.makeText(this@VisionActivity, "🔍 Mostre as 10 cartas ao bot uma a uma", Toast.LENGTH_LONG).show()
                        }
                    } catch (e: Exception) {
                        Log.e("VisionActivity", "Error starting bot recognition", e)
                        Toast.makeText(this@VisionActivity, "Erro: ${e.message}", Toast.LENGTH_SHORT).show()
                    }
                }
            }
            
            btnStartGame.setOnClickListener {
                lifecycleScope.launch {
                    try {
                        val response = RetrofitClient.api.startGameReady(gameId)
                        if (response.success) {
                            Toast.makeText(this@VisionActivity, "✅ Jogo iniciado! Coloque as cartas", Toast.LENGTH_LONG).show()
                            btnStartGame.isEnabled = false
                            btnStartGame.text = "Jogo em curso..."
                        } else {
                            Toast.makeText(this@VisionActivity, "Erro: ${response.message}", Toast.LENGTH_LONG).show()
                        }
                    } catch (e: Exception) {
                        Log.e("VisionActivity", "Error starting game", e)
                        Toast.makeText(this@VisionActivity, "Erro: ${e.message}", Toast.LENGTH_LONG).show()
                    }
                }
            }

            // Get game info from intent
            val playerName = intent.getStringExtra("playerName") ?: "Player"
            val roomId = intent.getStringExtra("roomId")
            gameId = roomId ?: "default"
            
            Log.d("VisionActivity", "Starting with gameId: $gameId, playerName: $playerName")

            // Initialize the card ImageViews
            cardNorth = findViewById(R.id.card_north)
            cardWest = findViewById(R.id.card_west)
            cardEast = findViewById(R.id.card_east)
            cardSouth = findViewById(R.id.card_south)
            trumpCard = findViewById(R.id.trump_card)

            // Initialize bot cards section
            botCardsSection = findViewById(R.id.botCardsSection)
            txtBotStatus = findViewById(R.id.txtBotStatus)
            botCardViews = arrayOf(
                findViewById(R.id.botCard1),
                findViewById(R.id.botCard2),
                findViewById(R.id.botCard3),
                findViewById(R.id.botCard4),
                findViewById(R.id.botCard5),
                findViewById(R.id.botCard6),
                findViewById(R.id.botCard7),
                findViewById(R.id.botCard8),
                findViewById(R.id.botCard9),
                findViewById(R.id.botCard10)
            )

            // Check if there are bots
            checkForBots()

            // Hardcoded card display for testing purposes
            testCardDisplay()

            if (allPermissionsGranted()) {
                startCamera()
                // Delay WebSocket connection to ensure everything is initialized
                Handler(Looper.getMainLooper()).postDelayed({
                    connectWebSocket()
                }, 500)
            } else {
                ActivityCompat.requestPermissions(
                    this,
                    arrayOf(Manifest.permission.CAMERA),
                    10
                )
            }
        } catch (e: Exception) {
            Log.e("VisionActivity", "Fatal error in onCreate", e)
            Toast.makeText(this, "Erro ao iniciar: ${e.message}", Toast.LENGTH_LONG).show()
            finish()
        }
    }

    // ------------------ CAMERA X ---------------------
    private fun startCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(this)

        cameraProviderFuture.addListener({
            val cameraProvider = cameraProviderFuture.get()

            val preview = Preview.Builder().build().also {
                it.setSurfaceProvider(findViewById<PreviewView>(R.id.previewView).surfaceProvider)
            }

            val imageAnalyzer = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()

            imageAnalyzer.setAnalyzer(executor) { imageProxy ->
                sendFrameToBackend(imageProxy)
                imageProxy.close()
            }

            val cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA

            try {
                cameraProvider.unbindAll()
                cameraProvider.bindToLifecycle(
                    this,
                    cameraSelector,
                    preview,
                    imageAnalyzer
                )
            } catch (e: Exception) {
                Log.e("VisionActivity", "Use case binding failed", e)
            }
        }, ContextCompat.getMainExecutor(this))
    }

    // ------- CONVERTER FRAME -> JPEG -> BASE64 -------
    private fun sendFrameToBackend(imageProxy: ImageProxy) {
        val bitmap = imageProxy.toBitmap() ?: return

        val output = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.JPEG, 70, output)
        val base64 = Base64.encodeToString(output.toByteArray(), Base64.NO_WRAP)

        // Send frame via WebSocket to middleware
        if (::webSocket.isInitialized) {
            try {
                webSocket.send(base64)
                // Log less frequently to avoid spam
                if (System.currentTimeMillis() % 1000 < 100) {
                    Log.d("VisionActivity", "Frame sent via WebSocket")
                }
            } catch (e: Exception) {
                Log.e("VisionActivity", "Error sending frame: ${e.message}")
            }
        }
    }

    // ------- EXTENSÃO PARA CONVERTER IMAGEPROXY -------
    private fun ImageProxy.toBitmap(): Bitmap? {
        val planeProxy = planes.firstOrNull() ?: return null
        val buffer = planeProxy.buffer
        val bytes = ByteArray(buffer.remaining())
        buffer.get(bytes)
        return BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
    }

    /**
     * Updates an ImageView with the corresponding card drawable.
     *
     * @param cardIdentifier The string identifier for the card (e.g., "spades_ace").
     *                       Assumes card drawables are named like "spades_ace".
     * @param imageView The ImageView to update.
     */
    private fun updateCardView(cardIdentifier: String, imageView: ImageView) {
        val resourceId = resources.getIdentifier(cardIdentifier, "drawable", packageName)
        if (resourceId != 0) {
            imageView.setImageResource(resourceId)
        } else {
            // Set a default "card back" image if the identifier is not found
            Log.w("VisionActivity", "Card drawable not found for identifier: $cardIdentifier. Using card_back.")
            imageView.setImageResource(R.drawable.card_back)
        }
    }

    /**
     * Resets the four player cards to their back.
     */
    private fun resetCardsToBack() {
        Log.d("VisionActivity", "Resetting cards to back.")
        cardNorth.setImageResource(R.drawable.card_back)
        cardWest.setImageResource(R.drawable.card_back)
        cardEast.setImageResource(R.drawable.card_back)
        cardSouth.setImageResource(R.drawable.card_back)
    }

    /**
     * Starts a 5-second timer to reset the cards.
     */
    private fun startResetTimer() {
        cancelResetTimer() // Ensure no previous timer is running
        resetRunnable = Runnable { resetCardsToBack() }
        resetRunnable?.let {
            handler.postDelayed(it, 5000) // 5 seconds delay
            Log.d("VisionActivity", "Reset timer started.")
        }
    }

    /**
     * Cancels the currently active reset timer.
     */
    private fun cancelResetTimer() {
        resetRunnable?.let {
            handler.removeCallbacks(it)
            Log.d("VisionActivity", "Reset timer cancelled.")
        }
        resetRunnable = null
    }


    /**
     * Test function to display hardcoded cards.
     */
    private fun testCardDisplay() {
        updateCardView("clubs_2", cardNorth)
        updateCardView("diamonds_king", cardWest)
        updateCardView("hearts_7", cardEast)
        updateCardView("spades_queen", cardSouth)
        updateCardView("spades_ace", trumpCard)

        // Start the 5-second timer to reset the cards
        startResetTimer()
    }

    // ------------------ WEBSOCKET ---------------------
    private fun connectWebSocket() {
        val client = OkHttpClient()

        val request = Request.Builder()
            .url(wsUrl + gameId)
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(ws: WebSocket, response: Response) {
                Log.d("WS", "WebSocket connected to ${wsUrl + gameId}")
                runOnUiThread {
                    Toast.makeText(this@VisionActivity, "Vision AI Connected", Toast.LENGTH_SHORT).show()
                }
            }

            override fun onMessage(ws: WebSocket, text: String) {
                Log.d("WS", "Response: $text")
                runOnUiThread {
                    // Tentar parsear como JSON para detectar mensagens especiais
                    try {
                        val json = JSONObject(text)
                        when (json.optString("type")) {
                            "round_end" -> {
                                handleRoundEnd(json)
                                return@runOnUiThread
                            }
                            "bot_added" -> {
                                val playerId = json.getInt("player_id")
                                Toast.makeText(this@VisionActivity, "🤖 Bot adicionado: Jogador $playerId", Toast.LENGTH_SHORT).show()
                                hasBots = true
                                botCardsSection.visibility = View.VISIBLE
                                return@runOnUiThread
                            }
                            "bot_cards_dealt" -> {
                                // Guardar IDs dos bots e mostrar botão para iniciar reconhecimento
                                val botsData = json.getJSONObject("bots")
                                val botsList = mutableListOf<Int>()
                                val keys = botsData.keys()
                                while (keys.hasNext()) {
                                    botsList.add(keys.next().toInt())
                                }
                                activeBotIds = botsList
                                
                                txtBotStatus.text = "🃏 Trunfo definido! Retire a carta e clique no botão abaixo"
                                btnShowBotCards.visibility = View.VISIBLE
                                botCardsSection.visibility = View.VISIBLE
                                
                                Toast.makeText(
                                    this@VisionActivity,
                                    "🃏 Retire o trunfo da câmara e clique '🤖 Mostrar cartas ao bot'",
                                    Toast.LENGTH_LONG
                                ).show()
                                return@runOnUiThread
                            }
                            "bot_played" -> {
                                val playerId = json.getInt("player_id")
                                val cardName = json.getString("card_name")
                                val cardIndex = json.getInt("card_index")
                                handleBotPlayed(playerId, cardName, cardIndex)
                                return@runOnUiThread
                            }
                            "bot_recognition_start" -> {
                                handleBotRecognitionStart()
                                return@runOnUiThread
                            }
                            "bot_card_recognized" -> {
                                val cardNumber = json.getInt("card_number")
                                val cardId = json.getString("card_id")
                                handleBotCardRecognized(cardNumber, cardId)
                                return@runOnUiThread
                            }
                        }
                    } catch (e: Exception) {
                        // Não é JSON, tratar como mensagem de carta normal
                    }
                    
                    if (text != lastWebSocketMessage) {
                        // When a new card arrives, cancel the timer and reset the board
                        cancelResetTimer()
                        resetCardsToBack()
                    }
                    lastWebSocketMessage = text

                    Toast.makeText(this@VisionActivity, "Card: $text", Toast.LENGTH_SHORT).show()
                }
            }

            override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                Log.e("WS", "WebSocket error", t)
                runOnUiThread {
                    Toast.makeText(this@VisionActivity, "Connection error: ${t.message}", Toast.LENGTH_LONG).show()
                }
            }

            override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                Log.d("WS", "WebSocket closed: $reason")
            }
        })
    }

    private fun handleRoundEnd(json: JSONObject) {
        val roundNumber = json.getInt("round_number")
        val winnerTeam = json.getInt("winner_team")
        val winnerPoints = json.getInt("winner_points")
        val team1Points = json.getInt("team1_points")
        val team2Points = json.getInt("team2_points")
        val gameEnded = json.getBoolean("game_ended")
        
        val title = if (gameEnded) "🏆 Jogo Terminado!" else "✅ Ronda $roundNumber Concluída"
        val message = buildString {
            append("Equipa $winnerTeam ganhou esta ronda!\n\n")
            append("Pontos:\n")
            append("Equipa 1: $team1Points\n")
            append("Equipa 2: $team2Points\n\n")
            append("Equipa vencedora: $winnerPoints pontos")
            
            if (gameEnded) {
                append("\n\n🎮 O jogo completo terminou após 4 rondas!")
            }
        }
        
        val builder = AlertDialog.Builder(this)
        builder.setTitle(title)
        builder.setMessage(message)
        builder.setCancelable(false)
        
        if (gameEnded) {
            // Jogo acabou - voltar ao menu
            builder.setPositiveButton("Voltar ao Menu") { dialog, _ ->
                dialog.dismiss()
                finish()
            }
        } else {
            // Mais rondas disponíveis
            builder.setPositiveButton("Nova Ronda") { dialog, _ ->
                dialog.dismiss()
                startNewRound()
            }
            builder.setNegativeButton("Terminar Jogo") { dialog, _ ->
                dialog.dismiss()
                finish()
            }
        }
        
        builder.show()
    }
    
    private fun startNewRound() {
        lifecycleScope.launch {
            try {
                // Chamar endpoint para iniciar nova ronda
                val response = RetrofitClient.api.startNewRound(gameId)
                if (response.success) {
                    Toast.makeText(this@VisionActivity, "Nova ronda iniciada! Mostre o trunfo", Toast.LENGTH_LONG).show()
                    // Re-habilitar o botão de começar jogo
                    val btnStartGame = findViewById<Button>(R.id.btnStartGame)
                    btnStartGame.isEnabled = true
                    btnStartGame.text = "▶ Começar Jogo (após mostrar trunfo)"
                } else {
                    Toast.makeText(this@VisionActivity, "Erro: ${response.message}", Toast.LENGTH_LONG).show()
                }
            } catch (e: Exception) {
                Log.e("VisionActivity", "Error starting new round", e)
                Toast.makeText(this@VisionActivity, "Erro: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 10) {
            if (allPermissionsGranted()) {
                startCamera()
                connectWebSocket()
            } else {
                Toast.makeText(this, "Permissions not granted by the user.", Toast.LENGTH_SHORT).show()
                finish()
            }
        }
    }

    private fun allPermissionsGranted() =
        ContextCompat.checkSelfPermission(
            this, Manifest.permission.CAMERA
        ) == PackageManager.PERMISSION_GRANTED

    override fun onDestroy() {
        super.onDestroy()
        // Cancel timer to prevent memory leaks
        cancelResetTimer()
        executor.shutdown()

        // Close WebSocket connection
        if (::webSocket.isInitialized) {
            webSocket.close(1000, "Activity Destroyed")
        }
    }

    // ========== BOT FUNCTIONS ==========

    private fun checkForBots() {
        lifecycleScope.launch {
            try {
                val response = RetrofitClient.api.getBots()
                val bots = response.bots
                if (bots.isNotEmpty()) {
                    hasBots = true
                    botCardsSection.visibility = View.VISIBLE
                    txtBotStatus.text = "🤖 Bot ativo: Jogador ${bots.first()}"
                }
            } catch (e: Exception) {
                Log.e("VisionActivity", "Error checking bots", e)
            }
        }
    }

    private fun handleBotRecognitionStart() {
        txtBotStatus.text = "🔍 Reconhecendo cartas do bot..."
        // Show all 10 cards face down for recognition
        showBotCards()
        Toast.makeText(this, "🔍 Mostre as cartas ao bot uma a uma", Toast.LENGTH_LONG).show()
    }

    private fun handleBotCardRecognized(cardNumber: Int, cardId: String) {
        if (cardNumber in 1..10) {
            // Show the card with its number overlay
            val cardView = botCardViews[cardNumber - 1]
            updateCardView(cardId, cardView)
            
            // You could add a TextView overlay with the number here
            // For now, show it in a toast
            Toast.makeText(
                this,
                "✅ Carta $cardNumber reconhecida: $cardId",
                Toast.LENGTH_SHORT
            ).show()
            
            txtBotStatus.text = "✅ $cardNumber/10 cartas reconhecidas"
            
            // If all 10 cards are recognized, show completion message
            if (cardNumber == 10) {
                Handler(Looper.getMainLooper()).postDelayed({
                    txtBotStatus.text = "✅ Todas as cartas reconhecidas! Pronto para começar"
                    Toast.makeText(
                        this,
                        "✅ Bot pronto! Clique em 'Começar Jogo'",
                        Toast.LENGTH_LONG
                    ).show()
                }, 500)
            }
        }
    }

    private fun showBotCards() {
        botCardsSection.visibility = View.VISIBLE
        // Show all 10 cards face down
        for (cardView in botCardViews) {
            cardView.setImageResource(R.drawable.card_back)
            cardView.visibility = View.VISIBLE
        }
        txtBotStatus.text = "🎴 Bot tem 10 cartas"
    }

    private fun handleBotPlayed(playerId: Int, cardName: String, cardIndex: Int) {
        // Show toast with bot's play
        Toast.makeText(
            this,
            "🤖 Bot $playerId jogou carta $cardIndex: $cardName",
            Toast.LENGTH_LONG
        ).show()
        
        txtBotStatus.text = "🤖 Bot jogou: $cardName"
        
        // Hide the card that was played (cardIndex is 1-10)
        if (cardIndex in 1..10) {
            botCardViews[cardIndex - 1].visibility = View.INVISIBLE
        }
        
        // Update remaining cards count
        val remainingCards = botCardViews.count { it.visibility == View.VISIBLE }
        if (remainingCards > 0) {
            txtBotStatus.text = "🤖 Bot tem $remainingCards cartas restantes"
        } else {
            txtBotStatus.text = "🤖 Bot jogou todas as cartas"
        }
    }

    private fun dealCardsToBot() {
        lifecycleScope.launch {
            try {
                val response = RetrofitClient.api.dealBotCards()
                if (response.success) {
                    showBotCards()
                    Toast.makeText(this@VisionActivity, "Cartas distribuídas ao bot", Toast.LENGTH_SHORT).show()
                }
            } catch (e: Exception) {
                Log.e("VisionActivity", "Error dealing cards to bot", e)
            }
        }
    }
}