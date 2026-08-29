import { schemeOf } from "./deeplink.js";

/** SHA-256 of an Android signing cert: lowercase hex, no separators. */
export function normalizeCertSha256(fp: string): string {
  return (fp || "").replace(/[^0-9a-fA-F]/g, "").toLowerCase();
}

export function fingerprintsOverlap(a: string[], b: string[]): boolean {
  const set = new Set(a.map(normalizeCertSha256).filter((x) => x.length === 64));
  for (const fp of b) {
    const n = normalizeCertSha256(fp);
    if (n.length === 64 && set.has(n)) return true;
  }
  return false;
}

export function formatCertSha256Display(fp: string): string {
  const n = normalizeCertSha256(fp);
  if (n.length !== 64) return fp || "—";
  return (n.match(/.{2}/g) || []).join(":").toUpperCase();
}

/**
 * Native Android site ids:
 *   android://com.example.app
 *   android-app://com.example.app
 */
export function androidPackageFromSiteId(site: string): string | null {
  const raw = (site || "").trim();
  const m =
    /^(?:android:\/\/|android-app:\/\/)([a-zA-Z0-9._]+)(?:[/?#]|$)/i.exec(raw);
  return m ? m[1]!.toLowerCase() : null;
}

/** ios://com.example.app */
export function iosBundleFromSiteId(site: string): string | null {
  const raw = (site || "").trim();
  const m = /^(?:ios:\/\/|iphone-app:\/\/)([a-zA-Z0-9.-]+)(?:[/?#]|$)/i.exec(raw);
  return m ? m[1]!.toLowerCase() : null;
}

export interface AttestedCaller {
  packageName: string;
  appLabel?: string;
  sha256CertFingerprints: string[];
  handlesCallback?: boolean;
}

export interface SiteCallerPin {
  packageName: string;
  sha256CertFingerprints: string[];
}

export interface AssetLinkEntry {
  relation?: string[];
  target?: {
    namespace?: string;
    package_name?: string;
    sha256_cert_fingerprints?: string[];
  };
}

export interface AppleAppSiteAssociation {
  applinks?: {
    apps?: string[];
    details?: Array<{
      appID?: string;
      appIDs?: string[];
      paths?: string[];
    }>;
  };
  webcredentials?: { apps?: string[] };
}

export type VerifyCallerResult =
  | {
      ok: true;
      reason: string;
      pin: SiteCallerPin;
      displayName: string;
    }
  | {
      ok: false;
      reason: string;
      pin?: SiteCallerPin;
      displayName?: string;
    };

const ASSETLINK_RELATIONS = new Set([
  "delegate_permission/common.handle_all_urls",
  "delegate_permission/common.get_login_creds",
  "delegate_permission/common.use_as_origin",
]);

export function assetLinkMatchesCaller(
  links: AssetLinkEntry[] | null | undefined,
  caller: AttestedCaller
): boolean {
  if (!links || !Array.isArray(links)) return false;
  const pkg = caller.packageName.toLowerCase();
  for (const entry of links) {
    const rel = entry?.relation;
    if (Array.isArray(rel) && rel.length) {
      const okRel = rel.some((r) => ASSETLINK_RELATIONS.has(r));
      if (!okRel) continue;
    }
    const t = entry?.target;
    if (!t || (t.namespace && t.namespace !== "android_app")) continue;
    if ((t.package_name || "").toLowerCase() !== pkg) continue;
    const fps = t.sha256_cert_fingerprints || [];
    if (fingerprintsOverlap(fps, caller.sha256CertFingerprints)) return true;
  }
  return false;
}

export function aasaMatchesCaller(
  aasa: AppleAppSiteAssociation | null | undefined,
  bundleId: string
): boolean {
  if (!aasa || !bundleId) return false;
  const ids: string[] = [];
  for (const d of aasa.applinks?.details || []) {
    if (d.appID) ids.push(d.appID);
    if (d.appIDs) ids.push(...d.appIDs);
  }
  ids.push(...(aasa.applinks?.apps || []));
  ids.push(...(aasa.webcredentials?.apps || []));
  const b = bundleId.toLowerCase();
  return ids.some((id) => {
    const x = (id || "").toLowerCase();
    return x === b || x.endsWith("." + b);
  });
}

export async function fetchAndroidAssetLinks(
  origin: string,
  fetchImpl: typeof fetch = globalThis.fetch.bind(globalThis)
): Promise<AssetLinkEntry[] | null> {
  const base = origin.replace(/\/+$/, "");
  const url = `${base}/.well-known/assetlinks.json`;
  try {
    const res = await fetchImpl(url, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return null;
    const body = await res.json();
    return Array.isArray(body) ? (body as AssetLinkEntry[]) : null;
  } catch {
    return null;
  }
}

export async function fetchAppleAppSiteAssociation(
  origin: string,
  fetchImpl: typeof fetch = globalThis.fetch.bind(globalThis)
): Promise<AppleAppSiteAssociation | null> {
  const base = origin.replace(/\/+$/, "");
  const urls = [
    `${base}/.well-known/apple-app-site-association`,
    `${base}/apple-app-site-association`,
  ];
  for (const url of urls) {
    try {
      const res = await fetchImpl(url, {
        headers: { Accept: "application/json" },
      });
      if (!res.ok) continue;
      const body = await res.json();
      if (body && typeof body === "object") {
        return body as AppleAppSiteAssociation;
      }
    } catch {
      /* try next */
    }
  }
  return null;
}

function pinFromCaller(caller: AttestedCaller): SiteCallerPin {
  return {
    packageName: caller.packageName.toLowerCase(),
    sha256CertFingerprints: caller.sha256CertFingerprints
      .map(normalizeCertSha256)
      .filter((x) => x.length === 64),
  };
}

function pinMatches(
  pin: SiteCallerPin,
  caller: AttestedCaller,
  platform: string
): boolean {
  if (pin.packageName.toLowerCase() !== caller.packageName.toLowerCase()) {
    return false;
  }
  const pinFps = (pin.sha256CertFingerprints || [])
    .map(normalizeCertSha256)
    .filter((x) => x.length === 64);
  const callerFps = (caller.sha256CertFingerprints || [])
    .map(normalizeCertSha256)
    .filter((x) => x.length === 64);
  if (platform === "ios") {
    if (!pinFps.length || !callerFps.length) return true;
    return fingerprintsOverlap(pinFps, callerFps);
  }
  return fingerprintsOverlap(pinFps, callerFps);
}

export function verifyNativeCaller(opts: {
  platform: string;
  claimedSite: string;
  callback: string;
  caller: AttestedCaller | null;
  pin?: SiteCallerPin | null;
  assetLinks?: AssetLinkEntry[] | null;
  appleAppSiteAssociation?: AppleAppSiteAssociation | null;
}): VerifyCallerResult {
  const site = (opts.claimedSite || "").trim();
  const callback = (opts.callback || "").trim();
  const siteScheme = schemeOf(site);
  const cbScheme = schemeOf(callback);
  const platform = opts.platform;

  if (platform !== "android" && platform !== "ios") {
    return {
      ok: true,
      reason: "non-native-unverified",
      pin: opts.pin || {
        packageName: "",
        sha256CertFingerprints: [],
      },
      displayName: site,
    };
  }

  const caller = opts.caller;
  if (!caller?.packageName) {
    return { ok: false, reason: "os-caller-missing" };
  }
  const fps = caller.sha256CertFingerprints.map(normalizeCertSha256).filter(
    (x) => x.length === 64
  );
  if (platform === "android" && !fps.length) {
    return {
      ok: false,
      reason: "os-certs-missing",
      displayName: caller.appLabel || caller.packageName,
    };
  }
  const attested: AttestedCaller = {
    ...caller,
    packageName: caller.packageName.toLowerCase(),
    sha256CertFingerprints: fps,
  };

  if (!cbScheme || cbScheme === "http" || cbScheme === "https") {
    return {
      ok: false,
      reason: "callback-not-app-owned",
      displayName: attested.appLabel || attested.packageName,
    };
  }

  const androidPkg = androidPackageFromSiteId(site);
  const iosBundle = iosBundleFromSiteId(site);
  if (androidPkg) {
    if (platform !== "android" || androidPkg !== attested.packageName) {
      return {
        ok: false,
        reason: "package-site-mismatch",
        displayName: attested.appLabel || attested.packageName,
      };
    }
  } else if (iosBundle) {
    if (platform !== "ios" || iosBundle !== attested.packageName) {
      return {
        ok: false,
        reason: "package-site-mismatch",
        displayName: attested.appLabel || attested.packageName,
      };
    }
  } else if (siteScheme === "https") {
    if (platform === "android") {
      if (!assetLinkMatchesCaller(opts.assetLinks, attested)) {
        return {
          ok: false,
          reason: "assetlinks-mismatch",
          displayName: attested.appLabel || attested.packageName,
        };
      }
    } else if (!aasaMatchesCaller(opts.appleAppSiteAssociation, attested.packageName)) {
      return {
        ok: false,
        reason: "aasa-mismatch",
        displayName: attested.appLabel || attested.packageName,
      };
    }
  } else if (siteScheme === "http") {
    return {
      ok: false,
      reason: "http-origin-not-bindable",
      displayName: attested.appLabel || attested.packageName,
    };
  } else {
    if (!siteScheme || siteScheme !== cbScheme) {
      return {
        ok: false,
        reason: "site-callback-scheme-mismatch",
        displayName: attested.appLabel || attested.packageName,
      };
    }
  }

  if (opts.pin?.packageName) {
    if (!pinMatches(opts.pin, attested, platform)) {
      return {
        ok: false,
        reason: "pinned-caller-mismatch",
        displayName: attested.appLabel || attested.packageName,
        pin: opts.pin,
      };
    }
  }

  const bound = androidPkg || iosBundle;
  return {
    ok: true,
    reason: bound
      ? platform === "ios"
        ? "ios-bundle-site"
        : "android-package-site"
      : siteScheme === "https"
        ? platform === "ios"
          ? "aasa"
          : "assetlinks"
        : opts.pin?.packageName
          ? "pinned-tofu"
          : "tofu-first-seen",
    pin: pinFromCaller(attested),
    displayName: attested.appLabel || attested.packageName,
  };
}

/** @deprecated use verifyNativeCaller */
export const verifyAndroidCaller = verifyNativeCaller;
