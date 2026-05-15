<template>
  <div class="qr-scanner">
    <div class="qr-header">
      <span class="qr-title">{{ title }}</span>
      <button v-if="closable" class="qr-close" @click="$emit('cancel')">
        ✕
      </button>
    </div>

    <div v-if="hint" class="qr-hint">{{ hint }}</div>

    <div v-if="cameraSupported" class="qr-video-wrap">
      <video ref="videoEl" autoplay muted playsinline></video>
      <div class="qr-overlay-frame"></div>
    </div>

    <div v-if="!cameraSupported" class="qr-no-cam">
      Live QR scanning isn't available in this browser. Paste the payload from
      your device below.
    </div>

    <div class="qr-paste-row">
      <label>Paste payload manually</label>
      <textarea
        v-model="pasted"
        rows="3"
        placeholder="WIF|twice_prerotated_key_hash|prerotated_key_hash|prev_public_key_hash|rotation_index"
        @keydown.enter.prevent="submitPasted"
      ></textarea>
      <button
        class="qr-submit"
        :disabled="!pasted.trim()"
        @click="submitPasted"
      >
        Use Pasted Payload
      </button>
    </div>

    <div v-if="error" class="qr-err">⚠ {{ error }}</div>
    <div v-if="status" class="qr-status">{{ status }}</div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";

const props = defineProps({
  title: { type: String, default: "Scan QR from hardware device" },
  hint: { type: String, default: "" },
  closable: { type: Boolean, default: true },
});
const emit = defineEmits(["scanned", "cancel"]);

const videoEl = ref(null);
const pasted = ref("");
const error = ref("");
const status = ref("");
const cameraSupported = ref(
  typeof window !== "undefined" &&
    "BarcodeDetector" in window &&
    typeof navigator !== "undefined" &&
    navigator.mediaDevices?.getUserMedia,
);

let stream = null;
let detector = null;
let rafId = null;
let stopped = false;

async function startCamera() {
  if (!cameraSupported.value) return;
  try {
    // Some Chromium builds expose BarcodeDetector but only support certain formats.
    const formats = await window.BarcodeDetector.getSupportedFormats();
    if (!formats.includes("qr_code")) {
      cameraSupported.value = false;
      error.value =
        "QR format not supported by this browser's BarcodeDetector.";
      return;
    }
    detector = new window.BarcodeDetector({ formats: ["qr_code"] });
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment" },
      audio: false,
    });
    if (stopped) {
      stream.getTracks().forEach((t) => t.stop());
      return;
    }
    if (videoEl.value) {
      videoEl.value.srcObject = stream;
      await videoEl.value.play().catch(() => {});
    }
    status.value = "Point the camera at the QR code…";
    scanLoop();
  } catch (e) {
    cameraSupported.value = false;
    error.value =
      "Camera unavailable: " +
      (e?.message || String(e)) +
      " — paste payload below.";
  }
}

async function scanLoop() {
  if (stopped || !detector || !videoEl.value) return;
  try {
    const codes = await detector.detect(videoEl.value);
    if (codes && codes.length) {
      const raw = codes[0].rawValue || "";
      if (raw) {
        emit("scanned", raw);
        return; // parent will unmount us
      }
    }
  } catch {
    // detect() can throw on certain frames; ignore and keep trying
  }
  rafId = requestAnimationFrame(scanLoop);
}

function submitPasted() {
  const text = pasted.value.trim();
  if (!text) return;
  emit("scanned", text);
}

function teardown() {
  stopped = true;
  if (rafId) cancelAnimationFrame(rafId);
  rafId = null;
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
  if (videoEl.value) {
    try {
      videoEl.value.pause();
      videoEl.value.srcObject = null;
    } catch {}
  }
}

onMounted(() => {
  startCamera();
});
onBeforeUnmount(() => {
  teardown();
});
</script>

<style scoped>
.qr-scanner {
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: var(--surface, #1e1e2e);
  border: 1px solid var(--border, #333);
  border-radius: 10px;
  padding: 12px 14px;
}
.qr-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.qr-title {
  font-weight: 700;
  color: var(--accent);
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.qr-close {
  background: transparent;
  color: var(--subtext, #999);
  border: none;
  font-size: 1.1rem;
  cursor: pointer;
}
.qr-hint {
  font-size: 0.8rem;
  color: var(--subtext, #aaa);
}
.qr-video-wrap {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.qr-video-wrap video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.qr-overlay-frame {
  position: absolute;
  inset: 14%;
  border: 2px solid var(--accent, #7c6af7);
  border-radius: 10px;
  pointer-events: none;
  box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.35);
}
.qr-no-cam {
  font-size: 0.82rem;
  color: var(--subtext, #aaa);
  background: var(--bg, #0f1117);
  border: 1px dashed var(--border, #333);
  border-radius: 6px;
  padding: 10px;
}
.qr-paste-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.qr-paste-row label {
  font-size: 0.72rem;
  color: var(--subtext, #999);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.qr-paste-row textarea {
  background: var(--bg, #0f1117);
  color: var(--text, #e0e0e0);
  border: 1px solid var(--border, #333);
  border-radius: 6px;
  padding: 8px 10px;
  font-family: ui-monospace, SFMono-Regular, monospace;
  font-size: 0.78rem;
  resize: vertical;
}
.qr-paste-row textarea:focus {
  outline: none;
  border-color: var(--accent);
}
.qr-submit {
  align-self: flex-start;
  background: var(--accent, #7c6af7);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 6px 14px;
  font-size: 0.82rem;
  cursor: pointer;
}
.qr-submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.qr-err {
  color: var(--red2, #ff7676);
  font-size: 0.8rem;
}
.qr-status {
  font-size: 0.78rem;
  color: var(--subtext, #aaa);
}
</style>
