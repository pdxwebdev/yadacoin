(function () {
  var state = {
    status: null,
    job: null,
    startedAt: null,
    bootId: null,
    restarting: false,
    stopping: false,
    holdNotice: false
  };
  var seenLogs = {};
  var stick = true;
  var pollTimer = null;

  var pill = document.getElementById("header-pill");
  var flash = document.getElementById("flash");
  var reloadBtn = document.getElementById("reload-btn");
  var modal = document.getElementById("modal");
  var confirmInput = document.getElementById("confirm-input");
  var confirmBtn = document.getElementById("confirm-btn");
  var logEl = document.getElementById("log");

  function formatBytes(n) {
    if (n == null || !isFinite(n)) return "—";
    var value = n;
    var units = ["B", "KB", "MB", "GB", "TB"];
    var i = 0;
    while (value >= 1024 && i < units.length - 1) {
      value /= 1024;
      i += 1;
    }
    if (i === 0) return Math.round(value) + " " + units[i];
    return value.toFixed(1) + " " + units[i];
  }

  function formatDuration(seconds) {
    if (seconds == null || !isFinite(seconds)) return "";
    seconds = Math.max(0, Math.round(seconds));
    var h = Math.floor(seconds / 3600);
    var m = Math.floor((seconds % 3600) / 60);
    var s = seconds % 60;
    if (h) return h + "h " + m + "m " + s + "s";
    if (m) return m + "m " + s + "s";
    return s + "s";
  }

  function formatCount(n) {
    if (n == null) return "—";
    return Number(n).toLocaleString();
  }

  function setPill(kind, text) {
    pill.className = "Label " + (kind || "");
    pill.textContent = text;
  }

  function showFlash(kind, text) {
    if (!text) {
      flash.hidden = true;
      flash.textContent = "";
      return;
    }
    flash.hidden = false;
    flash.className = "flash " + kind;
    flash.textContent = text;
  }

  function renderStatus() {
    var mongo = state.status && state.status.mongo;
    var tools = state.status && state.status.tools;
    document.getElementById("stat-blocks").textContent = mongo && mongo.ok ? formatCount(mongo.blocks) : "—";
    document.getElementById("stat-consensus").textContent = mongo && mongo.ok ? formatCount(mongo.consensus) : "—";
    document.getElementById("stat-height").textContent = mongo && mongo.ok && mongo.height != null ? formatCount(mongo.height) : "—";
    var meta = "Config unavailable";
    if (mongo && mongo.host) {
      meta = mongo.database + " @ " + mongo.host + ":" + mongo.port;
      if (mongo.authenticated) meta += " · authenticated";
      if (mongo.note) meta += " · " + mongo.note;
      if (mongo.error) meta += " · " + mongo.error;
    } else if (mongo && mongo.error) {
      meta = mongo.error;
    }
    document.getElementById("status-meta").textContent = meta;
    if (state.status && state.status.bootstrap_url) {
      var link = document.getElementById("bootstrap-url");
      link.href = state.status.bootstrap_url;
      link.textContent = state.status.bootstrap_url.replace(/^https?:\/\//, "");
    }
    var tool = "mongorestore not found";
    if (tools && tools.mode === "local") tool = "mongorestore on PATH";
    if (tools && tools.mode === "docker") tool = "docker mongo:latest";
    document.getElementById("about-tool").textContent = tool;
    document.getElementById("about-target").textContent = mongo && mongo.host
      ? mongo.database + " @ " + mongo.host + ":" + mongo.port
      : "—";
    var running = state.job && state.job.status === "running";
    reloadBtn.disabled = running || state.restarting;
    if (state.restarting) setPill("warn", "Restarting");
    else if (running) setPill("warn", "Reload running");
    else if (state.job && state.job.status === "failed") setPill("danger", "Reload failed");
    else if (mongo && mongo.ok) setPill("ok", "MongoDB connected");
    else if (state.job && state.job.status === "succeeded") setPill("ok", "Reload complete");
    else setPill("danger", "MongoDB unreachable");
    if (state.holdNotice || running) return;
    if (state.job && state.job.status === "failed") showFlash("error", state.job.error);
    else if (state.job && state.job.status === "succeeded" && state.job.warning) showFlash("warn", state.job.warning);
    else if (state.job && state.job.status === "succeeded") {
      var deleted = state.job.result && state.job.result.consensus_deleted;
      var back = state.cameBack ? "Node is back. " : "";
      showFlash("ok", back + "Database reloaded. Consensus truncated (" + formatCount(deleted || 0) + " documents removed).");
    } else if (mongo && !mongo.ok && mongo.error) showFlash("warn", mongo.error);
    else if (tools && tools.mode === "missing") showFlash("warn", "Install MongoDB database tools or Docker before reloading.");
    else showFlash("", "");
  }

  function iconText(status) {
    if (status === "succeeded") return "✓";
    if (status === "failed") return "✕";
    if (status === "skipped") return "–";
    return "";
  }

  function renderJob() {
    var job = state.job;
    var empty = document.getElementById("job-empty");
    var steps = document.getElementById("steps");
    var command = document.getElementById("command");
    var logWrap = document.getElementById("log-wrap");
    if (!job) {
      empty.hidden = false;
      steps.hidden = true;
      command.hidden = true;
      logWrap.hidden = true;
      document.getElementById("elapsed").textContent = "";
      document.title = "Node dashboard · yadacoin";
      return;
    }
    empty.hidden = true;
    steps.hidden = false;
    logWrap.hidden = false;
    steps.innerHTML = "";
    job.steps.forEach(function (step) {
      var li = document.createElement("li");
      li.className = "step " + step.status;
      var icon = document.createElement("span");
      icon.className = "step-icon";
      icon.textContent = iconText(step.status);
      var body = document.createElement("div");
      var label = document.createElement("div");
      label.className = "step-label";
      label.textContent = step.label;
      var msg = document.createElement("div");
      msg.className = "step-msg";
      msg.textContent = step.message || step.status;
      body.appendChild(label);
      body.appendChild(msg);
      if (step.status === "running") {
        var bar = document.createElement("div");
        var fill = document.createElement("span");
        var percent = step.progress && step.progress.percent;
        if (percent == null) bar.className = "progress indeterminate";
        else {
          bar.className = "progress";
          fill.style.width = Math.max(0, Math.min(100, percent)) + "%";
        }
        bar.appendChild(fill);
        body.appendChild(bar);
      }
      li.appendChild(icon);
      li.appendChild(body);
      steps.appendChild(li);
    });
    if (job.result && job.result.command) {
      command.hidden = false;
      command.textContent = job.result.command;
    } else {
      command.hidden = true;
    }
    var end = job.finished_at || (Date.now() / 1000);
    document.getElementById("elapsed").textContent = formatDuration(end - job.started_at);
    document.title = (job.status === "running" ? "(running) " : "") + "Node dashboard · yadacoin";
  }

  function appendLog(entry) {
    if (!entry || seenLogs[entry.id]) return;
    seenLogs[entry.id] = true;
    var atBottom = logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight < 48;
    var row = document.createElement("div");
    row.className = "log-line";
    var ts = document.createElement("span");
    ts.className = "log-ts";
    ts.textContent = new Date(entry.ts * 1000).toLocaleTimeString();
    var step = document.createElement("span");
    step.className = "log-step";
    step.textContent = entry.step;
    var text = document.createElement("span");
    text.className = "log-text";
    text.textContent = entry.line;
    row.appendChild(ts);
    row.appendChild(step);
    row.appendChild(text);
    logEl.appendChild(row);
    while (logEl.childNodes.length > 1500) logEl.removeChild(logEl.firstChild);
    if (stick || atBottom) logEl.scrollTop = logEl.scrollHeight;
  }

  function applySnapshot(payload) {
    var next = payload.job;
    if (!state.job || !next || state.job.id !== next.id) {
      seenLogs = {};
      logEl.innerHTML = "";
    }
    state.job = next;
    state.cursor = payload.cursor || state.cursor;
    if (state.job && state.job.logs) state.job.logs.forEach(appendLog);
    renderJob();
    renderStatus();
  }

  var SIGNIN = "/yada-password/signin?purpose=operator&next=" + encodeURIComponent("/operator");
  var signingIn = false;

  function goSignin() {
    if (signingIn) return;
    signingIn = true;
    window.location.assign(SIGNIN);
  }

  function nodeBackSignIn() {
    if (signingIn) return;
    signingIn = true;
    state.restarting = false;
    state.holdNotice = false;
    showFlash("ok", "Node is back. Sign in again to continue.");
    setPill("ok", "Node is back");
    setTimeout(function () { window.location.assign(SIGNIN); }, 1200);
  }

  function loadStatus() {
    if (state.restarting) return Promise.resolve();
    return fetch("/operator/api/status", { cache: "no-store" })
      .then(function (res) {
        if (res.status === 401) {
          goSignin();
          return null;
        }
        if (!res.ok) throw new Error("status");
        return res.json();
      })
      .then(function (data) {
        if (!data) return;
        state.status = data;
        if (data.started_at != null) state.startedAt = data.started_at;
        if (data.boot_id != null) state.bootId = data.boot_id;
        renderStatus();
      })
      .catch(function () {
        if (!state.holdNotice) setPill("danger", "Node unreachable");
      });
  }

  function schedulePoll(ms) {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(pollJob, ms);
  }

  function watchRestart() {
    if (state.restarting) return;
    state.restarting = true;
    state.holdNotice = true;
    clearTimeout(pollTimer);
    showFlash("warn", "Node is restarting. Do not refresh this page.");
    setPill("warn", "Restarting");
    renderJob();
    var previous = state.startedAt;
    var previousBoot = state.bootId;
    var sawDown = false;
    var watchStarted = Date.now();
    function markBack(data) {
      state.restarting = false;
      state.holdNotice = false;
      state.cameBack = true;
      if (data && data.started_at != null) state.startedAt = data.started_at;
      if (data && data.boot_id != null) state.bootId = data.boot_id;
      setPill("ok", "Node is back");
      loadStatus();
      schedulePoll(0);
    }
    function sameProcess(data) {
      if (previousBoot != null && data.boot_id != null) return data.boot_id === previousBoot;
      return previous != null && data.started_at === previous;
    }
    function tick() {
      fetch("/operator/api/health", { cache: "no-store" })
        .then(function (res) {
          if (res.status === 401) {
            nodeBackSignIn();
            return null;
          }
          if (!res.ok) throw new Error("down");
          return res.json();
        })
        .then(function (data) {
          if (!data || !data.ok) throw new Error("down");
          if (sawDown || !sameProcess(data) || Date.now() - watchStarted > 8000) {
            markBack(data);
            return;
          }
          setTimeout(tick, 1000);
        })
        .catch(function () {
          sawDown = true;
          showFlash("warn", "Node is restarting. Do not refresh this page.");
          setTimeout(tick, 1000);
        });
    }
    setTimeout(tick, 1000);
  }

  function watchStop() {
    if (state.stopping) return;
    state.stopping = true;
    state.holdNotice = true;
    clearTimeout(pollTimer);
    showFlash("warn", "Stopping the node. Do not refresh this page.");
    setPill("warn", "Stopping node");
    var sawDown = false;
    function tick() {
      fetch("/operator/api/health", { cache: "no-store" })
        .then(function (res) {
          if (!res.ok) throw new Error("down");
          return res.json();
        })
        .then(function (data) {
          if (!data || !data.ok) throw new Error("down");
          if (sawDown) {
            if (state.bootId != null && data.boot_id === state.bootId) {
              sawDown = false;
              setTimeout(tick, 1000);
              return;
            }
            state.stopping = false;
            state.restarting = false;
            state.holdNotice = false;
            state.cameBack = true;
            if (data.boot_id != null) state.bootId = data.boot_id;
            if (data.started_at != null) state.startedAt = data.started_at;
            setPill("ok", "Node is back");
            pollJob();
            return;
          }
          setTimeout(tick, 1000);
        })
        .catch(function () {
          sawDown = true;
          fetch("http://127.0.0.1:8102/job", { cache: "no-store" })
            .then(function (res) { return res.ok ? res.json() : null; })
            .then(function (data) {
              if (data && data.job) applySnapshot(data);
            })
            .catch(function () {
              var job = state.job;
              (job && job.steps || []).forEach(function (step) {
                if (step.id === "restore" && step.status === "running") {
                  step.message = "Node is down. mongorestore is running.";
                }
              });
              renderJob();
            });
          showFlash("warn", "Node is down. mongorestore is running. Do not refresh this page.");
          setPill("warn", "Restoring");
          setTimeout(tick, 1000);
        });
    }
    setTimeout(tick, 1000);
  }

  function plannedRestart(job) {
    return !!(job && job.result && (job.result.restarting || job.result.reloaded));
  }

  function failDisconnected() {
    var job = state.job;
    if (!job || job.status !== "running") {
      schedulePoll(2000);
      return;
    }
    var step = null;
    (job.steps || []).forEach(function (item) {
      if (item.status === "running") step = item;
    });
    var label = step ? step.label : "reload";
    var message = "Lost the node during " + label + ". This was not a restart.";
    job.status = "failed";
    job.error = message;
    job.finished_at = Date.now() / 1000;
    if (step) {
      step.status = "failed";
      step.message = message;
    }
    state.holdNotice = false;
    state.restarting = false;
    showFlash("error", message);
    renderJob();
    renderStatus();
    schedulePoll(3000);
  }

  function pollJob() {
    if (state.restarting) return;
    fetch("/operator/api/job", { cache: "no-store" })
      .then(function (res) {
        if (res.status === 401) {
          if (state.job && state.job.result && (state.job.result.restarting || state.job.result.reloaded)) {
            nodeBackSignIn();
          } else {
            goSignin();
          }
          return null;
        }
        if (!res.ok) throw new Error("job");
        return res.json();
      })
      .then(function (data) {
        if (!data) return;
        if (data.job && data.job.status === "failed") state.holdNotice = false;
        applySnapshot(data);
        if (data.job && data.job.result && data.job.result.stopping) {
          watchStop();
          return;
        }
        if (data.job && data.job.result && data.job.result.restarting) {
          watchRestart();
          return;
        }
        schedulePoll(data.job && data.job.status === "running" ? 1000 : 3000);
      })
      .catch(function () {
        if (state.stopping) {
          watchStop();
          return;
        }
        if (plannedRestart(state.job)) {
          watchRestart();
          return;
        }
        if (state.job && state.job.status === "running") {
          failDisconnected();
          return;
        }
        schedulePoll(2000);
      });
  }

  function openModal() {
    var mongo = state.status && state.status.mongo;
    document.getElementById("modal-target").textContent = mongo && mongo.host
      ? "Target: " + mongo.database + " @ " + mongo.host + ":" + mongo.port
      : "Target: the database in config.json";
    confirmInput.value = "";
    confirmBtn.disabled = true;
    modal.hidden = false;
    confirmInput.focus();
  }

  function closeModal() {
    modal.hidden = true;
    reloadBtn.focus();
  }

  reloadBtn.addEventListener("click", openModal);
  document.getElementById("cancel-btn").addEventListener("click", closeModal);
  modal.addEventListener("click", function (event) {
    if (event.target === modal) closeModal();
  });
  confirmInput.addEventListener("input", function () {
    confirmBtn.disabled = confirmInput.value !== "reload";
  });
  confirmInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !confirmBtn.disabled) confirmBtn.click();
    if (event.key === "Escape") closeModal();
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !modal.hidden) closeModal();
  });
  logEl.addEventListener("scroll", function () {
    stick = logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight < 48;
  });
  confirmBtn.addEventListener("click", function () {
    confirmBtn.disabled = true;
    fetch("/operator/api/reload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: "reload" })
    }).then(function (res) {
      return res.json().then(function (data) {
        if (res.status === 401) {
          goSignin();
          return;
        }
        if (!res.ok) throw new Error(data.error || "Reload failed to start");
        closeModal();
        seenLogs = {};
        logEl.innerHTML = "";
        state.holdNotice = true;
        showFlash("warn", "Do not refresh this page. Writers will pause, then mongorestore starts.");
        applySnapshot(data);
        schedulePoll(1000);
      });
    }).catch(function (err) {
      state.holdNotice = false;
      showFlash("error", err.message);
      confirmBtn.disabled = confirmInput.value !== "reload";
    });
  });

  setInterval(function () {
    if (state.job && state.job.status === "running" && !state.restarting) renderJob();
  }, 1000);
  setInterval(function () {
    if (!state.restarting) loadStatus();
  }, 3000);
  loadStatus();
  pollJob();
})();
