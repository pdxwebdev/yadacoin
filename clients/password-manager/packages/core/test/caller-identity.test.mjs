import assert from "node:assert/strict";
import { test } from "node:test";
import {
  androidPackageFromSiteId,
  assetLinkMatchesCaller,
  fingerprintsOverlap,
  formatCertSha256Display,
  normalizeCertSha256,
  verifyAndroidCaller,
} from "../dist/caller-identity.js";

const FP_A = "a".repeat(64);
const FP_B = "b".repeat(64);
const FP_A_COLON = formatCertSha256Display(FP_A);

const demoCaller = {
  packageName: "com.yadacoin.passworddemo",
  appLabel: "Yada Auth Demo",
  sha256CertFingerprints: [FP_A],
  handlesCallback: true,
};

test("normalizeCertSha256 strips colons and case", () => {
  assert.equal(normalizeCertSha256(FP_A_COLON), FP_A);
});

test("fingerprintsOverlap", () => {
  assert.equal(fingerprintsOverlap([FP_A], [FP_A_COLON]), true);
  assert.equal(fingerprintsOverlap([FP_A], [FP_B]), false);
});

test("androidPackageFromSiteId", () => {
  assert.equal(androidPackageFromSiteId("android://com.Foo.Bar"), "com.foo.bar");
  assert.equal(
    androidPackageFromSiteId("android-app://com.foo.bar/path"),
    "com.foo.bar"
  );
  assert.equal(androidPackageFromSiteId("yadademo://app"), null);
  assert.equal(androidPackageFromSiteId("https://example.com"), null);
});

test("non-android is unverified-ok", () => {
  const r = verifyAndroidCaller({
    platform: "web",
    claimedSite: "yadademo://app",
    callback: "yadademo://result",
    caller: null,
  });
  assert.equal(r.ok, true);
  assert.equal(r.reason, "non-android-unverified");
});

test("android without OS caller fails closed", () => {
  const r = verifyAndroidCaller({
    platform: "android",
    claimedSite: "yadademo://app",
    callback: "yadademo://result",
    caller: null,
  });
  assert.equal(r.ok, false);
  assert.equal(r.reason, "os-caller-missing");
});

test("custom scheme TOFU: matching scheme + caller", () => {
  const r = verifyAndroidCaller({
    platform: "android",
    claimedSite: "yadademo://app",
    callback: "yadademo://result",
    caller: demoCaller,
  });
  assert.equal(r.ok, true);
  assert.equal(r.reason, "tofu-first-seen");
  assert.equal(r.pin.packageName, "com.yadacoin.passworddemo");
});

test("custom scheme rejects site/callback scheme mismatch", () => {
  const r = verifyAndroidCaller({
    platform: "android",
    claimedSite: "yadademo://app",
    callback: "evil://result",
    caller: { ...demoCaller, handlesCallback: true },
  });
  assert.equal(r.ok, false);
  assert.equal(r.reason, "site-callback-scheme-mismatch");
});

test("custom scheme rejects http(s) callback", () => {
  const r = verifyAndroidCaller({
    platform: "android",
    claimedSite: "yadademo://app",
    callback: "https://evil.example/steal",
    caller: demoCaller,
  });
  assert.equal(r.ok, false);
  assert.equal(r.reason, "callback-not-app-owned");
});

test("android:// site id must equal caller package", () => {
  const ok = verifyAndroidCaller({
    platform: "android",
    claimedSite: "android://com.yadacoin.passworddemo",
    callback: "yadademo://result",
    caller: demoCaller,
  });
  assert.equal(ok.ok, true);
  const bad = verifyAndroidCaller({
    platform: "android",
    claimedSite: "android://com.bank.app",
    callback: "yadademo://result",
    caller: demoCaller,
  });
  assert.equal(bad.ok, false);
  assert.equal(bad.reason, "package-site-mismatch");
});

test("https origin requires Digital Asset Links match", () => {
  const links = [
    {
      relation: ["delegate_permission/common.get_login_creds"],
      target: {
        namespace: "android_app",
        package_name: "com.yadacoin.passworddemo",
        sha256_cert_fingerprints: [FP_A_COLON],
      },
    },
  ];
  const ok = verifyAndroidCaller({
    platform: "android",
    claimedSite: "https://bank.example",
    callback: "yadademo://result",
    caller: demoCaller,
    assetLinks: links,
  });
  assert.equal(ok.ok, true);
  assert.equal(ok.reason, "assetlinks");

  const bad = verifyAndroidCaller({
    platform: "android",
    claimedSite: "https://bank.example",
    callback: "yadademo://result",
    caller: demoCaller,
    assetLinks: [],
  });
  assert.equal(bad.ok, false);
  assert.equal(bad.reason, "assetlinks-mismatch");
});

test("pin rejects a different package claiming the same site", () => {
  const first = verifyAndroidCaller({
    platform: "android",
    claimedSite: "yadademo://app",
    callback: "yadademo://result",
    caller: demoCaller,
  });
  assert.equal(first.ok, true);
  const spoof = verifyAndroidCaller({
    platform: "android",
    claimedSite: "yadademo://app",
    callback: "yadademo://result",
    caller: {
      packageName: "com.evil.app",
      appLabel: "Bank",
      sha256CertFingerprints: [FP_B],
      handlesCallback: true,
    },
    pin: first.pin,
  });
  assert.equal(spoof.ok, false);
  assert.equal(spoof.reason, "pinned-caller-mismatch");
});

test("pin rejects same package with unknown cert", () => {
  const r = verifyAndroidCaller({
    platform: "android",
    claimedSite: "yadademo://app",
    callback: "yadademo://result",
    caller: { ...demoCaller, sha256CertFingerprints: [FP_B] },
    pin: {
      packageName: "com.yadacoin.passworddemo",
      sha256CertFingerprints: [FP_A],
    },
  });
  assert.equal(r.ok, false);
  assert.equal(r.reason, "pinned-caller-mismatch");
});

test("assetLinkMatchesCaller ignores other packages", () => {
  const links = [
    {
      relation: ["delegate_permission/common.handle_all_urls"],
      target: {
        namespace: "android_app",
        package_name: "com.other.app",
        sha256_cert_fingerprints: [FP_A],
      },
    },
  ];
  assert.equal(assetLinkMatchesCaller(links, demoCaller), false);
});
