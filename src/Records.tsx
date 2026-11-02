import { useEffect, useState } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  CheckCheck,
  FileText,
  RefreshCw,
} from "lucide-react";
import { api, day, money, statusLabel } from "./api";
import type { Ledger, Revision, RevisionTerms } from "./types";
import "./records.css";

const kindLabel = {
  added: "Added scope",
  changed: "Changed scope",
  included: "Already included",
  unclear: "Clarified scope",
};
const fieldLabel: Record<string, string> = {
  title: "Title",
  kind: "Classification",
  amount_cents: "Fee",
  resolution: "Clarification",
  due_date: "Delivery date",
  note: "Studio note",
  payment_mode: "Payment mode",
};
const signedMoney = (cents: number) =>
  `${cents > 0 ? "+" : cents < 0 ? "−" : ""}${money(Math.abs(cents))}`;

function Terms({ value, label }: { value: RevisionTerms; label: string }) {
  return (
    <div className="revision-terms">
      <span>{label}</span>
      <strong>{value.title}</strong>
      <p>
        {kindLabel[value.kind]} · {money(value.amount_cents)}
      </p>
      {value.resolution && <p>{value.resolution}</p>}
    </div>
  );
}

export function RevisionSummary({
  revision,
  saved = false,
}: {
  revision?: Revision | null;
  saved?: boolean;
}) {
  if (!revision) return null;
  return (
    <section className="revision-summary" aria-label="Version comparison">
      <div className="section-heading">
        <h3>What changed since v{revision.previous_version}</h3>
        <span className="subtle-pill">
          {saved ? "Saved comparison" : "Version comparison"}
        </span>
      </div>
      {saved && (
        <p className="revision-hint">
          Save the draft to update this comparison before sharing.
        </p>
      )}
      {revision.response_note && (
        <blockquote className="revision-feedback">
          <span>PREVIOUS CLIENT FEEDBACK</span>
          {revision.response_note}
        </blockquote>
      )}
      <div className="revision-totals">
        <span>
          Previous fee<strong>{money(revision.previous_total_cents)}</strong>
        </span>
        <ArrowRight size={16} />
        <span>
          {saved ? "Saved fee" : "This version"}
          <strong>{money(revision.total_cents)}</strong>
        </span>
        <span className="revision-delta">
          {signedMoney(revision.delta_cents)}
        </span>
      </div>
      {revision.baseline_changed && (
        <p className="revision-baseline">
          The agreed baseline changed. This revision was analyzed against the
          updated scope.
        </p>
      )}
      {!revision.has_changes && (
        <p className="revision-hint">
          No scope, fee, delivery or note differences from the last shared
          version.
        </p>
      )}
      <ul className="revision-items">
        {revision.items.map((item, index) => (
          <li key={index}>
            <span className={`revision-kind ${item.kind}`}>
              {item.kind === "modified"
                ? "Updated"
                : item.kind === "added"
                  ? "Added to quote"
                  : "Removed from quote"}
            </span>
            {item.fields.length > 0 && (
              <span className="revision-fields">
                {item.fields
                  .map((field) => fieldLabel[field] || field)
                  .join(" · ")}
              </span>
            )}
            <div className="revision-pair">
              {item.before && <Terms label="BEFORE" value={item.before} />}
              {item.after && <Terms label="AFTER" value={item.after} />}
            </div>
          </li>
        ))}
      </ul>
      {revision.metadata.map((meta) => (
        <div className="revision-meta" key={meta.field}>
          <strong>{fieldLabel[meta.field] || meta.field}</strong>
          <span>
            <del>
              {meta.field === "due_date"
                ? day(meta.before)
                : meta.before || "None"}
            </del>
            <ArrowRight size={13} />
            {meta.field === "due_date" ? day(meta.after) : meta.after || "None"}
          </span>
        </div>
      ))}
      <details className="version-details">
        <summary>Previous version fingerprint</summary>
        <code>{revision.previous_quote_hash}</code>
      </details>
    </section>
  );
}

export function ProjectLedger({
  projectId,
  onOpen,
}: {
  projectId: string;
  onOpen: (id: string) => void;
}) {
  const [record, setRecord] = useState<Ledger | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    setRecord(null);
    api<Ledger>(`/projects/${projectId}/ledger`)
      .then((data) => {
        if (active) setRecord(data);
      })
      .catch((err) => {
        if (active) setError(err.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [projectId, refresh]);
  return (
    <section className="ledger-page" aria-label="Project scope and fees">
      <div className="ledger-toolbar">
        <p>Confirmed work and test-payment status, in one place.</p>
        <button
          className="button secondary small"
          disabled={loading}
          onClick={() => setRefresh((v) => v + 1)}
        >
          <RefreshCw size={14} className={loading ? "spin" : ""} /> Refresh
          summary
        </button>
      </div>
      {error && (
        <div className="notice error" role="alert">
          {error}
        </div>
      )}
      {loading && <p role="status">Loading confirmed scope…</p>}
      {record && (
        <>
          <div className="ledger-value">
            <div>
              <p className="eyebrow">AGREED PROJECT VALUE · NOT REVENUE</p>
              <h2>
                {money(record.totals.agreed_project_cents)}
                <span>USD</span>
              </h2>
              <p>
                Original fee {money(record.project.base_cents)} + confirmed
                additions {money(record.totals.confirmed_additional_cents)}
              </p>
            </div>
            <a
              className="button secondary"
              href={`/api/projects/${projectId}/ledger/export`}
            >
              <ArrowDownToLine size={16} /> Export project summary
            </a>
          </div>
          <div className="ledger-balances">
            <div>
              <span>Verified Sandbox captures</span>
              <strong>{money(record.totals.sandbox_paid_cents)}</strong>
              <small>Test money · not live revenue</small>
            </div>
            <div>
              <span>Sandbox · accepted, unpaid</span>
              <strong>{money(record.totals.sandbox_unpaid_cents)}</strong>
              <small>Confirmed scope awaiting test payment</small>
            </div>
            <div className="demo-balance">
              <span>Simulated payments</span>
              <strong>{money(record.totals.demo_paid_cents)}</strong>
              <small>No payment API or money movement</small>
            </div>
            <div className="demo-balance">
              <span>Demo · accepted, unpaid</span>
              <strong>{money(record.totals.demo_unpaid_cents)}</strong>
              <small>Walkthrough quotes only</small>
            </div>
          </div>
          <div className="ledger-notice">
            <FileText size={18} />
            <p>
              {record.totals.awaiting_count} current unaccepted{" "}
              {record.totals.awaiting_count === 1 ? "proposal" : "proposals"} ·{" "}
              {money(record.totals.awaiting_cents)} excluded from agreed value.
              {record.totals.stale_count > 0 &&
                ` ${record.totals.stale_count} stale unaccepted ${record.totals.stale_count === 1 ? "quote needs" : "quotes need"} fresh analysis.`}{" "}
              Original-fee payments are not tracked here.
            </p>
          </div>
          <div className="ledger-heading">
            <h2>Confirmed scope additions</h2>
            <span>
              {record.confirmed.length} confirmed{" "}
              {record.confirmed.length === 1 ? "version" : "versions"}
            </span>
          </div>
          {record.confirmed.length === 0 ? (
            <div className="ledger-empty">
              <CheckCheck size={25} />
              <h3>No additional scope confirmed yet.</h3>
              <p>
                Drafts, rejected quotes and replaced versions do not become
                agreed work.
              </p>
            </div>
          ) : (
            <div className="ledger-entries">
              {record.confirmed.map((change) => (
                <article key={change.id}>
                  <div className="ledger-entry-heading">
                    <div>
                      <span className={`badge ${change.status}`}>
                        {statusLabel[change.status] || change.status}
                      </span>
                      <h3>Change · v{change.version}</h3>
                      <p>
                        Confirmed by {change.confirmed_by} ·{" "}
                        {day(change.confirmed_at)}
                      </p>
                    </div>
                    <strong>{money(change.total_cents)}</strong>
                  </div>
                  <ul>
                    {change.items.map((item, index) => (
                      <li key={index}>
                        <div>
                          <strong>{item.title}</strong>
                          {item.resolution && <p>{item.resolution}</p>}
                        </div>
                        <span>{money(item.amount_cents)}</span>
                      </li>
                    ))}
                  </ul>
                  <div className="ledger-entry-footer">
                    <span>
                      Delivery for this change · {day(change.due_date)}
                    </span>
                    <button
                      className="text-button"
                      onClick={() => onOpen(change.id)}
                    >
                      Open confirmed record <ArrowRight size={13} />
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
          <p className="ledger-footnote">
            Snapshot generated {day(record.generated_at)}. {record.notice}
          </p>
        </>
      )}
    </section>
  );
}
