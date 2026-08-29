import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "io.yadacoin.passwordrotation.demo",
  appName: "Yada Auth Demo",
  webDir: "www",
  server: {
    // Must be http for cleartext LAN node access. https origin blocks fetch(http://...) as mixed content.
    androidScheme: "http",
    cleartext: true,
  },
  android: {
    allowMixedContent: true,
  },
};

export default config;
