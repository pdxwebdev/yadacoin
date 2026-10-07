(() => {
  const API_VIDEOS = "/file-announcements/api/v1/public/videos";
  const API_PROFILE = "/file-announcements/api/v1/public/profile";
  const API_BADGES = "/file-announcements/api/v1/public/badges";
  const API_ME = "/file-announcements/api/v1/public/me";
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
  const editUsername = document.getElementById("edit-username");
  const editUpload = document.getElementById("edit-upload");
  const publishEl = document.getElementById("publish");
  const publishBack = document.getElementById("publish-back");
  const playerEl = document.getElementById("player");
  const playerBack = document.getElementById("player-back");
  const playerVideo = document.getElementById("player-video");
  const playerSpinner = document.getElementById("player-spinner");
  const playerCaption = document.getElementById("player-caption");
  const playerLive = document.getElementById("player-live");
  const liveRow = document.getElementById("live-row");
  const railGift = document.getElementById("rail-gift");
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
  let activeIndex = 0;
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
  let feedGen = 0;
  let probeAbort = new AbortController();
  let viewName = "feed";
  /** @type {Array<object>} */
  let profileVideos = [];
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
    if (viewName !== "feed" && (ms === 0 || !msg)) return;
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

  function streamUrl(item) {
    if (!item || !item.stream_url) return "";
    const params = new URLSearchParams();
    if (item.filename) params.set("filename", item.filename);
    if (item.mime_type) params.set("mime_type", item.mime_type);
    const q = params.toString();
    return q ? `${item.stream_url}?${q}` : item.stream_url;
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

  function paintAvatar(el, username) {
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
    face.innerHTML = avatarMarkup(name);
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
    liveStreams = list || [];
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
    pauseAllExcept(video);
    const play = () => {
      if (!slide.isConnected || viewName !== "feed" || !playerEl.hidden) return;
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

  async function loadVideos(q, pinId) {
    pinId = pinId || "";
    loadedPin = pinId;
    probeAbort.abort();
    probeAbort = new AbortController();
    const signal = probeAbort.signal;
    const gen = ++feedGen;
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
      if (pinned && pinned.stream_url && pinned.file_id) candidates.push(pinned);
      for (const item of data.results || []) {
        if (pinId && item.transaction_id === pinId) continue;
        if (!item.stream_url || !item.file_id) continue;
        if (!canLikelyPlay(mimeFor(item))) continue;
        const id = itemKey(item);
        const content = contentKey(item);
        if (seen.has(id) || (content && seen.has(content))) continue;
        seen.add(id);
        if (content) seen.add(content);
        candidates.push(item);
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
          emptyEl.hidden = false;
          showStatus(firstFailure || "", firstFailure ? 8000 : 0);
        } else {
          showStatus(`${videos.length} video${videos.length === 1 ? "" : "s"}`);
        }
      };
      if (!candidates[0]) {
        emptyEl.hidden = false;
        showStatus("");
      } else if (!videos.length) {
        emptyEl.hidden = false;
        showStatus(firstFailure || "playback failed", 8000);
        probeRest();
      } else {
        showStatus("");
        probeRest();
      }
    } catch (err) {
      if (gen !== feedGen || signal.aborted) return;
      resetFeed();
      emptyEl.hidden = false;
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
    loadVideos(query);
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
      // Remove reported item from local feed
      videos = videos.filter((v) => v.transaction_id !== tid);
      renderFeed();
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
      loadVideos(query);
    }, 350);
  });

  window.addEventListener("keydown", (e) => {
    if (reportDlg.open || viewName !== "feed") return;
    if (e.target === searchEl) return;
    if (e.key === "ArrowDown" || e.key === "j") {
      e.preventDefault();
      const next = Math.min(activeIndex + 1, videos.length - 1);
      const slide = feed.querySelectorAll(".slide")[next];
      if (slide) slide.scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (e.key === "ArrowUp" || e.key === "k") {
      e.preventDefault();
      const prev = Math.max(activeIndex - 1, 0);
      const slide = feed.querySelectorAll(".slide")[prev];
      if (slide) slide.scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (e.key === "m") {
      muteBtn.click();
    } else if (e.key === "r") {
      const item = videos[activeIndex];
      if (item) openReport(item);
    } else if (e.key === " ") {
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
    if (path === "/me" || path === "me" || path === "/publish" || path === "publish") {
      return { view: "publish", transaction_id: "" };
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
    if (path === "/profile" && transaction_id && !owner) {
      return { view: "feed", transaction_id };
    }
    if (path === "/profile") {
      return { view: "profile", owner, transaction_id, username: "" };
    }
    return { view: "feed", transaction_id: path === "/" || path === "" ? transaction_id : "" };
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
    if (claim === "ageOver18") return "18+";
    return claim || "Credential";
  }

  function claimMark(claim) {
    if (claim === "ageOver18") return "18+";
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
    playerVideo.removeAttribute("src");
    playerVideo.srcObject = null;
    try {
      playerVideo.load();
    } catch (_) {}
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

  function openPlayer(item) {
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
    playerVideo.loop = true;
    playerCaption.textContent = item.title || item.filename || "";
    playerSpinner.hidden = false;
    playerEl.hidden = false;
    appEl.classList.add("player-open");
    playerVideo.muted = muted;
    playerVideo.src = url;
    playerVideo.play().catch(() => {});
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

  function renderProfile(profile) {
    currentProfile = profile || null;
    profileVideos = (profile && profile.videos) || [];
    const name = displayName(profile);
    profileTopTitle.textContent = profile && profile.username ? profile.username : "Profile";
    profileName.textContent = name;
    paintAvatar(profileAvatar, profile && profile.username);
    applyProfileLive(profile);
    if (profile && profile.username) {
      profileSub.hidden = true;
      profileSub.textContent = "";
    } else {
      profileSub.hidden = false;
      profileSub.textContent = "No identity announcement";
    }
    profileActions.hidden = !(profile && profile.is_me);
    statGifts.textContent = formatGifts(profile && profile.gifts);
    statFollowing.textContent = formatCount(profile && profile.following);
    statFollowers.textContent = formatCount(profile && profile.followers);
    statBadges.textContent = formatCount(profile && profile.badges);
    profileGrid.innerHTML = "";
    if (!profileVideos.length) {
      profileEmpty.hidden = false;
      profileEmpty.textContent = "No uploads yet";
      return;
    }
    profileEmpty.hidden = true;
    profileVideos.forEach((item, index) => {
      const tile = document.createElement("button");
      tile.type = "button";
      tile.className = "tile";
      const label = item.title || item.filename || "Upload";
      const still = item.thumbnail_url
        ? `<img alt="" src="${escapeHtml(item.thumbnail_url)}">`
        : `<span class="ph">${item.stream_url ? "▶" : "▣"}</span>`;
      tile.innerHTML = `${still}<span class="cap">${escapeHtml(label)}</span>`;
      tile.addEventListener("click", () => openPlayer(profileVideos[index]));
      profileGrid.appendChild(tile);
    });
  }

  function renderMissingProfile(message) {
    currentProfile = null;
    profileVideos = [];
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
    navFyp.classList.toggle("active", onFeed);
    navProfile.classList.toggle("active", viewName === "publish");
    if (onFeed) {
      const pin = route.transaction_id || "";
      if (loadedPin !== pin) {
        loadVideos(searchEl.value.trim(), pin);
        return;
      }
      if (videos.length) activateIndex(activeIndex, false);
      return;
    }
    pauseFeed();
    if (onProfile) loadProfile(route);
    if (viewName === "badges") loadBadges(route);
  }

  function leaveOverlay() {
    if (
      location.hash.startsWith("#/profile") ||
      location.hash.startsWith("#/@") ||
      location.hash.startsWith("#/badges") ||
      location.hash.startsWith("#/publish") ||
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
    return videos[activeIndex] || null;
  }

  playerBack.addEventListener("click", closePlayer);
  railGift.addEventListener("click", () => openGift(activeItem()));
  railReport.addEventListener("click", () => openReport(activeItem()));
  editAvatar.addEventListener("click", () => showStatus("Edit avatar is coming soon"));
  editUsername.addEventListener("click", () => showStatus("Edit username is coming soon"));
  editUpload.addEventListener("click", () => showStatus("Upload is coming soon"));
  function openPublish() {
    if ((location.hash || "") === "#/publish") {
      closePlayer();
      syncRoute();
      return;
    }
    location.hash = "#/publish";
  }

  navUpload.addEventListener("click", openPublish);
  navFyp.addEventListener("click", () => {
    const hash = location.hash || "";
    if (!hash || hash === "#" || hash === "#/") {
      closePlayer();
      syncRoute();
      return;
    }
    location.hash = "#/";
  });
  navProfile.addEventListener("click", openPublish);
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

  loadReasons();
  loadLive();
  setInterval(loadLive, 20000);
  syncRoute();
})();
