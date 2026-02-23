package com.example.MVP

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import androidx.recyclerview.widget.RecyclerView
import com.example.MVP.models.Card

class CardsAdapter(
    private var cards: List<Card>,
    private val onCardClick: (Card) -> Unit
) : RecyclerView.Adapter<CardsAdapter.CardViewHolder>() {

    var isEnabled: Boolean = true
        set(value) {
            field = value
            notifyDataSetChanged()
        }

    class CardViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val cardImage: ImageView = view.findViewById(R.id.cardImage)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): CardViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_card_mvp, parent, false)
        return CardViewHolder(view)
    }

    override fun onBindViewHolder(holder: CardViewHolder, position: Int) {
        val card = cards[position]
        val resId = getCardResource(holder.itemView, card)
        holder.cardImage.setImageResource(resId)
        
        // Visualmente desativar a carta se não for a vez
        holder.itemView.alpha = if (isEnabled) 1.0f else 0.5f
        
        holder.itemView.setOnClickListener {
            if (isEnabled) {
                onCardClick(card)
            }
        }
    }

    override fun getItemCount() = cards.size

    fun updateCards(newCards: List<Card>) {
        cards = newCards
        notifyDataSetChanged()
    }

    fun getCards(): List<Card> = cards

    private fun getCardResource(view: View, card: Card): Int {
        val context = view.context
        val suit = card.suit.lowercase()
        val value = when (val v = card.value.lowercase()) {
            "k" -> "king"
            "q" -> "queen"
            "j" -> "jack"
            "a" -> "ace"
            else -> v
        }
        val identifier = "${suit}_$value"
        val resId = context.resources.getIdentifier(identifier, "drawable", context.packageName)
        return if (resId != 0) resId else R.drawable.card_back
    }
}