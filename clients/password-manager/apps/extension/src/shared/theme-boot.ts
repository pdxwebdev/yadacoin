import {
  applyTheme,
  resolveTheme,
  type ResolvedTheme,
} from "@yadacoin/password-shared-ui";
import {
  fetchRemoteTheme,
  loadSettings,
  settingsToThemePartial,
} from "./settings.js";

export async function bootTheme(): Promise<ResolvedTheme> {
  const settings = await loadSettings();
  const remote = await fetchRemoteTheme(settings.themeUrl);
  const theme = resolveTheme({
    preset: settings.presetId,
    remote,
    user: settingsToThemePartial(settings),
  });
  applyTheme(theme);
  const brandEl = document.getElementById("brandName");
  if (brandEl && theme.brand?.name) {
    brandEl.textContent = theme.brand.name;
  }
  return theme;
}
