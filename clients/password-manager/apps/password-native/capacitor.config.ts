import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.yadacoin.password",
  appName: "Yada Password",
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
