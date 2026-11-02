# PayPal Sandbox configuration — 2026-10-29

Historical setup-stage record. Later on the same date, real model inference and a USD 99 Sandbox capture were verified; see [the subsequent verification](verification-2026-10-29.md). Statements below about an unconfigured model or untested payment describe the earlier setup stage, not the final status.

## Completed

- Used the existing Default Application in the authenticated PayPal Developer Sandbox dashboard. Existing default Sandbox Business and Personal accounts were present.
- With explicit user consent, stored the existing Sandbox Client ID and Secret in the project-root `.env`. Did not create, rotate or publish keys; did not change app capabilities or switch to Live.
- Verified `.env` is excluded by Git. No credential values are included in this report or screenshot.
- Confirmed a direct Sandbox OAuth request returned HTTP 200 and an access token. Then independently verified the project's `PayPal.token()` adapter obtained and cached a token. Token values were not printed or persisted.
- Started the local backend on 127.0.0.1:8791. `/api/status` returned `paypal_ready=true`, `payment_environment=sandbox`, `ai_ready=false`, `ai_provider=demo`, and `webhook_ready=false`.
- Opened the actual Connections page and verified PayPal Sandbox displays Configured, with the warning that a successful test transaction is still required.

## Scope and limitations

This confirms credentials and OAuth connectivity only. No test order, buyer approval, capture, seller transaction or webhook has been verified in this setup turn. No real money moved. Existing walkthrough quotes keep their demo payment mode; create a new positive-value quote for Sandbox payment testing.

The model remains unconfigured. The `.env` retains explicit demo analysis. A real model endpoint/model/key still needs configuration and a verified request before claiming AI integration readiness.

Webhook registration was intentionally left empty because there is no public HTTPS listener configured. Local return-page capture can be tested first; webhook recovery must be verified separately if included in submission claims.

Evidence screenshot: `output/paypal-setup/connections-20261029.png`. Local preview: http://127.0.0.1:8791 . This is not public judging access.
