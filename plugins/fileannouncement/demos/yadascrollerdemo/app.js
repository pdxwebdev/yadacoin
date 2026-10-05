(() => {
  const API_VIDEOS = "/file-announcements/api/v1/public/videos";
  const API_PROFILE = "/file-announcements/api/v1/public/profile";
  const API_ME = "/file-announcements/api/v1/public/me";
  const API_REASONS = "/file-announcements/api/v1/public/takedown-reasons";
  const API_TAKEDOWN = "/file-announcements/api/v1/public/takedown";
  const PREFETCH_COUNT = 10;
  /** ~2s of video at ~2 Mbps ≈ 512 KiB; used for Range prefetch warm-up */
  const PREFETCH_BYTES = 512 * 1024;
  const PAGE_SIZE = 40;

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
    el.style.background = avatarColor(name || "?");
    el.innerHTML = avatarMarkup(name);
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
    avatarBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openProfile(item);
    });
    const reportBtn = document.createElement("button");
    reportBtn.type = "button";
    reportBtn.textContent = "Report";
    reportBtn.title = "Report / request takedown";
    reportBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openReport(item);
    });
    side.appendChild(avatarBtn);
    side.appendChild(reportBtn);
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
    const active = feed.querySelectorAll("video")[activeIndex];
    if (active && !muted) active.play().catch(() => {});
  });

  refreshBtn.addEventListener("click", () => loadVideos(query));

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

  function pauseFeed() {
    feed.querySelectorAll("video").forEach((v) => {
      try {
        v.pause();
      } catch (_) {}
    });
  }

  function closePlayer() {
    try {
      playerVideo.pause();
    } catch (_) {}
    playerVideo.removeAttribute("src");
    try {
      playerVideo.load();
    } catch (_) {}
    playerEl.hidden = true;
    playerSpinner.hidden = true;
    playerCaption.textContent = "";
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
    pauseFeed();
    playerCaption.textContent = item.title || item.filename || "";
    playerSpinner.hidden = false;
    playerEl.hidden = false;
    playerVideo.muted = muted;
    playerVideo.src = url;
    playerVideo.play().catch(() => {});
  }

  playerVideo.addEventListener("playing", hidePlayerSpinner);
  playerVideo.addEventListener("error", hidePlayerSpinner);

  function renderProfile(profile) {
    profileVideos = (profile && profile.videos) || [];
    const name = displayName(profile);
    profileTopTitle.textContent = profile && profile.username ? profile.username : "Profile";
    profileName.textContent = name;
    paintAvatar(profileAvatar, profile && profile.username);
    if (profile && profile.username) {
      profileSub.hidden = true;
      profileSub.textContent = "";
    } else {
      profileSub.hidden = false;
      profileSub.textContent = "No identity announcement";
    }
    profileActions.hidden = !(profile && profile.is_me);
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
    profileVideos = [];
    profileTopTitle.textContent = "Profile";
    profileName.textContent = "Profile";
    paintAvatar(profileAvatar, "");
    profileSub.hidden = false;
    profileSub.textContent = message;
    profileActions.hidden = true;
    profileGrid.innerHTML = "";
    profileEmpty.hidden = true;
  }

  async function loadProfile(route) {
    profileGrid.innerHTML = "";
    profileEmpty.hidden = true;
    profileName.textContent = "Loading…";
    profileActions.hidden = true;
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
    const onFeed = viewName === "feed";
    const onProfile = viewName === "profile";
    appEl.classList.toggle("view-profile", !onFeed);
    profileEl.hidden = !onProfile;
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
  }

  function leaveOverlay() {
    if (
      location.hash.startsWith("#/profile") ||
      location.hash.startsWith("#/@") ||
      location.hash.startsWith("#/publish") ||
      location.hash === "#/me"
    ) {
      history.back();
      return;
    }
    location.hash = "#/";
  }

  profileBack.addEventListener("click", leaveOverlay);
  publishBack.addEventListener("click", leaveOverlay);
  playerBack.addEventListener("click", closePlayer);
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
  window.addEventListener("hashchange", syncRoute);

  setTimeout(() => hintEl.classList.add("fade"), 4500);

  loadReasons();
  syncRoute();
})();
