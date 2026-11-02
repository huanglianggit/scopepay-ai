export type Project = {
  id: string;
  title: string;
  client_name: string;
  client_email: string;
  scope: string;
  base_cents: number;
  due_date: string;
  currency: string;
  rates: { id: string; name: string; amount_cents: number; unit: string }[];
};
export type Item = {
  id: string;
  title: string;
  kind: "added" | "changed" | "included" | "unclear";
  analysis_kind?: Item["kind"];
  explanation: string;
  request_quote: string;
  scope_quote: string;
  rate_id: string;
  question: string;
  resolution: string;
  selected: boolean;
  amount_cents: number;
};
export type Event = { kind: string; detail: string; created_at: string };
export type RevisionTerms = Pick<
  Item,
  "title" | "kind" | "amount_cents" | "resolution"
>;
export type Revision = {
  previous_version: number;
  previous_quote_hash: string;
  previous_total_cents: number;
  total_cents: number;
  delta_cents: number;
  baseline_changed: boolean;
  response_note: string;
  has_changes: boolean;
  items: {
    kind: "added" | "removed" | "modified";
    before: RevisionTerms | null;
    after: RevisionTerms | null;
    fields: string[];
  }[];
  metadata: { field: string; before: string; after: string }[];
};
export type Change = {
  id: string;
  project_id: string;
  project: Project;
  message: string;
  summary: string;
  provider: string;
  items: Item[];
  version: number;
  status: string;
  total_cents: number;
  due_date: string;
  note: string;
  share_token?: string;
  quote_hash?: string;
  created_at: string;
  published_at?: string;
  payment_mode?: "demo" | "sandbox" | "none";
  scope_changed?: boolean;
  paid_at?: string;
  capture_id?: string;
  response?: { name: string; note: string; at: string };
  events?: Event[];
  revision?: Revision | null;
};
export type Ledger = {
  project: Pick<
    Project,
    | "id"
    | "title"
    | "client_name"
    | "currency"
    | "scope"
    | "base_cents"
    | "due_date"
  >;
  totals: Record<
    | "confirmed_additional_cents"
    | "agreed_project_cents"
    | "sandbox_paid_cents"
    | "demo_paid_cents"
    | "sandbox_unpaid_cents"
    | "demo_unpaid_cents"
    | "awaiting_cents"
    | "awaiting_count"
    | "stale_count",
    number
  >;
  confirmed: {
    id: string;
    version: number;
    status: string;
    payment_mode: string;
    total_cents: number;
    due_date: string;
    quote_hash: string;
    confirmed_at: string;
    confirmed_by: string;
    items: RevisionTerms[];
  }[];
  notice: string;
  generated_at: string;
};
export type Status = {
  paypal_ready: boolean;
  ai_ready: boolean;
  ai_provider: string;
  ai_model: string;
  webhook_ready: boolean;
  sample_message: string;
};
