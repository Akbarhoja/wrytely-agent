# Wrytely team agreement

Updated October 30, 2026. Active scope/order: [revision 7](docs/BUILD-PLAN.md).
Read [work orders](docs/WORK-ORDERS.md), [status](STATUS.md), [contracts](CONTRACTS.md)
and [coordination issue #4](https://github.com/Akbarhoja/wrytely-agent/issues/4) before work.

## Current P0 ownership — October 31, 2026

Akbar's latest instruction reassigns P0-M1 Canvas (#51) and P0-M2 Outlook (#53)
completion to Akbar/Codex under #104, superseding the prior return to Murtazo.
[Supervisor record](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6548991501)
and [Murtazo acknowledgment/handoff](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6549014013).
Murtazo has paused duplicate P0 Canvas/Outlook live runs. P0-M3 WhatsApp remains
Murtazo's under the earlier explicit exclusion. A retains P0-A1/A2/A3. P1+
implementation owners below are unchanged; this is a P0 access exception only.

[Current local access record](docs/P0-LOCAL-ACCESS-2026-10-31.md) and the
[earlier redacted handoff](docs/P0-ACCESS-2026-10-31.md) distinguish UI observations
from extension/API proof. Preserve Chrome-open instructions; coordinate disruptive
session/restart tests. No ownership change supplies login/admin consent, human GitHub
approval, new paid-call allowance or permission to publish private source evidence.

October31 product amendment: Outlook is optional; A's P0 Outlook access work and
new/duplicate CSU approval requests are paused. Preserve the existing app/probe and
M's optional P1 connector ownership. Canvas/core-agent work proceeds without email.
Do not call the blocked optional connector completed or advertise unverified live access.

## Exact ownership

Akbar is product supervisor and owns account/legal/budget/release decisions. Akbar's
engineering track is implemented with Codex. Murtazo (`murtazokhon-tech`) owns the
integration track. No task is jointly implemented in the same files by default.

| Surface                                                                | Implementation owner           | Boundary                                                                                                       |
| ---------------------------------------------------------------------- | ------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| runtime/                                                               | Akbar/Codex                    | Supervisor, task planner, tools, reasoning, draft/check/revision, rendering, grade math                        |
| shared/                                                                | Akbar/Codex                    | All stores, identity abstractions, model client, memory, schedules, credentials, budgets, action authorization |
| contracts/ including SQL                                               | Akbar/Codex                    | Typed shared interfaces and additive migrations; Murtazo agrees consumer changes before coding                 |
| extension/ (new)                                                       | Murtazo                        | Canvas session reads, pairing client, collection, resumable local checkpoints                                  |
| integrations/                                                          | Murtazo                        | Canvas/Outlook/WhatsApp network adapters, document extraction and file delivery IO                             |
| app/                                                                   | Murtazo                        | HTTP/OAuth/webhook assembly, private reads, process entrypoints, WhatsApp worker; no duplicate shared store    |
| web/                                                                   | Murtazo                        | Signup, connections, course coverage, controls and private results                                             |
| deploy/ and service configuration                                      | Murtazo                        | Continuous process deployment, health and operational recovery within approved scope                           |
| tests/                                                                 | Owner of tested implementation | A owns store/runtime/model/schema tests; M owns API/provider/extension/transport tests                         |
| tests/fixtures/ and cross-layer acceptance                             | Akbar coordinates              | Name one file editor per fixture/scenario; M reviews provider realism and supplies scoped data                 |
| .github/ CI and review policy                                          | Akbar/Codex                    | M reviews changes; extension/connector checks requested through a scoped claim                                 |
| BUILD-PLAN, WORK-ORDERS, IMPLEMENTATION-AUDIT, AGENTS, TEAM, CONTRACTS | Akbar/Codex                    | Shared plan/interface editor; M reviews and requests changes                                                   |
| STATUS and operational evidence                                        | Claim-specific editor          | One short row per completed/current step; serialize conflicting edits                                          |

A implements private artifact rendering and storage contracts; M implements concrete
file upload/download/delivery assembly. A implements connection/sync persistence;
M implements provider identity verification and ingestion assembly. M does not put
provider IO into shared/; A does not reimplement M's collector inside runtime/.
Each new PR lists exact files, including tests and any temporary shared-file claim.

## Base branch and consolidation

Current consolidation candidate: codex/p0-baseline (#45 work order), combining
a8cac79, reviewed #40/#42, revision7 from #44, and M's a383782 Canvas proposal.
It awaits combined CI and counterpart review; main is not yet consolidated.
Check fresh heads and review state in #4/STATUS before implementation.

P0-A1 consolidates accepted changes and requests independent review/CI before the
protected main merge. Until then, branch from the explicitly recorded candidate.
Never assume old codex/team-integration or minimal main contains the implementation.
After consolidation lands, use main as the normal base. Do not mass-merge constituent
PRs or delete branches automatically. Keep parked #24/A4 out until P4 review.

Use codex/<step>-<description> for Codex branches; Murtazo uses his own scoped branch.
One coherent slice per PR; split large work orders into sequential small PRs. Never
push to the other engineer's branch, force shared history, or bypass main protection.

## Streamlined coordination and review — supervisor decision November 1

Akbar removed routine agreement gates and unnecessary bureaucracy. This decision
supersedes earlier mandatory exact-file claims and consumer-agreement prerequisites,
including #157. Ownership and actual review/merge protections remain unchanged.

Check active work, then proceed within the assigned area. One brief feature-level
owner/branch entry is enough; no acknowledgment or new issue is required before
routine implementation. Do not duplicate active work or take another owner's files.
Only Akbar reassigns ownership. No journal/publication ownership transfer is implied.

A can finalize/version Store and runtime contracts and implement them without waiting
for M's explicit agreement. M can assemble the documented interface in owned HTTP/UI/
extension code without another agreement round. Communicate concrete decisions and
changes asynchronously. Raise actual incompatibilities promptly and stop only the
affected conflicting work. Do not invent a parallel store or journal to avoid a dependency.

Group related implementation, tests and evidence into complete features. Use focused
checks during development and combined checks before integration. The opposite engineer
reviews the feature. Assistant comments are not independent human approval; required
human review, configured CI and protected-main rules still apply.

Update STATUS/#4 at a meaningful handoff, blocker or completed feature, not each helper.
GitHub remains the shared record; project issues/PR communication is authorized.
No email/Discord messages or recurring monitor are implied. Preserve evidence,
privacy, permissions and live-budget limits; fewer process gates do not create live
activation or release authorization.

## Evidence and operation

Mark code/scripted/live evidence separately. Fixture success cannot pass Canvas,
Outlook, Meta or WhatsApp live gates. A reviewed PR is not a deployed service.
Three demo runs do not establish long-term reliability; use P5 recovery/soak evidence.

The current plan permits independent source and runtime work alongside provider
blockers, superseding the old M1-only implementation freeze. It does not expand
paid usage, authorize connector grants, activate continuous workers or change
existing Wrytely production. Keep existing development approvals within their
original bounds. Akbar decides new operating budgets and public releases.

## Next assignments

- Akbar/Codex: P0-A1 integration; P0-A2 Meta diagnosis; P0-A3 interfaces; reassigned P0-M1/M2 access completion (#104).
- Murtazo: P0-M3 WhatsApp recovery and existing P1 integration claims; P0-M1/M2 live runs paused.

These are queued responsibilities, not claims that anyone has started them. Old
B1/B2 documents remain historical implementation context; revision7 work orders
supersede their conflicting product/access instructions. M's Canvas proposal is
credited and retained; he can update his document in his next scoped task.
