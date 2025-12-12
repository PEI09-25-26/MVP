package com.example.MVP

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.example.MVP.models.Player

class PlayersAdapter(private val players: List<Player>) : RecyclerView.Adapter<PlayersAdapter.VH>() {
    class VH(view: View) : RecyclerView.ViewHolder(view) {
        val name: TextView = view.findViewById(R.id.txtPlayerName)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_player_mvp, parent, false)
        return VH(v)
    }

    override fun getItemCount(): Int = players.size

    override fun onBindViewHolder(holder: VH, position: Int) {
        holder.name.text = players[position].name
    }
}
