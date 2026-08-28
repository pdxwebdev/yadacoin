package com.yadacoin.password;

import java.util.ArrayList;
import java.util.List;

final class CallerSnapshot {
    final String packageName;
    final String appLabel;
    final List<String> sha256CertFingerprints;
    final boolean handlesCallback;
    final String url;
    final long timestampMs;

    CallerSnapshot(
            String packageName,
            String appLabel,
            List<String> sha256CertFingerprints,
            boolean handlesCallback,
            String url,
            long timestampMs) {
        this.packageName = packageName;
        this.appLabel = appLabel;
        this.sha256CertFingerprints =
                sha256CertFingerprints != null
                        ? sha256CertFingerprints
                        : new ArrayList<>();
        this.handlesCallback = handlesCallback;
        this.url = url;
        this.timestampMs = timestampMs;
    }
}
