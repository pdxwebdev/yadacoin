import assert from "node:assert/strict";
import { test } from "node:test";
import {
  aasaMatchesCaller,
  androidPackageFromSiteId,
  assetLinkMatchesCaller,
  fingerprintsOverlap,
  formatCertSha256Display,
  iosBundleFromSiteId,
  normalizeCertSha256,
  verifyAndroidCaller,
  verifyNativeCaller,
} from "../dist/caller-identity.js";

const FP_A = "a".repeat(64);
const FP_B = "b".repeat(64);
const FP_A_COLON = formatCertSha256Display(FP_A);

const demoCaller = {
  packageName: "io.yadacoin.passwordrotation.demo",
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

test("web is unverified-ok", () => {
  const r = verifyAndroidCaller({
    platform: "web",
    claimedSite: "yadademo://app",
    callback: "yadademo://result",
    caller: null,
  });
  assert.equal(r.ok, true);
  assert.equal(r.reason, "non-native-unverified");
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
  assert.equal(r.pin.packageName, "io.yadacoin.passwordrotation.demo");
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
    claimedSite: "android://io.yadacoin.passwordrotation.demo",
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
        package_name: "io.yadacoin.passwordrotation.demo",
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
      packageName: "io.yadacoin.passwordrotation.demo",
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

const iosCaller = {
  packageName: "io.yadacoin.passwordrotation.demo",
  appLabel: "Yada Auth Demo",
  sha256CertFingerprints: [],
  handlesCallback: true,
};

test("iosBundleFromSiteId", () => {
  assert.equal(iosBundleFromSiteId("ios://com.Foo.Bar"), "com.foo.bar");
  assert.equal(iosBundleFromSiteId("yadademo://app"), null);
});

test("ios without OS caller fails closed", () => {
  const r = verifyNativeCaller({
    platform: "ios",
    claimedSite: "yadademo://app",
    callback: "yadademo://result",
    caller: null,
  });
  assert.equal(r.ok, false);
  assert.equal(r.reason, "os-caller-missing");
});

test("ios custom scheme TOFU pins bundle id without certs", () => {
  const r = verifyNativeCaller({
    platform: "ios",
    claimedSite: "yadademo://app",
    callback: "yadademo://result",
    caller: iosCaller,
  });
  assert.equal(r.ok, true);
  assert.equal(r.reason, "tofu-first-seen");
  assert.equal(r.pin.packageName, "io.yadacoin.passwordrotation.demo");
  assert.equal(r.pin.sha256CertFingerprints.length, 0);
});

test("ios pin rejects a different bundle claiming the same site", () => {
  const first = verifyNativeCaller({
    platform: "ios",
    claimedSite: "yadademo://app",
    callback: "yadademo://result",
    caller: iosCaller,
  });
  const spoof = verifyNativeCaller({
    platform: "ios",
    claimedSite: "yadademo://app",
    callback: "yadademo://result",
    caller: { ...iosCaller, packageName: "com.evil.app" },
    pin: first.pin,
  });
  assert.equal(spoof.ok, false);
  assert.equal(spoof.reason, "pinned-caller-mismatch");
});

test("ios:// site id must equal caller bundle", () => {
  const ok = verifyNativeCaller({
    platform: "ios",
    claimedSite: "ios://io.yadacoin.passwordrotation.demo",
    callback: "yadademo://result",
    caller: iosCaller,
  });
  assert.equal(ok.ok, true);
  assert.equal(ok.reason, "ios-bundle-site");
  const bad = verifyNativeCaller({
    platform: "ios",
    claimedSite: "ios://com.bank.app",
    callback: "yadademo://result",
    caller: iosCaller,
  });
  assert.equal(bad.ok, false);
  assert.equal(bad.reason, "package-site-mismatch");
});

test("https origin on ios requires AASA match", () => {
  const aasa = {
    applinks: {
      details: [
        { appIDs: ["ABCD1234.io.yadacoin.passwordrotation.demo"], paths: ["*"] },
      ],
    },
  };
  const ok = verifyNativeCaller({
    platform: "ios",
    claimedSite: "https://bank.example",
    callback: "yadademo://result",
    caller: iosCaller,
    appleAppSiteAssociation: aasa,
  });
  assert.equal(ok.ok, true);
  assert.equal(ok.reason, "aasa");
  const bad = verifyNativeCaller({
    platform: "ios",
    claimedSite: "https://bank.example",
    callback: "yadademo://result",
    caller: iosCaller,
    appleAppSiteAssociation: { applinks: { details: [] } },
  });
  assert.equal(bad.ok, false);
  assert.equal(bad.reason, "aasa-mismatch");
});

test("aasaMatchesCaller matches TEAMID.bundle", () => {
  assert.equal(
    aasaMatchesCaller(
      { webcredentials: { apps: ["ABCD.io.yadacoin.passwordrotation.demo"] } },
      "io.yadacoin.passwordrotation.demo"
    ),
    true
  );
  assert.equal(
    aasaMatchesCaller(
      { webcredentials: { apps: ["ABCD.com.other.app"] } },
      "io.yadacoin.passwordrotation.demo"
    ),
    false
  );
});
