import { registerPlugin } from "@capacitor/core";

export interface OpenPasswordManagerPlugin {
  open(options: { url: string }): Promise<void>;
}

export const OpenPasswordManager = registerPlugin<OpenPasswordManagerPlugin>(
  "OpenPasswordManager"
);
