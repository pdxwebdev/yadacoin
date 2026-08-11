import type { ResolvedTheme, ThemeConfig } from "./types.js";

const VAR_MAP: Array<[string, (t: ThemeConfig) => string | number]> = [
  ["--pm-bg", (t) => t.colors.background],
  ["--pm-surface", (t) => t.colors.surface],
  ["--pm-surface-elevated", (t) => t.colors.surfaceElevated],
  ["--pm-text", (t) => t.colors.text],
  ["--pm-text-muted", (t) => t.colors.textMuted],
  ["--pm-primary", (t) => t.colors.primary],
  ["--pm-primary-text", (t) => t.colors.primaryText],
  ["--pm-danger", (t) => t.colors.danger],
  ["--pm-danger-text", (t) => t.colors.dangerText],
  ["--pm-success", (t) => t.colors.success],
  ["--pm-border", (t) => t.colors.border],
  ["--pm-focus", (t) => t.colors.focus],
  ["--pm-input-bg", (t) => t.colors.inputBackground],
  ["--pm-overlay", (t) => t.colors.overlay],
  ["--pm-font", (t) => t.typography.fontFamily],
  ["--pm-font-size", (t) => `${t.typography.baseSizePx}px`],
  ["--pm-font-weight", (t) => t.typography.fontWeightNormal],
  ["--pm-font-weight-bold", (t) => t.typography.fontWeightBold],
  ["--pm-radius-sm", (t) => `${t.shape.radiusSm}px`],
  ["--pm-radius-md", (t) => `${t.shape.radiusMd}px`],
  ["--pm-radius-lg", (t) => `${t.shape.radiusLg}px`],
  [
    "--pm-space-unit",
    (t) => (t.shape.density === "compact" ? "0.75rem" : "1rem"),
  ],
];

/** Apply resolved theme as CSS custom properties on a root element. */
export function applyTheme(
  theme: ThemeConfig | ResolvedTheme,
  root: HTMLElement | null = typeof document !== "undefined"
    ? document.documentElement
    : null
): void {
  if (!root) return;

  for (const [cssVar, getter] of VAR_MAP) {
    root.style.setProperty(cssVar, String(getter(theme)));
  }

  root.dataset.theme = theme.id;
  root.dataset.mode =
    "resolvedMode" in theme && theme.resolvedMode
      ? theme.resolvedMode
      : theme.mode === "system"
        ? "light"
        : theme.mode;
  root.dataset.density = theme.shape.density;

  if (theme.brand?.name) {
    root.dataset.brand = theme.brand.name;
  }
}

/** Serialize theme for storage / remote. */
export function themeToJson(theme: ThemeConfig): string {
  return JSON.stringify(theme, null, 2);
}

export function themeFromJson(raw: string): ThemeConfig {
  return JSON.parse(raw) as ThemeConfig;
}
