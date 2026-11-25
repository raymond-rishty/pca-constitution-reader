package org.pcareader.preview;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import javax.net.ssl.HttpsURLConnection;
import org.json.JSONObject;

final class ReaderUpdates {

    private static final Object LOCK = new Object();
    private static final String TAG = "ReaderUpdates";
    private static final String FEED = "https://raw.githubusercontent.com/raymond-rishty/pca-constitution-reader/android-content-feed/";
    private static final String GOOD = "good";
    private static final String PENDING = "pending";
    private static final String TRIAL = "trial";
    private static final String REJECTED = "rejected";
    private static final int MAX_DOWNLOAD = 12 * 1024 * 1024;
    private static final int MAX_EXPANDED = 32 * 1024 * 1024;

    private final SharedPreferences state;
    private final File directory;
    private final long bundledTime;

    ReaderUpdates(Context context) {
        state = context.getSharedPreferences("reader-web-v1", Context.MODE_PRIVATE);
        directory = new File(context.getNoBackupFilesDir(), "reader-web-v1");
        long timestamp = 0;
        try (InputStream input = context.getAssets().open("public/reader-build-time.txt")) {
            timestamp = Long.parseLong(new String(readBytes(input, 64), StandardCharsets.UTF_8));
        } catch (IOException | NumberFormatException error) {
            Log.w(TAG, "Could not read bundled reader version", error);
        }
        bundledTime = timestamp;
    }

    File select() {
        synchronized (LOCK) {
            Bundle interrupted = saved(TRIAL);
            if (interrupted != null) reject(interrupted);
            Bundle good = saved(GOOD);
            Bundle pending = saved(PENDING);
            prune(good, pending);
            if (pending != null && (good == null || pending.timestamp >= good.timestamp)
                && state.edit().putString(TRIAL, pending.metadata).commit()) {
                return path(pending);
            }
            return good == null ? null : path(good);
        }
    }

    void ready(File active) {
        if (active == null) return;
        synchronized (LOCK) {
            Bundle trial = saved(TRIAL);
            if (trial != null && active.equals(path(trial))) {
                state.edit().putString(GOOD, trial.metadata).remove(TRIAL).remove(PENDING).commit();
            }
        }
    }

    File failed(File active) {
        synchronized (LOCK) {
            Bundle failed = saved(TRIAL);
            if (failed == null) failed = saved(GOOD);
            if (failed != null && active.equals(path(failed))) reject(failed);
            Bundle good = saved(GOOD);
            return good == null || active.equals(path(good)) ? null : path(good);
        }
    }

    void check() {
        try {
            Bundle latest = new Bundle(new String(download("reader-web-v1.json", 4096), StandardCharsets.UTF_8));
            synchronized (LOCK) {
                if (!isNew(latest)) return;
            }
            byte[] bytes = download("reader-web-v1.zip", latest.size);
            if (bytes.length != latest.size ||
                !MessageDigest.isEqual(MessageDigest.getInstance("SHA-256").digest(bytes), latest.digest())) {
                throw new IOException("Reader web bundle did not match manifest");
            }

            synchronized (LOCK) {
                if (!isNew(latest)) return;
                if (!directory.isDirectory() && !directory.mkdirs()) throw new IOException("Could not create update directory");
                File staging = new File(directory, "incoming");
                remove(staging);
                if (!staging.mkdir()) throw new IOException("Could not create staging directory");
                try {
                    unpack(bytes, staging);
                    File target = path(latest);
                    remove(target);
                    if (!staging.renameTo(target)) throw new IOException("Could not install reader web bundle");
                    state.edit().putString(PENDING, latest.metadata).commit();
                } finally {
                    remove(staging);
                }
            }
        } catch (Exception error) {
            Log.d(TAG, "Reader update unavailable", error);
        }
    }

    private boolean isNew(Bundle latest) {
        if (latest.timestamp <= bundledTime || latest.hash.equals(state.getString(REJECTED, ""))) return false;
        for (String key : Arrays.asList(GOOD, PENDING, TRIAL)) {
            Bundle existing = saved(key);
            if (existing != null && (latest.timestamp < existing.timestamp || latest.hash.equals(existing.hash))) return false;
        }
        return true;
    }

    private Bundle saved(String key) {
        String value = state.getString(key, null);
        if (value == null) return null;
        try {
            Bundle bundle = new Bundle(value);
            return bundle.timestamp > bundledTime && new File(path(bundle), "index.html").isFile() ? bundle : null;
        } catch (Exception error) {
            return null;
        }
    }

    private void reject(Bundle bundle) {
        SharedPreferences.Editor editor = state.edit().putString(REJECTED, bundle.hash);
        for (String key : Arrays.asList(GOOD, PENDING, TRIAL)) {
            Bundle saved = saved(key);
            if (saved != null && bundle.hash.equals(saved.hash)) editor.remove(key);
        }
        editor.commit();
    }

    private File path(Bundle bundle) {
        return new File(directory, bundle.hash);
    }

    private void prune(Bundle good, Bundle pending) {
        File[] children = directory.listFiles();
        if (children == null) return;
        for (File child : children) {
            if ((good == null || !child.equals(path(good))) && (pending == null || !child.equals(path(pending)))) remove(child);
        }
    }

    private static void remove(File file) {
        File[] children = file.listFiles();
        if (children != null) {
            for (File child : children) remove(child);
        }
        if (file.exists() && !file.delete()) Log.w(TAG, "Could not remove unused update file");
    }

    private static byte[] download(String name, int limit) throws IOException {
        HttpsURLConnection connection = (HttpsURLConnection) new URL(FEED + name).openConnection();
        connection.setConnectTimeout(5000);
        connection.setReadTimeout(8000);
        connection.setInstanceFollowRedirects(false);
        connection.setRequestProperty("Cache-Control", "no-cache");
        try {
            if (connection.getResponseCode() != 200) throw new IOException("Reader feed returned HTTP " + connection.getResponseCode());
            try (InputStream input = connection.getInputStream()) {
                return readBytes(input, limit);
            }
        } finally {
            connection.disconnect();
        }
    }

    private static byte[] readBytes(InputStream input, int limit) throws IOException {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int count;
        while ((count = input.read(buffer)) != -1) {
            if (output.size() + count > limit) throw new IOException("Reader download exceeded size limit");
            output.write(buffer, 0, count);
        }
        return output.toByteArray();
    }

    static void unpack(byte[] bytes, File destination) throws IOException {
        int expanded = 0;
        int files = 0;
        byte[] buffer = new byte[8192];
        try (ZipInputStream input = new ZipInputStream(new ByteArrayInputStream(bytes))) {
            ZipEntry entry;
            while ((entry = input.getNextEntry()) != null) {
                String name = entry.getName();
                if (++files > 1024 || entry.isDirectory() ||
                    !name.matches("(?:[a-zA-Z0-9_-]+/)*[a-zA-Z0-9_-]+(?:\\.[a-zA-Z0-9_-]+)+")) {
                    throw new IOException("Unexpected file in reader update");
                }
                File target = new File(destination, name);
                File parent = target.getParentFile();
                if ((!parent.isDirectory() && !parent.mkdirs()) || !target.createNewFile()) {
                    throw new IOException("Could not extract reader update");
                }
                try (FileOutputStream output = new FileOutputStream(target)) {
                    int count;
                    while ((count = input.read(buffer)) != -1) {
                        expanded += count;
                        if (expanded > MAX_EXPANDED) throw new IOException("Reader update exceeded unpacked size limit");
                        output.write(buffer, 0, count);
                    }
                }
            }
        }
        if (!new File(destination, "index.html").isFile() || !new File(destination, "android-reader.js").isFile()) {
            throw new IOException("Reader update was missing startup files");
        }
    }

    private static final class Bundle {
        final String metadata;
        final String hash;
        final long timestamp;
        final int size;

        Bundle(String metadata) throws Exception {
            JSONObject json = new JSONObject(metadata);
            this.metadata = metadata;
            hash = json.getString("sha256");
            timestamp = json.getLong("timestamp");
            size = json.getInt("size");
            if (json.getInt("schema") != 1 || !hash.matches("[0-9a-f]{64}") ||
                timestamp <= 0 || size <= 0 || size > MAX_DOWNLOAD) {
                throw new IOException("Invalid reader update manifest");
            }
        }

        byte[] digest() {
            byte[] bytes = new byte[32];
            for (int i = 0; i < bytes.length; i++) {
                bytes[i] = (byte) Integer.parseInt(hash.substring(i * 2, i * 2 + 2), 16);
            }
            return bytes;
        }
    }
}
