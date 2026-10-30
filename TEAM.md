# Wrytely team agreement

Updated October 30, 2026. Active scope/order: [revision 7](docs/BUILD-PLAN.md).
Read [work orders](docs/WORK-ORDERS.md), [status](STATUS.md), [contracts](CONTRACTS.md)
and [coordination issue #4](https://github.com/Akbarhoja/wrytely-agent/issues/4) before work.

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

Last recorded integration base: codex/m2-integration-review at a8cac79. #40/#42 are
separate reviewed fixes, not integrated there; #44 carries this plan. M's #28 latest
proposal is a383782. Check fresh heads in #4/STATUS before implementation.

P0-A1 consolidates accepted changes and requests independent review/CI before the
protected main merge. Until then, branch from the explicitly recorded candidate.
Never assume old codex/team-integration or minimal main contains the implementation.
After consolidation lands, use main as the normal base. Do not mass-merge constituent
PRs or delete branches automatically. Keep parked #24/A4 out until P4 review.

Use codex/<step>-<description> for Codex branches; Murtazo uses his own scoped branch.
One coherent slice per PR; split large work orders into sequential small PRs. Never
push to the other engineer's branch, force shared history, or bypass main protection.

## Mandatory coordination and review

Before implementation, claim the work order in an issue with owner, branch/base,
files, dependency contracts and acceptance. Read existing claims first. Nobody
inherits work because the other engineer is absent, blocked or slow. Only Akbar
can reassign it; record that decision before crossing ownership.

An unresolved shared interface blocks dependent edits, not unrelated owned work.
A proposes payloads, identity/error/replay/migration semantics; M agrees the consumer
boundary in #4/PR before dependent implementation. CONTRACTS.md then records the
agreed version. A plan's proposed operation is not an existing API.

The opposite engineer reviews implementation and evidence. Codex and Murtazo's
assistant may both post through Akbarhoja: those comments do not create independent
human GitHub approval. Required human approval and configured CI remain mandatory.
CODEOWNERS routes review; it is not permission to edit another person's files.

At session end update STATUS and #4 with completed work, exact tested commit,
next eligible step, blockers and interface changes. GitHub is the shared record,
not separate chats. Akbar has authorized project communication in issues/PRs;
that authorization does not extend to email/Discord or unrelated channels.
Do not create a duplicate scheduled monitor. Check GitHub during active work sessions.

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

- Akbar/Codex: P0-A1 integration; P0-A2 Meta diagnosis; P0-A3 interfaces.
- Murtazo: P0-M1 extension access, P0-M2 Outlook access, P0-M3 WhatsApp recovery.

These are queued responsibilities, not claims that anyone has started them. Old
B1/B2 documents remain historical implementation context; revision7 work orders
supersede their conflicting product/access instructions. M's Canvas proposal is
credited and retained; he can update his document in his next scoped task.
