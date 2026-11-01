# Bounded course metadata collector

M-owned continuation of [#100](https://github.com/Akbarhoja/wrytely-agent/issues/100), based on #106 `7c62bb36`. The existing #56 canonicalizer is reused unchanged. Ownership and exact paths were claimed in [coordination](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6549276088), with the prerequisite reuse recorded before cherry-pick.

## Behavior

`createPairingClient(...).collectCoursePage()` performs one explicit worker tick beneath the existing per-storage pairing lock. It returns only controlled state/action, generation/scope revision and counts/coverage. It never returns the provider course title, body, cursor, subject, bearer or lease. No timer, background host or automatic invocation is installed.

An idle tick begins a scan. Subsequent ticks recover a pending receipt, renew an expired/replaced writer lease, fetch and commit at most one bounded course page, close the courses resource, or finish only when all required resource rows are closed. A primary receipt is retried before automatic expiry renewal, since an accepted finish receipt can outlive its lease and the terminal scan cannot resume. An already pending resume remains reconciled by its original key. A retry that is definitively rejected for an expired/replaced lease may perform one bounded resume in the same tick; there is no recovery loop. Recovery ticks do not refetch provider data. A finished journal remains finished until the caller explicitly starts another scan. Lost responses retain exact pending keys and captured payloads; resumed uploads change only their writer lease. The existing receipt, checkpoint, scope, profile and expiration fences remain authoritative.

The private operation set is wrapped once for every public discovery method. Only collector orchestration calls the private operations while already under that same lock; no second store, reentrant lock bypass or new durable schema exists. This is still one worker realm and one storage object, not cross-realm coordination. A future installed host must enforce a single writer.

## Mapping and partial evidence

Only provider ID, name, course code, time zone and current-user enrollment states become C2 course metadata. A provider ID must be a positive interoperable number or canonical decimal string of at most20 digits; duplicate/invalid IDs fail the entire page. Body/HTML/grade/person fields are excluded. Provider modification time stays unknown (`null`), not the collection time.

Supported strings normalize CR/LF and NFC before the500-scalar limit. Missing, empty, nonportable or oversized fields produce explicit missing-field names and partial metadata; nothing is clipped. Conflicting/unknown enrollment states stay unknown rather than assuming active from the request filter. The inherited canonicalizer validates the exact portable payload.

Any partial course item sets the existing conservative scan-incomplete flag, preserving early-page gaps across a later complete page. Closing courses is conservative if that flag is set; a manually recorded incomplete resource elsewhere in the scan can therefore also keep the courses close partial. This avoids a false complete scan without a journal format fork; a separate per-resource historical quality ledger would require a later compatibility design.

Selected academic resources remain open. `awaiting_resources` means course enumeration has been handled but assignments, syllabus or other resource collectors are still needed. No unsupported placeholder is inserted merely to finish a scan. A metadata-only scan can finish; that is not academic collection or a working semester agent.

## Verification and limits

New mapper and collector integration cases were run RED before their implementations. A fresh reviewer independently passed79 focused cases, then reproduced a missing terminal-receipt/expiry combination. The added regression failed before receipt-first recovery and passed afterward; final Node verification passed233 cases with no skips. That final fix was verified by the implementer, not a second independent run. Exact remaining verification is recorded in the PR. The existing eight HTTP/Store scenarios test the underlying journal/client boundary, not the new collector orchestration; a collector-driven real HTTP/Store scenario needs the next agreed cross-layer increment.

The full unchanged backend suite passed673 tests on disposable local PostgreSQL in397.15seconds, with two existing warnings. Web regression passed114 tests; TypeScript, required Ruff check/format, changed-file Prettier and diff checks passed. After the final JavaScript fix, all8 existing actual client/API/Store scenarios passed again in13.27seconds. Remote CI remains separate.

The reader retains #106 bounds: one course data request per tick, exact configured HTTPS origin/course endpoint, constrained pagination, strict UTF-8/final response URL, at most50 rows,1MiB body and15-second Fetch signal. The existing journal caps100 pages,5000 items,1MiB envelopes and8MiB local state/finish replies. Limits are controlled failures, not silent clipping. No source response or private diagnostic is committed.

P0 Canvas/Outlook access checks stay with Akbar. Real Canvas compatibility, installed extension suspension/restart, host/startup/alarms, academic resources and live acceptance are still unfinished. No new account read, grant, token, send, provider spend, deployment or main merge occurs in this increment. Chrome remains open and the deleted automation is not recreated.

Akbar-owned CI must include the new collector tests and inherited digest tests on a combined base containing those files, in addition to the existing Node suites. Foundation explicit Node24 setup remains a separate requested workflow prerequisite. No CI or shared STATUS file is edited in this branch.
