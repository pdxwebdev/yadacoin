/** Thin HTTP helpers — prefer vault.ts for full workflow. */
export interface PasswordNodeClientOptions {
  baseUrl: string;
  fetch?: typeof fetch;
}

export class PasswordNodeClient {
  readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;

  constructor(opts: PasswordNodeClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/+$/, "");
    this.fetchImpl = opts.fetch ?? globalThis.fetch.bind(globalThis);
  }

  async getTheme(): Promise<unknown> {
    const res = await this.fetchImpl(this.baseUrl + "/password-rotation/theme.json");
    return res.json();
  }

  async getOffchainTip(branchPeer: string): Promise<unknown> {
    const res = await this.fetchImpl(
      this.baseUrl +
        "/password-rotation/offchain/tip?branch_peer=" +
        encodeURIComponent(branchPeer)
    );
    return res.json();
  }

  async submitOffchain(body: unknown): Promise<unknown> {
    const res = await this.fetchImpl(this.baseUrl + "/password-rotation/offchain", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
    return res.json();
  }

  async broadcastTransactions(txns: unknown[]): Promise<unknown> {
    const res = await this.fetchImpl(
      this.baseUrl + "/transaction?username_signature=1",
      {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(txns),
      }
    );
    return res.json();
  }
}
