# ScopePay upgrade verification — 2026-10-19

## Delivered

1. **Version comparison** in the studio draft, locked quote and client review. Shows additions/removals, before/after title/category/fee/clarification, fee delta, changed delivery/notes/payment environment, prior feedback and baseline refresh. Draft comparisons are explicitly the saved state. New revision hashes bind the frozen previous terms; old quote hashes are preserved.
2. **Scope & fees** project ledger. Agreed value excludes unaccepted/draft/declined/replaced quotes. Confirmed additions list typed confirmation and per-change delivery. Sandbox captures, simulated payments, and the respective unpaid fees remain separate. No revenue or original-fee collection is implied.
3. **Project summary export** with Markdown, JSON and SHA-256 checksums. Owner-only, no review tokens, approval URLs, sessions or API secrets. Individual change exports now include revision differences.
4. **State consistency** when opening a confirmed record: refresh the server rather than reopening stale cached state. Changing projects in the ledger clears a previously selected quote.

## Automated verification

- `../.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp=output/pytest-20261019-03 --tb=short` → **65 passed** (previously 49).
- New checks include comparison terms, feedback, price/removal/date/note changes, export privacy, revision hash binding, exact/ambiguous reanalysis matches, stale-baseline reanalysis, ledger status arithmetic, project isolation, owner access, project ZIP checksums, zero-fee accounting, payment-mode changes and revision chains.
- `npm run build` → PASS (TypeScript and Vite production build).
- Tests use temporary databases and mocked external providers. Unmocked outgoing HTTP is blocked in the test modules. One existing Starlette/HTTPX deprecation warning remains.

## Actual browser verification

Used the Playwright CLI against the local production build on port 8791. No CUA policy bypass or browser-security changes were used. This is a fresh local test session, not the old blocked browser-tab binding.

Synthetic UI flow:

1. Created **Northstar website - QA demo**, original recorded fee USD 500, synthetic client Morgan Test. Existing Bloom and Lumen records were preserved.
2. Analyzed the sample message using explicitly labeled walkthrough rules; clarified embedded booking and published v1 at USD 340.
3. Client requested removing booking, including supplied translation for free, and moving delivery by one day. Owner refresh displayed the response.
4. Created v2; previous feedback appeared. Changed language classification to included; its fee became zero and disabled. Publishing without a correction reason was blocked in the UI.
5. Recorded the reason, excluded booking, moved delivery from Nov 5 to Nov 6, and saved. Comparison showed language before/after, booking removed, fee USD 340 → USD 40, delta −USD 300, and the date/note changes. Published and reopened the independent client page.
6. Client accepted v2. Ledger showed agreed value USD 540 and demo unpaid USD 40, with all Sandbox paid totals at zero. Clicked the summary export and verified the browser downloaded a ZIP.
7. Simulated payment, refreshed the ledger, and verified simulated USD 40, demo unpaid USD 0, Sandbox paid USD 0, agreed value still USD 540. Opened the confirmed record through the new navigation and verified its latest status.
8. Requested confirmation of the already included language work. Selected the free item, published a zero-total quote, and confirmed it on mobile. It displayed **Changes confirmed**, no payment due and no payment action.
9. Reloaded the old v1 client link: **Replaced** was visible and acceptance/payment controls were unavailable.

Layout and screenshots:

- Client revision and project ledger inspected at desktop **1440×1000** and mobile **390×844**.
- Ledger measured `viewport/client/scroll = 1440/1440/1440` on desktop, `390/390/390` on mobile. Mobile client comparison also measured `390/390/390`; no horizontal overflow.
- Screenshots viewed after capture: `output/playwright/revision-desktop-20261019.png`, `revision-mobile-20261019.png`, `ledger-desktop-20261019.png`, `ledger-mobile-20261019.png`. Additional zero-charge evidence: `no-charge-mobile-20261019.png`.
- Fresh-session owner bootstrap initially received an expected workspace HTTP 401 before local session creation. The app recovered and subsequent reloads worked. No unexpected application failure was observed in the tested flows; this is not a claim that every possible UI state or external provider was tested.

## Remaining before submission

- Configure and verify actual model inference. The current local runtime still uses `AI_PROVIDER=demo`, not a live AI model.
- Configure PayPal Sandbox credentials and verify an actual test buyer approval/capture and seller activity, cancellation/recovery, and the optional signed webhook. Browser tests above simulated payment only; no real funds or PayPal transaction occurred.
- Public licensed source repository, reproducible judging access, final English/translated demo video, and Devpost submission remain outstanding. No publishing, account changes, commits, pushes or external messages were performed in this upgrade.

Local preview: http://127.0.0.1:8791 . Use `./start.ps1` if it has stopped. The address is local-only, not public judging access.
