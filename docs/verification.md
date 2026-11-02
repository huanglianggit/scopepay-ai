# Verification record — 2026-10-13

## Automated checks

- `npm run build`: PASS. TypeScript check and production build completed. The project uses Vite's runner config loader to avoid the Windows sandbox's ancestor-directory enumeration restriction in esbuild's bundled config loader.
- `../.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=output/pytest-20261013-03 --tb=short`: **34 passed**.
- One non-failing Starlette/HTTPX deprecation warning from the existing parent environment. No dependency changes were made to the original ProofPack app.

Covered: full walkthrough and ZIP checksums; unresolved ambiguity rejection; immutable published/accepted versions; decline/revision; superseded link rejection; saved-draft persistence; previously accepted scope context; English and Chinese rule examples; invalid amounts/items; unauthorized and cross-origin requests; hosted owner-code requirement; order acceptance gates; idempotent payment reconciliation; mismatched order/version/amount/currency/pending capture rejection; webhook deduplication; unsigned webhook rejection; missing model configuration; model HTTP failure; malformed JSON; fabricated source quotes; PayPal HTTP payloads, Sandbox-only endpoint and token reuse.

AI and PayPal external responses in these tests are mocked. Passing these checks is not proof of successful real-provider inference or real PayPal Sandbox connectivity.

## Browser checks

Performed through the Codex in-app browser after the CLI package lookup was unavailable under network restrictions.

- Desktop viewport: 1440 × 1000. `window.innerWidth=1440`; document client/scroll widths both 1425 (15px scrollbar), no horizontal overflow.
- Mobile viewport: 390 × 844. `window.innerWidth=390`; document client/scroll widths both 375, no horizontal overflow on workspace or client review.
- Actual UI workflow: analyze sample → attempt publication with unresolved question (blocked) → clarify booking → change language price to USD 125.50 → save draft → reload and reopen → verify restored content → publish → open independent client page → verify empty-name rejection → accept as synthetic test client → simulate payment → reload and verify persisted `demo_paid` state.
- New project form created a synthetic Lumen portfolio project. Mobile dialog closed with Escape. Chinese example generated three cited items and the booking clarification question.
- Connections navigation displayed accurate unconfigured model/PayPal status. Studio browser console contained no error entries at final check.
- SQLite records survived backend restart. Studio owner cookie also remained usable.

Screenshots, excluded from Git:

- `output/playwright/workspace-desktop.jpg`
- `output/playwright/workspace-mobile.jpg`
- `output/playwright/client-complete-desktop.jpg`
- `output/playwright/client-complete-mobile.jpg`

## Still required before final submission

1. Configure and verify an actual model endpoint; no Ollama service was running on localhost:11434 during this run.
2. Configure PayPal Sandbox credentials and verify buyer approval, capture, seller activity, cancellation and webhook behavior against PayPal itself.
3. Provide a public licensed repository, reproducible/hosted judging access and testing instructions.
4. Record and publicly upload the final English/translated YouTube demonstration after real integration verification.

The local preview runs at http://127.0.0.1:8791. It is not a publicly hosted judging URL. Demo analysis and simulated payment are explicitly labeled throughout the current runtime.
