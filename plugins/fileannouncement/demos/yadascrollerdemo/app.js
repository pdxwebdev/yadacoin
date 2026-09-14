(() => {
  const API_VIDEOS = "/file-announcements/api/v1/public/videos";
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

  const probe = document.createElement("video");

  function showStatus(msg, ms = 2800) {
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

  function formatHint(item) {
    const mime = mimeFor(item);
    const name = item.filename || "";
    if (mime === "video/quicktime" || /\.mov$/i.test(name)) {
      return (
        "This is a QuickTime (.mov) file — often HEVC from macOS screen recording. " +
        "Chrome/Edge usually cannot decode it. Open in Safari, or re-upload as H.264 MP4 " +
        "(video/mp4) from File Announcements."
      );
    }
    return (
      "Browser could not decode this video. Prefer H.264 + AAC in an .mp4 container " +
      `(got ${mime || "unknown"}).`
    );
  }

  function setSlideError(slide, message) {
    slide.classList.add("ready", "error");
    slide.dataset.error = "1";
    let err = slide.querySelector(".err");
    if (!err) {
      err = document.createElement("div");
      err.className = "err";
      slide.appendChild(err);
    }
    err.textContent = message;
  }

  function buildSlide(item, index) {
    const slide = document.createElement("section");
    slide.className = "slide";
    slide.dataset.index = String(index);
    slide.dataset.key = `${item.backend}:${item.file_id}`;
    slide.dataset.mime = mimeFor(item);

    const video = document.createElement("video");
    video.playsInline = true;
    video.setAttribute("playsinline", "");
    video.setAttribute("webkit-playsinline", "");
    video.loop = true;
    video.muted = muted;
    video.preload = "metadata";
    video.controls = false;
    video.setAttribute("data-src", streamUrl(item));
    video.setAttribute("data-type", mimeFor(item));

    const spinner = document.createElement("div");
    spinner.className = "spinner";

    const tags = (item.keywords || [])
      .slice(0, 6)
      .map((k) => `<span class="tag">#${escapeHtml(k)}</span>`)
      .join("");

    const meta = document.createElement("div");
    meta.className = "meta";
    meta.innerHTML = `
      <h2>${escapeHtml(item.title || "Untitled")}</h2>
      <p>${escapeHtml(item.description || "")}</p>
      ${tags ? `<div class="tags">${tags}</div>` : ""}
    `;

    slide.appendChild(video);
    slide.appendChild(spinner);
    slide.appendChild(meta);

    const side = document.createElement("div");
    side.className = "side-actions";
    const reportBtn = document.createElement("button");
    reportBtn.type = "button";
    reportBtn.textContent = "Report";
    reportBtn.title = "Report / request takedown";
    reportBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openReport(item);
    });
    side.appendChild(reportBtn);
    slide.appendChild(side);

    if (!canLikelyPlay(mimeFor(item))) {
      setSlideError(slide, formatHint(item));
    }

    video.addEventListener("loadeddata", () => {
      slide.classList.add("ready");
      slide.classList.remove("error");
      const err = slide.querySelector(".err");
      if (err) err.remove();
    });
    video.addEventListener("error", () => {
      const mediaErr = video.error;
      const code = mediaErr ? mediaErr.code : 0;
      const detail =
        code === 4
          ? formatHint(item)
          : `Playback error (code ${code || "?"}). ${formatHint(item)}`;
      setSlideError(slide, detail);
    });
    video.addEventListener("click", () => {
      if (slide.classList.contains("error")) return;
      if (video.paused) video.play().catch(() => {});
      else video.pause();
    });

    return slide;
  }

  function renderFeed() {
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
    requestAnimationFrame(() => {
      activateIndex(0, true);
      prefetchAround(0);
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
    const type = video.getAttribute("data-type") || "";
    if (!src) return;
    if (video.getAttribute("src") === src) return;
    // Use <source> so the browser gets an explicit MIME type
    video.removeAttribute("src");
    while (video.firstChild) video.removeChild(video.firstChild);
    const source = document.createElement("source");
    source.src = src;
    if (type) source.type = type;
    video.appendChild(source);
    video.setAttribute("src", src); // keep for equality checks / some engines
    video.load();
  }

  function activateIndex(index, forceScroll) {
    if (!videos.length) return;
    index = Math.max(0, Math.min(index, videos.length - 1));
    activeIndex = index;
    const slides = feed.querySelectorAll(".slide");
    const slide = slides[index];
    if (!slide) return;
    const video = slide.querySelector("video");
    if (slide.classList.contains("error") && !video.getAttribute("src")) {
      // still try once — Safari may play quicktime even if canPlayType is empty
      ensureSrc(video);
    } else {
      ensureSrc(video);
    }
    video.muted = muted;
    pauseAllExcept(video);
    const play = () => {
      video.play().catch((err) => {
        if (!slide.classList.contains("error")) {
          setSlideError(
            slide,
            `Autoplay blocked or decode failed: ${err && err.message ? err.message : err}. ${formatHint(videos[index] || {})}`
          );
        }
      });
    };
    if (video.readyState >= 2) play();
    else {
      video.addEventListener("canplay", play, { once: true });
      // Fallback if neither canplay nor error fires (stuck spinner)
      setTimeout(() => {
        if (!slide.classList.contains("ready") && video.readyState < 2) {
          if (video.error) {
            video.dispatchEvent(new Event("error"));
          } else if (video.readyState === 0) {
            setSlideError(slide, formatHint(videos[index] || {}));
          }
        }
      }, 8000);
    }

    slides.forEach((s, i) => {
      const v = s.querySelector("video");
      if (!v) return;
      if (Math.abs(i - index) > 3) {
        if (v.getAttribute("src") || v.querySelector("source")) {
          v.removeAttribute("src");
          while (v.firstChild) v.removeChild(v.firstChild);
          v.load();
          s.classList.remove("ready");
        }
      } else if (Math.abs(i - index) <= 2 && i !== index) {
        ensureSrc(v);
      }
    });

    if (forceScroll) {
      slide.scrollIntoView({ behavior: "auto", block: "start" });
    }
    prefetchAround(index);
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
    const key = `${item.backend}:${item.file_id}`;
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
        .map((v) => `${v.backend}:${v.file_id}`)
    );
    for (const [key, ac] of prefetchControllers) {
      if (!keep.has(key)) {
        ac.abort();
        prefetchControllers.delete(key);
      }
    }
  }

  async function loadVideos(q) {
    if (loading) return;
    loading = true;
    showStatus("Loading videos…", 0);
    try {
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        skip: "0",
      });
      if (q) params.set("q", q);
      const res = await fetch(`${API_VIDEOS}?${params}`, {
        credentials: "same-origin",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.status) throw new Error(data.error || "search failed");
      videos = (data.results || []).filter((r) => r.stream_url && r.file_id);
      prefetched.clear();
      for (const ac of prefetchControllers.values()) ac.abort();
      prefetchControllers.clear();
      renderFeed();
      if (videos.length) {
        const unsupported = videos.filter((v) => !canLikelyPlay(mimeFor(v))).length;
        let msg = `${videos.length} video${videos.length === 1 ? "" : "s"}`;
        if (unsupported) {
          msg += ` · ${unsupported} may need Safari or H.264 MP4`;
        }
        showStatus(msg, unsupported ? 6000 : 2800);
      } else {
        showStatus("");
      }
    } catch (err) {
      videos = [];
      renderFeed();
      showStatus(`Failed to load: ${err.message || err}`, 5000);
    } finally {
      loading = false;
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
    if (reportDlg.open) return;
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

  setTimeout(() => hintEl.classList.add("fade"), 4500);

  loadReasons();
  loadVideos("");
})();
