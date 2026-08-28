package com.yadacoin.password;

import android.content.Intent;
import android.net.Uri;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "CallerIdentity")
public class CallerIdentityPlugin extends Plugin {

    @PluginMethod
    public void getLastCaller(PluginCall call) {
        CallerSnapshot snap = CallerIdentityStore.load(getContext());
        JSObject o = new JSObject();
        if (snap == null || snap.packageName == null || snap.packageName.isEmpty()) {
            o.put("packageName", "");
            o.put("appLabel", "");
            o.put("sha256CertFingerprints", new JSArray());
            o.put("handlesCallback", false);
            call.resolve(o);
            return;
        }
        o.put("packageName", snap.packageName);
        if (snap.appLabel != null) {
            o.put("appLabel", snap.appLabel);
        } else {
            o.put("appLabel", "");
        }
        JSArray fps = new JSArray();
        for (String fp : snap.sha256CertFingerprints) {
            fps.put(fp);
        }
        o.put("sha256CertFingerprints", fps);
        o.put("handlesCallback", snap.handlesCallback);
        call.resolve(o);
    }

    @PluginMethod
    public void openUrlInPackage(PluginCall call) {
        String url = call.getString("url");
        String pkg = call.getString("packageName");
        if (url == null || url.isEmpty() || pkg == null || pkg.isEmpty()) {
            call.reject("url and packageName required");
            return;
        }
        try {
            Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            i.setPackage(pkg);
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(i);
            call.resolve();
        } catch (Exception e) {
            call.reject(e.getMessage());
        }
    }
}
