package com.example.MVP

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.appcompat.app.AppCompatActivity
import android.os.Bundle
import android.os.Handler
import android.os.Looper
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
import java.io.ByteArrayOutputStream
import java.util.concurrent.Executors
import androidx.appcompat.app.AlertDialog
import org.json.JSONObject

class VisionActivity : AppCompatActivity() {

    private val executor = Executors.newSingleThreadExecutor()
    private lateinit var webSocket: WebSocket

    private val wsUrl = "ws://10.196.16.35:8000/ws/camera/"  // IP do Mac na rede local
    // For emulator use: "ws://10.0.2.2:8000/ws/camera/"

    private var gameId: String = "default"

    // Views for the cards on the table
    private lateinit var cardNorth: ImageView
    private lateinit var cardWest: ImageView
    private lateinit var cardEast: ImageView
    private lateinit var cardSouth: ImageView
    private lateinit var trumpCard: ImageView

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

            btnBack.setOnClickListener { finish() }
            
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
                        if (json.has("type") && json.getString("type") == "round_end") {
                            // Fim de ronda
                            handleRoundEnd(json)
                            return@runOnUiThread
                        }
                    } catch (e: Exception) {
                        // Não é JSON, tratar como mensagem de carta normal
                    }
                    
                    if (text != lastWebSocketMessage) {
                        // When a new card arrives, cancel the timer and reset the board
                    }
                    lastWebSocketMessage = text

                    Toast.makeText(this@VisionActivity, "Card: $text", Toast.LENGTH_SHORT).show()

                    val json = JSONObject(text)

                    val detectionjson = json.optString("detection", "{}")
                    val detection = JSONObject(detectionjson)

                    val rankjson = detection.optString("rank", "").lowercase()
                    Toast.makeText(this@VisionActivity, "Rank: $rankjson", Toast.LENGTH_SHORT).show()
                    val suit = detection.optString("suit", "").lowercase()
                    Toast.makeText(this@VisionActivity, "Suit: $suit", Toast.LENGTH_SHORT).show()


                    if (rankjson.isEmpty() || suit.isEmpty()) {
                        Log.w("VisionActivity", "Incomplete card detection data.")
                    }

                    val rank = when (rankjson) {
                        "k" -> "king"
                        "q" -> "queen"
                        "j" -> "jack"
                        else -> rankjson
                    }

                    val cardIdentifier = "${suit}_$rank"

                    Toast.makeText(this@VisionActivity, "Card: $cardIdentifier", Toast.LENGTH_SHORT).show()

                    Log.d("VisionActivity", "Updating South view with card: $cardIdentifier")

                    val  state= json.optString("game_state", "{}")
                    val game_state = JSONObject(state)
                    val player = game_state.optString("current_player", "")

                    when (player) {
                        "1" -> {
                            resetCardsToBack()
                            updateCardView(cardIdentifier, cardNorth)
                        }
                        "2" -> updateCardView(cardIdentifier, cardWest)
                        "3" -> updateCardView(cardIdentifier, cardSouth)
                        "4" -> updateCardView(cardIdentifier, cardEast)
                        else -> {
                            // Opcional: caso o valor não seja 1-4
                            println("Jogador desconhecido: $player")
                        }
                    }
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
}