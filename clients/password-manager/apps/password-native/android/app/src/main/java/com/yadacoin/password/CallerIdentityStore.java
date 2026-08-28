package com.yadacoin.password;

import android.content.Context;
import android.content.SharedPreferences;
import android.text.TextUtils;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

final class CallerIdentityStore {
    private static final String PREFS = "yada_caller_identity";
    private static final String KEY_PKG = "packageName";
    private static final String KEY_LABEL = "appLabel";
    private static final String KEY_FPS = "fingerprints";
    private static final String KEY_HANDLES = "handlesCallback";
    private static final String KEY_URL = "url";
    private static final String KEY_TS = "timestampMs";

    static volatile CallerSnapshot last;

    private CallerIdentityStore() {}

    static void save(Context ctx, CallerSnapshot snap) {
        last = snap;
        SharedPreferences.Editor ed =
                ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit();
        if (snap == null) {
            ed.clear().apply();
            return;
        }
        ed.putString(KEY_PKG, snap.packageName);
        ed.putString(KEY_LABEL, snap.appLabel);
        ed.putString(KEY_FPS, TextUtils.join(",", snap.sha256CertFingerprints));
        ed.putBoolean(KEY_HANDLES, snap.handlesCallback);
        ed.putString(KEY_URL, snap.url);
        ed.putLong(KEY_TS, snap.timestampMs);
        ed.apply();
    }

    static CallerSnapshot load(Context ctx) {
        if (last != null) return last;
        SharedPreferences p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String pkg = p.getString(KEY_PKG, null);
        if (pkg == null || pkg.isEmpty()) return null;
        String fps = p.getString(KEY_FPS, "");
        List<String> list =
                fps.isEmpty()
                        ? new ArrayList<>()
                        : new ArrayList<>(Arrays.asList(fps.split(",")));
        last =
                new CallerSnapshot(
                        pkg,
                        p.getString(KEY_LABEL, null),
                        list,
                        p.getBoolean(KEY_HANDLES, false),
                        p.getString(KEY_URL, null),
                        p.getLong(KEY_TS, 0));
        return last;
    }
}
