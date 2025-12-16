package com.example.MVP.network

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import com.example.MVP.network.ApiService
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object RetrofitClient {
    // For Android Emulator: use 10.0.2.2 to access localhost on host machine
    // For Real Device: replace with your computer's IP address (e.g., "http://10.196.16.35:8000/")
    private const val BASE_URL = "http://192.168.176.252:8000/"

    private val logger = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY
    }

    private val client = OkHttpClient.Builder()
        .addInterceptor(logger)
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()

    val api: ApiService by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ApiService::class.java)
    }
}
