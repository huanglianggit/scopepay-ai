# ScopePay AI

Turn a client's “could we also…” into a source-backed, explicitly approved, payable change order.

ScopePay is a single-studio prototype for freelance web developers and designers. It compares a client's new message with the agreed scope, raises clarification questions, prepares editable line items using a starting rate card, freezes the reviewed quote, and gives the client a private confirmation and payment page.

[中文体验与配置说明](docs/START-HERE.zh-CN.md)

## Hackathon judging

- Hosted prototype: https://47.79.243.86:18080
- Demo video: https://youtu.be/rMoDZ5U19lk (2 minutes 45 seconds, English narration and captions).
- [English judging and testing guide](JUDGING.md). The studio access code is provided privately in the Devpost testing instructions, never in this public repository.
- On November 2, 2026, public HTTPS, owner login, real SiliconFlow analysis, Sandbox OAuth, revision gates, no-charge confirmation, and checksum exports were verified. The entrant completed the hosted Harbor version 2 USD 12.00 Sandbox purchase; an independent PayPal order read verified the completed capture, exact quote reference/fingerprint, amount and USD currency. Paid state, ledger and exports passed 24 follow-up checks. See [sanitized payment evidence](docs/evidence/hosted-payment-verification-2026-11-02.json). An accepted quote alone is not a completed payment.

## Current implementation status

- Implemented: project creation; English/Chinese message input; analysis adapters; source-quotation validation; editable classifications/fees with recorded correction reasons; ambiguity gates; saved drafts; immutable published versions; stale-scope rejection; revision/decline flow with version differences; client confirmation, including no-charge changes; project scope/fee ledger; SQLite persistence; change-record and project-summary ZIP exports; PayPal Sandbox OAuth, create-order, approval redirect, capture reconciliation, expired-order retry and signed webhooks.
- Default runtime: `AI_PROVIDER=demo` uses **explicitly labeled matching rules**, not an AI model. Unknown requests remain unclear. Demo payments are stored as `demo_paid`, never `paid`.
- Live inference was verified on 2026-10-29 using SiliconFlow's `deepseek-ai/DeepSeek-V4-Flash`, including schema and exact-source quotation checks. OpenAI-compatible API and local Ollama adapters remain available; Ollama was not live-tested.
- A USD 99 PayPal Sandbox transaction was completed on 2026-10-29. A subsequent server-side GET confirmed the PayPal order was COMPLETED and the capture matched the locked quote and local paid record. This was test money, not a production transaction. Retry/cancellation/webhook paths have automated test coverage; real-provider edge-case and webhook verification remain separate work.
- Submission preparation is in progress. The public MIT source, hosted build, English-captioned video, private judging access instructions and updated supporting kit are prepared. Devpost remains a draft until the entrant accepts final terms and submits. This repository is not a submission receipt.

## Run locally on Windows

Requirements: Node.js 20.19+ (24 recommended), Python 3.12+, npm.

For the dependency versions used in the November 2 clean-install check, install with `python -m pip install -r requirements-lock.txt` instead of the ranged requirements. `npm ci` uses the committed package lock. Python 3.12.10 and Node.js 24.19.0 were verified on Windows; the hosted runtime is Python 3.12.16 on Alibaba Cloud Linux.

From this directory:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
npm ci
npm run build
.venv/Scripts/python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8791
```

Open **http://127.0.0.1:8791**. The Python server serves both the API and the built frontend. It creates a sample Bloom Studio project on first startup. Data persists in `data/scopepay.sqlite3`, excluded from Git.

In the current parent workspace an existing Python virtual environment can also be used:

```powershell
../.venv/Scripts/python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8791
```

After initial installation, `./start.ps1` selects this project's environment or the existing parent environment and starts the app. To work on the frontend with hot reload, keep the API running and use `npm run dev` in a second terminal; open http://127.0.0.1:5191.

## Try the walkthrough

1. Select Bloom Studio, leave the sample request in place, and click **Run walkthrough analysis**.
2. Inspect the source evidence. Clarify the booking deliverable, for example: “Embed the client's existing scheduling page; no custom accounts or payment backend.”
3. Edit prices, exclude unwanted items, set the delivery date, and **Save draft**. Refresh and reopen the draft to verify persistence.
4. **Lock & share quote**, then open the private client review link.
5. Enter a test name, check the review confirmation, and accept. Choose **Simulate demo payment** when no Sandbox credentials are configured.
6. Export the ZIP. It contains `agreement.md`, `record.json`, and checksums. The record includes quotation evidence, clarifications, confirmation, status, and payment environment.

Published quotes cannot be edited. An unanswered or declined quote can be revised; the old link remains visibly replaced and cannot be accepted. Confirmed additions are included in subsequent analysis context so the same work is not automatically re-quoted. This is context assistance, not a guarantee that an AI will classify all repeat work correctly.

You can correct a suggested classification, but publication requires a recorded reason for changing the analysis result. Included work must remain free; classify genuinely new work separately and explain the correction. A selected zero-total quote records `accepted_no_payment` on acceptance and never offers checkout or claims a completed payment. If another version changes the agreed scope, stale drafts cannot be published and stale client quotes cannot be accepted. Revising a stale unanswered/declined quote reruns analysis against the latest scope; prices and clarifications must be reviewed again.

## Review revisions and project fees

- **What changed since vN** shows selected additions/removals, before/after classifications, titles, fees and clarification, plus delivery, note and payment-mode changes. The prior client's feedback remains visible. In a draft the comparison describes the last saved state; save before reviewing it. Shared/client views and exports use the locked terms.
- Each new revision freezes a minimal previous-terms snapshot. The new quote fingerprint includes this snapshot and the previous fingerprint. This is a version link, not certified signing or proof of who signed. Older revisions created before this feature have no comparison snapshot and remain readable without changing their original hashes.
- **Scope & fees** lists confirmed additions and per-change delivery dates. The agreed project value is the original recorded fee plus confirmed additional fees, not money received. Unaccepted, declined, replaced and draft quotes do not count; stale pending quotes are called out separately.
- Verified Sandbox captures, Sandbox unpaid fees, simulated payments and demo unpaid fees are separate. Neither Sandbox nor demo totals represent real revenue. The original fee's payment is not tracked. No-charge confirmations do not invent payments.
- **Export project summary** downloads `project-summary.md`, `ledger.json`, and `checksums.sha256`. It is owner-only and excludes private review tokens, session data and API credentials. Opening a confirmed record refreshes its server state rather than trusting an older workspace cache.

## Connect an AI model

Copy `.env.example` to `.env` using your editor. Secrets stay server-side and are never returned by the API or included in exports.

For an OpenAI-compatible provider:

```dotenv
AI_PROVIDER=openai
AI_BASE_URL=https://YOUR-PROVIDER/v1
AI_MODEL=YOUR-MODEL
AI_API_KEY=YOUR-KEY
```

For an already-installed Ollama model:

```dotenv
AI_PROVIDER=ollama
AI_BASE_URL=http://127.0.0.1:11434/v1
AI_MODEL=YOUR-LOCAL-MODEL
AI_API_KEY=
```

For SiliconFlow China (the provider verified for this project):

```dotenv
AI_PROVIDER=openai
AI_BASE_URL=https://api.siliconflow.cn/v1
AI_MODEL=deepseek-ai/DeepSeek-V4-Flash
AI_API_KEY=YOUR-SILICONFLOW-KEY
```

`openai` names the compatible protocol, not the model vendor. Keep the full model ID from your provider. A key and sufficient provider access/credits are required. Use synthetic documents for testing; request contents are sent to the configured provider. Do not put private customer material into a public demonstration.

The provider must implement `/chat/completions` with JSON-object output. Restart the backend after changes. The adapter validates the result schema and checks every quoted passage against the input. Failed or fabricated citations return an error without creating a draft. Provider failures never silently switch to demo output. Fees come from the studio rate card and human edits, not model-generated payment instructions.

## Connect PayPal Sandbox

1. Sign in to [PayPal Developer](https://developer.paypal.com/).
2. Apps & Credentials → **Sandbox** → create/select an app.
3. Add its client ID and secret to `.env`:

```dotenv
PAYPAL_CLIENT_ID=YOUR-SANDBOX-CLIENT-ID
PAYPAL_CLIENT_SECRET=YOUR-SANDBOX-SECRET
PUBLIC_BASE_URL=http://127.0.0.1:8791
```

4. Restart the server. Create a **new** quote: its payment mode is fixed at publication, so an earlier demo quote remains a demo quote.
5. Accept the quote in the client view, choose **PayPal Sandbox checkout**, and sign in with a Sandbox **Personal/buyer** account. These are generated test accounts, separate from your real PayPal login.
6. Approve the test payment and return to ScopePay. Only a completed capture with the correct order, quote hash, purchase-unit reference, amount and USD currency changes the state to `paid`.

The API base is hardcoded to `https://api-m.sandbox.paypal.com`. Production payment credentials and live money movement are outside this prototype.

Cancellation preserves the accepted/unpaid quote. Capture retries use an idempotency key and read the authoritative order representation; a completed capture can be recovered without creating another charge. A voided or no-longer-available order starts a new checkout attempt with a new attempt-specific request ID, without changing the confirmed quote. Network failures do not trigger replacement orders. **Refresh payment status** only checks and reconciles an already completed capture; it does not initiate capture. Use the checkout button to finish a previously approved order.

### Optional webhook

For an HTTPS-hosted build, register `https://YOUR-HOST/api/paypal/webhook` with `PAYMENT.CAPTURE.COMPLETED`, and set `PAYPAL_WEBHOOK_ID`. ScopePay verifies signatures with PayPal, deduplicates event IDs, reads the authoritative order, and verifies it against the stored quote. This recovers completed captures when the client browser closes. It does not claim to capture an order that was never captured.

## Hosting and judging

- Configure `PUBLIC_BASE_URL` to the exact public HTTPS origin and set a strong `OWNER_ACCESS_CODE` before hosting. Public-origin owner sessions are refused without that code, including behind a loopback reverse proxy.
- The studio uses an HttpOnly, SameSite cookie; client pages use unguessable private capability links. This is a single-studio application, not a multi-tenant account system. Anyone holding a client link can review/respond to that quote; do not publish real client links or sensitive client documents in a demo.
- Persist the SQLite data directory on the host. Build with `npm ci && npm run build`, install Python requirements, and run Uvicorn behind the hosting platform's HTTPS endpoint.
- Supply judges with the studio access code through submission testing instructions. Keep API secrets on the server; do not commit secrets to a public repository.
- Provide a separate synthetic demo project for judging. Keep the working build accessible during judging.

## Verify

```powershell
npm run build
.venv/Scripts/python.exe -m pytest -q
```

In the existing parent environment, use `../.venv/Scripts/python.exe`. In a restricted desktop sandbox, use a fresh workspace-local temp directory and disable Pytest's cache if inherited temp-folder ACLs prevent access:

```powershell
New-Item -ItemType Directory -Path output -Force
../.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=output/pytest-fresh-run
```

Use a new empty basetemp path for each restricted run. Tests use temporary databases, fake model responses, and fake PayPal responses; they never perform financial transactions.

See [architecture](docs/architecture.md), [demo script](docs/demo-script.md), [submission draft](docs/submission-draft.md), [initial browser verification](docs/verification.md), [2026-10-14 business audit](docs/verification-2026-10-14.md), [2026-10-19 upgrade verification](docs/verification-2026-10-19.md), and [2026-10-29 live integration verification](docs/verification-2026-10-29.md). Older verification files describe their dated stage, not the current integration status.

## License

MIT. Product design and implementation were assisted by an AI coding agent. Rate-card amounts and Bloom Studio materials are synthetic examples, not researched market rates. Version fingerprints provide integrity comparison, not certified signatures, legal enforceability, escrow, or a guarantee of dispute outcomes.
