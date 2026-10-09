package com.jackbots.app;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.TextView;

import java.lang.ref.WeakReference;
import java.net.InetSocketAddress;
import java.net.Socket;

/** Панель JackBOTS в WebView; сам сервер живёт в BotService. */
public class MainActivity extends Activity {
    private static WeakReference<MainActivity> current = new WeakReference<>(null);
    private final Handler ui = new Handler(Looper.getMainLooper());
    private WebView web;
    private TextView status;

    static void finishAll() {
        MainActivity a = current.get();
        if (a != null) a.runOnUiThread(a::finishAndRemoveTask);
    }

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        current = new WeakReference<>(this);
        status = new TextView(this);
        status.setText(R.string.starting);
        status.setTextColor(Color.parseColor("#22303f"));
        status.setBackgroundColor(Color.parseColor("#f6f1e4"));
        status.setTextSize(18);
        status.setGravity(Gravity.CENTER);
        status.setPadding(48, 48, 48, 48);
        setContentView(status);

        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 1);
        }
        startForegroundService(new Intent(this, BotService.class));
        waitForServer(System.currentTimeMillis());
    }

    private void waitForServer(long t0) {
        new Thread(() -> {
            while (true) {
                if (BotService.error != null) {
                    String e = BotService.error;
                    ui.post(() -> status.setText(getString(R.string.server_failed, e)));
                    return;
                }
                try (Socket s = new Socket()) {
                    s.connect(new InetSocketAddress("127.0.0.1", BotService.PORT), 500);
                    ui.post(this::showPanel);
                    return;
                } catch (Exception ignored) {
                    // сервер ещё стартует
                }
                if (System.currentTimeMillis() - t0 > 60000) {
                    ui.post(() -> status.setText(R.string.server_timeout));
                    return;
                }
                try {
                    Thread.sleep(300);
                } catch (InterruptedException e) {
                    return;
                }
            }
        }, "jackbots-wait").start();
    }

    private void showPanel() {
        if (web != null) return;
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setCacheMode(WebSettings.LOAD_NO_CACHE);
        web.setWebViewClient(new WebViewClient());
        web.setWebChromeClient(new WebChromeClient());
        web.loadUrl("http://127.0.0.1:" + BotService.PORT + "/");
        setContentView(web);
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) {
            web.goBack();
        } else {
            moveTaskToBack(true);  // не убиваем приложение: боты продолжают играть в фоне
        }
    }
}
