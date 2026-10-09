package com.jackbots.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;
import android.util.Log;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;

/** Keeps the Python bot server alive in the background: foreground notification + wake/wifi lock. */
public class BotService extends Service {
    static final String TAG = "JackBOTS";
    static final String ACTION_STOP = "com.jackbots.app.STOP";
    static final int PORT = 4791;
    static volatile String error;  // server startup error text, shown by MainActivity

    private static Thread server;
    private PowerManager.WakeLock wake;
    private WifiManager.WifiLock wifi;

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            shutdown();
            return START_NOT_STICKY;
        }
        goForeground();
        acquireLocks();
        startServer(getApplicationContext());
        return START_STICKY;
    }

    private void goForeground() {
        NotificationManager nm = getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel("bots", getString(R.string.channel_bots), NotificationManager.IMPORTANCE_LOW));
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class),
                PendingIntent.FLAG_IMMUTABLE);
        PendingIntent stop = PendingIntent.getService(this, 1,
                new Intent(this, BotService.class).setAction(ACTION_STOP), PendingIntent.FLAG_IMMUTABLE);
        Notification n = new Notification.Builder(this, "bots")
                .setSmallIcon(R.drawable.ic_stat_jackbots)
                .setContentTitle(getString(R.string.notif_title))
                .setContentText(getString(R.string.notif_text))
                .setContentIntent(open)
                .setOngoing(true)
                .addAction(new Notification.Action.Builder(null, getString(R.string.notif_stop), stop).build())
                .build();
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(1, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        } else {
            startForeground(1, n);
        }
    }

    private void acquireLocks() {
        if (wake == null) {
            wake = getSystemService(PowerManager.class).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "JackBOTS:bots");
            wake.acquire();
        }
        if (wifi == null) {
            WifiManager wm = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
            if (wm != null) {
                wifi = wm.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "JackBOTS:bots");
                wifi.acquire();
            }
        }
    }

    static synchronized void startServer(Context ctx) {
        if (server != null && server.isAlive()) return;
        error = null;
        server = new Thread(() -> {
            try {
                String root = Files.prepare(ctx);
                PyObject launcher = Python.getInstance().getModule("jackbots_launcher");
                launcher.callAttr("run", root, PORT);  // blocks until the server is stopped
            } catch (Throwable t) {
                Log.e(TAG, "server failed", t);
                error = String.valueOf(t);
            }
        }, "jackbots-server");
        server.start();
    }

    private void shutdown() {
        try {
            Python.getInstance().getModule("jackbots_launcher").callAttr("stop");
            if (server != null) server.join(5000);
        } catch (Throwable t) {
            Log.w(TAG, "stop failed", t);
        }
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
        // Python can't be restarted cleanly inside the process, so close the whole app
        MainActivity.finishAll();
        android.os.Process.killProcess(android.os.Process.myPid());
    }

    @Override
    public void onDestroy() {
        if (wake != null && wake.isHeld()) wake.release();
        if (wifi != null && wifi.isHeld()) wifi.release();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
