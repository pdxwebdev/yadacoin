import { applyTheme, resolveTheme } from "@yadacoin/password-shared-ui";
import {
  DEFAULT_SETTINGS,
  fetchRemoteTheme,
  loadSettings,
  saveSettings,
  settingsToThemePartial,
  type UserSettings,
} from "../shared/settings.js";
import { bootTheme } from "../shared/theme-boot.js";
import { requestOriginAccess } from "../shared/permissions.js";

function $(id: string): HTMLElement {
  const el = document.getElementById(id);
  if (!el) throw new Error(`#${id} missing`);
  return el;
}

function showAlert(message: string, kind: "error" | "success" | "" = "") {
  const el = $("alert");
  if (!message) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  el.textContent = message;
  el.className = `pm-alert${kind ? ` pm-alert--${kind}` : ""}`;
}

function readForm(): UserSettings {
  return {
    presetId: ($("preset") as HTMLSelectElement).value,
    mode: ($("mode") as HTMLSelectElement).value as UserSettings["mode"],
    primary: ($("primary") as HTMLInputElement).value,
    density: ($("density") as HTMLSelectElement).value as UserSettings["density"],
    nodeUrl: ($("nodeUrl") as HTMLInputElement).value.trim(),
    themeUrl: ($("themeUrl") as HTMLInputElement).value.trim(),
    brandName: ($("brandNameInput") as HTMLInputElement).value.trim(),
  };
}

function fillForm(s: UserSettings) {
  ($("preset") as HTMLSelectElement).value = s.presetId || "default";
  ($("mode") as HTMLSelectElement).value = s.mode || "system";
  if (s.primary) ($("primary") as HTMLInputElement).value = s.primary;
  ($("density") as HTMLSelectElement).value = s.density || "comfortable";
  ($("nodeUrl") as HTMLInputElement).value = s.nodeUrl || "";
  ($("themeUrl") as HTMLInputElement).value = s.themeUrl || "";
  ($("brandNameInput") as HTMLInputElement).value = s.brandName || "";
}

async function preview(settings: UserSettings) {
  const remote = await fetchRemoteTheme(settings.themeUrl);
  const theme = resolveTheme({
    preset: settings.presetId,
    remote,
    user: settingsToThemePartial(settings),
  });
  applyTheme(theme);
  const brandEl = document.getElementById("brandName");
  if (brandEl && theme.brand?.name) brandEl.textContent = theme.brand.name;
}

async function main() {
  await bootTheme();
  const settings = await loadSettings();
  fillForm(settings);

  ($("themeForm") as HTMLFormElement).addEventListener("submit", async (e) => {
    e.preventDefault();
    const next = readForm();
    if (next.nodeUrl) {
      const ok = await requestOriginAccess(next.nodeUrl);
      if (!ok) {
        showAlert("Permission denied for node URL", "error");
        return;
      }
    }
    await saveSettings(next);
    await preview(next);
    showAlert("Settings saved", "success");
  });

  $("previewBtn").addEventListener("click", async () => {
    await preview(readForm());
    showAlert("Preview applied (not saved)", "");
  });

  $("resetBtn").addEventListener("click", async () => {
    await saveSettings({ ...DEFAULT_SETTINGS });
    fillForm(DEFAULT_SETTINGS);
    await preview(DEFAULT_SETTINGS);
    showAlert("Reset to defaults", "success");
  });
}

void main();
