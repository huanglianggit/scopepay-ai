# ScopePay AI — judging and testing

ScopePay connects a freelancer's scope-change request, human-reviewed quote, version-specific client confirmation, and PayPal Sandbox payment. AI proposes an interpretation; it cannot authorize fees or move money on its own.

## Access

- Hosted build: https://47.79.243.86:18080
- Video: https://youtu.be/rMoDZ5U19lk — 2:45, English narration and burned-in captions.
- Enter the studio access code supplied in the **private Devpost testing instructions**. It is not a PayPal password. If the code is missing, request it from the entrant through Devpost. No purchase or live payment is required.
- Use synthetic names, agreements, and messages only. The single-studio prototype is shared; do not enter personal or customer documents. AI request content is sent to the configured model provider.
- The entrant must keep the build and sufficient API credits available until judging ends on December 15, 2026. Do not shut down hosting or change the access code without updating the private testing instructions. The IP certificate has automated renewal.

## Suggested working walkthrough

1. Choose **New project**. Use a synthetic agreement such as: "One responsive English landing page including a contact form and two revision rounds. Additional languages, booking, and extra pages are excluded."
2. Analyze: "Please add a Spanish version of the landing page. I will provide the translated copy."
3. Expand **View source evidence**. Quotes are validated against the exact submitted documents; this does not establish that the model's classification is correct. Model errors are shown instead of silently falling back to demonstration rules.
4. Review each classification, amount and clarification. Corrections require a reason. Included work cannot acquire a fee; unclear selected work must be clarified. Save the draft before sharing.
5. **Lock & share quote** creates an immutable version and a private client review link. Do not post that link publicly. A client may confirm the version or request a revision. Replaced links cannot accept an old quote.
6. Use a synthetic client name. For a selected zero-dollar change, confirmation ends at **accepted_no_payment** and checkout is unavailable. For a paid change, acceptance records **accepted**, not paid.
7. **PayPal Sandbox checkout** opens PayPal's test environment. Use a Sandbox Personal buyer, not a real PayPal account, live card, or the seller account. A test buyer may be created in the PayPal Developer dashboard; any entrant-provided buyer access belongs only in private testing instructions.
8. Cancel once: the quote should remain accepted and unpaid. Retry checkout and complete the Sandbox buyer approval yourself. Return to ScopePay. The server verifies the capture's order, amount, USD currency, reference, and quote fingerprint before displaying **Sandbox payment verified**.
9. Reload the client page, then inspect **Scope & fees**. Sandbox captures and simulated payments are separate; agreed project value is not revenue. Export a change record and project summary; `checksums.sha256` covers the archive contents.

Do not create a new order merely because a network response was interrupted. Use the existing checkout/status controls. The optional signed webhook recovery implementation is covered by automated tests, but its public listener has not been live-verified.

## What has been verified

- November 2: public HTTPS and access-code login; anonymous workspace denial; live hosted SiliconFlow inference with source validation; server-side PayPal Sandbox OAuth.
- November 2: hosted API regression covering draft persistence, immutable publication, client revision feedback, superseded-link rejection, repeated-acceptance rejection, zero-dollar confirmation/payment blocking, and verified ZIP checksums.
- October 29: a separate local USD 99 Sandbox purchase was completed by the entrant and independently reconciled against the stored quote. This is historical test-fund evidence, not proof that every newer hosted checkout has been completed.
- Current clean-install/unit/build evidence is recorded in the dated regression report. Financial and model edge cases mocked in unit tests are not live-provider validation.

## Video and language notes

The video mixes genuine UI operations with authentic state close-ups; it is not one continuous checkout recording. Cedar and Northstar are separate synthetic cases. Cedar's USD 200 quote becomes USD 120 and remains unpaid in the video; Northstar shows the previously completed USD 99 Sandbox capture. There is no escrow or legal guarantee.

Model output can contain non-English labels and must be human reviewed. In the hosted test, **"Versión en español de la página de aterrizaje"** means **"Spanish version of the landing page"**. The English clarification below it defines the actual reviewed deliverable. Historical screenshot **"Online consultation booking"** refers to the Chinese booking label; its explanation says booking was excluded from the original agreement and needs a separate review. All test instructions and submitted narration are supplied in English.

## Run it yourself

Follow the root README using Python 3.12+ and Node.js 20.19+. Install Python requirements, run `npm ci` and `npm run build`, then run Uvicorn from the repository root with one worker. The Python application serves the built frontend and API.

Copy `.env.example` to `.env` and configure your own model and PayPal **Sandbox** credentials if testing independently. They are intentionally not committed. `AI_PROVIDER=openai` denotes an OpenAI-compatible protocol; the verified model is SiliconFlow `deepseek-ai/DeepSeek-V4-Flash`, not an OpenAI-hosted model. The explicit `demo` setting uses matching rules and labeled simulated payments, not inference or transactions.

MIT licensed. AI coding assistance was used in implementation, tests, and documentation. Prototype boundaries: one studio, USD, synthetic data, typed confirmations, Sandbox only; no certified electronic signature, production money movement, or proven legal enforceability.
