import { DEFAULT_THEME, DARK_THEME, PRESETS } from "./presets.js";
import type {
  ResolvedTheme,
  ThemeConfig,
  ThemeMode,
  ThemePartial,
} from "./types.js";

export interface ResolveThemeInput {
  /** Full preset or preset id */
  preset?: ThemeConfig | string | null;
  /** Remote / org white-label JSON */
  remote?: ThemePartial | null;
  /** User overrides (storage) */
  user?: ThemePartial | null;
  /** Override system preference detection */
  systemPrefersDark?: boolean;
}

function prefersDark(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function deepMergeTheme(base: ThemeConfig, overlay?: ThemePartial | null): ThemeConfig {
  if (!overlay) return base;
  return {
    id: overlay.id ?? base.id,
    name: overlay.name ?? base.name,
    mode: overlay.mode ?? base.mode,
    brand: { ...base.brand, ...overlay.brand },
    colors: { ...base.colors, ...overlay.colors },
    typography: { ...base.typography, ...overlay.typography },
    shape: { ...base.shape, ...overlay.shape },
  };
}

function resolveMode(
  mode: ThemeMode,
  systemPrefersDark?: boolean
): "light" | "dark" {
  if (mode === "light" || mode === "dark") return mode;
  const dark = systemPrefersDark ?? prefersDark();
  return dark ? "dark" : "light";
}

/**
 * Resolve order: default → preset → remote → user.
 * When final mode is system, colors come from light/dark base of the chosen family
 * unless remote/user already supplied a full palette for that mode.
 */
export function resolveTheme(input: ResolveThemeInput = {}): ResolvedTheme {
  let base: ThemeConfig = DEFAULT_THEME;

  if (typeof input.preset === "string") {
    base = PRESETS[input.preset] ?? DEFAULT_THEME;
  } else if (input.preset) {
    base = input.preset;
  }

  let merged = deepMergeTheme(base, input.remote);
  merged = deepMergeTheme(merged, input.user);

  const resolvedMode = resolveMode(merged.mode, input.systemPrefersDark);

  // If mode is system and no explicit color overrides from user/remote for contrast,
  // snap palette to built-in light/dark while keeping brand/primary overrides.
  if (merged.mode === "system") {
    const modeBase = resolvedMode === "dark" ? DARK_THEME : DEFAULT_THEME;
    const colorOverrides = {
      ...input.remote?.colors,
      ...input.user?.colors,
    };
    merged = {
      ...merged,
      colors: { ...modeBase.colors, ...colorOverrides },
    };
  }

  return {
    ...merged,
    resolvedMode,
  };
}

export function listPresets(): ThemeConfig[] {
  return Object.values(PRESETS);
}
