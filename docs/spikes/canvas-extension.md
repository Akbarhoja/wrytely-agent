# Canvas extension feasibility — P0-M1

Owner: Murtazo and local assistant. Claim [#51](https://github.com/Akbarhoja/wrytely-agent/issues/51).
Base `9bbea97`; branch `codex/canvas-extension-feasibility`. This is an offline-prepared
diagnostic, not a completed Canvas connection or background collector.

## Current result

The read-only probe and fixture tests are implemented. Actual CSU session access,
browser behavior and installation have **not been tested**. Exact origin, consenting
course scope and unpacked installation permission were requested in this session.
No account information or academic content has been collected.

The extension runs on an explicit toolbar click, with no alarms or content scripts.
It requests only the configured Canvas HTTPS host: no cookies, tabs, scripting,
storage or broad host permissions. Fetch includes the browser session without reading
or exporting cookies. Whether that session is usable from the service worker must be
measured on the actual browser; host permission alone does not prove authentication.

No source content is written to disk, uploaded, rendered or logged. The worker prints
counts and controlled status codes only. Network diagnostics can still contain private
data: do not publish raw DevTools captures. A worker termination loses this diagnostic
run; repeat manually, never claim restart checkpoint recovery from this spike.

## Local preparation and operation

1. Confirm exact CSU origin and one or two consenting course IDs. The IDs restrict this
   diagnostic's content reads; course discovery itself is automatic. This restriction
   is not the production P1 design or satisfaction of its no-manual-ID acceptance.
2. Run `node extension/canvas-feasibility/prepare.mjs https://AUTHORIZED-CANVAS-HOST COURSE_ID`.
   The command validates the origin and creates an ignored `unpacked/` folder.
3. After installation authorization, use Chrome/Edge Extensions → Developer mode →
   Load unpacked → `extension/canvas-feasibility/unpacked`. Review its single-host scope.
4. Open the extension service worker console. Sign into Canvas normally, then click
   its toolbar action once. `RUN` means running, `READ` means a partial diagnostic
   report exists, `STOP` means blocked. `READ` does not mean full course coverage.
5. Record only controlled results/counts in the matrix below. Close the Canvas tab,
   click again with browser running, then repeat after restart/login expiry/account switch.
   Do not actively change another person's account or revoke access for this test.
6. Remove the extension when finished. The generated files contain local consenting
   host/course scope and must remain ignored. No ongoing polling is installed.

Bounds: 10 pages/resource, 50 requested items/page, 1 MiB/response, 15 seconds/request,
at most two consenting courses' contents per diagnostic. There is no retry loop.
Redirects, cross-origin/path-changing pagination, secret query parameters, invalid
JSON, oversized bodies and pagination cycles fail explicitly. Login HTML is blocked.
Session identity is rechecked after discovery and each resource; an observed switch
discards the entire report. A switch away and back between checks cannot be detected;
this is a boundary probe, not an independent provider attestation.

## Evidence matrix

| Check                                 | Evidence         | Current result                                  |
| ------------------------------------- | ---------------- | ----------------------------------------------- |
| Two-course discovery/read shapes      | Scripted fixture | Pass; not CSU evidence                          |
| Opaque pagination and origin bounds   | Scripted fixture | Pass                                            |
| Login HTML / 403 / size/page limits   | Scripted fixture | Explicit failure; no successful empty sync      |
| Account switch and redacted output    | Scripted fixture | Report discarded; no source text in result      |
| Exact CSU session with tab open       | Live             | Not run — scope/installation pending            |
| Canvas tab closed, browser running    | Live             | Not run                                         |
| Browser restart / suspended worker    | Live             | Not run                                         |
| Expired login / actual account switch | Live             | Not run                                         |
| Actual syllabus document contents     | Live             | Not run; linked files unsupported in this slice |
| Assignment instructions and rubric    | Live             | Not run                                         |
| Discussion full view/pagination       | Live             | Not run; one visible topic sampled only         |

Inline `syllabus_body` is inspected only for presence. Linked syllabus files, PDF/Word,
modules, pages, announcements, all discussion replies and attachment extraction remain
gaps. Listing assignments exposes returned rubric presence, not proof of full rubrics
for every course. Missing rubric or topic data stays unknown. `403` is not proof of an
initial-post restriction; the diagnostic does not post or otherwise unlock content.

## Review of Akbar's requests

Our implementation scope is `extension/`, `integrations/`, `app/`, `web/`, `deploy/`
and their tests. Akbar's track supplies runtime, stores, migrations and shared types.
The ordered work orders for our track are:

| Step  | Deliverable                                                   | Dependency                                                      |
| ----- | ------------------------------------------------------------- | --------------------------------------------------------------- |
| P0-M1 | Canvas session feasibility and redacted content/access matrix | Consenting institution scope and install permission             |
| P0-M2 | Outlook read consent, notifications and delta feasibility     | School mailbox and Microsoft app/admin access                   |
| P0-M3 | Actual WhatsApp reply delivery and signed status              | Existing business/account lock resolved; consenting recipient   |
| P1-M1 | Paired, resumable Canvas collector and ingestion routes       | P0-M1 and agreed/implemented C1/C2 storage                      |
| P1-M2 | Server Outlook OAuth, refresh, subscriptions and catch-up     | P0-M2 and C1/C2                                                 |
| P1-M3 | Connection/reconnection and course coverage screens           | Connector implementations and private projections               |
| P2-M1 | Proactive WhatsApp offers/templates and receipts              | Live channel plus typed action authorization                    |
| P2-M2 | Continuous isolated service, health, restart and stop         | Supervisor, budgets, connectors and bounded activation approval |
| P3-M1 | Student decisions, private documents and result screens       | Validated intent, checked rendering and delivery contracts      |
| P4-M1 | Submission/grade evidence and student controls                | Collection plus adaptation/progress contracts                   |
| P5-M1 | Connector failure/recovery checks and pilot onboarding        | Full workflow and approved pilot scope                          |
| P6-M1 | Reproducible setup, distribution and demonstration            | Reviewed reliability and Akbar's release decision               |

This is an execution map of existing work orders, not new permission to connect,
send, spend, deploy or implement a parallel runtime.

Reviewed coordination history through comment6536175863, current task claims, own
PR #14/#20/#28 histories and integration/review requests #25/#40/#42/#44/#46/#48/#50.
Earlier linking-expiry, malformed webhook, Clerk-origin, private delegation and saved
format-viewer requests have published fixes; they are retained in the baseline.
Old manual-intake-as-completion and initial Canvas cloud OAuth assumptions are
superseded by revision7. Prior A4 remains parked; no scheduler should be recreated.

| Current request                          | Our action / limit                                                                                                                                   |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Review combined #46 at `9bbea97`         | Inspect constituent delta and run combined checks; assistant evidence cannot grant human approval                                                    |
| Review C1–C7 #48 at `c8cadbb`            | Retain origin/identity/generation/freshness/unknown-outcome invariants; request exact wire/cursor/digest and file IO details before dependent coding |
| P0-M1 Canvas session feasibility         | Claimed #51; offline diagnostic implemented, live evidence pending                                                                                   |
| P0-M2 Outlook access                     | Next separately claimed slice; actual mailbox consent/admin access is not established                                                                |
| P0-M3 WhatsApp repair                    | Then diagnose existing 131031; legal/business changes and new sends need actual authorized access/recipient scope                                    |
| Continuous agent and real checked drafts | Later P2/P3 acceptance; do not infer from worker code or the successful two-call Meta diagnostic                                                     |

Newer owner evidence: P0-A2 succeeded on two bounded synthetic Meta calls in #50;
the original M2 failure cause and full planner/draft gates remain open. The old failure
reservation remains retained. No additional model-call allowance is inferred here.

## Proposed consumer feedback for #48

- C1/C2 design invariants are compatible with this probe. Actual background identity
  and session behavior remain unverified; do not promise a working CSU session yet.
- Before P1 consumers, specify exact begin/resume/commit/finish input and receipt/error
  shapes, scan lease lifetime, checkpoint generation, and old-batch replay behavior after
  lease renewal. MV3 suspension must not require silent unbounded rescans.
- Freeze canonical content normalization, field/segment identity and document manifest
  examples. A placeholder digest does not define interoperable fixtures. Preserve last
  successful checks separately from immutable versions and failed resource attempts.
- Raw Canvas `Link` and Outlook delta URLs cannot become arbitrary network targets.
  Connector validation must bind origin, endpoint, provider identity and allowed parameters.
- Confirm credential placement: pending-identity bearer allows only bind/revoke, not
  source reads/commits; extension-private storage never exposes it to a page/content script.
- C3–C7 direction fits existing consumers. Before implementation, provide concrete
  typed button/document/upload/download and health projections. Clarify streaming bytes
  versus descriptor, checksum acknowledgment and artifact version authorization at send.
- Notification limits, quiet hours, template approvals and distinct work/delivery consent
  remain gates; no agreement here asserts provider capability or approves live activation.

These are review requests, not changes to Akbar-owned contracts or blanket agreement to
an unspecified executable interface. Continue the independent access spike while those
details are agreed by the two owners.

## References and checks

- [Canvas courses](https://developerdocs.instructure.com/services/canvas/resources/courses)
- [Canvas pagination](https://developerdocs.instructure.com/services/canvas/basics/file.pagination)
- [Canvas discussions](https://developerdocs.instructure.com/services/canvas/resources/discussion_topics)
- [Chrome extension network requests](https://developer.chrome.com/docs/extensions/develop/concepts/network-requests)

Validation on the `9bbea97` baseline plus this isolated diagnostic:

- `node --test extension/canvas-feasibility/probe.test.mjs`: 12 passed. A malformed
  trailing pagination relation was reproduced failing, then corrected to reject the
  entire invalid header rather than silently claiming the last page.
- `uv run ruff check .` and `uv run ruff format --check .`: pass (98 Python files).
- `uv run pytest -q`: 391 passed, two existing dependency/test-key warnings. A new
  disposable local Postgres database was initialized for this run and stopped after it.
- `npm test` in `web/`: 114 passed; `npm run typecheck`: pass.
- Prettier for the new modules/documents and `git diff --check`: pass.
- Synthetic unpacked preparation and worker syntax check: pass; output is ignored.
  No extension was installed or live Canvas request made.

Initial uv/Vitest runs hit sandbox cache permissions; successful reruns used approved
execution outside the sandbox. The checked Python/web implementation matches exact
`9bbea97`; extension tests cover only the new diagnostic. No new production build or
live provider acceptance is claimed. Shared STATUS.md is held by Akbar's active claim;
the requested serialized status update and evidence are posted in coordination #4.
