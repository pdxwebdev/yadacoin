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

function pinFromCaller(caller: AttestedCaller): SiteCallerPin {
  return {
    packageName: caller.packageName.toLowerCase(),
    sha256CertFingerprints: caller.sha256CertFingerprints
      .map(normalizeCertSha256)
      .filter((x) => x.length === 64),
  };
}

function pinMatches(pin: SiteCallerPin, caller: AttestedCaller): boolean {
  if (pin.packageName.toLowerCase() !== caller.packageName.toLowerCase()) {
    return false;
  }
  return fingerprintsOverlap(
    pin.sha256CertFingerprints,
    caller.sha256CertFingerprints
  );
}

export function verifyAndroidCaller(opts: {
  platform: string;
  claimedSite: string;
  callback: string;
  caller: AttestedCaller | null;
  pin?: SiteCallerPin | null;
  assetLinks?: AssetLinkEntry[] | null;
}): VerifyCallerResult {
  const site = (opts.claimedSite || "").trim();
  const callback = (opts.callback || "").trim();
  const siteScheme = schemeOf(site);
  const cbScheme = schemeOf(callback);

  if (opts.platform !== "android") {
    return {
      ok: true,
      reason: "non-android-unverified",
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
  if (!fps.length) {
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
  if (androidPkg) {
    if (androidPkg !== attested.packageName) {
      return {
        ok: false,
        reason: "package-site-mismatch",
        displayName: attested.appLabel || attested.packageName,
      };
    }
  } else if (siteScheme === "https") {
    if (!assetLinkMatchesCaller(opts.assetLinks, attested)) {
      return {
        ok: false,
        reason: "assetlinks-mismatch",
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

  if (opts.pin?.packageName && opts.pin.sha256CertFingerprints?.length) {
    if (!pinMatches(opts.pin, attested)) {
      return {
        ok: false,
        reason: "pinned-caller-mismatch",
        displayName: attested.appLabel || attested.packageName,
        pin: opts.pin,
      };
    }
  }

  return {
    ok: true,
    reason: androidPkg
      ? "android-package-site"
      : siteScheme === "https"
        ? "assetlinks"
        : opts.pin?.packageName
          ? "pinned-tofu"
          : "tofu-first-seen",
    pin: pinFromCaller(attested),
    displayName: attested.appLabel || attested.packageName,
  };
}
