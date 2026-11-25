package org.pcareader.preview;

import android.os.Handler;
import android.os.Looper;
import android.webkit.WebView;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.ServerPath;
import com.getcapacitor.WebViewListener;
import java.io.File;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends BridgeActivity {

    private static final ExecutorService UPDATE_WORKER = Executors.newSingleThreadExecutor();
    private final Handler startup = new Handler(Looper.getMainLooper());
    private ReaderUpdates updates;
    private File active;
    private boolean booted;

    @Override
    protected void load() {
        updates = new ReaderUpdates(this);
        active = updates.select();
        if (active != null) {
            bridgeBuilder.setServerPath(new ServerPath(ServerPath.PathType.BASE_PATH, active.getAbsolutePath()));
        }
        bridgeBuilder.addWebViewListener(new WebViewListener() {
            @Override
            public void onPageLoaded(WebView webView) {
                if (booted) return;
                File loading = active;
                webView.evaluateJavascript("window.__pcaReaderReady === true", result -> {
                    if (!booted && loading == active && "true".equals(result)) {
                        booted = true;
                        startup.removeCallbacksAndMessages(null);
                        updates.ready(active);
                        UPDATE_WORKER.execute(updates::check);
                    }
                });
            }
        });
        super.load();
        watchStartup();
    }

    private void watchStartup() {
        if (active == null || booted) return;
        startup.postDelayed(() -> {
            if (booted || active == null) return;
            active = updates.failed(active);
            if (active == null) {
                bridge.setServerAssetPath("public");
            } else {
                bridge.setServerBasePath(active.getAbsolutePath());
            }
            watchStartup();
        }, 12000);
    }

    @Override
    public void onDestroy() {
        startup.removeCallbacksAndMessages(null);
        super.onDestroy();
    }
}
