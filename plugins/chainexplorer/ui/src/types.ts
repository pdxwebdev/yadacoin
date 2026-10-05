export type Output = {
  to?: string;
  value?: number | string;
};

export type Input = {
  id?: string;
};

export type Identity = {
  username?: string;
  username_signature?: string;
  identity_type?: string;
};

export type FileAnnouncement = {
  title?: string;
  description?: string;
  file_id?: string;
  filename?: string;
  keywords?: string[] | string;
  mime_type?: string;
  backend?: string;
  share_url?: string;
};

export type Relationship = {
  identity?: Identity;
  file?: FileAnnouncement;
  [key: string]: unknown;
};

export type Txn = {
  time?: number | string;
  rid?: string;
  id?: string;
  hash?: string;
  public_key?: string;
  dh_public_key?: string;
  fee?: number;
  masternode_fee?: number;
  inputs?: Input[];
  outputs?: Output[];
  relationship?: Relationship;
  relationship_hash?: string;
  version?: number;
  private?: boolean | string;
  never_expire?: boolean | string;
  requester_rid?: string;
  requested_rid?: string;
  public_key_hash?: string;
  prev_public_key_hash?: string;
  prerotated_key_hash?: string;
  twice_prerotated_key_hash?: string;
  miner_signature?: string;
  reason?: string;
  error?: string;
};

export type Block = {
  version?: number;
  time?: number | string;
  index: number;
  public_key?: string;
  prevHash?: string;
  nonce?: string;
  transactions?: Txn[];
  hash: string;
  merkleRoot?: string;
  special_min?: boolean;
  target?: string;
  special_target?: string;
  header?: string;
  id?: string;
};

export type Stats = {
  time?: number;
  circulating?: number;
  height?: number;
  network_hash_rate?: number;
  difficulty?: number;
};

export type MempoolPage = {
  transactions: Txn[];
  total: number;
  page: number;
  page_size: number;
};

export type FeeEstimate = {
  status?: string;
  message?: string;
  recommended_fee?: number;
  txns_count?: number;
  fee_estimate?: {
    min_fee?: number;
    median_fee?: number;
    max_fee?: number;
  };
};

export type AnnouncementHit = {
  kind: string;
  source?: string;
  block_index?: number;
  block_hash?: string;
  reason?: string;
  error?: string;
  txn?: Txn;
};

export type IdentityProfile = {
  username?: string;
  username_signature?: string;
  identity_type?: string;
  public_key?: string;
  public_keys?: string[];
  addresses?: string[];
  transaction_id?: string;
  source?: string;
  block_index?: number;
  block_hash?: string;
};

export type SearchPayload = {
  resultType?: string;
  result?: unknown;
  balance?: string;
  username?: string;
  identity?: IdentityProfile;
  counts?: Record<string, number>;
  announcements?: AnnouncementHit[];
};

export type Panel = "chain" | "search" | "mempool";
