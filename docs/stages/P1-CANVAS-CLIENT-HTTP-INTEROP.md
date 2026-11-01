# Actual Canvas client-to-HTTP acceptance

M single-editor agreement [#96/6548725324](https://github.com/Akbarhoja/wrytely-agent/pull/96#issuecomment-6548725324), [claim #102](https://github.com/Akbarhoja/wrytely-agent/issues/102). Branch `codex/canvas-client-http-interop` starts from reviewed A CI-only #101 `fec20562cd2becc533547f7fd329bf21e9db5a62`, which contains exact M journal #96 `95c38cb`. The newly available cross-layer agreement took priority before any #100 collector edits; that collector remains planned.

## Boundary exercised

Pytest starts the actual `create_app` routes with the existing synthetic SessionVerifier/Store fixtures and a fresh disposable Postgres database. The owned socket binds only127.0.0.1 port0 and Uvicorn access logging is off. An owned child Node process invokes the actual pairing/discovery client, including protected-record intent persistence, receipt validation, restart recovery and fencing.

The fixture-only fetch adapter maps a configured HTTPS test origin to that loopback HTTP service and presents its response at the client-facing test URL. This verifies actual request/response serialization, routing, session-versus-ingestion authority, receipts and database state. It does not verify production TLS/origin networking, real Clerk JWTs, browser cookie authentication or MV3 service-worker behavior. Product validation and auth configuration have no bypass flag or edit.

Node config travels over stdin; generated test pairing codes/bearers/leases remain in memory, not args/env/files/logs. Child environment is an explicit OS-only allowlist excluding provider settings, NODE_OPTIONS and parent canaries. The tested app Settings instance is constructed without envfile/provider environment inheritance. A refusing synthetic Canvas reader serves only a fixed profile endpoint; no live provider URL is contacted. Child output is a fixed pass/scenario or controlled phase/code object; exception text/stacks and credentials are not printed. Missing Node fails rather than skipping. Socket/thread/child cleanup touches only owned test resources.

## Actual scenarios

| Scenario                     | Evidence                                                                                                                 |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Loss before dispatch         | Pending capture survives; restart sends the original key/body once                                                       |
| Loss after server commit     | Replayed receipt does not create a second batch/catalog application                                                      |
| Replaced lease               | Another writer's actual resume fences old lease; own resume/retry keeps the captured page                                |
| Expired lease                | Fixture-only clock-state injection triggers real409; resume permits the original capture                                 |
| Scoped partial finish        | Discover, select an observed course, change generation, then preserve unsupported academic resource as aggregate partial |
| Scope change during dispatch | Existing Store scope operation aborts/fences old scan; stale batch creates no catalog/receipt                            |
| Revoke during dispatch       | Existing Store revoke causes401 and local credential/journal cleanup                                                     |
| Cross-account denial         | Bob session/ingestion cannot scope, begin or resume Alice's connection/scan                                              |

Race injection exists only in the fixture middleware/transport; actual route authorization and Store transactions decide the outcomes. Direct database assertions check receipt/catalog counts, a single distinct provider course and no academic source_versions. The scoped case correctly retains two catalog generations rather than mistaking history for duplicate application.

## Verification and limits

Initial RED: the lost-after case failed because the Node harness was absent. First implemented run passed seven scenarios and exposed an incorrect test expectation of one catalog row after scope generation change; that fixture assertion was corrected, no product code changed. Focused final eight scenarios passed in12.40 seconds on actual loopback API/disposable Postgres. Full required backend673 passed/two existing warnings/385.79 seconds, including all eight bridge cases; unchanged Node119 passed/no skips, web114 passed/32.69 seconds, TypeScript/Ruff check/format/changed-file Prettier/diff passed. Read-only harness review found no blocking issue and did not rerun tests. Remote CI remains separate.

These results close the simulator-to-API contract gap for the named scenarios. They remain synthetic identities/storage/provider profiles, not real Chrome suspension, browser persistence/quota, live Canvas content/session coverage, authorization grants or semester-agent acceptance. New A #98 normalized reader bounds are reviewed separately and are not silently mixed into this metadata test base.

The inherited #101 unconditional Node24 root job remains intact. Since pytest now invokes Node too, A was asked to add explicit Node24 setup to the foundation job; no M workflow edit or missing-file skip is introduced. STATUS remains serialized through A. No provider/model spend, sends, source activation, retained migration, deployment/main merge or automation restart. Chrome remains open.

Next: counterpart review and any required CI prerequisite, then the planned course collector. Its pagination and field mapping will follow the [Canvas course API](https://canvas.instructure.com/doc/api/courses.html) and [opaque Link pagination](https://canvas.instructure.com/doc/api/file.pagination.html); it has not been implemented or live-tested by this acceptance slice.
