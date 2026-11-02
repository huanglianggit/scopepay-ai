import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  Check,
  CheckCheck,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  Copy,
  ExternalLink,
  FileCheck2,
  FileText,
  FolderOpen,
  History,
  Layers3,
  LoaderCircle,
  LockKeyhole,
  MessageSquareText,
  Plus,
  RefreshCw,
  ScanText,
  Settings2,
  ShieldCheck,
  Sparkles,
  Wallet,
  X,
} from "lucide-react";
import { api, day, money, statusLabel } from "./api";
import type { Change, Event, Item, Project, Status } from "./types";
import { ProjectLedger, RevisionSummary } from "./Records";

const CHINESE_SAMPLE =
  "页面看起来不错！能不能顺便增加中文版本，再加一个在线预约咨询的功能？另外想再多一轮修改。新增预算可以商量。";
type View = "workspace" | "changes" | "ledger" | "connections";

function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark">
        <Layers3 size={23} />
      </span>
      ScopePay<span className="brand-dot">●</span>
    </div>
  );
}
function Button({
  children,
  loading,
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean }) {
  return (
    <button
      {...props}
      disabled={props.disabled || loading}
      className={"button " + className}
    >
      {loading && <LoaderCircle size={16} className="spin" />}
      {children}
    </button>
  );
}
function Badge({ status }: { status: string }) {
  return (
    <span className={"badge " + status}>
      <span />
      {statusLabel[status] || status}
    </span>
  );
}
function Notice({
  children,
  error = false,
}: {
  children: ReactNode;
  error?: boolean;
}) {
  return (
    <div
      className={"notice " + (error ? "error" : "")}
      role={error ? "alert" : undefined}
    >
      {error ? <CircleHelp size={18} /> : <CircleHelp size={18} />}
      <div>{children}</div>
    </div>
  );
}

function Connections({ status }: { status: Status }) {
  return (
    <section className="connections">
      <p className="eyebrow">YOUR WORKSPACE</p>
      <h1>Connections & readiness</h1>
      <p className="subtext">
        Know what is connected before you share a quote.
      </p>
      <div className="connection-grid">
        <article className="connection">
          <div className="connection-head">
            <span className="icon-box">
              <Sparkles />
            </span>
            <span
              className={
                "connection-status " + (status.ai_ready ? "ready" : "")
              }
            >
              {status.ai_ready ? "Configured" : "Walkthrough"}
            </span>
          </div>
          <h2>Change analysis</h2>
          <p>
            {status.ai_ready
              ? `Model: ${status.ai_model}. Every cited passage is checked against your source documents.`
              : "The current walkthrough uses sample matching rules. Connect a model to analyze new requests semantically."}
          </p>
          <details>
            <summary>Connect your model</summary>
            <p>
              In the server’s <code>.env</code>, set{" "}
              <code>AI_PROVIDER=openai</code> for an OpenAI-compatible endpoint,
              plus <code>AI_BASE_URL</code>, <code>AI_MODEL</code>, and{" "}
              <code>AI_API_KEY</code>. For local Ollama use{" "}
              <code>AI_PROVIDER=ollama</code> and its <code>/v1</code> URL.
              Restart the server.
            </p>
          </details>
        </article>
        <article className="connection">
          <div className="connection-head">
            <span className="icon-box blue">
              <Wallet />
            </span>
            <span
              className={
                "connection-status " + (status.paypal_ready ? "ready" : "")
              }
            >
              {status.paypal_ready ? "Configured" : "Not connected"}
            </span>
          </div>
          <h2>PayPal Sandbox</h2>
          <p>
            {status.paypal_ready
              ? "New quotes use PayPal Sandbox checkout with test money. Account credentials still require a successful test transaction."
              : "Quotes can use an explicitly simulated payment while your Sandbox account is being prepared. No PayPal transaction is created."}
          </p>
          <details>
            <summary>Connect PayPal Sandbox</summary>
            <p>
              Open PayPal Developer → Apps & Credentials → Sandbox. Add your
              Sandbox <code>PAYPAL_CLIENT_ID</code> and{" "}
              <code>PAYPAL_CLIENT_SECRET</code> to the server’s{" "}
              <code>.env</code> and restart. Keep the secret private. Create a
              new quote to use Sandbox.
            </p>
            <a
              href="https://developer.paypal.com/dashboard/applications/sandbox"
              target="_blank"
              rel="noreferrer"
            >
              Open Developer Dashboard <ExternalLink size={13} />
            </a>
          </details>
        </article>
        <article className="connection">
          <div className="connection-head">
            <span className="icon-box">
              <ShieldCheck />
            </span>
            <span
              className={
                "connection-status " + (status.webhook_ready ? "ready" : "")
              }
            >
              {status.webhook_ready ? "Configured" : "Optional"}
            </span>
          </div>
          <h2>Payment reconciliation</h2>
          <p>
            Payment is confirmed on the server against the accepted version and
            amount. A signed webhook recovers completed captures when a browser
            closes.
          </p>
          <details>
            <summary>Configure a webhook</summary>
            <p>
              Register a publicly reachable HTTPS URL ending in{" "}
              <code>/api/paypal/webhook</code> for{" "}
              <code>PAYMENT.CAPTURE.COMPLETED</code>. Set its{" "}
              <code>PAYPAL_WEBHOOK_ID</code> in <code>.env</code> and restart.
              See the README for hosting and access setup.
            </p>
          </details>
        </article>
      </div>
      <div className="rate-heading">
        <h2>Starting rate card</h2>
        <span>Each quote remains editable before sharing.</span>
      </div>
      <div className="rate-list">
        {[
          ["Additional language", 12000],
          ["Embedded booking integration", 18000],
          ["Additional page", 8000],
          ["Additional revision round", 4000],
          ["Expedited delivery", 6000],
        ].map(([name, amount]) => (
          <div key={name}>
            <span>{name}</span>
            <strong>{money(Number(amount))}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function NewProject({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (p: Project) => void;
}) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const dialogRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    function keys(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key === "Tab") {
        const fields = Array.from(
          dialogRef.current?.querySelectorAll<HTMLElement>(
            "button:not(:disabled), input, textarea, select, a[href]",
          ) || [],
        );
        const first = fields[0],
          last = fields[fields.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    }
    document.addEventListener("keydown", keys);
    return () => {
      document.removeEventListener("keydown", keys);
      previous?.focus();
    };
  }, [onClose]);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const p = await api<Project>("/projects", {
        title: form.get("title"),
        client_name: form.get("name"),
        client_email: form.get("email"),
        base_cents: Math.round(Number(form.get("amount")) * 100),
        due_date: form.get("due"),
        scope: form.get("scope"),
      });
      onCreated(p);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section
        ref={dialogRef}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="project-dialog"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-heading">
          <div>
            <p className="eyebrow">A CLEAR START</p>
            <h2 id="project-dialog">New project</h2>
          </div>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="Close new project"
          >
            <X />
          </button>
        </div>
        <form onSubmit={submit}>
          <label>
            Project name
            <input
              autoFocus
              name="title"
              required
              minLength={2}
              maxLength={100}
              placeholder="e.g. Bloom Studio website"
            />
          </label>
          <div className="form-grid">
            <label>
              Client name
              <input
                name="name"
                required
                minLength={2}
                maxLength={100}
                placeholder="Alex Morgan"
              />
            </label>
            <label>
              Client email <span className="muted">optional</span>
              <input name="email" type="email" placeholder="alex@example.com" />
            </label>
          </div>
          <div className="form-grid">
            <label>
              Original fee · USD
              <input
                name="amount"
                type="number"
                required
                min="0"
                max="1000000"
                step="0.01"
                defaultValue="500"
              />
            </label>
            <label>
              Original delivery date
              <input name="due" type="date" required />
            </label>
          </div>
          <label>
            Agreed scope
            <textarea
              name="scope"
              required
              minLength={30}
              maxLength={18000}
              rows={5}
              placeholder="Describe the deliverables, included revisions, exclusions, and any assumptions already agreed with the client."
            />
          </label>
          {error && <Notice error>{error}</Notice>}
          <div className="modal-actions">
            <Button type="button" className="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" loading={busy}>
              Create project <ArrowRight size={16} />
            </Button>
          </div>
        </form>
      </section>
    </div>
  );
}

function QuoteEditor({
  change,
  onPublish,
  onSave,
  busy,
}: {
  change: Change;
  onPublish: (items: Item[], due: string, note: string) => void;
  onSave: (items: Item[], due: string, note: string) => Promise<void>;
  busy: boolean;
}) {
  const [items, setItems] = useState(() =>
    change.items.map((item) => ({
      ...item,
      analysis_kind: item.analysis_kind || item.kind,
    })),
  );
  const [due, setDue] = useState(change.due_date);
  const [note, setNote] = useState(change.note);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const total = items
    .filter((i) => i.selected)
    .reduce((sum, i) => sum + i.amount_cents, 0);
  function update(id: string, patch: Partial<Item>) {
    setSaved(false);
    setItems((old) => old.map((i) => (i.id === id ? { ...i, ...patch } : i)));
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    const unresolved = items.find(
      (i) =>
        i.selected &&
        (i.kind === "unclear" || i.kind !== (i.analysis_kind || i.kind)) &&
        !i.resolution.trim(),
    );
    if (unresolved) {
      setError(
        `Please resolve “${unresolved.title}” or exclude it from this quote.`,
      );
      return;
    }
    if (!items.some((i) => i.selected)) {
      setError("Include at least one change to confirm with your client.");
      return;
    }
    setError("");
    onPublish(items, due, note);
  }
  return (
    <form onSubmit={submit} className="quote-editor">
      <div className="analysis-summary">
        <span className="icon-box">
          <ScanText size={21} />
        </span>
        <div>
          <h2>Here’s what changed</h2>
          <p>{change.summary}</p>
        </div>
      </div>
      <div className="source-mode">
        {change.provider === "demo-rules" ? (
          <>
            <span className="mode-dot amber" /> Rule-based walkthrough · review
            every suggestion
          </>
        ) : (
          <>
            <span className="mode-dot" /> Model analysis · source quotations
            verified
          </>
        )}
      </div>
      <RevisionSummary revision={change.revision} saved />
      <div className="quote-items">
        {change.scope_changed && (
          <Notice error>
            The agreed scope has changed. Start a new analysis before sharing
            this draft.
          </Notice>
        )}
        {items.map((item, index) => (
          <article
            className={"quote-item " + (!item.selected ? "excluded" : "")}
            key={item.id}
          >
            <div className="item-top">
              <label className="item-selection">
                <input
                  type="checkbox"
                  checked={item.selected}
                  onChange={(e) =>
                    update(item.id, { selected: e.target.checked })
                  }
                  aria-label={`Include ${item.title}`}
                />
                <span className="item-number">
                  {String(index + 1).padStart(2, "0")}
                </span>
              </label>
              <select
                className={"kind-select " + item.kind}
                aria-label={`Classification for item ${index + 1}`}
                value={item.kind}
                onChange={(e) => {
                  const kind = e.target.value as Item["kind"];
                  update(item.id, {
                    kind,
                    ...(kind === "included" ? { amount_cents: 0 } : {}),
                  });
                }}
              >
                <option value="added">Added scope</option>
                <option value="changed">Changed scope</option>
                <option value="included">Already included</option>
                <option value="unclear">Needs clarification</option>
              </select>
            </div>
            <div className="item-title-price">
              <input
                className="editable-title"
                aria-label={`Title for item ${index + 1}`}
                value={item.title}
                onChange={(e) => update(item.id, { title: e.target.value })}
                required
                minLength={2}
                maxLength={160}
              />
              <label className="price-input">
                <span>$</span>
                <input
                  type="number"
                  aria-label={`Price for item ${index + 1}`}
                  min="0"
                  max="100000"
                  step="0.01"
                  value={item.amount_cents / 100}
                  disabled={item.kind === "included"}
                  onChange={(e) =>
                    update(item.id, {
                      amount_cents: Math.round(Number(e.target.value) * 100),
                    })
                  }
                />
              </label>
            </div>
            <p className="item-explanation">{item.explanation}</p>
            <details className="evidence">
              <summary>
                <FileText size={13} /> View source evidence
              </summary>
              <div className="evidence-content">
                <span>CLIENT REQUEST</span>
                <blockquote>{item.request_quote}</blockquote>
                <span>ORIGINAL AGREEMENT</span>
                <blockquote>
                  {item.scope_quote ||
                    "No exact clause was cited. Confirm this against the agreement."}
                </blockquote>
              </div>
            </details>
            {(item.kind === "unclear" ||
              item.kind !== (item.analysis_kind || item.kind)) &&
              item.selected && (
                <div className="clarification">
                  <p>
                    <CircleHelp size={15} />
                    {item.kind !== (item.analysis_kind || item.kind)
                      ? "Explain the correction so your client can understand why this classification changed."
                      : item.question ||
                        "What needs to be clarified before this change is agreed?"}
                  </p>
                  <label>
                    {item.kind === "unclear"
                      ? "Agreed clarification"
                      : "Reason for classification change"}
                    <textarea
                      rows={2}
                      value={item.resolution}
                      onChange={(e) =>
                        update(item.id, { resolution: e.target.value })
                      }
                      maxLength={1600}
                      placeholder="Record the clarification you will ask the client to confirm."
                    />
                  </label>
                </div>
              )}
          </article>
        ))}
      </div>
      <div className="quote-details">
        <label>
          Revised delivery date
          <input
            type="date"
            value={due}
            required
            onChange={(e) => {
              setDue(e.target.value);
              setSaved(false);
            }}
          />
        </label>
        <label>
          Note to your client <span className="muted">optional</span>
          <textarea
            rows={2}
            maxLength={2000}
            value={note}
            onChange={(e) => {
              setNote(e.target.value);
              setSaved(false);
            }}
            placeholder="e.g. The original deliverables remain unchanged. These additions begin after confirmation."
          />
        </label>
      </div>
      {error && <Notice error>{error}</Notice>}
      {total === 0 && items.some((i) => i.selected) && (
        <Notice>
          This change has no additional fee. Your client can confirm it without
          a payment step.
        </Notice>
      )}
      <div className="draft-save">
        <button
          type="button"
          className="text-button"
          disabled={busy}
          onClick={async () => {
            try {
              setError("");
              await onSave(items, due, note);
              setSaved(true);
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          {saved ? (
            <>
              <Check size={13} /> Draft saved
            </>
          ) : (
            <>
              <FileText size={13} /> Save draft
            </>
          )}
        </button>
      </div>
      <div className="quote-total">
        <div>
          <span>Additional fee · USD</span>
          <strong>{money(total)}</strong>
        </div>
        <Button loading={busy} disabled={change.scope_changed} type="submit">
          <LockKeyhole size={15} /> Lock & share quote <ArrowRight size={15} />
        </Button>
      </div>
      <p className="footnote">
        <ShieldCheck size={13} /> Sharing locks this version. Your client
        reviews the scope and amount before accepting.
      </p>
    </form>
  );
}

function Timeline({ events }: { events: Event[] }) {
  return (
    <ol className="timeline">
      {events.map((event, index) => (
        <li key={index}>
          <span
            className={
              "timeline-dot " +
              (event.kind === "paid" || event.kind === "demo_paid"
                ? "done"
                : "")
            }
          />
          <div>
            <p>{event.detail}</p>
            <time>{new Date(event.created_at).toLocaleString()}</time>
          </div>
        </li>
      ))}
    </ol>
  );
}

function LockedQuote({
  change,
  events,
  onRefresh,
  onRevise,
  busy,
}: {
  change: Change;
  events: Event[];
  onRefresh: () => void;
  onRevise: () => void;
  busy: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState("");
  const link = `${location.origin}/review/${change.share_token}`;
  async function copy() {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      setCopyError("Copy the review URL from the field below.");
    }
  }
  return (
    <section className="locked-quote">
      <div className="locked-heading">
        <span className="success-icon">
          <FileCheck2 size={26} />
        </span>
        <div>
          <p className="eyebrow">VERSION {change.version} · LOCKED</p>
          <h2>A clear agreement, ready to share.</h2>
        </div>
      </div>
      <div className="locked-status">
        <Badge status={change.status} />
        <button className="text-button" onClick={onRefresh} disabled={busy}>
          <RefreshCw size={14} className={busy ? "spin" : ""} /> Refresh
        </button>
      </div>
      {change.scope_changed && (
        <Notice error>
          The agreed scope changed after this version was prepared. Create a
          revision to compare it with the latest agreement.
        </Notice>
      )}
      {change.response && (
        <div className="client-response">
          <strong>Client response · {change.response.name}</strong>
          <p>{change.response.note || "No additional message."}</p>
        </div>
      )}
      <RevisionSummary revision={change.revision} />
      {change.payment_mode === "demo" && (
        <Notice>
          This quote uses a simulated payment. Create a new quote after
          connecting PayPal Sandbox to test a PayPal transaction.
        </Notice>
      )}
      <div className="share-panel">
        <label>
          Private client review link
          <div className="copy-field">
            <input readOnly value={link} aria-label="Client review link" />
            <button onClick={copy} aria-label="Copy client review link">
              {copied ? <Check size={17} /> : <Copy size={17} />}
            </button>
          </div>
        </label>
        {copyError && <p role="alert">{copyError}</p>}
        <a
          className="button"
          href={`/review/${change.share_token}`}
          target="_blank"
          rel="noreferrer"
        >
          Open client review <ExternalLink size={15} />
        </a>
      </div>
      <div className="locked-lines">
        {change.items
          .filter((i) => i.selected)
          .map((item) => (
            <div key={item.id}>
              <div>
                <strong>{item.title}</strong>
                {item.resolution && <p>{item.resolution}</p>}
              </div>
              <span>{money(item.amount_cents)}</span>
            </div>
          ))}
      </div>
      <div className="locked-total">
        <span>Additional total</span>
        <strong>{money(change.total_cents)}</strong>
      </div>
      <div className="locked-meta">
        <span>
          <History size={15} />
          Delivery {day(change.due_date)}
        </span>
        <span>
          <LockKeyhole size={15} />
          Version {change.version} confirmed separately
        </span>
      </div>
      <div className="record-actions">
        <a
          className="button secondary"
          href={`/api/changes/${change.id}/export`}
        >
          <ArrowDownToLine size={15} /> Export record
        </a>
        {["awaiting", "declined"].includes(change.status) && (
          <Button className="secondary" loading={busy} onClick={onRevise}>
            Create revision
          </Button>
        )}
      </div>
      <h3 className="section-title">Agreement activity</h3>
      <Timeline events={events} />
    </section>
  );
}

function Review({ token }: { token: string }) {
  const [change, setChange] = useState<Change | null>(null);
  const [error, setError] = useState("");
  const [paymentNotice, setPaymentNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        let c = await api<Change>(`/review/${token}`);
        const params = new URLSearchParams(location.search);
        const order = params.get("token");
        if (params.get("checkout") === "return" && order) {
          try {
            c = await api<Change>(`/review/${token}/capture`, {
              order_id: order,
            });
            history.replaceState(null, "", location.pathname);
          } catch (e) {
            if (active) setError((e as Error).message);
          }
        }
        if (active) setChange(c);
      } catch (e) {
        if (active) setError((e as Error).message);
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [token]);
  async function respond(action: "accept" | "decline") {
    if (!change) return;
    if (name.trim().length < 2) {
      setError("Enter your name to record your response.");
      return;
    }
    if (action === "accept" && !agreed) {
      setError("Confirm that you have reviewed the changes and amount.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      setChange(
        await api<Change>(`/review/${token}/respond`, {
          action,
          name,
          note,
          version: change.version,
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function pay() {
    if (!change) return;
    setBusy(true);
    setError("");
    try {
      if (change.payment_mode === "demo") {
        setChange(await api<Change>(`/review/${token}/demo-payment`, {}));
      } else {
        const data = await api<{ approval_url?: string; payment?: Change }>(
          `/review/${token}/order`,
          {},
        );
        if (data.payment) setChange(data.payment);
        else if (data.approval_url) location.assign(data.approval_url);
        else
          throw new Error(
            "No checkout link was returned. Refresh the payment status and retry.",
          );
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function refreshPayment() {
    setBusy(true);
    setError("");
    try {
      const updated = await api<Change>(`/review/${token}/payment-status`, {});
      setChange(updated);
      setPaymentNotice(
        updated.status === "paid"
          ? ""
          : "PayPal has not reported a completed payment yet. If you already approved checkout, use PayPal Sandbox checkout to finish verification.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const paid = change && ["paid", "demo_paid"].includes(change.status);
  const noPayment = change?.status === "accepted_no_payment";
  return (
    <div className="client-page">
      <header className="client-header">
        <Brand />
        <span>
          <LockKeyhole size={14} />
          Private change review
        </span>
      </header>
      <main className="client-main">
        {loading ? (
          <div className="loading">
            <LoaderCircle className="spin" />
            Loading your agreement…
          </div>
        ) : !change ? (
          <Notice error>{error || "This link is unavailable."}</Notice>
        ) : (
          <>
            <div className="client-intro">
              <p className="eyebrow">LET’S KEEP THE PROJECT CLEAR</p>
              <h1>
                {paid || noPayment
                  ? "All agreed. All recorded."
                  : "A little more scope.\nA clear next step."}
              </h1>
              <p>
                Review the additions to <strong>{change.project.title}</strong>,
                prepared for {change.project.client_name}.
              </p>
              <div className="client-tags">
                <Badge status={change.status} />
                <span>Change order · v{change.version}</span>
              </div>
            </div>
            {change.payment_mode === "none" ? (
              <Notice>
                No additional payment is requested. This page records your
                confirmation of the scope and delivery date.
              </Notice>
            ) : change.payment_mode === "demo" ? (
              <Notice>
                Walkthrough only. Payment on this page is simulated; no PayPal
                transaction or money movement occurs.
              </Notice>
            ) : (
              <Notice>
                PayPal Sandbox checkout uses test money. Sign in with a Sandbox
                buyer account, not your real PayPal account.
              </Notice>
            )}
            {change.scope_changed && (
              <Notice error>
                The agreed project scope changed after this quote was issued.
                Request a revision from the studio before accepting.
              </Notice>
            )}
            {change.status === "accepted" &&
              new URLSearchParams(location.search).get("checkout") ===
                "cancel" && (
                <Notice>
                  You cancelled checkout. Your accepted quote is saved and
                  remains unpaid. You can try payment again.
                </Notice>
              )}
            <div className="client-grid">
              <div>
                <RevisionSummary revision={change.revision} />
                <section className="client-section">
                  <div className="section-heading">
                    <h2>
                      {paid || noPayment || change.status === "accepted"
                        ? "Your confirmed scope"
                        : "Scope for your review"}
                    </h2>
                    <span>
                      {change.items.filter((i) => i.selected).length} items
                    </span>
                  </div>
                  {change.items
                    .filter((i) => i.selected)
                    .map((item, index) => (
                      <article className="client-item" key={item.id}>
                        <span className="item-number">
                          {String(index + 1).padStart(2, "0")}
                        </span>
                        <div>
                          <h3>{item.title}</h3>
                          <p>{item.resolution || item.explanation}</p>
                          <details className="evidence">
                            <summary>View scope evidence</summary>
                            <div className="evidence-content">
                              <span>YOUR REQUEST</span>
                              <blockquote>{item.request_quote}</blockquote>
                              <span>ORIGINAL AGREEMENT</span>
                              <blockquote>
                                {item.scope_quote ||
                                  "No exact clause cited; review the original scope below."}
                              </blockquote>
                            </div>
                          </details>
                        </div>
                        <strong>{money(item.amount_cents)}</strong>
                      </article>
                    ))}
                </section>
                <section className="client-section">
                  <h2>The original agreement</h2>
                  <p className="original-text">{change.project.scope}</p>
                  <div className="original-meta">
                    <span>
                      Original fee{" "}
                      <strong>{money(change.project.base_cents)}</strong>
                    </span>
                    <span>
                      Original delivery{" "}
                      <strong>{day(change.project.due_date)}</strong>
                    </span>
                  </div>
                </section>
                {change.note && (
                  <section className="client-section">
                    <h2>A note from your studio</h2>
                    <p className="original-text">{change.note}</p>
                  </section>
                )}
                <section className="client-section">
                  <h2>Agreement activity</h2>
                  <Timeline events={change.events || []} />
                </section>
              </div>
              <aside className="client-checkout">
                <p className="eyebrow">
                  CHANGE ORDER · VERSION {change.version}
                </p>
                <div className="client-amount">
                  {money(change.total_cents)}
                  <span>USD · additional fee</span>
                </div>
                <div className="checkout-line">
                  <span>Revised delivery</span>
                  <strong>{day(change.due_date)}</strong>
                </div>
                <div className="checkout-line">
                  <span>Original project fee</span>
                  <span>{money(change.project.base_cents)}</span>
                </div>
                <div className="checkout-divider" />
                {change.status === "awaiting" && (
                  <>
                    <label>
                      Your name
                      <input
                        value={name}
                        minLength={2}
                        maxLength={100}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="Name of person confirming"
                      />
                    </label>
                    <label>
                      Message to the studio{" "}
                      <span className="muted">optional</span>
                      <textarea
                        rows={2}
                        maxLength={1500}
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        placeholder="Any final questions or feedback?"
                      />
                    </label>
                    <label className="consent">
                      <input
                        type="checkbox"
                        checked={agreed}
                        onChange={(e) => setAgreed(e.target.checked)}
                      />
                      <span>
                        I have reviewed version {change.version}, its additions,
                        fee, and revised delivery date.
                      </span>
                    </label>
                    <Button
                      disabled={change.scope_changed}
                      loading={busy}
                      onClick={() => respond("accept")}
                    >
                      Accept this version <Check size={16} />
                    </Button>
                    <Button
                      className="secondary"
                      loading={busy}
                      onClick={() => respond("decline")}
                    >
                      Request a revision
                    </Button>
                  </>
                )}
                {change.status === "accepted" && (
                  <>
                    <div className="confirmation">
                      <CheckCheck size={22} />
                      <div>
                        <strong>Scope confirmed</strong>
                        <p>
                          Accepted by {change.response?.name}. Payment is the
                          next step.
                        </p>
                      </div>
                    </div>
                    <Button
                      className={
                        change.payment_mode === "sandbox" ? "paypal-button" : ""
                      }
                      loading={busy}
                      onClick={pay}
                    >
                      {change.payment_mode === "sandbox" ? (
                        <>
                          <span className="paypal-word">PayPal</span> Sandbox
                          checkout
                        </>
                      ) : (
                        <>
                          Simulate demo payment <ArrowRight size={16} />
                        </>
                      )}
                    </Button>
                    <p className="footnote">
                      {change.payment_mode === "sandbox"
                        ? "Your confirmed amount is verified on the server."
                        : "This demonstration does not create a PayPal payment."}
                    </p>
                    {change.payment_mode === "sandbox" && (
                      <Button
                        className="secondary"
                        loading={busy}
                        onClick={refreshPayment}
                      >
                        <RefreshCw size={14} /> Refresh payment status
                      </Button>
                    )}
                  </>
                )}
                {paid && (
                  <div className="payment-success">
                    <span className="success-icon">
                      <CheckCheck size={28} />
                    </span>
                    <h2>
                      {change.status === "paid"
                        ? "Sandbox payment verified"
                        : "Demo payment recorded"}
                    </h2>
                    <p>
                      {change.status === "paid"
                        ? "Your test payment matches this exact quote version."
                        : "The walkthrough is complete. This payment was simulated."}
                    </p>
                    <small>{change.capture_id}</small>
                  </div>
                )}
                {noPayment && (
                  <div className="payment-success">
                    <span className="success-icon">
                      <CheckCheck size={28} />
                    </span>
                    <h2>Changes confirmed</h2>
                    <p>
                      Accepted by {change.response?.name}. No payment is due for
                      this version.
                    </p>
                  </div>
                )}
                {change.status === "declined" && (
                  <Notice>
                    Your revision request is saved. The studio can prepare a new
                    version for you to review.
                  </Notice>
                )}
                {change.status === "superseded" && (
                  <Notice>
                    This quote has been replaced. Ask the studio for the latest
                    review link.
                  </Notice>
                )}
                {paymentNotice && change.status === "accepted" && (
                  <Notice>{paymentNotice}</Notice>
                )}
                {error && <Notice error>{error}</Notice>}
                <a
                  className="download-link"
                  href={`/api/review/${token}/export`}
                >
                  <ArrowDownToLine size={15} /> Download change record
                </a>
                <details className="version-details">
                  <summary>
                    <ShieldCheck size={13} />
                    Version fingerprint
                  </summary>
                  <code>{change.quote_hash}</code>
                  <p>
                    The fingerprint binds the scope, price, delivery, and
                    version in the exported record.
                  </p>
                </details>
              </aside>
            </div>
          </>
        )}
      </main>
      <footer className="client-footer">
        <Brand />
        <span>Good work. Clear agreements.</span>
      </footer>
    </div>
  );
}

export default function App() {
  const review = location.pathname.match(/^\/review\/([A-Za-z0-9_-]+)$/);
  if (review) return <Review token={review[1]} />;
  return <Studio />;
}

function Studio() {
  const [status, setStatus] = useState<Status | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [changes, setChanges] = useState<Change[]>([]);
  const [projectId, setProjectId] = useState("");
  const [active, setActive] = useState<Change | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [message, setMessage] = useState("");
  const [view, setView] = useState<View>("workspace");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [newProject, setNewProject] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loginNeeded, setLoginNeeded] = useState(false);
  const [code, setCode] = useState("");
  async function refresh(selectedId?: string) {
    const data = await api<{ projects: Project[]; changes: Change[] }>(
      "/workspace",
    );
    setProjects(data.projects);
    setChanges(data.changes);
    setProjectId((old) => old || data.projects[0]?.id || "");
    if (selectedId) {
      const c = data.changes.find((c) => c.id === selectedId);
      if (c) {
        setActive(c);
        setEvents(await api<Event[]>(`/changes/${c.id}/events`));
      }
    }
  }
  useEffect(() => {
    async function load() {
      try {
        const s = await api<Status>("/status");
        setStatus(s);
        setMessage(s.sample_message);
        try {
          await refresh();
        } catch {
          await api("/session", { code: "" });
          await refresh();
        }
      } catch (e) {
        setLoginNeeded(true);
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);
  async function login(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/session", { code });
      await refresh();
      setLoginNeeded(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const project = projects.find((p) => p.id === projectId);
  const projectChanges = changes.filter((c) => c.project_id === projectId);
  const outstanding = projectChanges
    .filter((c) => c.status === "accepted")
    .reduce((sum, c) => sum + c.total_cents, 0);
  async function selectChange(change: Change) {
    setError("");
    setProjectId(change.project_id);
    setMessage(change.message);
    setActive(change);
    setView("workspace");
    try {
      setEvents(await api<Event[]>(`/changes/${change.id}/events`));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function openConfirmedRecord(id: string) {
    setBusy(true);
    setError("");
    try {
      await refresh(id);
      setView("workspace");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function analyze() {
    if (!project) return;
    setBusy(true);
    setError("");
    try {
      const c = await api<Change>(`/projects/${project.id}/analyze`, {
        message,
      });
      setActive(c);
      setChanges((old) => [c, ...old]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function publish(items: Item[], due: string, note: string) {
    if (!active) return;
    setBusy(true);
    setError("");
    try {
      const c = await api<Change>(`/changes/${active.id}/publish`, {
        items: items.map(
          ({ id, title, selected, amount_cents, resolution, kind }) => ({
            id,
            title,
            selected,
            amount_cents,
            resolution,
            kind,
          }),
        ),
        due_date: due,
        note,
      });
      await refresh(c.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function saveDraft(items: Item[], due: string, note: string) {
    if (!active) return;
    setBusy(true);
    try {
      const c = await api<Change>(`/changes/${active.id}/draft`, {
        items: items.map(
          ({ id, title, selected, amount_cents, resolution, kind }) => ({
            id,
            title,
            selected,
            amount_cents,
            resolution,
            kind,
          }),
        ),
        due_date: due,
        note,
      });
      setActive(c);
      setChanges((old) => old.map((v) => (v.id === c.id ? c : v)));
    } finally {
      setBusy(false);
    }
  }
  async function reload() {
    setBusy(true);
    setError("");
    try {
      await refresh(active?.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function revise() {
    if (!active) return;
    setBusy(true);
    setError("");
    try {
      const c = await api<Change>(`/changes/${active.id}/revise`, {});
      await refresh();
      setActive(c);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (loading)
    return (
      <div className="full-loading">
        <Brand />
        <LoaderCircle className="spin" />
        Opening your studio…
      </div>
    );
  if (loginNeeded)
    return (
      <div className="login-page">
        <form onSubmit={login}>
          <Brand />
          <h1>Welcome to your studio.</h1>
          <p>Enter your studio access code to continue.</p>
          <label>
            Access code
            <input
              type="password"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          {error && <Notice error>{error}</Notice>}
          <Button type="submit" loading={busy}>
            Open workspace <ArrowRight size={16} />
          </Button>
        </form>
      </div>
    );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Brand />
        <div className="studio-label">
          <span className="studio-avatar">S</span>
          <div>
            <strong>Your studio</strong>
            <span>Independent by design</span>
          </div>
        </div>
        <p className="nav-caption">WORKSPACE</p>
        <nav aria-label="Main navigation">
          {[
            { id: "workspace", icon: FolderOpen, label: "Project workspace" },
            { id: "changes", icon: ClipboardCheck, label: "Change requests" },
            { id: "ledger", icon: Layers3, label: "Scope & fees" },
            { id: "connections", icon: Settings2, label: "Connections" },
          ].map((n) => (
            <button
              key={n.id}
              className={view === n.id ? "active" : ""}
              onClick={() => {
                setView(n.id as View);
                setError("");
              }}
            >
              <n.icon size={18} />
              <span>{n.label}</span>
              {n.id === "changes" && (
                <span className="nav-count">
                  {
                    changes.filter((c) => !["superseded"].includes(c.status))
                      .length
                  }
                </span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <span className="tiny-leaf">
              <Layers3 size={19} />
            </span>
            <h3>Keep the good work going.</h3>
            <p>A clear scope makes space for a better collaboration.</p>
          </div>
          <button
            onClick={() => setView("connections")}
            className="sidebar-mode"
          >
            <span className="mode-dot amber" />
            {status?.paypal_ready ? "PayPal Sandbox" : "Walkthrough mode"}
            <ChevronRight size={14} />
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>Studio</span>
            <ChevronRight size={13} />
            <strong>
              {view === "connections"
                ? "Connections"
                : view === "changes"
                  ? "Change requests"
                  : view === "ledger"
                    ? "Scope & fees"
                    : project?.title || "Projects"}
            </strong>
          </div>
          <div className="top-actions">
            <span className="environment-label">
              <ShieldCheck size={14} />
              Sandbox only
            </span>
            <Button
              className="secondary small"
              onClick={() => setNewProject(true)}
            >
              <Plus size={15} /> New project
            </Button>
          </div>
        </header>
        <main className="main-content">
          {error && (
            <div className="global-error">
              <Notice error>{error}</Notice>
            </div>
          )}
          {view === "connections" && status ? (
            <Connections status={status} />
          ) : view === "changes" ? (
            <section>
              <p className="eyebrow">EVERY AGREEMENT, ACCOUNTED FOR</p>
              <div className="page-heading">
                <div>
                  <h1>Change requests</h1>
                  <p className="subtext">
                    Follow each version from first request to confirmed payment.
                  </p>
                </div>
                <Button className="secondary" loading={busy} onClick={reload}>
                  <RefreshCw size={15} />
                  Refresh
                </Button>
              </div>
              <div className="changes-table">
                {changes.length === 0 ? (
                  <div className="empty-list">
                    <FileText />
                    <h2>No change requests yet.</h2>
                    <p>
                      Analyze a client’s request in your project workspace to
                      get started.
                    </p>
                    <Button onClick={() => setView("workspace")}>
                      Go to workspace
                    </Button>
                  </div>
                ) : (
                  changes.map((c) => (
                    <button
                      className="change-row"
                      key={c.id}
                      onClick={() => selectChange(c)}
                    >
                      <span className="table-icon">
                        <FileText size={19} />
                      </span>
                      <div>
                        <strong>{c.project.title}</strong>
                        <span>
                          {c.project.client_name} · v{c.version} ·{" "}
                          {day(c.created_at)}
                        </span>
                      </div>
                      <Badge status={c.status} />
                      <strong className="row-money">
                        {c.status === "draft" ? "Draft" : money(c.total_cents)}
                      </strong>
                      <ChevronRight size={17} />
                    </button>
                  ))
                )}
              </div>
            </section>
          ) : view === "ledger" && project ? (
            <>
              <div className="page-heading">
                <div>
                  <p className="eyebrow">ONLY AGREED WORK COUNTS</p>
                  <h1>Scope & fees</h1>
                  <p className="subtext">
                    A shared record of what changed, what was confirmed, and
                    what remains unpaid.
                  </p>
                </div>
                <label className="project-picker">
                  <span>PROJECT</span>
                  <select
                    value={projectId}
                    onChange={(event) => {
                      setProjectId(event.target.value);
                      setActive(null);
                      setError("");
                    }}
                    aria-label="Select project"
                  >
                    {projects.map((p) => (
                      <option value={p.id} key={p.id}>
                        {p.title}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <ProjectLedger
                projectId={project.id}
                onOpen={openConfirmedRecord}
              />
            </>
          ) : project ? (
            <>
              <div className="page-heading">
                <div>
                  <p className="eyebrow">CLARITY BEFORE THE NEXT STEP</p>
                  <h1>Your project, on the same page.</h1>
                  <p className="subtext">
                    Turn “could we also…” into a clear, agreed change.
                  </p>
                </div>
                <label className="project-picker">
                  <span>PROJECT</span>
                  <select
                    value={projectId}
                    onChange={(e) => {
                      setProjectId(e.target.value);
                      setActive(null);
                      setError("");
                    }}
                    aria-label="Select project"
                  >
                    {projects.map((p) => (
                      <option value={p.id} key={p.id}>
                        {p.title}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <section className="metrics" aria-label="Project summary">
                <div>
                  <span className="metric-icon">
                    <FolderOpen size={19} />
                  </span>
                  <div>
                    <span>Original agreement</span>
                    <strong>
                      {money(project.base_cents)}
                      <small>USD</small>
                    </strong>
                  </div>
                </div>
                <div>
                  <span className="metric-icon gold">
                    <MessageSquareText size={19} />
                  </span>
                  <div>
                    <span>Change requests</span>
                    <strong>
                      {
                        projectChanges.filter((c) => c.status !== "superseded")
                          .length
                      }
                      <small>tracked</small>
                    </strong>
                  </div>
                </div>
                <div>
                  <span className="metric-icon sage">
                    <Wallet size={19} />
                  </span>
                  <div>
                    <span>Confirmed · unpaid test quotes</span>
                    <strong>
                      {money(outstanding)}
                      <small>USD</small>
                    </strong>
                  </div>
                </div>
              </section>
              <button
                className="text-button ledger-shortcut"
                onClick={() => setView("ledger")}
              >
                <Layers3 size={14} /> View confirmed scope & fee breakdown{" "}
                <ArrowRight size={13} />
              </button>
              <div className="workflow-heading">
                <div className="workflow-steps">
                  <span className="current">
                    <b>01</b>Compare scope
                  </span>
                  <ChevronRight size={14} />
                  <span className={active ? "current" : ""}>
                    <b>02</b>Review changes
                  </span>
                  <ChevronRight size={14} />
                  <span
                    className={
                      active && active.status !== "draft" ? "current" : ""
                    }
                  >
                    <b>03</b>Agree & pay
                  </span>
                </div>
                {active && (
                  <button
                    className="text-button"
                    onClick={() => {
                      setActive(null);
                      setError("");
                    }}
                  >
                    <Plus size={14} />
                    New request
                  </button>
                )}
              </div>
              <div className="workspace-grid">
                <div className="source-column">
                  <section className="source-panel">
                    <div className="section-heading">
                      <h2>
                        <FileText size={17} />
                        Original agreement
                      </h2>
                      <span className="subtle-pill">Baseline</span>
                    </div>
                    <h3>{project.title}</h3>
                    <p className="client-label">
                      <span className="avatar">
                        {project.client_name.slice(0, 1)}
                      </span>
                      {project.client_name}
                      <span className="muted">· client</span>
                    </p>
                    <p className="scope-text">
                      {active?.project.scope || project.scope}
                    </p>
                    <div className="source-footer">
                      <span>
                        <History size={14} />
                        {day(project.due_date)}
                      </span>
                      <strong>{money(project.base_cents)}</strong>
                    </div>
                  </section>
                  <section className="message-panel">
                    <div className="section-heading">
                      <h2>
                        <MessageSquareText size={17} />
                        The new request
                      </h2>
                      <span className="message-dot" />
                    </div>
                    <p>
                      Paste your client’s message. Keep their original wording.
                    </p>
                    <label className="sr-only" htmlFor="client-message">
                      Client request message
                    </label>
                    <textarea
                      id="client-message"
                      value={active ? active.message : message}
                      onChange={(e) => setMessage(e.target.value)}
                      readOnly={!!active}
                      minLength={8}
                      maxLength={12000}
                      rows={7}
                      placeholder="Could we also add…"
                    />
                    {!active && (
                      <>
                        <div className="sample-actions">
                          <span>Try an example</span>
                          <button
                            onClick={() =>
                              setMessage(status?.sample_message || "")
                            }
                          >
                            English
                          </button>
                          <button onClick={() => setMessage(CHINESE_SAMPLE)}>
                            中文
                          </button>
                        </div>
                        <Button
                          className="analyze-button"
                          onClick={analyze}
                          loading={busy}
                          disabled={message.trim().length < 8}
                        >
                          <Sparkles size={16} />
                          {status?.ai_ready
                            ? "Analyze scope changes"
                            : "Run walkthrough analysis"}
                          <ArrowRight size={16} />
                        </Button>
                      </>
                    )}
                    {active && (
                      <button
                        className="text-button"
                        onClick={() => {
                          setActive(null);
                          setMessage(active.message);
                        }}
                      >
                        Use this message for a new analysis{" "}
                        <ArrowRight size={13} />
                      </button>
                    )}
                  </section>
                  {projectChanges.length > 0 && (
                    <section className="recent-panel">
                      <h3>Recent versions</h3>
                      {projectChanges.slice(0, 4).map((c) => (
                        <button
                          key={c.id}
                          onClick={() => selectChange(c)}
                          className={active?.id === c.id ? "selected" : ""}
                        >
                          <span>Change · v{c.version}</span>
                          <Badge status={c.status} />
                          <ChevronRight size={13} />
                        </button>
                      ))}
                    </section>
                  )}
                </div>
                <section className="result-panel">
                  {active ? (
                    active.status === "draft" ? (
                      <QuoteEditor
                        key={active.id}
                        change={active}
                        onPublish={publish}
                        onSave={saveDraft}
                        busy={busy}
                      />
                    ) : (
                      <LockedQuote
                        key={active.id}
                        change={active}
                        events={events}
                        onRefresh={reload}
                        onRevise={revise}
                        busy={busy}
                      />
                    )
                  ) : (
                    <div className="analysis-empty">
                      <div className="document-illustration" aria-hidden="true">
                        <div className="doc-back" />
                        <div className="doc-front">
                          <span />
                          <span />
                          <span />
                          <div>
                            <Check size={19} />
                          </div>
                        </div>
                        <span className="floating-spark">
                          <Sparkles size={21} />
                        </span>
                      </div>
                      <span className="subtle-pill">A FAIRER WAY FORWARD</span>
                      <h2>
                        See the change.
                        <br />
                        Agree on what’s next.
                      </h2>
                      <p>
                        Compare your client’s request with the original
                        agreement, review a clear quote, and give both sides a
                        shared next step.
                      </p>
                      <div className="empty-benefits">
                        <span>
                          <ScanText size={16} />
                          Source-backed scope comparison
                        </span>
                        <span>
                          <ClipboardCheck size={16} />A quote you review and
                          control
                        </span>
                        <span>
                          <Wallet size={16} />
                          Client confirmation & payment
                        </span>
                      </div>
                      <div className="empty-mode">
                        <span
                          className={
                            "mode-dot " + (!status?.ai_ready ? "amber" : "")
                          }
                        />
                        {status?.ai_ready
                          ? "Your model is configured."
                          : "Sample rules are active. Connect a model for AI analysis."}
                        <button onClick={() => setView("connections")}>
                          Connections <ArrowRight size={12} />
                        </button>
                      </div>
                    </div>
                  )}
                </section>
              </div>
            </>
          ) : (
            <div className="empty-list">
              <FolderOpen />
              <h1>Your next project starts here.</h1>
              <Button onClick={() => setNewProject(true)}>
                Create your first project
              </Button>
            </div>
          )}
        </main>
        <footer className="studio-footer">
          <span>ScopePay · Good work. Clear agreements.</span>
          <span>
            <LockKeyhole size={12} />
            Your quotes stay versioned.
          </span>
        </footer>
      </div>
      {newProject && (
        <NewProject
          onClose={() => setNewProject(false)}
          onCreated={(p) => {
            setProjects((old) => [p, ...old]);
            setProjectId(p.id);
            setActive(null);
            setView("workspace");
            setNewProject(false);
          }}
        />
      )}
    </div>
  );
}
