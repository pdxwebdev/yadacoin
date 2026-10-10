(() => {
  const API_VIDEOS = "/file-announcements/api/v1/public/videos";
  const API_PHOTOS = "/file-announcements/api/v1/public/photos";
  const API_FILES = "/file-announcements/api/v1/files";
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
  const playerEl = document.getElementById("player");
  const playerBack = document.getElementById("player-back");
  const playerVideo = document.getElementById("player-video");
  const playerPhoto = document.getElementById("player-photo");
  const uploadFile = document.getElementById("upload-file");
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
  let photos = [];
  let activeIndex = 0;
  let photoIndex = 0;
  let mediaMode = "videos";
  let photosLoadedQuery = null;
  let uploadBusy = false;
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
        if (isProfilePhoto(item) || !photoSrc(item)) continue;
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

  function wantsPhotoUpload() {
    if (viewName === "profile") return profileMedia === "photos";
    return mediaMode === "photos";
  }

  function pickUpload() {
    if (uploadBusy) return;
    uploadFile.accept = wantsPhotoUpload() ? "image/*" : "video/*";
    uploadFile.value = "";
    uploadFile.click();
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
    if (!file || !String(file.type || "").startsWith("video/")) return null;
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

  function postForm(url, fd) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", url);
      xhr.withCredentials = true;
      xhr.upload.onprogress = (ev) => {
        if (!ev.lengthComputable) return;
        const pct = Math.round((ev.loaded / ev.total) * 100);
        showStatus(`Uploading ${pct}%`, 0);
      };
      xhr.onload = () => {
        let data = {};
        try {
          data = JSON.parse(xhr.responseText || "{}");
        } catch (_) {}
        if (xhr.status === 401) {
          reject(new Error("Unlock File Announcements to upload"));
          return;
        }
        if (xhr.status < 200 || xhr.status >= 300 || data.status === false) {
          reject(new Error(data.error || "upload failed"));
          return;
        }
        resolve(data);
      };
      xhr.onerror = () => reject(new Error("upload failed"));
      xhr.send(fd);
    });
  }

  async function uploadSelected(file) {
    if (!file || uploadBusy) return;
    const image = String(file.type || "").startsWith("image/") || /\.(jpe?g|png|gif|webp|bmp|heic|heif)$/i.test(file.name);
    const video = String(file.type || "").startsWith("video/");
    if (!image && !video) {
      showStatus("Choose a photo or video", 2500);
      return;
    }
    uploadBusy = true;
    showStatus(image ? "Resizing photo…" : "Capturing thumbnail…", 0);
    try {
      const fd = new FormData();
      fd.set("title", titleFromName(file.name));
      fd.set("upload_id", crypto.randomUUID ? crypto.randomUUID() : `up${Date.now()}`);
      if (image) {
        const packed = await compressPhoto(file);
        fd.set("file", packed.file, packed.file.name);
        fd.set("thumbnail", packed.thumb, "thumbnail.jpg");
      } else {
        fd.set("file", file, file.name);
        const thumb = await captureVideoThumbnail(file);
        if (thumb) fd.set("thumbnail", thumb, "thumbnail.jpg");
      }
      showStatus("Uploading 0%", 0);
      await postForm(API_FILES, fd);
      showStatus("Announced", 2200);
      if (image) {
        photosLoadedQuery = null;
        profileMedia = "photos";
        if (viewName === "feed") setMedia("photos");
        else loadProfile(parseRoute());
      } else if (viewName === "feed") {
        setMedia("videos");
        loadVideos(query);
      } else {
        profileMedia = "videos";
        loadProfile(parseRoute());
      }
    } catch (err) {
      showStatus(err.message || "upload failed", 4000);
    } finally {
      uploadBusy = false;
    }
  }

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
    playerVideo.hidden = false;
    playerPhoto.hidden = true;
    playerPhoto.removeAttribute("src");
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

  function openPhoto(item) {
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
      tile.innerHTML = `${still}<span class="cap">${escapeHtml(label)}</span>`;
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
    navFyp.classList.toggle("active", onFeed);
    navProfile.classList.toggle("active", viewName === "publish");
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
    if (mediaMode === "photos") return photos[photoIndex] || null;
    return videos[activeIndex] || null;
  }

  playerBack.addEventListener("click", closePlayer);
  railGift.addEventListener("click", () => openGift(activeItem()));
  railReport.addEventListener("click", () => openReport(activeItem()));
  function openAnnouncements(fileType) {
    const params = new URLSearchParams({ tab: "upload" });
    if (fileType) params.set("type", fileType);
    location.assign(`/file-announcements?${params}`);
  }

  editAvatar.addEventListener("click", () => openAnnouncements(PROFILE_PHOTO_TYPE));
  editUpload.addEventListener("click", () => openAnnouncements(""));
  profileTabVideos.addEventListener("click", () => {
    profileMedia = "videos";
    renderProfileGrid();
  });
  profileTabPhotos.addEventListener("click", () => {
    profileMedia = "photos";
    renderProfileGrid();
  });
  function openPublish() {
    if ((location.hash || "") === "#/publish") {
      closePlayer();
      syncRoute();
      return;
    }
    location.hash = "#/publish";
  }

  navUpload.addEventListener("click", pickUpload);
  tabVideos.addEventListener("click", () => setMedia("videos"));
  tabPhotos.addEventListener("click", () => setMedia("photos"));
  uploadFile.addEventListener("change", () => {
    const file = uploadFile.files && uploadFile.files[0];
    if (file) uploadSelected(file);
  });
  navFyp.addEventListener("click", () => {
    const hash = location.hash || "";
    if (!hash || hash === "#" || hash === "#/" || hash === "#/photos") {
      closePlayer();
      syncRoute();
      return;
    }
    location.hash = mediaMode === "photos" ? "#/photos" : "#/";
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
