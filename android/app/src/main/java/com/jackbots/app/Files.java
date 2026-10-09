package com.jackbots.app;

import android.content.Context;
import android.content.res.AssetManager;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

/** Распаковывает код панели (assets/panel, собирается из корня репозитория) в папку приложения: Python и StaticFiles нужны настоящие файлы. */
final class Files {
    private Files() {}

    static synchronized String prepare(Context ctx) throws Exception {
        File root = new File(ctx.getFilesDir(), "panel");
        long stamp = ctx.getPackageManager().getPackageInfo(ctx.getPackageName(), 0).lastUpdateTime;
        File marker = new File(root, ".installed");
        String want = String.valueOf(stamp);
        if (!marker.exists() || !want.equals(read(marker))) {
            copy(ctx.getAssets(), "panel", root);
            try (OutputStream o = new FileOutputStream(marker)) {
                o.write(want.getBytes("UTF-8"));
            }
        }
        return root.getAbsolutePath();
    }

    private static void copy(AssetManager am, String path, File dst) throws IOException {
        String[] kids = am.list(path);
        if (kids != null && kids.length > 0) {
            if (!dst.isDirectory() && !dst.mkdirs()) throw new IOException("cannot create " + dst);
            for (String k : kids) copy(am, path + "/" + k, new File(dst, k));
            return;
        }
        // настройки пользователя (ключи, боты, промты) при обновлении не перетираем
        if (dst.exists() && dst.getParentFile() != null && dst.getParentFile().getName().equals("config")) return;
        try (InputStream in = am.open(path); OutputStream out = new FileOutputStream(dst)) {
            byte[] buf = new byte[65536];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
        }
    }

    private static String read(File f) {
        try (InputStream in = new java.io.FileInputStream(f)) {
            java.io.ByteArrayOutputStream b = new java.io.ByteArrayOutputStream();
            byte[] buf = new byte[256];
            int n;
            while ((n = in.read(buf)) > 0) b.write(buf, 0, n);
            return b.toString("UTF-8");
        } catch (IOException e) {
            return "";
        }
    }
}
