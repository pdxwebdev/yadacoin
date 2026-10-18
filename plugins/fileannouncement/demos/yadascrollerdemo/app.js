(() => {
  const API_VIDEOS = "/file-announcements/api/v1/public/videos";
  const API_PHOTOS = "/file-announcements/api/v1/public/photos";
  const API_FILES = "/file-announcements/api/v1/files";
  const API_BACKENDS = "/file-announcements/api/v1/backends";
  const API_UPLOADS = "/file-announcements/api/v1/uploads";
  const API_PROFILE = "/file-announcements/api/v1/public/profile";
  const API_BADGES = "/file-announcements/api/v1/public/badges";
  const API_ME = "/file-announcements/api/v1/public/me";
  const API_PURCHASE = "/file-announcements/api/v1/public/purchase";
  const API_REASONS = "/file-announcements/api/v1/public/takedown-reasons";
  const API_TAKEDOWN = "/file-announcements/api/v1/public/takedown";
  const API_LIVE = "/livestream-announcements/api/v1/live";
  const API_WATCH = "/livestream-announcements/api/v1/watch";
  const HLS_SRC = "https://cdn.jsdelivr.net/npm/hls.js@1.5.17/dist/hls.min.js";
  const PREFETCH_COUNT = 10;
  /** ~2s of video at ~2 Mbps ≈ 512 KiB; used for Range prefetch warm-up */
  const PREFETCH_BYTES = 512 * 1024;
  const PAGE_SIZE = 40;
  const GIFT_CHAINS = [{ id: "yadacoin", label: "Yadacoin", symbol: "YDA" }];
  const GIFTS = [
    { id: "rose", name: "Rose", emoji: "🌹", price: 1 },
    { id: "heart", name: "Heart", emoji: "❤️", price: 5 },
    { id: "star", name: "Star", emoji: "⭐", price: 10 },
    { id: "crown", name: "Crown", emoji: "👑", price: 50 },
    { id: "rocket", name: "Rocket", emoji: "🚀", price: 100 },
    { id: "diamond", name: "Diamond", emoji: "💎", price: 500 },
  ];

  const feed = document.getElementById("feed");
  const photoPane = document.getElementById("photo-pane");
  const photoEmpty = document.getElementById("photo-empty");
  const tabVideos = document.getElementById("tab-videos");
  const tabPhotos = document.getElementById("tab-photos");
  const statusEl = document.getElementById("status");
  const emptyEl = document.getElementById("empty");
  const searchEl = document.getElementById("search");
  const refreshBtn = document.getElementById("refresh");
  const muteBtn = document.getElementById("mute-btn");
  const hintEl = document.getElementById("hint");
  const reportDlg = document.getElementById("report-dlg");
  const reportForm = document.getElementById("report-form");
  const reportReason = document.getElementById("report-reason");
  const reportTitle = document.getElementById("report-title");
  const reportErr = document.getElementById("report-err");
  const reportCancel = document.getElementById("report-cancel");
  const reportSubmit = document.getElementById("report-submit");
  const appEl = document.getElementById("app");
  const profileEl = document.getElementById("profile");
  const profileBack = document.getElementById("profile-back");
  const profileTopTitle = document.getElementById("profile-top-title");
  const profileAvatar = document.getElementById("profile-avatar");
  const profileName = document.getElementById("profile-name");
  const profileSub = document.getElementById("profile-sub");
  const profileActions = document.getElementById("profile-actions");
  const profileGrid = document.getElementById("profile-grid");
  const profileEmpty = document.getElementById("profile-empty");
  const profileTabVideos = document.getElementById("profile-tab-videos");
  const profileTabPhotos = document.getElementById("profile-tab-photos");
  const statGifts = document.getElementById("stat-gifts");
  const statFollowing = document.getElementById("stat-following");
  const statFollowers = document.getElementById("stat-followers");
  const statBadges = document.getElementById("stat-badges");
  const statBadgesBtn = document.getElementById("stat-badges-btn");
  const badgesEl = document.getElementById("badges");
  const badgesBack = document.getElementById("badges-back");
  const badgesTitle = document.getElementById("badges-title");
  const badgeList = document.getElementById("badge-list");
  const badgeEmpty = document.getElementById("badge-empty");
  const badgeDetail = document.getElementById("badge-detail");
  const editAvatar = document.getElementById("edit-avatar");
  const editUpload = document.getElementById("edit-upload");
  const publishEl = document.getElementById("publish");
  const publishBack = document.getElementById("publish-back");
  const extStatus = document.getElementById("ext-status");
  const signinMsg = document.getElementById("signin-msg");
  const signinTrack = document.getElementById("signin-track");
  const registerBtn = document.getElementById("register-btn");
  const resyncBtn = document.getElementById("resync-btn");
  const signinBtn = document.getElementById("signin-btn");
  const signinUsername = document.getElementById("signin-username");
  const playerEl = document.getElementById("player");
  const playerBack = document.getElementById("player-back");
  const playerVideo = document.getElementById("player-video");
  const playerPhoto = document.getElementById("player-photo");
  const uploadEl = document.getElementById("upload");
  const uploadBack = document.getElementById("upload-back");
  const composeForm = document.getElementById("compose-form");
  const composeFields = document.getElementById("compose-fields");
  const composeFile = document.getElementById("compose-file");
  const composeTitle = document.getElementById("compose-title");
  const composeType = document.getElementById("compose-type");
  const composeBackend = document.getElementById("compose-backend");
  const composeProgress = document.getElementById("compose-progress");
  const composeProgressLabel = document.getElementById("compose-progress-label");
  const composeProgressTrack = document.getElementById("compose-progress-track");
  const composeProgressBar = document.getElementById("compose-progress-bar");
  const composeMsg = document.getElementById("compose-msg");
  const composeSubmit = document.getElementById("compose-submit");
  const composeSignin = document.getElementById("compose-signin");
  const playerSpinner = document.getElementById("player-spinner");
  const playerCaption = document.getElementById("player-caption");
  const playerLive = document.getElementById("player-live");
  const playerGate = document.getElementById("player-gate");
  const playerGateBg = document.getElementById("player-gate-bg");
  const playerGateKicker = document.getElementById("player-gate-kicker");
  const playerGateTitle = document.getElementById("player-gate-title");
  const playerGateMsg = document.getElementById("player-gate-msg");
  const playerGateChips = document.getElementById("player-gate-chips");
  const liveRow = document.getElementById("live-row");
  const railGift = document.getElementById("rail-gift");
  const railBuy = document.getElementById("rail-buy");
  const buyDlg = document.getElementById("buy-dlg");
  const buyTo = document.getElementById("buy-to");
  const buyPrice = document.getElementById("buy-price");
  const buyQr = document.getElementById("buy-qr");
  const buyAddress = document.getElementById("buy-address");
  const buyNote = document.getElementById("buy-note");
  const buyClose = document.getElementById("buy-close");
  const buyCheck = document.getElementById("buy-check");
  const buyNode = document.getElementById("buy-node");
  let buyItem = null;
  const railReport = document.getElementById("rail-report");
  const giftDlg = document.getElementById("gift-dlg");
  const giftTo = document.getElementById("gift-to");
  const giftChain = document.getElementById("gift-chain");
  const giftPick = document.getElementById("gift-pick");
  const giftGrid = document.getElementById("gift-grid");
  const giftPay = document.getElementById("gift-pay");
  const giftPicked = document.getElementById("gift-picked");
  const giftQr = document.getElementById("gift-qr");
  const giftAddress = document.getElementById("gift-address");
  const giftNote = document.getElementById("gift-note");
  const giftClose = document.getElementById("gift-close");
  const giftBack = document.getElementById("gift-back");
  const navFyp = document.getElementById("nav-fyp");
  const navUpload = document.getElementById("nav-upload");
  const navProfile = document.getElementById("nav-profile");

  /** @type {Array<object>} */
  let videos = [];
  let photos = [];
  let activeIndex = 0;
  let photoIndex = 0;
  let mediaMode = "videos";
  let photosLoadedQuery = null;
  let uploadBusy = false;
  let composeBusy = false;
  let composeLocked = false;
  let composePoll = null;
  let composeGen = 0;
  let composeReq = 0;
  let composeXhr = null;
  let composeTypeApplied = null;
  let composeAutoTitle = "";
  let muted = true;
  let loading = false;
  let query = "";
  /** @type {Array<{value:string,name:string,label:string}>} */
  let reasonCodes = [];
  /** @type {object | null} */
  let reportTarget = null;
  /** @type {Map<string, AbortController>} */
  const prefetchControllers = new Map();
  /** @type {Set<string>} */
  const prefetched = new Set();
  /** @type {IntersectionObserver | null} */
  let observer = null;
  let photoObserver = null;
  let feedGen = 0;
  let photoGen = 0;
  let probeAbort = new AbortController();
  let viewName = "feed";
  /** @type {Array<object>} */
  let profileVideos = [];
  let profilePhotos = [];
  let profileMedia = sessionStorage.getItem("yada-scroller-profile") === "photos" ? "photos" : "videos";
  /** @type {object | null} */
  let giftTarget = null;
  /** @type {object | null} */
  let playerItem = null;
  let currentProfile = null;
  /** @type {Array<object>} */
  let liveStreams = [];
  /** @type {Map<string, object>} */
  const liveByName = new Map();
  /** @type {Map<string, object>} */
  const liveByOwner = new Map();
  let liveHls = null;
  let livePc = null;
  let liveWhep = "";
  /** @type {Array<object>} */
  let badgeItems = [];
  let badgeDetailFromList = false;
  let armBadgeDetailBack = false;

  const probe = document.createElement("video");

  function showStatus(msg, ms = 2800) {
    if (viewName !== "feed" && !uploadBusy && (ms === 0 || !msg)) return;
    if (!msg) {
      statusEl.hidden = true;
      return;
    }
    statusEl.textContent = msg;
    statusEl.hidden = false;
    clearTimeout(showStatus._t);
    if (ms > 0) {
      showStatus._t = setTimeout(() => {
        statusEl.hidden = true;
      }, ms);
    }
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  let myBadges = [];
  let signedIn = false;
  let myUsername = "";

  const ADULT_CLAIMS = ["ageOver18", "isOver18"];

  function adultClaim(claim) {
    return ADULT_CLAIMS.indexOf(String(claim || "").trim()) !== -1;
  }

  function postIsAdult(item) {
    return credentialGates(item).some((gate) => adultClaim(gate.claim));
  }

  function viewerIsOver18() {
    return ADULT_CLAIMS.some((claim) => myBadges.some((badge) => badgeMatches(badge, { claim, issuer: "" })));
  }

  function hideAdult(item) {
    return postIsAdult(item) && !viewerIsOver18();
  }

  function credentialGates(item) {
    const raw = item && item.required_credentials;
    const gates = [];
    if (Array.isArray(raw)) {
      raw.forEach((gate) => {
        const claim = String((gate && gate.claim) || "").trim();
        const issuer = String((gate && gate.issuer) || "").trim();
        if (claim || issuer) gates.push({ claim, issuer });
      });
    }
    if (!gates.length) {
      const claim = String((item && item.required_claim) || "").trim();
      const issuer = String((item && item.required_issuer) || "").trim();
      if (claim || issuer) gates.push({ claim, issuer });
    }
    return gates;
  }

  function credentialNeed(item) {
    const gates = credentialGates(item);
    return gates[0] || { claim: "", issuer: "" };
  }

  function issuerId(value) {
    let text = String(value || "").trim();
    const prefix = "did:yadacoin:";
    if (text.toLowerCase().startsWith(prefix)) text = text.slice(prefix.length).trim();
    if (text.startsWith("@")) text = text.slice(1).trim();
    return text;
  }

  function sameIssuer(wanted, candidate) {
    const want = issuerId(wanted);
    const got = issuerId(candidate);
    if (!want || !got) return false;
    if (want === got) return true;
    if (want.length <= 32 && got.length <= 32 && !/[+/=]/.test(want + got)) {
      return want.toLowerCase() === got.toLowerCase();
    }
    return false;
  }

  function badgeMatches(badge, need) {
    if (!badge || !need || (!need.claim && !need.issuer)) return false;
    const expires = Number(badge.expires);
    if (Number.isFinite(expires) && expires > 0 && expires * 1000 < Date.now()) return false;
    if (badge.proof_valid === false) return false;
    const vc = badge.vc || {};
    const subject = vc.credentialSubject || {};
    const claimOk = !need.claim || badge.claim === need.claim || !!subject[need.claim];
    if (!claimOk) return false;
    if (!need.issuer) return true;
    return (
      sameIssuer(need.issuer, badge.issuer_username_signature) ||
      sameIssuer(need.issuer, badge.issuer_username) ||
      sameIssuer(need.issuer, vc.issuer)
    );
  }

  function matchingBadges(item) {
    const gates = credentialGates(item);
    if (!gates.length) return [];
    const found = [];
    for (const gate of gates) {
      const badge = myBadges.find((row) => badgeMatches(row, gate));
      if (!badge) return null;
      found.push(badge);
    }
    return found;
  }

  function matchingBadge(item) {
    const found = matchingBadges(item);
    return found && found.length ? found[0] : null;
  }

  function presentationQuery(badges) {
    const list = Array.isArray(badges) ? badges : badges ? [badges] : [];
    const vcs = [];
    let holder = "";
    for (const badge of list) {
      const vc = badge && badge.vc;
      const id = vc && vc.credentialSubject && vc.credentialSubject.id;
      if (!vc || !id) return "";
      if (holder && holder !== id) return "";
      holder = id;
      vcs.push(vc);
    }
    if (!vcs.length) return "";
    const vp = {
      "@context": ["https://www.w3.org/ns/credentials/v2"],
      type: ["VerifiablePresentation"],
      holder,
      verifiableCredential: vcs,
    };
    try {
      const json = JSON.stringify(vp);
      return btoa(unescape(encodeURIComponent(json)))
        .replace(/\+/g, "-")
        .replace(/\//g, "_")
        .replace(/=+$/g, "");
    } catch (_) {
      return "";
    }
  }

  function missingGates(item) {
    return credentialGates(item).filter((gate) => !myBadges.some((badge) => badgeMatches(badge, gate)));
  }

  function chipHue(text) {
    let n = 0;
    const s = String(text || "badge");
    for (let i = 0; i < s.length; i++) n = (n * 33 + s.charCodeAt(i)) >>> 0;
    return n % 360;
  }

  function gateIssuerLabel(issuer) {
    const id = issuerId(issuer);
    if (!id) return "";
    if (id.length <= 32 && !/[+/=]/.test(id)) return `@${id.replace(/^@/, "")}`;
    return shortId(id);
  }

  function itemWatchVerb(item, kind) {
    if (kind === "photo") return "view";
    if (kind === "video") return "watch";
    const mime = String((item && item.mime_type) || "").toLowerCase();
    return mime.startsWith("image/") ? "view" : "watch";
  }

  function accessGateMessage(item, kind) {
    const missing = missingGates(item);
    const labels = (missing.length ? missing : credentialGates(item)).map((gate) =>
      gate.claim ? claimLabel(gate.claim) : "a credential"
    );
    const text = labels.join(" and ") || "a credential";
    const which = labels.length === 1 ? "that badge is" : "those badges are";
    let msg = `You can't ${itemWatchVerb(item, kind)} this yet. It requires ${text}, and ${which} not in your wallet.`;
    if (!signedIn) {
      msg = `Sign in on this node so your badges can be checked. ${msg}`;
    }
    const price = itemPrice(item);
    if (price && !(item && item.price_unlocked)) {
      msg += ` It also costs ${formatPrice(price)} YDA. Payment stays closed until every required badge is in your wallet.`;
    }
    return msg;
  }

  function credentialMessage(item) {
    return accessGateMessage(item);
  }

  function gateChipHtml(gate) {
    const claim = gate.claim ? claimLabel(gate.claim) : "Credential";
    const issuer = gate.issuer ? gateIssuerLabel(gate.issuer) : "";
    const hue = chipHue(`${gate.claim}|${gate.issuer}`);
    return `<span class="gate-chip" style="--chip:${hue}"><span class="gate-mark">${escapeHtml(
      claimMark(gate.claim)
    )}</span><span class="gate-chip-text"><strong>${escapeHtml(claim)}</strong><small>${
      issuer ? `from ${escapeHtml(issuer)}` : "Missing"
    }</small></span></span>`;
  }

  function priceGateChipHtml(item) {
    const price = itemPrice(item);
    if (!price || (item && item.price_unlocked)) return "";
    return `<span class="gate-chip gate-chip-price"><span class="gate-mark">YDA</span><span class="gate-chip-text"><strong>${escapeHtml(
      formatPrice(price)
    )} YDA</strong><small>Pay after badges</small></span></span>`;
  }

  function hideAccessGate() {
    if (!playerGate) return;
    playerGate.hidden = true;
    playerEl.classList.remove("gated");
    if (playerGateBg) {
      playerGateBg.hidden = true;
      playerGateBg.removeAttribute("src");
    }
    if (playerGateChips) playerGateChips.innerHTML = "";
  }

  function openAccessGate(item, kind) {
    if (!item) return Promise.resolve();
    return loadMyBadges().then(() => {
      stopLiveHls();
      pauseFeed();
      playerItem = item;
      playerLive.hidden = true;
      railReport.hidden = false;
      playerSpinner.hidden = true;
      try {
        playerVideo.pause();
      } catch (_) {}
      playerVideo.hidden = true;
      playerVideo.removeAttribute("src");
      playerVideo.srcObject = null;
      try {
        playerVideo.load();
      } catch (_) {}
      playerPhoto.hidden = true;
      playerPhoto.removeAttribute("src");
      playerCaption.textContent = "";
      const missing = missingGates(item);
      const gates = missing.length ? missing : credentialGates(item);
      playerGateKicker.textContent = "Locked";
      playerGateTitle.textContent = item.title || item.filename || "This post";
      playerGateMsg.textContent = accessGateMessage(item, kind);
      playerGateChips.innerHTML = gates.map(gateChipHtml).join("") + priceGateChipHtml(item);
      const poster = String((item && item.thumbnail_url) || "").trim();
      if (poster) {
        playerGateBg.hidden = false;
        playerGateBg.src = poster;
      } else {
        playerGateBg.hidden = true;
        playerGateBg.removeAttribute("src");
      }
      playerGate.hidden = false;
      playerEl.classList.add("gated");
      playerEl.hidden = false;
      appEl.classList.add("player-open");
      renderLiveRow();
    });
  }

  async function loadMyBadges() {
    try {
      const me = await fetch(API_ME, { credentials: "same-origin" });
      const who = await me.json().catch(() => ({}));
      if (!who.authenticated || !who.username) {
        signedIn = false;
        myUsername = "";
        myBadges = [];
        return myBadges;
      }
      signedIn = true;
      myUsername = String(who.username || "").replace(/^@/, "");
      const res = await fetch(
        `${API_BADGES}?username=${encodeURIComponent(who.username)}`,
        { credentials: "same-origin" }
      );
      const data = await res.json().catch(() => ({}));
      myBadges = data.badges || [];
    } catch (_) {
      signedIn = false;
      myBadges = [];
    }
    refreshCredentialSources();
    return myBadges;
  }

  async function downloadAllowed(item) {
    if (!credentialGates(item).length) return true;
    await loadMyBadges();
    return !!matchingBadges(item);
  }

  function grantNote(item) {
    const seconds = Number(item && item.grant_seconds);
    if (!Number.isFinite(seconds) || seconds <= 0) return "Access does not expire.";
    const day = 86400;
    const hour = 3600;
    const minute = 60;
    if (seconds % day === 0) {
      const days = seconds / day;
      return `Access lasts ${days} day${days === 1 ? "" : "s"} after the first confirmed purchase.`;
    }
    if (seconds % hour === 0) {
      const hours = seconds / hour;
      return `Access lasts ${hours} hour${hours === 1 ? "" : "s"} after the first confirmed purchase.`;
    }
    if (seconds % minute === 0) {
      const minutes = seconds / minute;
      return `Access lasts ${minutes} minute${minutes === 1 ? "" : "s"} after the first confirmed purchase.`;
    }
    return `Access lasts ${seconds} second${seconds === 1 ? "" : "s"} after the first confirmed purchase.`;
  }

  function itemPrice(item) {
    const raw = String((item && item.price) || "").trim();
    const n = Number(raw);
    if (!raw || !Number.isFinite(n) || n <= 0) return "";
    return raw;
  }

  function formatPrice(raw) {
    return String(raw).replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
  }

  function priceChipHtml(item) {
    const price = itemPrice(item);
    if (!price || item.price_unlocked) return "";
    return `<span class="price-chip">PPV ${escapeHtml(formatPrice(price))} YDA</span>`;
  }

  function credentialChipHtml(item) {
    const missing = credentialGates(item).filter(
      (gate) => !myBadges.some((badge) => badgeMatches(badge, gate))
    );
    if (!missing.length) return "";
    const label = missing.map((gate) => (gate.claim ? claimLabel(gate.claim) : "credential")).join(" · ");
    return `<span class="price-chip cred-chip">Needs ${escapeHtml(label)}</span>`;
  }

  function paintCredentialChip(root, item) {
    if (!root) return;
    const existing = root.querySelector(".cred-chip");
    if (existing) existing.remove();
    const html = credentialChipHtml(item);
    if (html) root.insertAdjacentHTML("beforeend", html);
  }

  function paidStreamUrl(item) {
    const id = String((item && item.transaction_id) || "").trim();
    if (!id) return "";
    const params = new URLSearchParams();
    const access = String((item && item.access) || "").trim();
    const paymentId = String((item && item.payment_id) || "").trim();
    if (access) params.set("access", access);
    if (paymentId) params.set("payment_id", paymentId);
    const vp = presentationQuery(matchingBadges(item) || []);
    if (vp) params.set("vp", vp);
    const q = params.toString();
    return `${API_PURCHASE}/stream/${encodeURIComponent(id)}${q ? `?${q}` : ""}`;
  }

  function lockedPrice(item) {
    return !!(itemPrice(item) && !(item && item.price_unlocked));
  }

  function videoCandidate(item) {
    if (!item || !item.file_id) return false;
    if (!canLikelyPlay(mimeFor(item))) return false;
    if (item.stream_url) return true;
    return lockedPrice(item);
  }

  function streamUrl(item) {
    if (lockedPrice(item)) return "";
    if (credentialGates(item).length && !matchingBadges(item)) return "";
    if (!item || !item.stream_url) return "";
    const params = new URLSearchParams();
    if (item.filename) params.set("filename", item.filename);
    if (item.mime_type) params.set("mime_type", item.mime_type);
    const vp = presentationQuery(matchingBadges(item) || []);
    if (vp) params.set("vp", vp);
    const q = params.toString();
    if (!q) return item.stream_url;
    const join = item.stream_url.includes("?") ? "&" : "?";
    return `${item.stream_url}${join}${q}`;
  }

  function refreshCredentialSources() {
    if (!feed) return;
    feed.querySelectorAll(".slide").forEach((slide) => {
      const item = videos.find((row) => itemKey(row) === slide.dataset.key);
      if (!item) return;
      paintCredentialChip(slide, item);
      const video = slide.querySelector("video");
      if (!video || video.getAttribute("src")) return;
      const url = streamUrl(item);
      if (!url) return;
      video.setAttribute("data-src", url);
      if (Number(slide.dataset.index) === activeIndex) ensureSrc(video);
    });
    syncBuyRail();
  }

  function mimeFor(item) {
    const m = (item.mime_type || "").trim().toLowerCase();
    if (m) return m;
    const f = (item.filename || "").toLowerCase();
    if (f.endsWith(".mp4") || f.endsWith(".m4v")) return "video/mp4";
    if (f.endsWith(".webm")) return "video/webm";
    if (f.endsWith(".mov")) return "video/quicktime";
    if (f.endsWith(".ogv")) return "video/ogg";
    return "video/mp4";
  }

  function canLikelyPlay(mime) {
    const t = probe.canPlayType(mime) || "";
    if (t === "probably" || t === "maybe") return true;
    // Chrome often returns "" for quicktime even when Safari can play it
    if (mime === "video/quicktime") {
      return /Safari/i.test(navigator.userAgent) && !/Chrome|Chromium|Edg/i.test(navigator.userAgent);
    }
    return false;
  }

  function avatarColor(name) {
    const colors = ["#fe2c55", "#20d5ec", "#7c5cff", "#ffb703", "#3ddc97", "#4cc9f0"];
    let n = 0;
    const s = String(name || "?");
    for (let i = 0; i < s.length; i++) n = (n + s.charCodeAt(i)) % colors.length;
    return colors[n];
  }

  function avatarMarkup(username) {
    const name = String(username || "").trim();
    if (!name) {
      return `<span class="avatar-fallback" aria-hidden="true"><svg viewBox="0 0 24 24" width="22" height="22"><circle cx="12" cy="8" r="4" fill="currentColor"/><path d="M4 20c1.6-3.6 4.4-5.2 8-5.2S18.4 16.4 20 20" fill="currentColor"/></svg></span>`;
    }
    return `<span class="avatar-fallback">${escapeHtml(name.slice(0, 1).toUpperCase())}</span>`;
  }

  function paintAvatar(el, username, imageUrl) {
    const name = String(username || "").trim();
    const color = avatarColor(name || "?");
    el.style.background = color;
    let face = el.querySelector(":scope > .avatar-face");
    const tag = el.querySelector(":scope > .live-tag");
    if (!face) {
      el.innerHTML = "";
      face = document.createElement("span");
      face.className = "avatar-face";
      el.appendChild(face);
      if (tag) el.appendChild(tag);
    }
    face.style.background = color;
    const src = String(imageUrl || "").trim();
    if (!src) {
      face.innerHTML = avatarMarkup(name);
      return;
    }
    const img = document.createElement("img");
    img.className = "avatar-photo";
    img.alt = "";
    img.addEventListener("error", () => {
      face.innerHTML = avatarMarkup(name);
    });
    img.src = src;
    face.innerHTML = "";
    face.appendChild(img);
  }

  function setLiveRing(el, on) {
    if (!el) return;
    el.classList.toggle("is-live", !!on);
    let tag = el.querySelector(":scope > .live-tag");
    if (on) {
      if (!tag) {
        tag = document.createElement("span");
        tag.className = "live-tag";
        tag.textContent = "LIVE";
        el.appendChild(tag);
      }
      return;
    }
    if (tag) tag.remove();
  }

  function indexLive(list) {
    liveStreams = (list || []).filter((stream) => {
      if (!stream || !stream.age_restricted) return true;
      return viewerIsOver18();
    });
    liveByName.clear();
    liveByOwner.clear();
    liveStreams.forEach((stream) => {
      const name = String(stream.username || "").trim().toLowerCase();
      if (name) liveByName.set(name, stream);
      const owner = String(stream.owner || "").trim();
      if (owner) liveByOwner.set(owner, stream);
      const pkh = String(stream.public_key_hash || "").trim();
      if (pkh) liveByOwner.set(pkh, stream);
    });
  }

  function liveFor(item) {
    if (!item) return null;
    const name = String(item.username || "").trim().toLowerCase();
    if (name && liveByName.has(name)) return liveByName.get(name);
    const owner = String(item.owner || item.inception_public_key_hash || "").trim();
    if (owner && liveByOwner.has(owner)) return liveByOwner.get(owner);
    const pkh = String(item.public_key_hash || "").trim();
    if (pkh && liveByOwner.has(pkh)) return liveByOwner.get(pkh);
    return null;
  }

  function itemKey(item) {
    return `${(item && item.backend) || "sia"}:${(item && item.file_id) || ""}`;
  }

  function contentKey(item) {
    const name = String((item && item.filename) || "")
      .trim()
      .toLowerCase();
    const size = Number(item && item.size) || 0;
    if (!name || size <= 0) return "";
    const owner = String((item && item.owner) || "")
      .trim()
      .toLowerCase();
    if (owner) return `content:${owner}:${name}:${size}`;
    return `content:${name}:${size}`;
  }

  /** @type {Set<string>} */
  const dropped = new Set();

  function clearMedia(video) {
    video.dataset.unloading = "1";
    try {
      video.pause();
    } catch (_) {}
    video.removeAttribute("src");
    while (video.firstChild) video.removeChild(video.firstChild);
    try {
      video.load();
    } catch (_) {}
  }

  function dropVideo(key) {
    if (!key || dropped.has(key)) return;
    const index = videos.findIndex((v) => itemKey(v) === key);
    if (index < 0) return;
    dropped.add(key);
    const wasActive = index === activeIndex;
    videos.splice(index, 1);
    const slide = feed.querySelector(`.slide[data-key="${key}"]`);
    if (slide) {
      if (observer) observer.unobserve(slide);
      const video = slide.querySelector("video");
      if (video) clearMedia(video);
      slide.remove();
    }
    feed.querySelectorAll(".slide").forEach((s, i) => {
      s.dataset.index = String(i);
    });
    const ac = prefetchControllers.get(key);
    if (ac) {
      ac.abort();
      prefetchControllers.delete(key);
    }
    prefetched.delete(key);
    if (!videos.length) {
      emptyEl.hidden = false;
      activeIndex = 0;
      return;
    }
    emptyEl.hidden = true;
    if (index < activeIndex) activeIndex -= 1;
    if (wasActive) activateIndex(Math.min(index, videos.length - 1), true);
  }

  function buildSlide(item, index) {
    const slide = document.createElement("section");
    slide.className = "slide";
    slide.dataset.index = String(index);
    slide.dataset.key = itemKey(item);
    slide.dataset.mime = mimeFor(item);

    const video = document.createElement("video");
    video.playsInline = true;
    video.setAttribute("playsinline", "");
    video.setAttribute("webkit-playsinline", "");
    video.loop = true;
    video.muted = muted;
    video.autoplay = false;
    video.preload = "none";
    video.controls = false;
    video.setAttribute("fetchpriority", "high");
    video.setAttribute("data-src", streamUrl(item));
    if (item.thumbnail_url) video.poster = item.thumbnail_url;
    video.setAttribute("data-type", mimeFor(item));
    const chip = priceChipHtml(item);
    if (chip) {
      slide.classList.add("locked");
      slide.insertAdjacentHTML("beforeend", chip);
    }
    paintCredentialChip(slide, item);

    const spinner = document.createElement("div");
    spinner.className = "spinner";

    const tags = (item.keywords || [])
      .slice(0, 6)
      .map((k) => `<span class="tag">#${escapeHtml(k)}</span>`)
      .join("");

    const meta = document.createElement("div");
    meta.className = "meta";
    if (item.username) {
      const who = document.createElement("button");
      who.type = "button";
      who.className = "who";
      who.textContent = `@${item.username}`;
      who.addEventListener("click", (e) => {
        e.stopPropagation();
        openProfile(item);
      });
      meta.appendChild(who);
    }
    const title = document.createElement("h2");
    title.textContent = item.title || "Untitled";
    const desc = document.createElement("p");
    desc.textContent = item.description || "";
    meta.appendChild(title);
    meta.appendChild(desc);
    if (tags) {
      const tagWrap = document.createElement("div");
      tagWrap.className = "tags";
      tagWrap.innerHTML = tags;
      meta.appendChild(tagWrap);
    }

    slide.appendChild(video);
    slide.appendChild(spinner);
    slide.appendChild(meta);

    const side = document.createElement("div");
    side.className = "side-actions";
    const avatarBtn = document.createElement("button");
    avatarBtn.type = "button";
    avatarBtn.className = "avatar-btn";
    avatarBtn.title = item.username ? `@${item.username}` : "Profile";
    avatarBtn.setAttribute(
      "aria-label",
      item.username ? `Open @${item.username}` : "Open profile"
    );
    paintAvatar(avatarBtn, item.username);
    const live = liveFor(item);
    setLiveRing(avatarBtn, !!live);
    if (live) {
      avatarBtn.setAttribute(
        "aria-label",
        item.username ? `Watch @${item.username} live` : "Watch live"
      );
    }
    avatarBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const stream = liveFor(item);
      if (stream) openLive(stream);
      else openProfile(item);
    });
    side.appendChild(avatarBtn);
    slide.appendChild(side);

    video.addEventListener("loadeddata", () => {
      slide.classList.add("ready");
    });
    video.addEventListener("play", () => {
      if (Number(slide.dataset.index) !== activeIndex) video.pause();
    });
    slide.addEventListener(
      "error",
      (e) => {
        const target = e.target;
        if (!target || (target !== video && target.tagName !== "SOURCE")) return;
        if (video.dataset.unloading === "1") {
          video.dataset.unloading = "";
          return;
        }
        dropVideo(slide.dataset.key);
      },
      true
    );
    video.addEventListener("click", () => {
      if (!slide.isConnected) return;
      if (itemPrice(item) && !item.price_unlocked) {
        openBuy(item);
        return;
      }
      if (credentialGates(item).length) {
        downloadAllowed(item).then((ok) => {
          if (!slide.isConnected) return;
          if (!ok) {
            openAccessGate(item, "video");
            return;
          }
          const url = streamUrl(item);
          if (url) video.setAttribute("data-src", url);
          if (video.paused) video.play().catch(() => {});
          else video.pause();
        });
        return;
      }
      if (video.paused) video.play().catch(() => {});
      else video.pause();
    });

    return slide;
  }

  function renderFeed() {
    dropped.clear();
    feed.innerHTML = "";
    if (!videos.length) {
      emptyEl.hidden = false;
      return;
    }
    emptyEl.hidden = true;
    const frag = document.createDocumentFragment();
    videos.forEach((item, i) => frag.appendChild(buildSlide(item, i)));
    feed.appendChild(frag);
    setupObserver();
    // layout then activate
    activateIndex(0, false);
    requestAnimationFrame(() => {
      const slide = feed.querySelector(".slide");
      if (slide) slide.scrollIntoView({ behavior: "auto", block: "start" });
    });
  }

  function pauseAllExcept(keep) {
    feed.querySelectorAll("video").forEach((v) => {
      if (v !== keep) {
        try {
          v.pause();
        } catch (_) {}
      }
    });
  }

  function ensureSrc(video) {
    const src = video.getAttribute("data-src");
    if (!src) return;
    if (video.getAttribute("src") === src) return;
    video.dataset.unloading = "";
    video.preload = "auto";
    while (video.firstChild) video.removeChild(video.firstChild);
    video.src = src;
  }

  function activateIndex(index, forceScroll) {
    if (!videos.length) return;
    index = Math.max(0, Math.min(index, videos.length - 1));
    activeIndex = index;
    const slides = feed.querySelectorAll(".slide");
    const slide = slides[index];
    if (!slide) return;
    const video = slide.querySelector("video");
    ensureSrc(video);
    video.muted = muted;
    syncBuyRail();
    if (!video.getAttribute("data-src")) {
      slide.classList.add("ready");
      return;
    }
    pauseAllExcept(video);
    const play = () => {
      if (!slide.isConnected || viewName !== "feed" || mediaMode === "photos" || !playerEl.hidden) return;
      video.play().catch((err) => {
        if (err && err.name === "NotAllowedError") return;
        if (video.error) dropVideo(slide.dataset.key);
      });
    };
    if (video.readyState >= 2) play();
    else {
      video.addEventListener("loadeddata", play, { once: true });
      setTimeout(() => {
        if (slide.isConnected && video.error && video.dataset.unloading !== "1") {
          dropVideo(slide.dataset.key);
        }
      }, 8000);
    }
    video.addEventListener(
      "playing",
      () => {
        const next = slides[index + 1];
        if (!next) return;
        const nv = next.querySelector("video");
        if (!nv) return;
        nv.autoplay = false;
        nv.preload = "auto";
        ensureSrc(nv);
        nv.pause();
      },
      { once: true }
    );

    slides.forEach((s, i) => {
      if (i === index) return;
      const v = s.querySelector("video");
      if (!v) return;
      if (Math.abs(i - index) <= 1 && (v.getAttribute("src") || v.querySelector("source"))) {
        return;
      }
      if (v.getAttribute("src") || v.querySelector("source")) {
        clearMedia(v);
        s.classList.remove("ready");
      }
    });

    if (forceScroll) {
      slide.scrollIntoView({ behavior: "auto", block: "start" });
    }
  }

  function setupObserver() {
    if (observer) observer.disconnect();
    observer = new IntersectionObserver(
      (entries) => {
        let best = null;
        let bestRatio = 0;
        for (const e of entries) {
          if (e.isIntersecting && e.intersectionRatio > bestRatio) {
            best = e;
            bestRatio = e.intersectionRatio;
          }
        }
        if (best && bestRatio >= 0.55) {
          const idx = Number(best.target.dataset.index);
          if (!Number.isNaN(idx) && idx !== activeIndex) {
            activateIndex(idx, false);
          }
        }
      },
      { root: feed, threshold: [0.55, 0.75, 0.9] }
    );
    feed.querySelectorAll(".slide").forEach((s) => observer.observe(s));
  }

  async function prefetchOne(item) {
    const key = itemKey(item);
    if (!item.stream_url || prefetched.has(key) || prefetchControllers.has(key)) {
      return;
    }
    const url = streamUrl(item);
    const ac = new AbortController();
    prefetchControllers.set(key, ac);
    try {
      const res = await fetch(url, {
        method: "GET",
        headers: { Range: `bytes=0-${PREFETCH_BYTES - 1}` },
        signal: ac.signal,
        credentials: "same-origin",
      });
      if (!(res.ok || res.status === 206)) {
        try {
          await res.arrayBuffer();
        } catch (_) {}
        dropVideo(key);
        return;
      }
      if (res.ok || res.status === 206) {
        await res.arrayBuffer();
        prefetched.add(key);
      }
    } catch (_) {
      /* aborted or network — ignore */
    } finally {
      prefetchControllers.delete(key);
    }
  }

  function prefetchAround(index) {
    const slice = videos.slice(index + 1, index + 1 + PREFETCH_COUNT);
    slice.forEach((item) => {
      prefetchOne(item);
    });
    const keep = new Set(
      videos
        .slice(Math.max(0, index), index + 1 + PREFETCH_COUNT)
        .map((v) => itemKey(v))
    );
    for (const [key, ac] of prefetchControllers) {
      if (!keep.has(key)) {
        ac.abort();
        prefetchControllers.delete(key);
      }
    }
  }

  function resetFeed() {
    dropped.clear();
    feed.innerHTML = "";
    videos = [];
    activeIndex = 0;
    if (observer) {
      observer.disconnect();
      observer = null;
    }
    emptyEl.hidden = true;
  }

  function appendSlide(item) {
    const index = videos.length;
    videos.push(item);
    feed.appendChild(buildSlide(item, index));
    emptyEl.hidden = true;
    setupObserver();
    if (index === 0) {
      activateIndex(0, false);
      requestAnimationFrame(() => {
        const slide = feed.querySelector(".slide");
        if (slide) slide.scrollIntoView({ behavior: "auto", block: "start" });
      });
    }
  }

  async function streamFailure(item, signal) {
    if (lockedPrice(item)) return "";
    const url = streamUrl(item);
    if (!url) return "missing stream";
    try {
      const res = await fetch(url, {
        method: "GET",
        headers: { Range: "bytes=0-1" },
        credentials: "same-origin",
        signal,
      });
      if (res.status !== 200 && res.status !== 206) {
        let msg = "";
        try {
          msg = (await res.text()).trim();
        } catch (_) {}
        return msg || `playback failed (${res.status})`;
      }
      const type = (res.headers.get("content-type") || "")
        .split(";")[0]
        .trim()
        .toLowerCase();
      if (
        type.startsWith("text/") ||
        type.includes("json") ||
        type.includes("html") ||
        type.includes("xml")
      ) {
        try {
          await res.arrayBuffer();
        } catch (_) {}
        return "stream is not a video";
      }
      if (res.headers.get("content-length") === "0") return "empty stream";
      try {
        await res.arrayBuffer();
      } catch (_) {}
      return "";
    } catch (err) {
      if (err && err.name === "AbortError") return "";
      return (err && err.message) || "playback failed";
    }
  }

  async function mapPool(items, limit, fn) {
    let cursor = 0;
    const workers = Math.min(limit, items.length);
    if (!workers) return;
    await Promise.all(
      Array.from({ length: workers }, async () => {
        while (cursor < items.length) {
          const item = items[cursor++];
          await fn(item);
        }
      })
    );
  }

  let loadedPin = null;

  function imageStream(item) {
    const mime = String((item && item.mime_type) || "").toLowerCase();
    if (mime && !mime.startsWith("image/")) return "";
    return streamUrl(item);
  }

  function photoSrc(item) {
    if (item && item.thumbnail_url) return item.thumbnail_url;
    return imageStream(item);
  }

  function buildPhotoSlide(item, index) {
    const slide = document.createElement("section");
    slide.className = "slide";
    slide.dataset.index = String(index);
    slide.dataset.key = itemKey(item);
    const img = document.createElement("img");
    img.className = "photo";
    img.alt = item.title || item.filename || "";
    const primary = item.thumbnail_url || "";
    const full = imageStream(item);
    img.addEventListener("load", () => slide.classList.add("ready"));
    img.addEventListener("error", () => {
      if (primary && full && img.dataset.fellback !== "1") {
        img.dataset.fellback = "1";
        img.src = full;
        return;
      }
      dropPhoto(slide.dataset.key);
    });
    img.src = primary || full;
    const chip = priceChipHtml(item);
    if (chip) {
      slide.classList.add("locked");
      slide.insertAdjacentHTML("beforeend", chip);
    }
    paintCredentialChip(slide, item);
    const tags = (item.keywords || [])
      .slice(0, 6)
      .map((k) => `<span class="tag">#${escapeHtml(k)}</span>`)
      .join("");
    const meta = document.createElement("div");
    meta.className = "meta";
    if (item.username) {
      const who = document.createElement("button");
      who.type = "button";
      who.className = "who";
      who.textContent = `@${item.username}`;
      who.addEventListener("click", (e) => {
        e.stopPropagation();
        openProfile(item);
      });
      meta.appendChild(who);
    }
    const title = document.createElement("h2");
    title.textContent = item.title || "Untitled";
    const desc = document.createElement("p");
    desc.textContent = item.description || "";
    meta.appendChild(title);
    meta.appendChild(desc);
    if (tags) {
      const tagWrap = document.createElement("div");
      tagWrap.className = "tags";
      tagWrap.innerHTML = tags;
      meta.appendChild(tagWrap);
    }
    const side = document.createElement("div");
    side.className = "side-actions";
    const avatarBtn = document.createElement("button");
    avatarBtn.type = "button";
    avatarBtn.className = "avatar-btn";
    avatarBtn.title = item.username ? `@${item.username}` : "Profile";
    paintAvatar(avatarBtn, item.username);
    const live = liveFor(item);
    setLiveRing(avatarBtn, !!live);
    avatarBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const stream = liveFor(item);
      if (stream) openLive(stream);
      else openProfile(item);
    });
    side.appendChild(avatarBtn);
    slide.appendChild(img);
    slide.appendChild(meta);
    slide.appendChild(side);
    return slide;
  }

  function dropPhoto(key) {
    if (!key || dropped.has(key)) return;
    const index = photos.findIndex((item) => itemKey(item) === key);
    if (index < 0) return;
    dropped.add(key);
    photos.splice(index, 1);
    const slide = photoPane.querySelector(`.slide[data-key="${CSS.escape(key)}"]`);
    if (slide) {
      if (photoObserver) photoObserver.unobserve(slide);
      slide.remove();
    }
    photoPane.querySelectorAll(".slide").forEach((s, i) => {
      s.dataset.index = String(i);
    });
    if (!photos.length) {
      photoEmpty.hidden = mediaMode !== "photos";
      photoIndex = 0;
      return;
    }
    photoEmpty.hidden = true;
    if (index < photoIndex) photoIndex -= 1;
    if (index === photoIndex) photoIndex = Math.min(index, photos.length - 1);
  }

  function renderPhotos() {
    photoPane.innerHTML = "";
    if (photoObserver) {
      photoObserver.disconnect();
      photoObserver = null;
    }
    if (!photos.length) {
      photoEmpty.hidden = mediaMode !== "photos";
      photoIndex = 0;
      return;
    }
    photoEmpty.hidden = true;
    const frag = document.createDocumentFragment();
    photos.forEach((item, i) => frag.appendChild(buildPhotoSlide(item, i)));
    photoPane.appendChild(frag);
    photoObserver = new IntersectionObserver(
      (entries) => {
        let best = null;
        let bestRatio = 0;
        for (const entry of entries) {
          if (entry.isIntersecting && entry.intersectionRatio > bestRatio) {
            best = entry;
            bestRatio = entry.intersectionRatio;
          }
        }
        if (!best || bestRatio < 0.55) return;
        const idx = Number(best.target.dataset.index);
        if (!Number.isNaN(idx)) photoIndex = idx;
      },
      { root: photoPane, threshold: [0.55, 0.75, 0.9] }
    );
    photoPane.querySelectorAll(".slide").forEach((slide) => photoObserver.observe(slide));
    photoIndex = 0;
    requestAnimationFrame(() => {
      const slide = photoPane.querySelector(".slide");
      if (slide) slide.scrollIntoView({ behavior: "auto", block: "start" });
    });
  }

  async function loadPhotos(q) {
    const gen = ++photoGen;
    showStatus("Loading photos…", 0);
    await loadMyBadges();
    try {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE), skip: "0" });
      if (q) params.set("q", q);
      const res = await fetch(`${API_PHOTOS}?${params}`, { credentials: "same-origin" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.status) throw new Error(data.error || "search failed");
      if (gen !== photoGen || mediaMode !== "photos") return;
      const seen = new Set();
      photos = [];
      for (const item of data.results || []) {
        if (isProfilePhoto(item) || hideAdult(item) || !photoSrc(item)) continue;
        const id = itemKey(item);
        const content = contentKey(item);
        if (seen.has(id) || (content && seen.has(content))) continue;
        seen.add(id);
        if (content) seen.add(content);
        photos.push(item);
      }
      photosLoadedQuery = q || "";
      renderPhotos();
      showStatus("");
    } catch (err) {
      if (gen !== photoGen) return;
      photos = [];
      renderPhotos();
      photoEmpty.hidden = false;
      showStatus(`Failed to load: ${err.message || err}`, 5000);
    }
  }

  function setMedia(mode) {
    mediaMode = mode === "photos" ? "photos" : "videos";
    const photosOn = mediaMode === "photos";
    appEl.classList.toggle("media-photos", photosOn);
    tabVideos.classList.toggle("active", !photosOn);
    tabPhotos.classList.toggle("active", photosOn);
    tabVideos.setAttribute("aria-selected", photosOn ? "false" : "true");
    tabPhotos.setAttribute("aria-selected", photosOn ? "true" : "false");
    feed.hidden = photosOn;
    photoPane.hidden = !photosOn;
    searchEl.placeholder = photosOn ? "Search photos…" : "Search videos…";
    hintEl.textContent = photosOn
      ? "Swipe or scroll · gift · report"
      : "Swipe or scroll · gift · live · report · mute";
    if (photosOn) {
      emptyEl.hidden = true;
      probeAbort.abort();
      pauseFeed();
      if (photosLoadedQuery !== query) loadPhotos(query);
      else photoEmpty.hidden = photos.length > 0;
    } else {
      photoEmpty.hidden = true;
      if (videos.length) activateIndex(activeIndex, false);
      else if (!loading) loadVideos(query);
    }
    if (viewName === "feed") {
      const next = mediaMode === "photos" ? "#/photos" : "#/";
      const hash = location.hash || "#/";
      if (hash !== next && (!hash || hash === "#" || hash === "#/" || hash === "#/photos")) {
        location.hash = next;
      }
    }
  }

  function titleFromName(name) {
    const base = String(name || "").replace(/\.[^.]+$/, "").trim();
    return base || "Upload";
  }

  function sourceSize(source) {
    return {
      w: source.naturalWidth || source.videoWidth || source.width || 0,
      h: source.naturalHeight || source.videoHeight || source.height || 0,
    };
  }

  function drawScaled(source, maxEdge) {
    const size = sourceSize(source);
    if (!size.w || !size.h) return null;
    const scale = Math.min(1, maxEdge / Math.max(size.w, size.h));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(size.w * scale));
    canvas.height = Math.max(1, Math.round(size.h * scale));
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
    return canvas;
  }

  function canvasJpeg(canvas, quality) {
    return new Promise((resolve, reject) => {
      canvas.toBlob((blob) => {
        if (!blob || !blob.size) reject(new Error("could not encode image"));
        else resolve(blob);
      }, "image/jpeg", quality);
    });
  }

  async function decodeImage(file) {
    if (typeof createImageBitmap === "function") {
      try {
        return {
          source: await createImageBitmap(file, { imageOrientation: "from-image" }),
          url: "",
        };
      } catch (_) {}
    }
    const url = URL.createObjectURL(file);
    const img = new Image();
    await new Promise((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error("could not read image"));
      img.src = url;
    });
    return { source: img, url };
  }

  async function jpegFile(source, maxEdge, quality, name, maxBytes) {
    let edge = maxEdge;
    let q = quality;
    let blob = null;
    while (edge >= 160) {
      const canvas = drawScaled(source, edge);
      if (!canvas) throw new Error("could not read image");
      blob = await canvasJpeg(canvas, q);
      if (!maxBytes || blob.size <= maxBytes) break;
      if (q > 0.45) q = Math.round((q - 0.08) * 100) / 100;
      else edge = Math.round(edge * 0.75);
    }
    return new File([blob], name, { type: "image/jpeg" });
  }

  async function compressPhoto(file) {
    const decoded = await decodeImage(file);
    const source = decoded.source;
    try {
      const size = sourceSize(source);
      const long = Math.max(size.w, size.h);
      const jpeg = /^image\/jpe?g$/i.test(file.type);
      const thumb = await jpegFile(source, 480, 0.72, "thumbnail.jpg", 500 * 1024);
      if (jpeg && long > 0 && long <= 1600 && file.size <= 1536 * 1024) {
        return { file, thumb };
      }
      const base = titleFromName(file.name);
      const compressed = await jpegFile(source, 1600, 0.82, `${base}.jpg`);
      return { file: compressed, thumb };
    } finally {
      if (decoded.url) URL.revokeObjectURL(decoded.url);
      if (source && typeof source.close === "function") source.close();
    }
  }

  function waitMedia(el, event) {
    return new Promise((resolve, reject) => {
      const ok = () => {
        cleanup();
        resolve();
      };
      const bad = () => {
        cleanup();
        reject(new Error("thumbnail failed"));
      };
      const cleanup = () => {
        el.removeEventListener(event, ok);
        el.removeEventListener("error", bad);
      };
      el.addEventListener(event, ok, { once: true });
      el.addEventListener("error", bad, { once: true });
    });
  }

  async function captureVideoThumbnail(file) {
    if (!file || !isVideoFile(file)) return null;
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;
    video.preload = "auto";
    video.src = url;
    try {
      const ready = waitMedia(video, "loadeddata");
      video.load();
      await ready;
      const duration = Number(video.duration);
      const at = Number.isFinite(duration) && duration > 0 ? Math.min(1, duration / 2) : 0;
      if (at > 0) {
        const seeked = waitMedia(video, "seeked");
        video.currentTime = at;
        await seeked;
      }
      const canvas = drawScaled(video, 480);
      if (!canvas) return null;
      const blob = await canvasJpeg(canvas, 0.72);
      return new File([blob], "thumbnail.jpg", { type: "image/jpeg" });
    } catch (_) {
      return null;
    } finally {
      video.removeAttribute("src");
      video.load();
      URL.revokeObjectURL(url);
    }
  }

  function abortError() {
    const err = new Error("upload aborted");
    err.aborted = true;
    return err;
  }

  function abortComposeUpload() {
    if (!composeBusy && !composeXhr) return;
    composeReq += 1;
    const xhr = composeXhr;
    composeXhr = null;
    if (xhr && xhr.readyState !== 4) xhr.abort();
    stopComposePoll();
  }

  function postForm(url, fd, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      composeXhr = xhr;
      xhr.open("POST", url);
      xhr.withCredentials = true;
      xhr.upload.onprogress = (ev) => {
        if (!ev.lengthComputable) return;
        if (onProgress) onProgress(ev.loaded, ev.total);
        else showStatus(`Uploading ${Math.round((ev.loaded / ev.total) * 100)}%`, 0);
      };
      xhr.upload.onload = () => {
        if (onProgress) onProgress(-1, -1);
      };
      const finish = () => {
        if (composeXhr === xhr) composeXhr = null;
      };
      xhr.onload = () => {
        finish();
        let data = {};
        try {
          data = JSON.parse(xhr.responseText || "{}");
        } catch (_) {}
        if (xhr.status === 401) {
          const err = new Error("Unlock File Announcements to upload");
          err.status = 401;
          reject(err);
          return;
        }
        if (xhr.status < 200 || xhr.status >= 300 || data.status === false) {
          const err = new Error(data.error || "upload failed");
          err.status = xhr.status;
          reject(err);
          return;
        }
        resolve(data);
      };
      xhr.onerror = () => {
        finish();
        reject(new Error("upload failed"));
      };
      xhr.onabort = () => {
        finish();
        reject(abortError());
      };
      xhr.send(fd);
    });
  }

  function isImageFile(file) {
    return (
      String(file.type || "").startsWith("image/") ||
      /\.(jpe?g|png|gif|webp|bmp|heic|heif)$/i.test(file.name)
    );
  }

  function isVideoFile(file) {
    return (
      String(file.type || "").startsWith("video/") ||
      /\.(mp4|webm|mov|m4v|ogg|ogv|mkv)$/i.test(file.name || "")
    );
  }

  function fmtBytes(n) {
    n = Number(n) || 0;
    if (n < 1024) return `${n} B`;
    const units = ["KB", "MB", "GB", "TB"];
    let i = -1;
    do {
      n /= 1024;
      i++;
    } while (n >= 1024 && i < units.length - 1);
    return `${n.toFixed(n >= 10 ? 0 : 1)} ${units[i]}`;
  }

  function newUploadId() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return `up${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;
  }

  function setComposeMsg(text, kind) {
    composeMsg.textContent = text || "";
    composeMsg.hidden = !text;
    composeMsg.classList.toggle("err", kind === "err");
    composeMsg.classList.toggle("ok", kind === "ok");
  }

  function setComposeLocked(on) {
    composeLocked = on;
    composeSignin.hidden = !on;
    syncComposeControls();
  }

  function syncComposeControls() {
    const off = composeBusy || composeLocked;
    composeFields.querySelectorAll("input, textarea, select, button").forEach((el) => {
      el.disabled = off;
    });
    composeSubmit.textContent = composeBusy ? "Uploading…" : "Upload & announce";
    composeForm.setAttribute("aria-busy", composeBusy ? "true" : "false");
  }

  function showComposeProgress(pct, label) {
    composeProgress.hidden = false;
    composeProgressLabel.textContent = label;
    if (pct == null) {
      composeProgressBar.classList.add("indeterminate");
      composeProgressBar.style.width = "";
      composeProgressTrack.removeAttribute("aria-valuenow");
      composeProgressTrack.setAttribute("aria-valuetext", label);
    } else {
      const n = Math.max(0, Math.min(100, pct));
      composeProgressBar.classList.remove("indeterminate");
      composeProgressBar.style.width = `${n}%`;
      composeProgressTrack.setAttribute("aria-valuenow", String(n));
      composeProgressTrack.setAttribute("aria-valuetext", label);
    }
  }

  function hideComposeProgress() {
    composeProgress.hidden = true;
    composeProgressBar.classList.remove("indeterminate");
    composeProgressBar.style.width = "0";
  }

  function stopComposePoll() {
    if (composePoll) {
      clearInterval(composePoll);
      composePoll = null;
    }
  }

  function startComposePoll(id, hasFile) {
    stopComposePoll();
    const tick = async () => {
      try {
        const res = await fetch(`${API_UPLOADS}/${encodeURIComponent(id)}`, {
          credentials: "same-origin",
        });
        const data = await res.json().catch(() => ({}));
        const p = data.result || {};
        if (p.phase === "sia" || (hasFile && p.phase === "receiving")) {
          const shards = p.shards || 0;
          const extra = shards
            ? ` · ${shards} shard${shards === 1 ? "" : "s"} · ${fmtBytes(p.shard_bytes)}`
            : "";
          showComposeProgress(null, `Uploading to Sia${extra}`);
        } else if (p.phase === "announcing" || p.phase === "receiving") {
          showComposeProgress(null, "Announcing on-chain…");
        } else if (p.phase === "done") {
          showComposeProgress(100, "Done");
        } else if (p.phase === "error") {
          showComposeProgress(null, p.error || "Upload failed");
        }
      } catch (_) {}
    };
    tick();
    composePoll = setInterval(tick, 400);
  }

  function applyComposeType(route, force) {
    const next = String((route && route.type) || "");
    if (!force && composeTypeApplied === next) return;
    composeTypeApplied = next;
    composeType.value = next;
  }

  async function loadComposeBackends() {
    const res = await fetch(API_BACKENDS, { credentials: "same-origin" });
    const data = await res.json().catch(() => ({}));
    if (res.status === 401) {
      const err = new Error("Unlock File Announcements to upload");
      err.status = 401;
      throw err;
    }
    if (!res.ok || data.status === false) {
      throw new Error(data.error || `HTTP ${res.status}`);
    }
    const current = composeBackend.value;
    const opts = (data.results || []).filter((b) => b.implemented);
    composeBackend.innerHTML = opts
      .map((b) => `<option value="${escapeHtml(b.name)}">${escapeHtml(b.label)}</option>`)
      .join("");
    if (current && opts.some((b) => b.name === current)) composeBackend.value = current;
  }

  async function openCompose() {
    const gen = ++composeGen;
    applyComposeType(parseRoute());
    if (!composeBusy) setComposeMsg("");
    try {
      const res = await fetch(API_ME, { credentials: "same-origin" });
      const data = await res.json().catch(() => ({}));
      if (gen !== composeGen || parseRoute().view !== "upload") return;
      if (data.authenticated !== true) {
        setComposeLocked(true);
        setComposeMsg("Sign in to upload photos and videos.");
        return;
      }
      setComposeLocked(false);
      await loadComposeBackends();
    } catch (err) {
      if (gen !== composeGen || parseRoute().view !== "upload") return;
      if (err.status === 401) setComposeLocked(true);
      setComposeMsg(err.message || "Could not open upload", "err");
    }
  }

  async function submitCompose(e) {
    e.preventDefault();
    if (composeBusy || composeLocked) return;
    const fd = new FormData(composeForm);
    const file = fd.get("file");
    const hasFile = !!(file && file.name && file.size);
    const image = hasFile && isImageFile(file);
    const video = hasFile && isVideoFile(file);
    const uploadId = newUploadId();
    fd.set("upload_id", uploadId);
    const req = ++composeReq;
    composeBusy = true;
    syncComposeControls();
    setComposeMsg("");
    let announced = false;
    try {
      if (image) {
        showComposeProgress(0, "Resizing photo…");
        const packed = await compressPhoto(file);
        fd.set("file", packed.file, packed.file.name);
        fd.set("thumbnail", packed.thumb, "thumbnail.jpg");
      } else if (video) {
        showComposeProgress(0, "Capturing thumbnail…");
        const thumb = await captureVideoThumbnail(file);
        if (thumb) fd.set("thumbnail", thumb, "thumbnail.jpg");
      }
      if (req !== composeReq) throw abortError();
      showComposeProgress(hasFile ? 0 : null, hasFile ? "Sending to node 0%" : "Announcing…");
      const data = await postForm(API_FILES, fd, (loaded, total) => {
        if (loaded < 0) {
          showComposeProgress(null, hasFile ? "Uploading to Sia…" : "Announcing…");
          startComposePoll(uploadId, hasFile);
          return;
        }
        const pct = total ? Math.round((loaded / total) * 100) : 0;
        showComposeProgress(pct, `Sending to node ${pct}%`);
      });
      if (req !== composeReq) throw abortError();
      announced = true;
      stopComposePoll();
      showComposeProgress(100, "Done");
      if (parseRoute().view === "upload") {
        composeForm.reset();
        composeAutoTitle = "";
        applyComposeType(parseRoute(), true);
        setComposeMsg(`Announced${data.result && data.result.file_id ? `: ${data.result.file_id}` : ""}`, "ok");
      }
      photosLoadedQuery = null;
      loadedPin = null;
    } catch (err) {
      stopComposePoll();
      hideComposeProgress();
      if (err.status === 401) setComposeLocked(true);
      setComposeMsg(err.message || "upload failed", "err");
    } finally {
      stopComposePoll();
      composeBusy = false;
      syncComposeControls();
      if (announced) hideComposeProgress();
    }
  }

  async function loadVideos(q, pinId) {
    pinId = pinId || "";
    loadedPin = pinId;
    probeAbort.abort();
    probeAbort = new AbortController();
    const signal = probeAbort.signal;
    const gen = ++feedGen;
    await loadMyBadges();
    loading = true;
    showStatus("Loading videos…", 0);
    resetFeed();
    prefetched.clear();
    for (const ac of prefetchControllers.values()) ac.abort();
    prefetchControllers.clear();
    try {
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        skip: "0",
      });
      if (q) params.set("q", q);
      let pinned = null;
      if (pinId) {
        const pinRes = await fetch(
          `${API_VIDEOS}?transaction_id=${encodeURIComponent(pinId)}`,
          { credentials: "same-origin", signal }
        );
        if (pinRes.ok) {
          const pinData = await pinRes.json();
          pinned = (pinData.results || [])[0] || null;
        }
        if (!pinned) showStatus("Video not found", 4000);
      }
      const res = await fetch(`${API_VIDEOS}?${params}`, {
        credentials: "same-origin",
        signal,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.status) throw new Error(data.error || "search failed");
      const seen = new Set();
      const candidates = [];
      if (pinned && videoCandidate(pinned) && !hideAdult(pinned)) candidates.push(pinned);
      for (const item of data.results || []) {
        if (pinId && item.transaction_id === pinId) continue;
        if (!videoCandidate(item) || hideAdult(item)) continue;
        const id = itemKey(item);
        const content = contentKey(item);
        if (seen.has(id) || (content && seen.has(content))) continue;
        seen.add(id);
        if (content) seen.add(content);
        candidates.push(item);
      }
      if (!pinId) {
        const open = candidates.findIndex((item) => !lockedPrice(item));
        if (open > 0) candidates.unshift(candidates.splice(open, 1)[0]);
      }
      let firstFailure = "";
      const accept = async (item) => {
        if (gen !== feedGen || signal.aborted) return;
        const failure = await streamFailure(item, signal);
        if (failure) {
          if (!firstFailure) firstFailure = failure;
          return;
        }
        if (gen !== feedGen || signal.aborted) return;
        appendSlide(item);
      };
      if (candidates[0]) {
        showStatus("Opening video…", 0);
        await accept(candidates[0]);
      }
      if (gen !== feedGen) return;
      const probeRest = async () => {
        await mapPool(candidates.slice(1), 1, accept);
        if (gen !== feedGen) return;
        if (!videos.length) {
          if (mediaMode !== "photos") emptyEl.hidden = false;
          showStatus(firstFailure || "", firstFailure ? 8000 : 0);
        } else {
          showStatus(`${videos.length} video${videos.length === 1 ? "" : "s"}`);
        }
      };
      if (!candidates[0]) {
        if (mediaMode !== "photos") emptyEl.hidden = false;
        showStatus("");
      } else if (!videos.length) {
        if (mediaMode !== "photos") emptyEl.hidden = false;
        showStatus(firstFailure || "playback failed", 8000);
        probeRest();
      } else {
        showStatus("");
        probeRest();
      }
    } catch (err) {
      if (gen !== feedGen || signal.aborted) return;
      resetFeed();
      if (mediaMode !== "photos") emptyEl.hidden = false;
      showStatus(`Failed to load: ${err.message || err}`, 5000);
    } finally {
      if (gen === feedGen) loading = false;
    }
  }

  muteBtn.addEventListener("click", () => {
    muted = !muted;
    muteBtn.textContent = muted ? "🔇" : "🔊";
    muteBtn.setAttribute("aria-label", muted ? "Unmute" : "Mute");
    feed.querySelectorAll("video").forEach((v) => {
      v.muted = muted;
    });
    playerVideo.muted = muted;
    const active = feed.querySelectorAll("video")[activeIndex];
    if (active && !muted && playerEl.hidden) active.play().catch(() => {});
    if (!playerEl.hidden && !muted) playerVideo.play().catch(() => {});
  });

  refreshBtn.addEventListener("click", () => {
    if (mediaMode === "photos") {
      photosLoadedQuery = null;
      loadPhotos(query);
    } else loadVideos(query);
    loadLive();
  });

  function fillReasonSelect() {
    reportReason.innerHTML = "";
    reasonCodes.forEach((r) => {
      const opt = document.createElement("option");
      opt.value = r.value;
      opt.textContent = r.label || r.name || r.value;
      reportReason.appendChild(opt);
    });
  }

  async function loadReasons() {
    try {
      const res = await fetch(API_REASONS, { credentials: "same-origin" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.status) throw new Error(data.error || "reasons failed");
      reasonCodes = data.results || [];
      fillReasonSelect();
    } catch (err) {
      reasonCodes = [];
      console.warn("takedown reasons:", err);
    }
  }

  function creatorAddress(item) {
    return String((item && item.public_key_hash) || "").trim();
  }

  function syncBuyRail() {
    if (!railBuy) return;
    const item = activeItem();
    const priced = !!(item && itemPrice(item) && !item.price_unlocked);
    const missing = credentialGates(item).length && !matchingBadges(item);
    railBuy.hidden = !priced && !missing;
    railBuy.textContent = missing ? "Locked" : "Buy";
    railBuy.title = missing ? credentialMessage(item) : "Buy";
    railBuy.setAttribute("aria-label", railBuy.title);
  }

  function unlockPaid(item, playFeed) {
    if (!item) return;
    item.price_unlocked = true;
    const url = paidStreamUrl(item);
    if (!url) return;
    item.stream_url = url;
    const key = itemKey(item);
    const slide = feed.querySelector(`[data-key="${CSS.escape(key)}"]`);
    if (slide) {
      slide.classList.remove("locked");
      const badge = slide.querySelector(".price-chip:not(.cred-chip)");
      if (badge) badge.remove();
      const video = slide.querySelector("video");
      if (video) {
        video.setAttribute("data-src", url);
        ensureSrc(video);
        if (playFeed !== false) video.play().catch(() => {});
      }
    }
    if (photoPane) {
      const photoSlide = photoPane.querySelector(`[data-key="${CSS.escape(key)}"]`);
      if (photoSlide) {
        photoSlide.classList.remove("locked");
        const badge = photoSlide.querySelector(".price-chip:not(.cred-chip)");
        if (badge) badge.remove();
      }
    }
    syncBuyRail();
  }

  function closeBuy() {
    if (typeof buyDlg.close === "function") buyDlg.close();
    else buyDlg.removeAttribute("open");
  }

  function isPhotoItem(item) {
    if (!item) return false;
    const mime = String(item.mime_type || "").toLowerCase();
    if (mime.startsWith("image/")) return true;
    if (mime.startsWith("video/")) return false;
    return photos.includes(item) || profilePhotos.includes(item);
  }

  function revealPaid(item) {
    unlockPaid(item, false);
    closeBuy();
    if (!item) return;
    if (viewName === "profile") renderProfileGrid();
    if (isPhotoItem(item)) openPhoto(item, true);
    else openPlayer(item, true);
    const key = itemKey(item);
    const videoIndex = videos.findIndex((row) => itemKey(row) === key);
    if (videoIndex >= 0) activateIndex(videoIndex, true);
    const photoIdx = photos.findIndex((row) => itemKey(row) === key);
    if (photoIdx >= 0 && photoPane) {
      photoIndex = photoIdx;
      const slide = photoPane.querySelector(`[data-key="${CSS.escape(key)}"]`);
      if (slide) slide.scrollIntoView({ behavior: "auto", block: "start" });
    }
  }

  async function checkPurchase(item) {
    const id = String((item && item.transaction_id) || "").trim();
    if (!id) throw new Error("This post has no announcement id");
    const res = await fetch(`${API_PURCHASE}?transaction_id=${encodeURIComponent(id)}`, {
      credentials: "same-origin",
    });
    const data = await res.json().catch(() => ({}));
    if (res.status === 401) {
      throw new Error("Sign in on your node to pay from that identity");
    }
    if (!res.ok || data.status === false) {
      throw new Error(data.error || `HTTP ${res.status}`);
    }
    return data;
  }

  async function openBuy(item) {
    if (!(await downloadAllowed(item))) {
      openAccessGate(item);
      return;
    }
    buyItem = item || null;
    const price = itemPrice(item);
    const address = creatorAddress(item);
    if (!price || !address) {
      showStatus("This post has no sale address", 2500);
      return;
    }
    const who = item.username ? `@${item.username}` : "creator";
    buyTo.textContent = who;
    buyPrice.textContent = `${price} YDA`;
    buyAddress.textContent = address;
    buyQr.innerHTML = "";
    buyNote.textContent = `Scan with an external wallet and pay the exact amount shown. Once it is broadcast, I've paid. ${grantNote(item)}`;
    if (buyNode) buyNode.hidden = true;
    if (typeof QRCode === "function") {
      new QRCode(buyQr, {
        text: address,
        width: 220,
        height: 220,
        correctLevel: QRCode.CorrectLevel.M,
      });
    }
    if (typeof buyDlg.showModal === "function") buyDlg.showModal();
    else buyDlg.setAttribute("open", "");
    try {
      const me = await fetch(API_ME, { credentials: "same-origin" });
      const whoami = await me.json().catch(() => ({}));
      if (buyNode && whoami.authenticated === true) buyNode.hidden = false;
      const res = await fetch(`${API_PURCHASE}/invoice`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ transaction_id: item.transaction_id }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.status) {
        throw new Error(data.error || "could not start checkout");
      }
      buyPrice.textContent = `${data.amount} YDA`;
      buyNote.textContent = `Pay exactly ${data.amount} YDA to the address above from any wallet. This checkout is saved in this browser only. ${grantNote(item)}`;
    } catch (err) {
      buyNote.textContent = err.message || "Could not start checkout";
    }
  }

  async function payFromNode(item) {
    const price = itemPrice(item);
    const address = creatorAddress(item);
    const res = await fetch("/send-transaction", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ address, value: Number(price) }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.error || data.status === "error") {
      throw new Error(data.error || data.message || "this node wallet could not pay");
    }
    buyNote.textContent = "Payment sent from this node. Checking the mempool…";
  }

  railBuy.addEventListener("click", () => openBuy(activeItem()));
  buyClose.addEventListener("click", () => {
    if (typeof buyDlg.close === "function") buyDlg.close();
    else buyDlg.removeAttribute("open");
  });
  buyCheck.addEventListener("click", async () => {
    const item = buyItem || activeItem();
    const label = buyCheck.textContent;
    buyCheck.disabled = true;
    buyCheck.textContent = "Checking…";
    buyNote.textContent = "Checking the mempool and chain…";
    try {
      const res = await fetch(`${API_PURCHASE}/redeem`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ transaction_id: item && item.transaction_id }),
      });
      const data = await res.json().catch(() => ({}));
      if (!data.paid) {
        buyNote.textContent = data.expired
          ? data.error || "Access for this payment has expired. Pay again to keep watching."
          : data.error || "No payment in the mempool or on chain for this checkout yet.";
        return;
      }
      if (data.access) item.access = data.access;
      if (data.payment_id) item.payment_id = data.payment_id;
      revealPaid(item);
    } catch (err) {
      buyNote.textContent = err.message || "Could not check payment";
    } finally {
      buyCheck.disabled = false;
      buyCheck.textContent = label;
    }
  });
  if (buyNode) {
    buyNode.addEventListener("click", async () => {
      const item = buyItem || activeItem();
      buyNode.disabled = true;
      try {
        await payFromNode(item);
        const data = await checkPurchase(item);
        if (!data.paid) {
          buyNote.textContent = data.expired
            ? data.error || "Access for this payment has expired. Pay again to keep watching."
            : "Sent. Not in the mempool yet.";
          return;
        }
        revealPaid(item);
      } catch (err) {
        buyNote.textContent = err.message || "Could not pay from this node";
      } finally {
        buyNode.disabled = false;
      }
    });
  }

  function selectedChain() {
    return GIFT_CHAINS.find((c) => c.id === giftChain.value) || GIFT_CHAINS[0];
  }

  function fillGiftChain() {
    giftChain.innerHTML = "";
    GIFT_CHAINS.forEach((chain) => {
      const opt = document.createElement("option");
      opt.value = chain.id;
      opt.textContent = chain.label;
      giftChain.appendChild(opt);
    });
    giftChain.value = GIFT_CHAINS[0].id;
  }

  function fillGiftGrid() {
    giftGrid.innerHTML = "";
    const symbol = selectedChain().symbol;
    GIFTS.forEach((gift) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "gift-card";
      btn.innerHTML = `<em>${gift.emoji}</em><strong>${escapeHtml(gift.name)}</strong><span>${gift.price} ${escapeHtml(symbol)}</span>`;
      btn.addEventListener("click", () => selectGift(gift));
      giftGrid.appendChild(btn);
    });
  }

  function showGiftPicker() {
    giftPick.hidden = false;
    giftPay.hidden = true;
    giftQr.innerHTML = "";
  }

  function renderGiftQr(address) {
    giftQr.innerHTML = "";
    if (typeof QRCode !== "function") {
      giftNote.textContent = "QR library unavailable. Copy the address below.";
      return;
    }
    new QRCode(giftQr, {
      text: address,
      width: 220,
      height: 220,
      correctLevel: QRCode.CorrectLevel.M,
    });
    giftNote.textContent = "Scan to pay this address.";
  }

  function selectGift(gift) {
    const address = creatorAddress(giftTarget);
    const chain = selectedChain();
    const who = giftTarget && giftTarget.username ? `@${giftTarget.username}` : "creator";
    giftPicked.textContent = `${gift.emoji} ${gift.name} · ${gift.price} ${chain.symbol} · ${chain.label}`;
    giftAddress.textContent = address;
    giftPick.hidden = true;
    giftPay.hidden = false;
    if (!address) {
      giftQr.innerHTML = "";
      giftAddress.textContent = "";
      giftNote.textContent = "This announcement has no public key hash.";
      return;
    }
    renderGiftQr(address);
  }

  function openGift(item) {
    giftTarget = item || null;
    const who = item && item.username ? `@${item.username}` : "this creator";
    const address = creatorAddress(item);
    giftTo.textContent = address ? `To ${who}` : "This announcement has no public key hash";
    fillGiftChain();
    fillGiftGrid();
    showGiftPicker();
    giftDlg.showModal();
  }

  giftClose.addEventListener("click", () => {
    giftDlg.close();
    giftTarget = null;
  });
  giftBack.addEventListener("click", showGiftPicker);
  giftChain.addEventListener("change", () => {
    fillGiftGrid();
    if (!giftPay.hidden) showGiftPicker();
  });

  function openReport(item) {
    if (!item || !item.transaction_id) {
      showStatus("Cannot report: missing announcement transaction id", 4000);
      return;
    }
    reportTarget = item;
    reportTitle.textContent = item.title || item.filename || item.file_id || "Video";
    reportErr.hidden = true;
    reportErr.textContent = "";
    reportSubmit.disabled = false;
    if (!reasonCodes.length) {
      loadReasons().then(() => {
        if (!reasonCodes.length) {
          reportErr.textContent = "Could not load takedown reason codes";
          reportErr.hidden = false;
        }
        reportDlg.showModal();
      });
      return;
    }
    reportDlg.showModal();
  }

  reportCancel.addEventListener("click", () => {
    reportDlg.close();
    reportTarget = null;
  });

  reportForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!reportTarget || !reportTarget.transaction_id) {
      reportErr.textContent = "Missing transaction id";
      reportErr.hidden = false;
      return;
    }
    const reason = reportReason.value;
    if (!reason) {
      reportErr.textContent = "Select a reason";
      reportErr.hidden = false;
      return;
    }
    reportSubmit.disabled = true;
    reportErr.hidden = true;
    try {
      const res = await fetch(API_TAKEDOWN, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transaction_id: reportTarget.transaction_id,
          reason_code: reason,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.status) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      reportDlg.close();
      const tid = reportTarget.transaction_id;
      reportTarget = null;
      showStatus("Takedown announced on-chain", 4000);
      videos = videos.filter((v) => v.transaction_id !== tid);
      photos = photos.filter((item) => item.transaction_id !== tid);
      if (mediaMode === "photos") renderPhotos();
      else renderFeed();
    } catch (err) {
      reportErr.textContent = err.message || String(err);
      reportErr.hidden = false;
      reportSubmit.disabled = false;
    }
  });

  let searchTimer = null;
  searchEl.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      query = searchEl.value.trim();
      if (mediaMode === "photos") {
        photosLoadedQuery = null;
        loadPhotos(query);
      } else loadVideos(query);
    }, 350);
  });

  window.addEventListener("keydown", (e) => {
    if (reportDlg.open || viewName !== "feed") return;
    if (e.target === searchEl) return;
    const pane = mediaMode === "photos" ? photoPane : feed;
    const count = mediaMode === "photos" ? photos.length : videos.length;
    const index = mediaMode === "photos" ? photoIndex : activeIndex;
    if (e.key === "ArrowDown" || e.key === "j") {
      e.preventDefault();
      const next = Math.min(index + 1, count - 1);
      const slide = pane.querySelectorAll(".slide")[next];
      if (slide) slide.scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (e.key === "ArrowUp" || e.key === "k") {
      e.preventDefault();
      const prev = Math.max(index - 1, 0);
      const slide = pane.querySelectorAll(".slide")[prev];
      if (slide) slide.scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (e.key === "m") {
      if (mediaMode !== "photos") muteBtn.click();
    } else if (e.key === "r") {
      const item = activeItem();
      if (item) openReport(item);
    } else if (e.key === " " && mediaMode !== "photos") {
      e.preventDefault();
      const v = feed.querySelectorAll("video")[activeIndex];
      if (!v) return;
      if (v.paused) v.play().catch(() => {});
      else v.pause();
    }
  });

  function displayName(profile) {
    const name = String((profile && profile.username) || "").trim();
    if (name) return `@${name}`;
    return "Profile";
  }

  function openProfile(item) {
    const name = String((item && item.username) || "").trim().replace(/^@/, "");
    if (name) {
      location.hash = `#/@${encodeURIComponent(name)}`;
      return;
    }
    const params = new URLSearchParams();
    if (item && item.owner) params.set("owner", item.owner);
    location.hash = `#/profile?${params.toString()}`;
  }

  function parseRoute() {
    const raw = (location.hash || "#/").replace(/^#/, "");
    const path = raw.split("?")[0];
    const params = new URLSearchParams(raw.includes("?") ? raw.slice(raw.indexOf("?") + 1) : "");
    const transaction_id = params.get("transaction_id") || "";
    const owner = params.get("owner") || "";
    const username = (params.get("username") || "").replace(/^@/, "");
    const atBadges = path.match(/^\/@([^/]+)\/badges(?:\/([^/]+))?$/);
    if (atBadges) {
      return {
        view: "badges",
        username: decodeURIComponent(atBadges[1]),
        owner: "",
        transaction_id: "",
        badge_id: atBadges[2] ? decodeURIComponent(atBadges[2]) : "",
      };
    }
    const profileBadges = path.match(/^\/profile\/badges(?:\/([^/]+))?$/);
    if (profileBadges) {
      return {
        view: "badges",
        username,
        owner,
        transaction_id,
        badge_id: profileBadges[1] ? decodeURIComponent(profileBadges[1]) : "",
      };
    }
    if (path === "/upload" || path === "upload") {
      return { view: "upload", type: params.get("type") || "" };
    }
    if (path === "/publish" || path === "publish") {
      return { view: "publish" };
    }
    if (path === "/me" || path === "me") {
      return { view: "me" };
    }
    if (path.startsWith("/@") && path.length > 2) {
      return {
        view: "profile",
        username: decodeURIComponent(path.slice(2)),
        owner: "",
        transaction_id: "",
      };
    }
    if (path === "/profile" && username) {
      return { view: "profile", username, owner: "", transaction_id: "" };
    }
    if (path === "/photos") {
      return { view: "feed", media: "photos", transaction_id };
    }
    if (path === "/profile" && transaction_id && !owner) {
      return { view: "feed", media: "videos", transaction_id };
    }
    if (path === "/profile") {
      return { view: "profile", owner, transaction_id, username: "" };
    }
    return {
      view: "feed",
      media: "videos",
      transaction_id: path === "/" || path === "" ? transaction_id : "",
    };
  }

  function badgesHash(route, badgeId) {
    const id = badgeId ? `/${encodeURIComponent(badgeId)}` : "";
    if (route && route.username) {
      return `#/@${encodeURIComponent(route.username)}/badges${id}`;
    }
    const params = new URLSearchParams();
    if (route && route.owner) params.set("owner", route.owner);
    else if (route && route.transaction_id) params.set("transaction_id", route.transaction_id);
    const query = params.toString();
    return `#/profile/badges${id}${query ? `?${query}` : ""}`;
  }

  function claimLabel(claim) {
    if (claim === "ageOver18" || claim === "isOver18") return "18+";
    return claim || "Credential";
  }

  function claimMark(claim) {
    if (claim === "ageOver18" || claim === "isOver18") return "18+";
    return "🏅";
  }

  function shortId(value) {
    const text = String(value || "");
    if (!text) return "—";
    if (text.length <= 18) return text;
    return `${text.slice(0, 8)}…${text.slice(-6)}`;
  }

  function formatWhen(value) {
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0) return "";
    try {
      return new Date(n * 1000).toLocaleDateString();
    } catch (_) {
      return "";
    }
  }

  function formatExpiry(value) {
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0) return "—";
    try {
      return new Date(n * 1000).toLocaleString();
    } catch (_) {
      return "—";
    }
  }

  function isExpired(item) {
    const n = Number(item && item.expires);
    return Number.isFinite(n) && n > 0 && n * 1000 < Date.now();
  }

  function issuerLabel(item) {
    if (item && item.issuer_username) return `@${item.issuer_username}`;
    return shortId(item && item.issuer_username_signature);
  }

  function proofLabel(value) {
    if (value === true) return "Valid";
    if (value === false) return "Invalid";
    return "Not present";
  }

  function subjectClaims(vc) {
    const subject = vc && vc.credentialSubject;
    if (!subject || typeof subject !== "object") return "";
    return Object.keys(subject)
      .filter((key) => key !== "id")
      .map((key) => `${key}: ${subject[key]}`)
      .join(", ");
  }

  function credentialBody(item) {
    const vc = Object.assign({}, (item && item.vc) || {});
    delete vc.proof;
    try {
      return JSON.stringify(vc, null, 2);
    } catch (_) {
      return "";
    }
  }

  function renderBadgeDetail(item) {
    badgeList.hidden = true;
    badgeEmpty.hidden = true;
    badgeDetail.hidden = false;
    if (!item) {
      badgesTitle.textContent = "Badge";
      badgeDetail.innerHTML = `<p class="badge-status">Credential not found</p>`;
      return;
    }
    const expired = isExpired(item);
    const vc = item.vc || {};
    const types = Array.isArray(vc.type) ? vc.type.filter(Boolean).join(", ") : "";
    const rows = [
      ["Issuer", issuerLabel(item)],
      ["Expires", formatExpiry(item.expires)],
      ["Source", item.source === "mempool" ? "Mempool" : "On chain"],
      ["Proof", proofLabel(item.proof_valid)],
      ["Types", types],
      ["Claims", subjectClaims(vc)],
      ["Subject", item.subject_username ? `@${item.subject_username}` : shortId(item.subject_username_signature)],
      ["Transaction", item.transaction_id],
      ["Issuer announcement", item.issuer_identity_announcement],
    ].filter((row) => row[1]);
    badgesTitle.textContent = claimLabel(item.claim);
    const statusClass = expired ? "bad" : item.proof_valid === false ? "bad" : "ok";
    const status = expired ? "Expired" : "Received credential";
    badgeDetail.innerHTML = `
      <h2>${escapeHtml(claimLabel(item.claim))}</h2>
      <p class="badge-status ${statusClass}">${escapeHtml(status)}</p>
      ${rows
        .map(
          ([label, value]) =>
            `<div class="kv"><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></div>`
        )
        .join("")}
      <pre class="badge-raw">${escapeHtml(credentialBody(item))}</pre>
    `;
  }

  function renderBadgeList(items) {
    badgeItems = items || [];
    badgeDetail.hidden = true;
    badgeDetail.innerHTML = "";
    badgesTitle.textContent = "Badges";
    badgeList.innerHTML = "";
    if (!badgeItems.length) {
      badgeList.hidden = true;
      badgeEmpty.hidden = false;
      badgeEmpty.textContent = "No credential announcements yet";
      return;
    }
    badgeEmpty.hidden = true;
    badgeList.hidden = false;
    badgeItems.forEach((item) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = `badge-row${isExpired(item) ? " expired" : ""}`;
      const when = formatWhen(item.time) || formatWhen(item.expires);
      row.innerHTML = `
        <span class="badge-mark">${escapeHtml(claimMark(item.claim))}</span>
        <span><strong>${escapeHtml(claimLabel(item.claim))}</strong><em>${escapeHtml(issuerLabel(item))}</em></span>
        <span class="when">${escapeHtml(when)}</span>
      `;
      row.addEventListener("click", () => {
        armBadgeDetailBack = true;
        location.hash = badgesHash(parseRoute(), item.transaction_id);
      });
      badgeList.appendChild(row);
    });
  }

  async function loadBadges(route) {
    const requested = (route && route.badge_id) || "";
    badgeItems = [];
    badgeList.innerHTML = "";
    badgeDetail.hidden = true;
    badgeDetail.innerHTML = "";
    badgeList.hidden = true;
    badgeEmpty.hidden = false;
    badgeEmpty.textContent = "Loading…";
    badgesTitle.textContent = requested ? "Badge" : "Badges";
    try {
      const params = new URLSearchParams();
      if (route.username) params.set("username", route.username);
      else if (route.owner) params.set("owner", route.owner);
      else if (route.transaction_id) params.set("transaction_id", route.transaction_id);
      const res = await fetch(`${API_BADGES}?${params.toString()}`, { credentials: "same-origin" });
      const data = await res.json().catch(() => ({}));
      if (viewName !== "badges") return;
      if ((parseRoute().badge_id || "") !== requested) return;
      if (!res.ok || data.status === false) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      const items = data.badges || [];
      if (requested) {
        renderBadgeDetail(items.find((item) => item.transaction_id === requested) || null);
        return;
      }
      renderBadgeList(items);
    } catch (err) {
      if (viewName !== "badges") return;
      badgeList.hidden = true;
      badgeDetail.hidden = true;
      badgeEmpty.hidden = false;
      badgeEmpty.textContent = err.message || "Could not load badges";
    }
  }

  function pauseFeed() {
    feed.querySelectorAll("video").forEach((v) => {
      try {
        v.pause();
      } catch (_) {}
    });
  }

  function stopLiveHls() {
    if (liveHls) {
      try {
        liveHls.destroy();
      } catch (_) {}
      liveHls = null;
    }
    if (liveWhep) {
      const session = liveWhep;
      liveWhep = "";
      fetch(session, { method: "DELETE" }).catch(() => {});
    }
    if (livePc) {
      try {
        livePc.close();
      } catch (_) {}
      livePc = null;
    }
  }

  function closePlayer() {
    stopLiveHls();
    try {
      playerVideo.pause();
    } catch (_) {}
    playerVideo.loop = true;
    playerVideo.hidden = false;
    playerPhoto.hidden = true;
    playerPhoto.removeAttribute("src");
    playerVideo.removeAttribute("src");
    playerVideo.srcObject = null;
    try {
      playerVideo.load();
    } catch (_) {}
    hideAccessGate();
    playerEl.hidden = true;
    appEl.classList.remove("player-open");
    playerSpinner.hidden = true;
    playerCaption.textContent = "";
    playerLive.hidden = true;
    railReport.hidden = false;
    playerItem = null;
    renderLiveRow();
  }

  function hidePlayerSpinner() {
    playerSpinner.hidden = true;
  }

  function openPlayer(item, credentialChecked) {
    if (itemPrice(item) && !item.price_unlocked) {
      openBuy(item);
      return;
    }
    if (!credentialChecked && credentialGates(item).length) {
      downloadAllowed(item).then((ok) => {
        if (ok) openPlayer(item, true);
        else openAccessGate(item, "video");
      });
      return;
    }
    hideAccessGate();
    const url = streamUrl(item);
    if (!url) {
      showStatus("Playback isn't available for this file", 2500);
      return;
    }
    stopLiveHls();
    pauseFeed();
    playerItem = item;
    playerLive.hidden = true;
    railReport.hidden = false;
    playerPhoto.hidden = true;
    playerPhoto.removeAttribute("src");
    playerVideo.hidden = false;
    playerVideo.loop = true;
    playerCaption.textContent = item.title || item.filename || "";
    playerSpinner.hidden = false;
    playerEl.hidden = false;
    appEl.classList.add("player-open");
    playerVideo.muted = muted;
    playerVideo.src = url;
    playerVideo.play().catch(() => {});
  }

  function openPhoto(item, credentialChecked) {
    if (itemPrice(item) && !item.price_unlocked) {
      openBuy(item);
      return;
    }
    if (!credentialChecked && credentialGates(item).length) {
      downloadAllowed(item).then((ok) => {
        if (ok) openPhoto(item, true);
        else openAccessGate(item, "photo");
      });
      return;
    }
    hideAccessGate();
    const src = photoSrc(item);
    if (!src) {
      showStatus("Photo isn't available", 2500);
      return;
    }
    stopLiveHls();
    pauseFeed();
    playerItem = item;
    playerLive.hidden = true;
    railReport.hidden = false;
    try {
      playerVideo.pause();
    } catch (_) {}
    playerVideo.hidden = true;
    playerPhoto.hidden = false;
    playerPhoto.alt = item.title || item.filename || "";
    playerPhoto.src = src;
    playerCaption.textContent = item.title || item.filename || "";
    playerSpinner.hidden = true;
    playerEl.hidden = false;
    appEl.classList.add("player-open");
    renderLiveRow();
  }

  function hlsCandidates(url) {
    const clean = String(url || "").trim();
    if (!clean) return [];
    if (/\.m3u8(\?|#|$)/i.test(clean)) return [clean];
    if (/\.[a-z0-9]{2,5}(\?|#|$)/i.test(clean)) return [];
    const base = clean.replace(/\/$/, "");
    return [`${base}/index.m3u8`, `${base}.m3u8`];
  }

  function loadHlsLib() {
    if (window.Hls) return Promise.resolve(window.Hls);
    if (loadHlsLib.pending) return loadHlsLib.pending;
    loadHlsLib.pending = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = HLS_SRC;
      script.onload = () => resolve(window.Hls);
      script.onerror = () => reject(new Error("Could not load live player"));
      document.head.appendChild(script);
    });
    return loadHlsLib.pending;
  }

  function playNative(video, url) {
    video.src = url;
    return video.play().catch(() => {});
  }

  function whepUrl(playbackUrl) {
    try {
      const u = new URL(playbackUrl, location.origin);
      u.pathname = u.pathname.replace(/\/index\.m3u8$/i, "").replace(/\.m3u8$/i, "");
      if (u.port !== "8888") return "";
      u.port = "8889";
      u.pathname = `${u.pathname.replace(/\/$/, "")}/whep`;
      u.search = "";
      u.hash = "";
      return u.toString();
    } catch (_) {
      return "";
    }
  }

  function waitForIce(pc) {
    if (pc.iceGatheringState === "complete") return Promise.resolve();
    return new Promise((resolve) => {
      const timer = setTimeout(resolve, 800);
      pc.addEventListener("icegatheringstatechange", () => {
        if (pc.iceGatheringState === "complete") {
          clearTimeout(timer);
          resolve();
        }
      });
    });
  }

  async function playWhep(video, url) {
    if (!url || typeof RTCPeerConnection !== "function") return false;
    const pc = new RTCPeerConnection();
    livePc = pc;
    pc.addTransceiver("video", { direction: "recvonly" });
    pc.addTransceiver("audio", { direction: "recvonly" });
    pc.ontrack = (ev) => {
      const stream = ev.streams && ev.streams[0];
      if (!stream) return;
      video.srcObject = stream;
      video.play().catch(() => {});
    };
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    await waitForIce(pc);
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/sdp" },
      body: pc.localDescription.sdp,
    });
    if (!res.ok) throw new Error(`WHEP ${res.status}`);
    liveWhep = res.headers.get("Location") || "";
    const answer = await res.text();
    await pc.setRemoteDescription({ type: "answer", sdp: answer });
    const audio = await new Promise((resolve) => {
      const hasAudio = () =>
        pc.getReceivers().some((receiver) => receiver.track && receiver.track.kind === "audio");
      if (hasAudio()) return resolve(true);
      const timer = setTimeout(() => resolve(hasAudio()), 600);
      pc.addEventListener("track", () => {
        if (hasAudio()) {
          clearTimeout(timer);
          resolve(true);
        }
      });
    });
    if (!audio) throw new Error("WebRTC dropped AAC audio");
    return true;
  }

  async function playHls(video, url) {
    const Hls = await loadHlsLib();
    if (!Hls || !Hls.isSupported()) {
      if (video.canPlayType("application/vnd.apple.mpegurl")) {
        playNative(video, url);
        return true;
      }
      return false;
    }
    stopLiveHls();
    const hls = new Hls({
      lowLatencyMode: true,
      liveSyncDurationCount: 1,
      liveMaxLatencyDurationCount: 2,
      maxLiveSyncPlaybackRate: 1.5,
      backBufferLength: 0,
      maxBufferLength: 2,
      maxMaxBufferLength: 4,
    });
    liveHls = hls;
    hls.loadSource(url);
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      video.play().catch(() => {});
    });
    hls.on(Hls.Events.FRAG_BUFFERED, () => {
      const edge = hls.liveSyncPosition;
      if (Number.isFinite(edge) && edge - video.currentTime > 1.5) {
        video.currentTime = edge;
      }
    });
    return true;
  }

  async function playLive(video, url) {
    stopLiveHls();
    video.removeAttribute("src");
    video.srcObject = null;
    try {
      video.load();
    } catch (_) {}
    const whep = whepUrl(url);
    if (whep) {
      try {
        if (await playWhep(video, whep)) return;
      } catch (_) {
        stopLiveHls();
      }
    }
    const candidates = hlsCandidates(url);
    for (const candidate of candidates) {
      try {
        if (await playHls(video, candidate)) return;
      } catch (_) {}
    }
    playNative(video, url);
  }

  async function resolvePlayback(stream) {
    if (stream && stream.playback_url) return stream.playback_url;
    if (!stream || !stream.channel_id) return "";
    const res = await fetch(API_WATCH, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel_id: stream.channel_id }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.status === false) {
      throw new Error(data.error || "Live playback requires a credential");
    }
    return (data.result && data.result.playback_url) || "";
  }

  async function openLive(stream) {
    if (!stream) return;
    hideAccessGate();
    pauseFeed();
    const item = {
      kind: "livestream",
      username: stream.username || "",
      public_key_hash: stream.public_key_hash || stream.owner || "",
      owner: stream.owner || "",
      title: stream.title || "Live",
      description: stream.description || "",
      transaction_id: stream.transaction_id || stream.announcement_txn_id || "",
      channel_id: stream.channel_id || "",
      playback_url: stream.playback_url || "",
    };
    playerItem = item;
    railReport.hidden = true;
    playerLive.hidden = false;
    playerPhoto.hidden = true;
    playerPhoto.removeAttribute("src");
    playerVideo.hidden = false;
    playerVideo.loop = false;
    const who = item.username ? `@${item.username}` : "Live";
    playerCaption.textContent =
      item.title && item.title !== "Live" ? `${who} · ${item.title}` : who;
    playerSpinner.hidden = false;
    playerEl.hidden = false;
    appEl.classList.add("player-open");
    renderLiveRow();
    playerVideo.muted = muted;
    try {
      const url = item.playback_url || (await resolvePlayback(item));
      if (!url) {
        playerSpinner.hidden = true;
        showStatus("Live playback URL is not available", 3000);
        return;
      }
      item.playback_url = url;
      await playLive(playerVideo, url);
    } catch (err) {
      playerSpinner.hidden = true;
      showStatus(err.message || "Could not open live stream", 3500);
    }
  }

  playerVideo.addEventListener("playing", hidePlayerSpinner);
  playerVideo.addEventListener("error", hidePlayerSpinner);

  function formatCount(value) {
    if (value === null || value === undefined || value === "") return "—";
    const n = Number(value);
    if (!Number.isFinite(n)) return "—";
    return n.toLocaleString();
  }

  function formatGifts(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "—";
    return n.toLocaleString(undefined, { maximumFractionDigits: 8 });
  }

  function applyProfileLive(profile) {
    const live = liveFor(profile);
    setLiveRing(profileAvatar, !!live);
    profileAvatar.onclick = live ? () => openLive(live) : null;
    if (live) profileAvatar.setAttribute("aria-label", "Watch live");
    else profileAvatar.removeAttribute("aria-label");
  }

  const PROFILE_PHOTO_TYPE = "avatar";

  function itemType(item) {
    return String((item && item.type) || "").trim().toLowerCase();
  }

  function isProfilePhoto(item) {
    return itemType(item) === PROFILE_PHOTO_TYPE;
  }

  function splitProfileMedia(profile) {
    const photosOut = [];
    const videosOut = [];
    const seen = new Set();
    for (const item of (profile && profile.photos) || []) {
      if (isProfilePhoto(item)) continue;
      if (item.transaction_id && seen.has(item.transaction_id)) continue;
      photosOut.push(item);
      if (item.transaction_id) seen.add(item.transaction_id);
    }
    for (const item of (profile && profile.videos) || []) {
      if (item.transaction_id && seen.has(item.transaction_id)) continue;
      const mime = String(item.mime_type || "").toLowerCase();
      const image =
        mime.startsWith("image/") ||
        (!item.stream_url && item.thumbnail_url && !mime.startsWith("video/"));
      if (image) photosOut.push(item);
      else videosOut.push(item);
    }
    return { videos: videosOut, photos: photosOut };
  }

  function paintProfileTabs() {
    sessionStorage.setItem("yada-scroller-profile", profileMedia);
    const photosOn = profileMedia === "photos";
    profileTabVideos.classList.toggle("active", !photosOn);
    profileTabPhotos.classList.toggle("active", photosOn);
    profileTabVideos.setAttribute("aria-selected", photosOn ? "false" : "true");
    profileTabPhotos.setAttribute("aria-selected", photosOn ? "true" : "false");
  }

  function renderProfileGrid() {
    const items = profileMedia === "photos" ? profilePhotos : profileVideos;
    profileGrid.innerHTML = "";
    paintProfileTabs();
    if (!items.length) {
      profileEmpty.hidden = false;
      profileEmpty.textContent = profileMedia === "photos" ? "No photos yet" : "No videos yet";
      return;
    }
    profileEmpty.hidden = true;
    items.forEach((item, index) => {
      const tile = document.createElement("button");
      tile.type = "button";
      tile.className = "tile";
      const label = item.title || item.filename || "Upload";
      const src = profileMedia === "photos" ? photoSrc(item) : item.thumbnail_url;
      const still = src
        ? `<img alt="" src="${escapeHtml(src)}">`
        : `<span class="ph">${item.stream_url ? "▶" : "▣"}</span>`;
      tile.innerHTML = `${still}${priceChipHtml(item)}${credentialChipHtml(item)}<span class="cap">${escapeHtml(label)}</span>`;
      tile.addEventListener("click", () => {
        if (profileMedia === "photos") openPhoto(items[index]);
        else openPlayer(items[index]);
      });
      profileGrid.appendChild(tile);
    });
  }

  function renderProfile(profile) {
    currentProfile = profile || null;
    const split = splitProfileMedia(profile);
    profileVideos = split.videos;
    profilePhotos = split.photos;
    const name = displayName(profile);
    profileTopTitle.textContent = profile && profile.username ? profile.username : "Profile";
    profileName.textContent = name;
    const circle = ((profile && profile.photos) || []).find(
      (item) => isProfilePhoto(item) && photoSrc(item)
    );
    paintAvatar(profileAvatar, profile && profile.username, circle ? photoSrc(circle) : "");
    applyProfileLive(profile);
    if (profile && profile.username) {
      profileSub.hidden = true;
      profileSub.textContent = "";
    } else {
      profileSub.hidden = false;
      profileSub.textContent = "No identity announcement";
    }
    profileActions.hidden = !(profile && profile.is_me);
    if (profile && profile.is_me && parseRoute().view === "profile") {
      navProfile.classList.add("active");
    }
    statGifts.textContent = formatGifts(profile && profile.gifts);
    statFollowing.textContent = formatCount(profile && profile.following);
    statFollowers.textContent = formatCount(profile && profile.followers);
    statBadges.textContent = formatCount(profile && profile.badges);
    renderProfileGrid();
  }

  function renderMissingProfile(message) {
    currentProfile = null;
    profileVideos = [];
    profilePhotos = [];
    paintProfileTabs();
    profileTopTitle.textContent = "Profile";
    profileName.textContent = "Profile";
    paintAvatar(profileAvatar, "");
    applyProfileLive(null);
    profileSub.hidden = false;
    profileSub.textContent = message;
    profileActions.hidden = true;
    statGifts.textContent = "—";
    statFollowing.textContent = "—";
    statFollowers.textContent = "—";
    statBadges.textContent = "—";
    profileGrid.innerHTML = "";
    profileEmpty.hidden = true;
  }

  async function loadProfile(route) {
    profileGrid.innerHTML = "";
    profileEmpty.hidden = true;
    profileName.textContent = "Loading…";
    profileActions.hidden = true;
    statGifts.textContent = "—";
    statFollowing.textContent = "—";
    statFollowers.textContent = "—";
    statBadges.textContent = "—";
    try {
      let url = API_ME;
      if (route.view === "profile") {
        const params = new URLSearchParams();
        if (route.username) params.set("username", route.username);
        else if (route.owner) params.set("owner", route.owner);
        else if (route.transaction_id) params.set("transaction_id", route.transaction_id);
        url = `${API_PROFILE}?${params.toString()}`;
      }
      const res = await fetch(url, { credentials: "same-origin" });
      const data = await res.json().catch(() => ({}));
      if (viewName === "feed") return;
      if (!res.ok || data.status === false) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }
      if (!data.profile) {
        renderMissingProfile("No identity announcement yet");
        return;
      }
      renderProfile(data.profile);
    } catch (err) {
      if (viewName === "feed") return;
      renderMissingProfile(err.message || "Could not load profile");
    }
  }

  function syncRoute() {
    const route = parseRoute();
    viewName = route.view;
    closePlayer();
    renderLiveRow();
    const onFeed = viewName === "feed";
    const onProfile = viewName === "profile";
    appEl.classList.toggle("view-profile", !onFeed);
    profileEl.hidden = !onProfile;
    badgesEl.hidden = viewName !== "badges";
    publishEl.hidden = viewName !== "publish";
    uploadEl.hidden = viewName !== "upload";
    navFyp.classList.toggle("active", onFeed);
    navUpload.classList.toggle("active", viewName === "upload");
    navProfile.classList.toggle("active", viewName === "me" || viewName === "publish");
    if (onFeed) {
      const pin = route.transaction_id || "";
      const want = route.media === "photos" && !pin ? "photos" : pin ? "videos" : mediaMode;
      if (mediaMode !== want) {
        setMedia(want);
        return;
      }
      if (want === "photos") {
        pauseFeed();
        emptyEl.hidden = true;
        photoEmpty.hidden = photos.length > 0;
        if (photosLoadedQuery !== query) loadPhotos(query);
        return;
      }
      if (loadedPin !== pin) {
        loadVideos(searchEl.value.trim(), pin);
        return;
      }
      if (videos.length) activateIndex(activeIndex, false);
      return;
    }
    pauseFeed();
    if (onProfile) loadProfile(route);
    if (viewName === "me") loadOwnProfile();
    if (viewName === "badges") loadBadges(route);
    if (viewName === "upload") openCompose();
    else {
      if (composeBusy) abortComposeUpload();
      stopComposePoll();
    }
  }

  let ownProfileGen = 0;

  function showOwnGate() {
    profileEl.hidden = true;
    publishEl.hidden = false;
  }

  async function loadOwnProfile() {
    const gen = ++ownProfileGen;
    profileEl.hidden = true;
    publishEl.hidden = true;
    try {
      const res = await fetch(API_ME, { credentials: "same-origin" });
      const data = await res.json().catch(() => ({}));
      if (gen !== ownProfileGen || parseRoute().view !== "me") return;
      if (!res.ok || data.status === false) {
        publishEl.hidden = true;
        profileEl.hidden = false;
        renderMissingProfile(data.error || `HTTP ${res.status}`);
        return;
      }
      if (data.authenticated !== true) {
        showOwnGate();
        return;
      }
      publishEl.hidden = true;
      profileEl.hidden = false;
      profileGrid.innerHTML = "";
      profileEmpty.hidden = true;
      profileName.textContent = "Loading…";
      profileActions.hidden = true;
      if (!data.profile) {
        renderMissingProfile("No identity announcement yet");
        return;
      }
      renderProfile(data.profile);
    } catch (err) {
      if (gen !== ownProfileGen || parseRoute().view !== "me") return;
      publishEl.hidden = true;
      profileEl.hidden = false;
      renderMissingProfile(err.message || "Could not load profile");
    }
  }

  function leaveOverlay() {
    if (parseRoute().view === "upload") abortComposeUpload();
    if (
      location.hash.startsWith("#/profile") ||
      location.hash.startsWith("#/@") ||
      location.hash.startsWith("#/badges") ||
      location.hash.startsWith("#/publish") ||
      location.hash.startsWith("#/upload") ||
      location.hash === "#/me"
    ) {
      history.back();
      return;
    }
    location.hash = "#/";
  }

  profileBack.addEventListener("click", leaveOverlay);
  badgesBack.addEventListener("click", () => {
    const route = parseRoute();
    if (route.view === "badges" && route.badge_id) {
      const listHash = badgesHash(route, "");
      if (badgeDetailFromList) {
        badgeDetailFromList = false;
        armBadgeDetailBack = false;
        history.back();
        return;
      }
      if (location.hash !== listHash) {
        history.replaceState(history.state, "", listHash);
      }
      syncRoute();
      return;
    }
    badgeDetailFromList = false;
    leaveOverlay();
  });
  statBadgesBtn.addEventListener("click", () => {
    location.hash = badgesHash(parseRoute(), "");
  });
  publishBack.addEventListener("click", leaveOverlay);
  function activeItem() {
    if (!playerEl.hidden && playerItem) return playerItem;
    if (mediaMode === "photos") return photos[photoIndex] || null;
    return videos[activeIndex] || null;
  }

  playerBack.addEventListener("click", closePlayer);
  railGift.addEventListener("click", () => openGift(activeItem()));
  railReport.addEventListener("click", () => openReport(activeItem()));
  function openUpload(fileType) {
    const params = new URLSearchParams();
    if (fileType) params.set("type", fileType);
    const query = params.toString();
    const next = query ? `#/upload?${query}` : "#/upload";
    if ((location.hash || "") === next) {
      closePlayer();
      syncRoute();
      return;
    }
    location.hash = next;
  }

  editAvatar.addEventListener("click", () => openUpload(PROFILE_PHOTO_TYPE));
  editUpload.addEventListener("click", () => openUpload(""));
  profileTabVideos.addEventListener("click", () => {
    profileMedia = "videos";
    renderProfileGrid();
  });
  profileTabPhotos.addEventListener("click", () => {
    profileMedia = "photos";
    renderProfileGrid();
  });
  let ownNavBusy = false;

  async function openOwnProfile() {
    if (ownNavBusy) return;
    ownNavBusy = true;
    try {
      const res = await fetch(API_ME, { credentials: "same-origin" });
      const data = await res.json().catch(() => ({}));
      const name = String(
        (data && (data.username || (data.profile && data.profile.username))) || ""
      )
        .trim()
        .replace(/^@/, "");
      if (res.ok && data.authenticated === true && name) {
        const hash = `#/@${encodeURIComponent(name)}`;
        if ((location.hash || "") === hash) {
          closePlayer();
          syncRoute();
          return;
        }
        location.hash = hash;
        return;
      }
      if ((location.hash || "") === "#/me") {
        closePlayer();
        syncRoute();
        return;
      }
      location.hash = "#/me";
    } catch (_) {
      if ((location.hash || "") === "#/me") {
        closePlayer();
        syncRoute();
        return;
      }
      location.hash = "#/me";
    } finally {
      ownNavBusy = false;
    }
  }

  const signinOrigin = window.location.origin.toLowerCase();
  const USERNAME_KEY = "yada-scroller-username";
  let extReady = false;
  let signinReqSeq = 0;
  let signinWorking = false;
  let signinRequestId = "";
  let signinTimer = null;
  let signinStarted = 0;
  let signinLabel = "";
  let signinAbort = null;
  const SIGNIN_LABEL = "Sign in";
  const REGISTER_LABEL = "Register this origin";
  const RESYNC_LABEL = "Resync";

  function setSigninMsg(text, kind) {
    signinMsg.textContent = text || "";
    signinMsg.className = kind ? `signin-msg ${kind}` : "signin-msg";
  }

  function setSigninLocked(locked) {
    const extOff = locked || !extReady;
    registerBtn.disabled = extOff;
    resyncBtn.disabled = extOff;
    signinBtn.disabled = locked;
    if (signinUsername) signinUsername.disabled = locked;
  }

  function showSigninProgress(label) {
    signinLabel = label;
    const secs = signinStarted ? Math.floor((Date.now() - signinStarted) / 1000) : 0;
    setSigninMsg(label + (secs > 0 ? ` · ${secs}s` : ""), "busy");
    signinTrack.className = "signin-track on";
  }

  function stopSigninProgress() {
    if (signinTimer) clearInterval(signinTimer);
    signinTimer = null;
    signinStarted = 0;
    signinLabel = "";
    signinWorking = false;
    signinRequestId = "";
    signinTrack.className = "signin-track";
    setSigninLocked(false);
  }

  function startSigninProgress(label) {
    stopSigninProgress();
    signinWorking = true;
    signinStarted = Date.now();
    setSigninLocked(true);
    showSigninProgress(label);
    signinTimer = setInterval(() => showSigninProgress(signinLabel), 1000);
  }

  function extRequest(type, resultType, timeoutMs = 180000) {
    const requestId = `r${++signinReqSeq}_${Date.now()}`;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        window.removeEventListener("message", onMsg);
        reject(new Error("extension did not respond"));
      }, timeoutMs);
      function onMsg(event) {
        if (event.source !== window) return;
        const data = event.data;
        if (!data || data.type !== resultType || data.requestId !== requestId) return;
        clearTimeout(timer);
        window.removeEventListener("message", onMsg);
        resolve(data);
      }
      window.addEventListener("message", onMsg);
      signinRequestId = requestId;
      window.postMessage({ type, requestId }, "*");
    });
  }

  function stashOperatorToken(token) {
    if (!token) return;
    try {
      sessionStorage.setItem("yadaOperatorToken", token);
    } catch (_) {}
  }

  async function openOperatorSession(password, homeNode, passwordEnc) {
    const body = { branch_peer: signinOrigin };
    if (passwordEnc) body.password_enc = passwordEnc;
    else if (password) body.password = password;
    if (homeNode) body.home_node = String(homeNode).replace(/\/+$/, "");
    const res = await fetch("/password-rotation/admin-session", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      credentials: "include",
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.status) {
      throw new Error(data.message || `admin session failed (${res.status})`);
    }
    return data;
  }

  window.addEventListener("message", (event) => {
    if (event.source !== window) return;
    if (event.data && event.data.type === "YADA_PASSWORD_READY") {
      extReady = true;
      extStatus.textContent = "Extension ready.";
      extStatus.className = "signin-status ok";
      setSigninLocked(signinWorking);
    }
    if (
      event.data &&
      event.data.type === "YADA_PASSWORD_PROGRESS" &&
      event.data.requestId === signinRequestId &&
      event.data.message
    ) {
      showSigninProgress(String(event.data.message));
    }
  });
  setTimeout(() => {
    if (!extReady) {
      extStatus.textContent =
        "Sign in does not need the extension on this page. Approve the request in the Yada Password extension or the Android/iOS app. Register and Resync still use the extension.";
      extStatus.className = "signin-status";
    }
  }, 1500);

  function rememberUsername(name) {
    try {
      sessionStorage.setItem(USERNAME_KEY, name);
    } catch (_) {}
  }

  function currentUsername() {
    return ((signinUsername && signinUsername.value) || "")
      .trim()
      .replace(/^@/, "");
  }

  async function loadSigninUsername() {
    if (!signinUsername) return;
    try {
      const saved = sessionStorage.getItem(USERNAME_KEY) || "";
      if (saved && !signinUsername.value) signinUsername.value = saved;
    } catch (_) {}
    if (signinUsername.value) return;
    try {
      const res = await fetch("/yada-config", {
        headers: { Accept: "application/json" },
        credentials: "include",
      });
      const data = await res.json().catch(() => ({}));
      const name = (
        (data && data.identity && data.identity.username) ||
        ""
      )
        .trim()
        .replace(/^@/, "");
      if (name && !signinUsername.value) signinUsername.value = name;
    } catch (_) {}
  }

  function sleep(ms, signal) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(resolve, ms);
      if (!signal) return;
      const onAbort = () => {
        clearTimeout(timer);
        reject(new DOMException("cancelled", "AbortError"));
      };
      if (signal.aborted) {
        onAbort();
        return;
      }
      signal.addEventListener("abort", onAbort, { once: true });
    });
  }

  async function expectedSigninHash(signal) {
    try {
      const tipRes = await fetch(
        "/password-rotation/offchain/tip?branch_peer=" +
          encodeURIComponent(signinOrigin),
        { headers: { Accept: "application/json" }, credentials: "include", signal }
      );
      const tipData = await tipRes.json();
      const pre =
        tipData &&
        tipData.tip &&
        tipData.tip.password &&
        tipData.tip.password.prerotated_password_hash;
      return pre || undefined;
    } catch (_) {
      return undefined;
    }
  }

  function authPollBase(_created) {
    // Poll this node. It proxies to home_node. A browser fetch to the home
    // is often blocked by CORS, which leaves the page stuck on Waiting.
    return "";
  }

  async function fetchAuthView(sessionId, base, signal) {
    const root = String(base || "").replace(/\/+$/, "");
    const url =
      root +
      "/password-rotation/auth-session/" +
      encodeURIComponent(sessionId);
    const res = await fetch(url, {
      headers: { Accept: "application/json" },
      credentials: root && root !== signinOrigin ? "omit" : "include",
      signal,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok && res.status !== 404) {
      throw new Error(data.message || "poll failed (" + res.status + ")");
    }
    return data;
  }

  async function waitForAuthApproval(sessionId, created, signal) {
    const remote = authPollBase(created);
    const started = Date.now();
    while (!signal.aborted) {
      if (Date.now() - started > 180000) {
        throw new Error("timed out waiting for approval");
      }
      await sleep(1500, signal);
      let view = null;
      if (remote) {
        try {
          view = await fetchAuthView(sessionId, remote, signal);
        } catch (err) {
          if (err && err.name === "AbortError") throw err;
          view = null;
        }
      }
      let localView = null;
      try {
        localView = await fetchAuthView(sessionId, "", signal);
      } catch (err) {
        if (err && err.name === "AbortError") throw err;
      }
      if (
        localView &&
        (localView.session_status === "approved" ||
          localView.session_status === "denied" ||
          !view ||
          !view.session_status)
      ) {
        view = localView;
      }
      const st = view && view.session_status;
      if (st === "delivered" || st === "pending" || !st) {
        const where = created && created.home_node ? " · " + created.home_node : "";
        showSigninProgress(
          (st === "delivered" ? "Delivered" : "Waiting") +
            " — approve in the extension or the Android/iOS app" +
            where +
            " · " +
            Math.round((Date.now() - started) / 1000) +
            "s"
        );
        continue;
      }
      if (st === "denied" || st === "expired") {
        throw new Error((view && view.message) || st);
      }
      if (st === "approved") return view;
    }
    throw new DOMException("cancelled", "AbortError");
  }

  registerBtn.addEventListener("click", async () => {
    startSigninProgress("Contacting the extension to register this origin…");
    registerBtn.textContent = "Registering…";
    try {
      const data = await extRequest("YADA_PASSWORD_REGISTER", "YADA_PASSWORD_REGISTER_RESULT");
      if (!data.ok) throw new Error(data.message || "register failed");
      stopSigninProgress();
      setSigninMsg("Registered this origin. Click Sign in.", "ok");
    } catch (err) {
      stopSigninProgress();
      setSigninMsg(String(err.message || err), "err");
    } finally {
      registerBtn.textContent = REGISTER_LABEL;
    }
  });
  resyncBtn.addEventListener("click", async () => {
    startSigninProgress("Contacting the extension to resync…");
    resyncBtn.textContent = "Resyncing…";
    try {
      const data = await extRequest("YADA_PASSWORD_RESYNC", "YADA_PASSWORD_RESYNC_RESULT");
      if (!data.ok) throw new Error(data.message || "resync failed");
      stopSigninProgress();
      setSigninMsg(data.message || "Resynced to the node tip. Click Sign in.", "ok");
    } catch (err) {
      stopSigninProgress();
      setSigninMsg(String(err.message || err), "err");
    } finally {
      resyncBtn.textContent = RESYNC_LABEL;
    }
  });
  signinBtn.addEventListener("click", async () => {
    if (signinWorking && signinAbort) {
      signinAbort.abort();
      return;
    }
    const username = currentUsername();
    if (!username) {
      setSigninMsg("Enter your Yada username.", "err");
      if (signinUsername) signinUsername.focus();
      return;
    }
    rememberUsername(username);
    signinAbort = new AbortController();
    const signal = signinAbort.signal;
    startSigninProgress("Creating sign-in request…");
    signinBtn.textContent = "Cancel";
    try {
      const expectedHash = await expectedSigninHash(signal);
      const createRes = await fetch("/password-rotation/auth-session", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          username,
          site: signinOrigin,
          action: "operator",
          expectedHash,
        }),
        signal,
      });
      const created = await createRes.json().catch(() => ({}));
      if (!createRes.ok || !created.status || !created.session_id) {
        throw new Error(created.message || "failed to create sign-in request");
      }
      const home = created.home_node ? " · " + created.home_node : "";
      showSigninProgress(
        (created.delivered
          ? "Delivered to Yada Password"
          : "Open Yada Password (extension or Android/iOS app)") +
          " and Approve" +
          home
      );
      const view = await waitForAuthApproval(created.session_id, created, signal);
      if (!view.ok && !view.operator_session && !view.authenticated) {
        throw new Error(view.message || "sign-in was not approved");
      }
      showSigninProgress("Approved — opening operator session…");
      const session = await openOperatorSession(
        "",
        view.home_node || created.home_node || "",
        ""
      );
      stashOperatorToken((session && session.token) || view.token);
      stopSigninProgress();
      setSigninMsg("Session opened — opening your profile…", "ok");
      await openOwnProfile();
    } catch (err) {
      const aborted =
        (err && err.name === "AbortError") ||
        String((err && err.message) || err) === "cancelled";
      stopSigninProgress();
      if (!aborted) setSigninMsg(String(err.message || err), "err");
      else setSigninMsg("Cancelled", "err");
    } finally {
      signinAbort = null;
      signinBtn.textContent = SIGNIN_LABEL;
    }
  });
  loadSigninUsername();

  navUpload.addEventListener("click", () => {
    if (location.pathname !== "/") {
      openUpload("");
      return;
    }
    const next = "#/publish";
    if ((location.hash || "") === next) {
      closePlayer();
      syncRoute();
      return;
    }
    location.hash = next;
  });
  uploadBack.addEventListener("click", leaveOverlay);
  composeSignin.addEventListener("click", () => {
    location.hash = "#/me";
  });
  composeFile.addEventListener("change", () => {
    const file = composeFile.files && composeFile.files[0];
    if (!file) return;
    const next = titleFromName(file.name);
    if (!composeTitle.value || composeTitle.value === composeAutoTitle) {
      composeTitle.value = next;
      composeAutoTitle = next;
    }
  });
  composeForm.addEventListener("submit", submitCompose);
  tabVideos.addEventListener("click", () => setMedia("videos"));
  tabPhotos.addEventListener("click", () => setMedia("photos"));
  navFyp.addEventListener("click", () => {
    const hash = location.hash || "";
    if (!hash || hash === "#" || hash === "#/" || hash === "#/photos") {
      closePlayer();
      syncRoute();
      return;
    }
    location.hash = mediaMode === "photos" ? "#/photos" : "#/";
  });
  navProfile.addEventListener("click", openOwnProfile);
  window.addEventListener("pagehide", abortComposeUpload);
  window.addEventListener("hashchange", () => {
    if (armBadgeDetailBack) {
      badgeDetailFromList = true;
      armBadgeDetailBack = false;
    } else {
      badgeDetailFromList = false;
    }
    syncRoute();
  });

  setTimeout(() => hintEl.classList.add("fade"), 4500);

  function remarkFeedLive() {
    feed.querySelectorAll(".slide").forEach((slide) => {
      const item = videos[Number(slide.dataset.index)];
      const btn = slide.querySelector(".avatar-btn");
      if (!btn || !item) return;
      const live = liveFor(item);
      setLiveRing(btn, !!live);
      btn.setAttribute(
        "aria-label",
        live
          ? item.username
            ? `Watch @${item.username} live`
            : "Watch live"
          : item.username
            ? `Open @${item.username}`
            : "Open profile"
      );
    });
  }

  function renderLiveRow() {
    if (!liveRow) return;
    const show = viewName === "feed" && playerEl.hidden && liveStreams.length > 0;
    liveRow.hidden = !show;
    liveRow.innerHTML = "";
    if (!show) return;
    liveStreams.forEach((stream) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "live-chip";
      const label = stream.username
        ? `Watch @${stream.username} live`
        : stream.title || "Watch live";
      btn.title = stream.username ? `@${stream.username}` : stream.title || "Live";
      btn.setAttribute("aria-label", label);
      paintAvatar(btn, stream.username);
      setLiveRing(btn, true);
      btn.addEventListener("click", () => openLive(stream));
      liveRow.appendChild(btn);
    });
  }

  async function loadLive() {
    try {
      await loadMyBadges();
      const res = await fetch(API_LIVE, { credentials: "same-origin" });
      if (!res.ok) return;
      const data = await res.json();
      if (!data.status) return;
      indexLive(data.results || []);
    } catch (_) {
      return;
    }
    remarkFeedLive();
    renderLiveRow();
    if (viewName === "profile" && currentProfile) applyProfileLive(currentProfile);
  }

  loadMyBadges();
  loadReasons();
  loadLive();
  setInterval(loadLive, 20000);
  syncRoute();
})();
