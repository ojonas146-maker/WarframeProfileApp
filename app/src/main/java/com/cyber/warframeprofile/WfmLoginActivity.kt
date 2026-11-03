package com.cyber.warframeprofile

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.webkit.CookieManager
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast

/** Abre o login oficial do warframe.market numa WebView e devolve o token de sessão (cookie JWT) ao app. */
class WfmLoginActivity : Activity() {

    private lateinit var web: WebView
    private var done = false

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.parseColor("#0A0D13"))
        }
        val info = TextView(this).apply {
            text = "Entre no warframe.market. Quando terminar, toque em Concluir."
            setTextColor(Color.parseColor("#C9D1E0")); textSize = 14f; setPadding(32, 28, 32, 20)
        }
        val btn = Button(this).apply { text = "Concluir"; setOnClickListener { finishWith(true) } }
        web = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView, url: String) {
                    if (!url.contains("signin") && !url.contains("login") && !url.contains("auth")) finishWith(false)
                }
            }
        }
        root.addView(info)
        root.addView(web, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        root.addView(btn)
        setContentView(root)
        CookieManager.getInstance().setAcceptCookie(true)
        web.loadUrl("https://warframe.market/auth/signin")
    }

    private fun readToken(): String? {
        val cm = CookieManager.getInstance()
        var fallback: String? = null
        for (u in listOf("https://warframe.market", "https://api.warframe.market")) {
            val raw = cm.getCookie(u) ?: continue
            for (part in raw.split(";")) {
                val kv = part.trim().split("=", limit = 2)
                if (kv.size != 2) continue
                val v = Uri.decode(kv[1])
                if (kv[0].equals("JWT", true) && v.length > 40) return v
                if (fallback == null && v.startsWith("eyJ") && v.count { it == '.' } >= 2) fallback = v
            }
        }
        return fallback
    }

    private fun finishWith(manual: Boolean) {
        if (done) return
        val t = readToken()
        if (t == null) {
            if (manual) Toast.makeText(this, "Ainda não achei a sessão. Termine o login e toque de novo.", Toast.LENGTH_LONG).show()
            return
        }
        done = true
        setResult(RESULT_OK, Intent().putExtra("token", t))
        finish()
    }
}
