package com.cyber.warframeprofile

import android.annotation.SuppressLint
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.ViewGroup
import android.webkit.JavascriptInterface
import android.webkit.JsResult
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.TextView
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import java.io.FileOutputStream
import java.security.SecureRandom

/** Sobe o server.py (Python via Chaquopy) em 127.0.0.1 e mostra o site numa WebView. */
class MainActivity : Activity() {

    private lateinit var web: WebView
    private lateinit var status: TextView
    private var fileCallback: ValueCallback<Array<Uri>>? = null

    private companion object {
        const val REQ_FILE = 1001
        const val REQ_WFM = 1002
        // arquivos que só entram na 1ª instalação (depois são atualizados pelo próprio servidor)
        val SEED_ONLY = setOf("data/market_index.json", "data/keys.json")
        var port = 0
        var token = ""
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = FrameLayout(this).apply { setBackgroundColor(Color.parseColor("#0A0D13")) }
        web = WebView(this).apply {
            setBackgroundColor(Color.parseColor("#0A0D13"))
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.allowFileAccess = false
            settings.allowContentAccess = false
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                    val u = request.url
                    if (u.host == "127.0.0.1") return false
                    runCatching { startActivity(Intent(Intent.ACTION_VIEW, u)) }
                    return true
                }
            }
            webChromeClient = object : WebChromeClient() {
                override fun onShowFileChooser(
                    w: WebView, cb: ValueCallback<Array<Uri>>, params: FileChooserParams
                ): Boolean {
                    fileCallback?.onReceiveValue(null)
                    fileCallback = cb
                    val i = Intent(Intent.ACTION_GET_CONTENT).apply {
                        addCategory(Intent.CATEGORY_OPENABLE)
                        type = "*/*"   // o lastData.dat não tem tipo conhecido
                    }
                    return try {
                        startActivityForResult(Intent.createChooser(i, "Escolha o lastData"), REQ_FILE); true
                    } catch (e: Exception) {
                        fileCallback = null; false
                    }
                }

                override fun onJsAlert(v: WebView, url: String, msg: String, r: JsResult): Boolean {
                    AlertDialog.Builder(this@MainActivity).setMessage(msg)
                        .setPositiveButton("OK") { _, _ -> r.confirm() }
                        .setOnCancelListener { r.cancel() }.show()
                    return true
                }

                override fun onJsConfirm(v: WebView, url: String, msg: String, r: JsResult): Boolean {
                    AlertDialog.Builder(this@MainActivity).setMessage(msg)
                        .setPositiveButton("OK") { _, _ -> r.confirm() }
                        .setNegativeButton("Cancelar") { _, _ -> r.cancel() }
                        .setOnCancelListener { r.cancel() }.show()
                    return true
                }
            }
        }
        web.addJavascriptInterface(Bridge(), "Android")
        status = TextView(this).apply {
            text = "Iniciando…"; setTextColor(Color.parseColor("#9AA4B2")); textSize = 16f
            gravity = android.view.Gravity.CENTER
        }
        val lp = ViewGroup.LayoutParams.MATCH_PARENT
        root.addView(web, FrameLayout.LayoutParams(lp, lp))
        root.addView(status, FrameLayout.LayoutParams(lp, lp))
        setContentView(root)

        Thread { boot() }.start()
    }

    private fun boot() {
        try {
            if (port == 0) {
                val home = syncAssets()
                token = ByteArray(24).also { SecureRandom().nextBytes(it) }
                    .joinToString("") { "%02x".format(it) }
                if (!Python.isStarted()) Python.start(AndroidPlatform(this))
                port = Python.getInstance().getModule("wf_app")
                    .callAttr("start", home.absolutePath, token).toInt()
            }
            runOnUiThread {
                status.visibility = android.view.View.GONE
                if (web.url == null) web.loadUrl("http://127.0.0.1:$port/?k=$token")
            }
        } catch (e: Throwable) {
            runOnUiThread { status.text = "Erro ao iniciar:\n${e.message}" }
        }
    }

    /** Copia o site (assets/wf) para a pasta privada do app. Só recopia quando o app é atualizado. */
    private fun syncAssets(): File {
        val home = File(filesDir, "wf")
        val prefs = getSharedPreferences("wf", MODE_PRIVATE)
        val force = prefs.getInt("copied_version", 0) != BuildConfig.VERSION_CODE
        copyDir("wf", home, force)
        prefs.edit().putInt("copied_version", BuildConfig.VERSION_CODE).apply()
        File(home, "data/users").mkdirs()
        return home
    }

    private fun copyDir(assetPath: String, dst: File, force: Boolean) {
        val names = assets.list(assetPath) ?: return
        if (names.isEmpty()) {
            val rel = assetPath.removePrefix("wf/")
            val skip = dst.exists() && (!force || rel in SEED_ONLY)
            if (skip) return
            dst.parentFile?.mkdirs()
            val tmp = File(dst.path + ".tmp")
            assets.open(assetPath).use { i -> FileOutputStream(tmp).use { o -> i.copyTo(o) } }
            tmp.renameTo(dst)
        } else {
            dst.mkdirs()
            for (n in names) copyDir("$assetPath/$n", File(dst, n), force)
        }
    }

    /** Ponte JS -> Android (só a página local do app enxerga). */
    inner class Bridge {
        @JavascriptInterface
        fun loginWfm() {
            runOnUiThread { startActivityForResult(Intent(this@MainActivity, WfmLoginActivity::class.java), REQ_WFM) }
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        if (requestCode == REQ_WFM) {
            val tok = if (resultCode == RESULT_OK) data?.getStringExtra("token") else null
            if (!tok.isNullOrEmpty()) {
                web.evaluateJavascript("window.onWfmToken&&window.onWfmToken(" + org.json.JSONObject.quote(tok) + ")", null)
            }
            return
        }
        if (requestCode == REQ_FILE) {
            fileCallback?.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data))
            fileCallback = null
        } else super.onActivityResult(requestCode, resultCode, data)
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (web.canGoBack()) web.goBack() else super.onBackPressed()
    }
}
