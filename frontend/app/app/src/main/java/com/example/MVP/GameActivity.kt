package com.example.MVP

import android.os.Bundle
import android.view.LayoutInflater
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.example.MVP.models.Card

class GameActivity : AppCompatActivity() {

    private lateinit var cardsAdapter: CardsAdapter
    
    private lateinit var slotPlayer: FrameLayout
    private lateinit var slotPartner: FrameLayout
    private lateinit var slotLeft: FrameLayout
    private lateinit var slotRight: FrameLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_game_mvp)

        setupUI()
        loadDummyData()
    }

    private fun setupUI() {
        findViewById<ImageView>(R.id.backButton).setOnClickListener { finish() }

        slotPlayer = findViewById(R.id.slotPlayer)
        slotPartner = findViewById(R.id.slotPartner)
        slotLeft = findViewById(R.id.slotLeft)
        slotRight = findViewById(R.id.slotRight)

        val rvHand = findViewById<RecyclerView>(R.id.playerHandRecyclerView)
        // Alterado para GridLayout com 5 colunas (2 linhas para 10 cartas)
        rvHand.layoutManager = GridLayoutManager(this, 5)
        
        cardsAdapter = CardsAdapter(emptyList()) { card ->
            playCardMock(card)
        }
        rvHand.adapter = cardsAdapter
    }

    private fun loadDummyData() {
        val dummyHand = listOf(
            Card("1", "spades", "ace"),
            Card("2", "spades", "7"),
            Card("3", "hearts", "king"),
            Card("4", "hearts", "jack"),
            Card("5", "diamonds", "ace"),
            Card("6", "diamonds", "7"),
            Card("7", "clubs", "queen"),
            Card("8", "clubs", "2"),
            Card("9", "spades", "3"),
            Card("10", "hearts", "4")
        )
        cardsAdapter.updateCards(dummyHand)

        addCardToSlot(slotPartner, Card("11", "hearts", "ace"))
        addCardToSlot(slotLeft, Card("12", "spades", "king"))
    }

    private fun playCardMock(card: Card) {
        val currentCards = (cardsAdapter.getCards()).toMutableList()
        currentCards.remove(card)
        cardsAdapter.updateCards(currentCards)

        addCardToSlot(slotPlayer, card)

        cardsAdapter.isEnabled = false
        
        Toast.makeText(this, "Jogaste: ${card.value} de ${card.suit}. Aguarda a tua vez.", Toast.LENGTH_SHORT).show()
    }

    private fun addCardToSlot(slot: FrameLayout, card: Card) {
        val cardView = LayoutInflater.from(this).inflate(R.layout.item_card_mvp, slot, false)
        val imageView = cardView.findViewById<ImageView>(R.id.cardImage)
        imageView.setImageResource(getCardResource(card))
        
        slot.removeAllViews()
        slot.addView(cardView)
    }

    private fun getCardResource(card: Card): Int {
        val suit = card.suit.lowercase()
        val value = when (val v = card.value.lowercase()) {
            "k" -> "king"
            "q" -> "queen"
            "j" -> "jack"
            "a" -> "ace"
            else -> v
        }
        val identifier = "${suit}_$value"
        val resId = resources.getIdentifier(identifier, "drawable", packageName)
        return if (resId != 0) resId else R.drawable.card_back
    }
}