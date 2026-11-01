# Canvas scope and discovery HTTP handoff

M-owned [claim #93](https://github.com/Akbarhoja/wrytely-agent/issues/93), branch `codex/canvas-discovery-http`, base own #92 `c1075bda86c5ebf1b7807d6a5a352a8216e9b7a6` on accepted A #84. This closes the HTTP gap to existing Store transactions; no parallel store, sync receipt, checkpoint, lease or ownership mechanism is introduced.

## Routes and authorization

All routes are POST under `/v1/source-connections/canvas`. Stable operation paths keep provider subjects, bearer/lease values, scan identifiers and opaque cursors out of URLs.

| Suffix                | Authority                                       | Strict request fields                                                                            | Streamed body cap |
| --------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------ | ----------------- |
| `/scope`              | Verified session; Store checks connection owner | connection_id, generation, mode, course_ids, resource_kinds                                      | 64KiB             |
| `/discovery/begin`    | Current ingestion bearer                        | connection_id, generation, subject, scope_revision, begin_key                                    | 16KiB             |
| `/discovery/resume`   | Current ingestion bearer                        | scan_id, generation, resume_key                                                                  | 16KiB             |
| `/discovery/batch`    | Current ingestion bearer                        | scan_id, generation, lease_token, batch_key, expected_checkpoint, envelope                       | 2MiB              |
| `/discovery/resource` | Current ingestion bearer                        | scan_id, generation, lease_token, resource_key, finish_key, expected_checkpoint, outcome, reason | 64KiB             |
| `/discovery/finish`   | Current ingestion bearer                        | scan_id, generation, lease_token, finish_key                                                     | 16KiB             |

No posted user ID or actor is accepted. Unknown fields/query parameters, invalid UUIDs/replay keys and non-strict integers produce generic422. Current credential/origin/state/account checks remain inside the Store; invalid ingestion authority is generic401, missing/nonowned session-scoped connection is private404.409 exposes only an allowlisted conflict code; unknown future codes become `state_changed`. Input/exception text is not reflected. Existing database-error redaction and no-store responses are reused.

The existing CanvasRoute wrapper now has a per-class body limit; its16KiB default and lifecycle behavior are unchanged. Scope needs64KiB for all1000 legal20-digit course IDs. Resource receipts need64KiB for a4000-character JSON-escaped checkpoint. Discovery batch alone permits a2MiB HTTP wrapper while the unchanged Store retains its1MiB serialized-envelope limit. Raw ASGI tests verify overflow stops reading even with a lying Content-Length. Oversize envelopes reject before catalog/checkpoint changes.

## Transactions and coverage

The typed existing DiscoveryBatch accepts course metadata only. Academic body uploads cannot enter the shared academic commit branch through this route. Resource receipts can complete courses after an actually observed terminal page; selected academic resources can only be closed honestly as partial/restricted/unsupported here. Academic completion and source/body ingestion remain later increments. Aggregate finish requires every resource terminal and stays partial if a selected academic resource is unfinished/unsupported.

Existing Store fencing supplies current credential, bound subject, generation/scope revision, one owning writer lease, expected checkpoint and receipt idempotency. Begin/resume preserve their original replay responses; replacing a lease rejects new writes by the old writer. Exact committed batches replay without moving observations/checkpoints, while changed payload/key reuse conflicts. Scope/revoke/expiry fences remain authoritative. API handlers never fetch a cursor/provider URL or initiate a source/model/send action.

## Evidence and limits

Initial19 API tests failed on absent routes, then passed against real disposable Store transactions. Expanded lifecycle/context/discovery coverage passed64 cases, including valid full1000-course selection, a maximal encoded checkpoint, two-account scan isolation, stale checkpoint/expired/replaced lease, replay conflict, scope-change fencing, partial aggregate, streamed cap and atomic1MiB rejection. The two valid maximum-input cases first reproduced413 under the inadequate16KiB limit before their scoped cap correction. Final checks add overflow rejection for both64KiB routes, disabled-service behavior and unknown-conflict redaction; final full results are recorded in the PR handoff after execution.

Final full backend on fresh disposable Postgres:665 passed, two existing test-library warnings,368.88 seconds; includes all33 new discovery cases. Existing extension Node suites80 passed/no skips; full web114 passed/31.07 seconds; TypeScript, locked Ruff check/format, changed-doc Prettier and diff checks passed. Read-only review found no material finding and independently checked strict boolean-generation rejection; it did not rerun the database suite or assess live integration. Remote CI and A counterpart acceptance remain separate.

All records/users/origins/content are synthetic; no real Canvas data or account was accessed. This is HTTP-to-Store integration evidence, not installed extension-to-server, automatic collection, live pagination, current-browser identity validation, provider authorization or semester-agent completion. There is no new extension discovery client, durable collector checkpoint or collection loop in this slice.

No shared/contracts/runtime/STATUS/CI/dependency edit, academic source activation, #86 reader consumer, live grant/send/spend, retained migration, deployment or protected-main merge is included. STATUS remains serialized by A; counterpart review is required. The existing80 Node tests cover the unchanged pairing/context reader, not a discovery client. Chrome remains untouched; automation stays deleted.

Next M step: consume these reviewed operations from the paired extension and persist its durable scan/batch checkpoint before building the resumable course collector. A-owned reader fixes and P0 live access/account decisions remain separate gates.
