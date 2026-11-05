# M post-submission handoff

Claim: [coordination6647198922](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6647198922).
Branch `codex/post-submission-app` from A readiness9538c51. A owns final integration,
runtime/shared/contracts/provider diagnostics and remaining P1. M owns this narrow
app/web/setup follow-up. No submitted candidate is rewritten or redeployed.

## Delivered changes

- Telegram dispatch reports `unknown` when `finish_telegram_delivery` returns false.
  A provider result cannot be advertised as successfully persisted after a lost
  attempt fence. Regression expires an in-flight lease, lets another Store claimant
  reconcile it to unknown, then returns the late scripted provider result. Accepted,
  deferred and failed late receipts all report unknown; restart performs no resend.
  Lease expiry alone does not necessarily invalidate a receipt; the test exercises
  the actual lost fence. No Store or adapter behavior is changed.
- Private supervision uses fixed human-readable labels for A's published failure
  reasons. Unknown values get a generic label, never raw provider text. No retry
  control, budget refill, auto-resume or provider change is added.
- [Fresh-clone setup](../deploy/LOCAL-SETUP.md) lists configuration names only,
  separate API/web/extension/Telegram steps and local preflight scope.
- [Three-minute evidence script](M-DEMO-SCRIPT.md) distinguishes live source/link
  evidence, scripted draft/revision/download/Word fixtures and unproven live preparation.

## Remaining integration gaps

| Capability              | Implemented seam                                                                                                                         | What is still needed                                                                                                                                                                  |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ordinary Telegram reply | Private linked text → original task queue → existing runtime completion → fenced provider dispatch                                       | Working authorized model inference, active bounded runtime/dispatch operation and actual recipient acceptance evidence. The stopped approved run sent nothing.                        |
| Proactive preparation   | Explicit supervision + inspected/pinned sources → saved limited checklist → separately consented Telegram intent → one-use authorization | A real successful autonomous prepare decision and actual recipient receipt under a newly approved bounded test. Current partial sources/policy/physical-work limits remain.           |
| Accept                  | Existing web offer decision and WhatsApp signed command path                                                                             | Telegram v1 ignores `/accept`; A must publish trusted command/context/replay authority before M wires a new channel consumer. Do not reuse phone-number authority.                    |
| Checked file            | Existing private authenticated file GET and WhatsApp checked immutable file transport                                                    | Telegram `/file` is absent. TXT is not checked coursework. Needs A-owned request/owner/artifact/current-source authorization and provider document receipt boundary, then M assembly. |
| Revision                | Existing session/WhatsApp revision responsibility and immutable-version pipeline                                                         | Telegram `/revise` absent; requires version-bound trusted feedback/replay contract before app wiring.                                                                                 |
| Fresh source coverage   | Existing paired scoped extension/journal/extractors                                                                                      | Approved browser/session refresh and actual remaining readable sources; cloud cannot see unsynced updates. A owns remaining P1.                                                       |
| Reliable operation      | Persisted claims/one-use fences, unknown retention, bounded service controls                                                             | Measured live duration/restarts, useful model behavior and real channel evidence; no 24/7 proof.                                                                                      |

Do not silently replace any missing row with scripted acceptance. New shared channel
contracts belong to A; M can consume them after publication rather than inventing a
parallel Store, collector, queue or runtime.

## Current live facts and provider handoff

A reported owner submission complete; exact submission receipt/revision was not
independently observed by M. Executable992fe0d passed full CI and was deployed for
an approved bounded check: API/029–030/webhook and real owner Telegram pairing were
verified. One reply model call stopped before outbound; zero sends/live preparations.
Cleanup restored API-only operation, disabled test budget/permissions and stopped
workers. Two later explicitly authorized synthetic provider cases (minimal chat and
typed tools) both returned HTTP503/invalid_request_error. This does not distinguish
the tool shape or establish the exact provider root cause. Correlation identifiers
remain private; M has no additional safe provider metadata or new probe result.

A's latest recorded cumulative held liability is2.08984575/3, including every prior
unknown/external hold. Never reset/release it or infer zero usage. No provider swap,
new calls, send, migration, deployment, credential access or worker activation is
performed by this follow-up. Current provider recovery/status is A's task; a stale
incident report is not proof of current availability.

Validation belongs to the exact final PR/checkpoint. Focused regression, required
Ruff/format/full disposable-Postgres checks and web tests/types/build must be reported
as actually passed/failed/pending; prior integration green is not transferred to
these post-submission executable changes. Windows PDF failures remain separate
from Linux CI and must not be hidden.
