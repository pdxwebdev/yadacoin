import type { ThemeConfig } from "./types.js";

const baseTypography = {
  fontFamily:
    'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  baseSizePx: 14,
  fontWeightNormal: 400,
  fontWeightBold: 600,
};

const baseShape = {
  radiusSm: 6,
  radiusMd: 10,
  radiusLg: 16,
  density: "comfortable" as const,
};

export const DEFAULT_THEME: ThemeConfig = {
  id: "default",
  name: "Yada Light",
  mode: "light",
  brand: {
    name: "Yada Password",
  },
  colors: {
    background: "#f4f6f8",
    surface: "#ffffff",
    surfaceElevated: "#ffffff",
    text: "#0f172a",
    textMuted: "#64748b",
    primary: "#0d9488",
    primaryText: "#ffffff",
    danger: "#dc2626",
    dangerText: "#ffffff",
    success: "#16a34a",
    border: "#e2e8f0",
    focus: "#14b8a6",
    inputBackground: "#f8fafc",
    overlay: "rgba(15, 23, 42, 0.45)",
  },
  typography: { ...baseTypography },
  shape: { ...baseShape },
};

export const DARK_THEME: ThemeConfig = {
  id: "dark",
  name: "Yada Dark",
  mode: "dark",
  brand: {
    name: "Yada Password",
  },
  colors: {
    background: "#0b1220",
    surface: "#111827",
    surfaceElevated: "#1f2937",
    text: "#f1f5f9",
    textMuted: "#94a3b8",
    primary: "#2dd4bf",
    primaryText: "#042f2e",
    danger: "#f87171",
    dangerText: "#450a0a",
    success: "#4ade80",
    border: "#334155",
    focus: "#5eead4",
    inputBackground: "#0f172a",
    overlay: "rgba(0, 0, 0, 0.55)",
  },
  typography: { ...baseTypography },
  shape: { ...baseShape },
};

export const HIGH_CONTRAST_THEME: ThemeConfig = {
  id: "high-contrast",
  name: "High Contrast",
  mode: "dark",
  brand: {
    name: "Yada Password",
  },
  colors: {
    background: "#000000",
    surface: "#000000",
    surfaceElevated: "#0a0a0a",
    text: "#ffffff",
    textMuted: "#e5e5e5",
    primary: "#ffff00",
    primaryText: "#000000",
    danger: "#ff6b6b",
    dangerText: "#000000",
    success: "#00ff88",
    border: "#ffffff",
    focus: "#00ffff",
    inputBackground: "#000000",
    overlay: "rgba(0, 0, 0, 0.8)",
  },
  typography: {
    ...baseTypography,
    fontWeightBold: 700,
  },
  shape: {
    ...baseShape,
    radiusSm: 2,
    radiusMd: 4,
    radiusLg: 6,
  },
};

export const PRESETS: Record<string, ThemeConfig> = {
  default: DEFAULT_THEME,
  dark: DARK_THEME,
  "high-contrast": HIGH_CONTRAST_THEME,
};
