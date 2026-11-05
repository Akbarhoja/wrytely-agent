# P1 two-course acceptance review — November 1, 2026

Owner Akbar/Codex; [claim6555307109](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6555307109).
Branch `codex/p1-two-course-acceptance`, base #133 `c107b68`.
Exact M #132 handoff `00dad2ac30301ce32ec29f32e91b5fd9f0e8366d`;
combined executable merge `015dde1`.

A reviewed the four-file test/document delta. No production change or M harness
rewrite was introduced; all four merged files match exact M blobs and the A shared/
runtime/contracts trees remain identical to c107b68. Node24 environment guard and
all existing scenarios remain required; no missing-file skip or bypass.

The two new actual-client cases use synthetic same-session Canvas responses through
the production collector, actual authenticated extraction HTTP adapter and real
Store. Each discovers two courses with all_active scope and no manual course IDs.
Committed database snapshots after initial/unchanged/deadline-change scans show
versions/events2→2→3 and observations2→4→6, with two stable source objects.
Assertions verify canonical metadata/due dates, exact source revisions/digests,
retained immutable payloads, changed-event object/observation linkage, resource and
scan state, partial HTML coverage and absence of legacy source promotion.

The lost-ack scenario commits a real batch before simulating a lost response. A
fresh client replays its captured body/key and recovers the receipt without another
provider-page read or extraction. The same durable journal is reused. Private HTML,
credentials, subject and checkpoint/lease fields are absent from public tick status.
A found no scoped blocking issue in this test increment.

All19 actual HTTP/client/Store scenarios pass on macOS in8.38s (one existing
Starlette warning), including both new scenarios and the17 previous cases.
All365 extension tests pass on Node24. Ruff lint/format183 files, exact blob/
implementation-preservation and diff checks pass. Full combined backend at015dde1: **1123 passed**, zero skips, two existing
warnings in61.80s. M's Windows966 result remains separate evidence.

This is synthetic integration proof. It does not establish an installed MV3 host,
browser suspension/restart recovery, live CSU collection, complete source kinds,
linked document reading, continuous operation or source/model activation. M retains
integration/browser/provider ownership; A continues document finish/publication in
separate reviewed increments. No live call, send, spend, install, retained migration,
worker activation, deployment or protected-main merge occurred. P0/P1 remain open.
