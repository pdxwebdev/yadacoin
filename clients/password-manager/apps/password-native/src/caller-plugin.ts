import { registerPlugin } from "@capacitor/core";

export interface CallerSnapshot {
  packageName: string | null;
  appLabel: string | null;
  sha256CertFingerprints: string[];
  handlesCallback: boolean;
}

export interface CallerIdentityPlugin {
  getLastCaller(): Promise<CallerSnapshot>;
  openUrlInPackage(options: {
    url: string;
    packageName: string;
  }): Promise<void>;
}

const web: CallerIdentityPlugin = {
  async getLastCaller() {
    return {
      packageName: null,
      appLabel: null,
      sha256CertFingerprints: [],
      handlesCallback: false,
    };
  },
  async openUrlInPackage({ url }) {
    window.location.href = url;
  },
};

export const CallerIdentity = registerPlugin<CallerIdentityPlugin>(
  "CallerIdentity",
  {
    web: () => web,
  }
);
