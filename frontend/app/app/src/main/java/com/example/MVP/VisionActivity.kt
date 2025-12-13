package com.example.MVP

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.appcompat.app.AppCompatActivity
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Base64
import android.util.Log
import android.widget.ImageView
import android.widget.Toast
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import okhttp3.*
import java.io.ByteArrayOutputStream
import java.util.concurrent.Executors

class VisionActivity : AppCompatActivity() {

    private val executor = Executors.newSingleThreadExecutor()
    private lateinit var webSocket: WebSocket

    private val wsUrl = "ws://TEU_BACKEND_IP:PORT/ws/stream"  // <- muda isto

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
        setContentView(R.layout.activity_vision_game)

        val btnBack = findViewById<ImageView>(R.id.backButton)

        btnBack.setOnClickListener { finish() }

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
            // connectWebSocket() // Desativado para teste da câmara
        } else {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.CAMERA),
                10
            )
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

            val cameraSelector = CameraSelector.DEFAULT_FRONT_CAMERA

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

        // Apenas para teste: confirma no Logcat que os frames estão a ser processados
        Log.d("VisionActivity", "Frame processado. Tamanho do Base64: ${base64.length}")

        /* Desativado para teste da câmara
        if (::webSocket.isInitialized) {
            webSocket.send(base64) // <- envia frame
        }
        */
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
            .url(wsUrl)
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(ws: WebSocket, response: Response) {
                Log.d("WS", "WebSocket conectado")
            }

            override fun onMessage(ws: WebSocket, text: String) {
                Log.d("WS", "Resposta: $text")
                runOnUiThread {
                    if (text != lastWebSocketMessage) {
                        // When a new card arrives, cancel the timer and reset the board
                        cancelResetTimer()
                        resetCardsToBack()
                    }
                    lastWebSocketMessage = text

                    // Example of how you might use the new function:
                    // val (player, card) = parseWebSocketMessage(text) // You need to implement parseWebSocketMessage
                    // when (player) {
                    //     "North" -> updateCardView(card, cardNorth)
                    //     "South" -> updateCardView(card, cardSouth)
                    //     "East" -> updateCardView(card, cardEast)
                    //     "West" -> updateCardView(card, cardWest)
                    //     "Trump" -> updateCardView(card, trumpCard)
                    // }

                    // If the trick is complete, start the timer
                    // if (allPlayerCardsAreSet()) { // You need to implement allPlayerCardsAreSet
                    //     startResetTimer()
                    // }

                    Toast.makeText(this@VisionActivity, text, Toast.LENGTH_SHORT).show()
                }
            }

            override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                Log.e("WS", "Erro WebSocket", t)
            }
        })
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
                // connectWebSocket() // Desativado para teste da câmara
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
        /* Desativado para teste da câmara
        if (::webSocket.isInitialized) {
            webSocket.close(1000, "Activity Destroyed")
        }
        */
    }
}
