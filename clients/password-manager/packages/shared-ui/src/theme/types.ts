/** Canonical theme token schema for extension + mobile shells. */

export type ThemeMode = "light" | "dark" | "system";
export type ThemeDensity = "compact" | "comfortable";

export interface ThemeBrand {
  name?: string;
  logoUrl?: string;
  faviconUrl?: string;
}

export interface ThemeColors {
  background: string;
  surface: string;
  surfaceElevated: string;
  text: string;
  textMuted: string;
  primary: string;
  primaryText: string;
  danger: string;
  dangerText: string;
  success: string;
  border: string;
  focus: string;
  inputBackground: string;
  overlay: string;
}

export interface ThemeTypography {
  fontFamily: string;
  baseSizePx: number;
  fontWeightNormal: number;
  fontWeightBold: number;
}

export interface ThemeShape {
  radiusSm: number;
  radiusMd: number;
  radiusLg: number;
  density: ThemeDensity;
}

export interface ThemeConfig {
  id: string;
  name: string;
  mode: ThemeMode;
  brand?: ThemeBrand;
  colors: ThemeColors;
  typography: ThemeTypography;
  shape: ThemeShape;
}

/** Partial overlay from user prefs or remote white-label JSON */
export type ThemePartial = {
  id?: string;
  name?: string;
  mode?: ThemeMode;
  brand?: ThemeBrand;
  colors?: Partial<ThemeColors>;
  typography?: Partial<ThemeTypography>;
  shape?: Partial<ThemeShape>;
};

export interface ResolvedTheme extends ThemeConfig {
  /** Concrete light|dark after resolving system preference */
  resolvedMode: "light" | "dark";
}
