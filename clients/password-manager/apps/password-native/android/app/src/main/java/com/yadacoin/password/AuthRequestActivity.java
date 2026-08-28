package com.yadacoin.password;

import android.app.Activity;
import android.app.PendingIntent;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.content.pm.Signature;
import android.content.pm.SigningInfo;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;

import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;

/**
 * Trampoline for yadapass:// VIEW intents.
 *
 * A fresh standard-launch activity so {@link #getLaunchedFromPackage()} (API 31+)
 * and PendingIntent creator identity name the real calling app — not Capacitor's
 * singleTask MainActivity from a previous launch.
 */
public class AuthRequestActivity extends Activity {
    public static final String EXTRA_CALLER_IDENTITY = "yada.caller_identity";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Intent inbound = getIntent();
        Uri data = inbound != null ? inbound.getData() : null;
        String url = data != null ? data.toString() : null;

        String pkg = resolveCallerPackage(inbound);
        String label = null;
        List<String> fps = new ArrayList<>();
        boolean handles = false;
        if (pkg != null && !pkg.isEmpty()) {
            PackageManager pm = getPackageManager();
            try {
                CharSequence l = pm.getApplicationLabel(pm.getApplicationInfo(pkg, 0));
                if (l != null) label = l.toString();
            } catch (Exception ignored) {
            }
            fps = certSha256Hex(pkg);
            handles = callerHandlesCallback(pkg, data);
        }

        CallerIdentityStore.save(
                this,
                new CallerSnapshot(
                        pkg,
                        label,
                        fps,
                        handles,
                        url,
                        System.currentTimeMillis()));

        Intent next = new Intent(this, MainActivity.class);
        next.setAction(Intent.ACTION_VIEW);
        if (data != null) next.setData(data);
        next.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        startActivity(next);
        finish();
    }

    private String resolveCallerPackage(Intent inbound) {
        if (inbound != null) {
            PendingIntent pi = pendingIdentity(inbound);
            if (pi != null) {
                String creator = pi.getCreatorPackage();
                if (creator != null && !creator.isEmpty()) return creator;
            }
        }
        if (Build.VERSION.SDK_INT >= 31) {
            String launched = getLaunchedFromPackage();
            if (launched != null && !launched.isEmpty()) return launched;
        }
        String calling = getCallingPackage();
        if (calling != null && !calling.isEmpty()) return calling;

        // Only use getReferrer() when extras cannot spoof it.
        if (inbound != null
                && !inbound.hasExtra(Intent.EXTRA_REFERRER)
                && !inbound.hasExtra(Intent.EXTRA_REFERRER_NAME)) {
            Uri ref = getReferrer();
            if (ref != null && "android-app".equals(ref.getScheme())) {
                String host = ref.getHost();
                if (host != null && !host.isEmpty()) return host;
            }
        }
        return null;
    }

    private PendingIntent pendingIdentity(Intent inbound) {
        try {
            if (Build.VERSION.SDK_INT >= 33) {
                return inbound.getParcelableExtra(
                        EXTRA_CALLER_IDENTITY, PendingIntent.class);
            }
            return inbound.getParcelableExtra(EXTRA_CALLER_IDENTITY);
        } catch (Exception e) {
            return null;
        }
    }

    private boolean callerHandlesCallback(String pkg, Uri yadapassUri) {
        if (pkg == null || yadapassUri == null) return false;
        String callback = yadapassUri.getQueryParameter("callback");
        if (callback == null || callback.isEmpty()) return false;
        try {
            Intent view = new Intent(Intent.ACTION_VIEW, Uri.parse(callback));
            view.setPackage(pkg);
            ResolveInfo ri =
                    getPackageManager()
                            .resolveActivity(view, PackageManager.MATCH_DEFAULT_ONLY);
            return ri != null;
        } catch (Exception e) {
            return false;
        }
    }

    private List<String> certSha256Hex(String pkg) {
        List<String> out = new ArrayList<>();
        try {
            PackageManager pm = getPackageManager();
            PackageInfo info;
            Signature[] sigs;
            if (Build.VERSION.SDK_INT >= 28) {
                info = pm.getPackageInfo(pkg, PackageManager.GET_SIGNING_CERTIFICATES);
                SigningInfo si = info.signingInfo;
                if (si == null) return out;
                sigs =
                        si.hasMultipleSigners()
                                ? si.getApkContentsSigners()
                                : si.getSigningCertificateHistory();
            } else {
                info = pm.getPackageInfo(pkg, PackageManager.GET_SIGNATURES);
                sigs = info.signatures;
            }
            if (sigs == null) return out;
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            for (Signature sig : sigs) {
                md.reset();
                byte[] digest = md.digest(sig.toByteArray());
                out.add(toHex(digest));
            }
        } catch (Exception ignored) {
        }
        return out;
    }

    private static String toHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }
}
