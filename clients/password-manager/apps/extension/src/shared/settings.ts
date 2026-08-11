import type { ThemeMode, ThemeDensity, ThemePartial } from "@yadacoin/password-shared-ui";

export interface UserSettings {
  nodeUrl: string;
  themeUrl: string;
  presetId: string;
  mode: ThemeMode;
  primary: string;
  density: ThemeDensity;
  brandName: string;
}

export const DEFAULT_SETTINGS: UserSettings = {
  nodeUrl: "",
  themeUrl: "",
  presetId: "default",
  mode: "system",
  primary: "",
  density: "comfortable",
  brandName: "",
};

const KEY = "yadaPasswordSettings";

export async function loadSettings(): Promise<UserSettings> {
  if (typeof chrome !== "undefined" && chrome.storage?.sync) {
    const data = await chrome.storage.sync.get(KEY);
    return { ...DEFAULT_SETTINGS, ...(data[KEY] as Partial<UserSettings> | undefined) };
  }
  try {
    const raw = localStorage.getItem(KEY);
    return raw
      ? { ...DEFAULT_SETTINGS, ...(JSON.parse(raw) as Partial<UserSettings>) }
      : { ...DEFAULT_SETTINGS };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export async function saveSettings(settings: UserSettings): Promise<void> {
  if (typeof chrome !== "undefined" && chrome.storage?.sync) {
    await chrome.storage.sync.set({ [KEY]: settings });
    return;
  }
  localStorage.setItem(KEY, JSON.stringify(settings));
}

export function settingsToThemePartial(s: UserSettings): ThemePartial {
  const partial: ThemePartial = {
    mode: s.mode,
    shape: { density: s.density },
  };
  if (s.primary) {
    partial.colors = { primary: s.primary };
  }
  if (s.brandName) {
    partial.brand = { name: s.brandName };
  }
  return partial;
}

export async function fetchRemoteTheme(
  themeUrl: string
): Promise<ThemePartial | null> {
  if (!themeUrl) return null;
  try {
    const res = await fetch(themeUrl, { headers: { Accept: "application/json" } });
    if (!res.ok) return null;
    return (await res.json()) as ThemePartial;
  } catch {
    return null;
  }
}
