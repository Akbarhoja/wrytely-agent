# P1 bounded document staging cleanup — November 1, 2026

Owner Akbar/Codex; [claim6555541995](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6555541995).
Branch codex/p1-document-cleanup, base #137afc42c9.

## Implemented behavior

cleanup_canvas_document_staging is an explicit trusted operator method. No route,
timer, job, worker or live invocation is installed. It selects at most100 expired
uploads and100 old orphan protocol roots; callers can lower the1–100 strict bound.
Busy agents/uploads/roots are skipped, never awaited. Agent-before-root lock order
matches existing writers and prevents cleanup/publication lock-order deadlocks.

Expired upload parts and headers are scrubbed, ready pointers cleared and a cleaned
upload tombstone retained. Original receipts/IDs/digests/expiry remain byte-for-byte;
receipt recovery still rejects expired uploads, so old ready receipts cannot revive
content. Staged-byte quota is reclaimed by deleting those duplicate staging bodies,
without deleting any published root or observation. Header text, including rubric/
title metadata, does not survive in the tombstone. Migration019 adds cleaned_at and
reference/age indexes only.

Orphan candidates require a protocol payload, server root age >=24h, no binding,
no matching observation payload for that owned object and no retained upload
pointer. ALL historical observations/bindings protect roots, including A→B→A.
Expired uploads not processed in this pass still protect their pointer. Legacy
internal roots without protocol payload are outside scope. After agent/root locks,
all predicates are rechecked before deleting original sections/root in the same
transaction. FKs prevent a committed dangling binding or upload. Shell objects,
receipts, observations, event history and source/readiness state are retained.

## Verification

Twenty-one focused cases cover content-free tombstones with original receipts,
expiry fail-closed replay, idempotent repeated passes, root age boundaries, live
ready pointers, complete published/reverted historical retention/readability,
observation protection without a binding, global per-class pass limits, quota
reclamation, busy agent/root nonblocking behavior, concurrent passes without double
counts, interruption rollback, legacy internal roots and strict limit validation.
Fixed synthetic records and disposable Postgres are used throughout. The default
100 limit and smaller limits share the same bounded candidate queries.

At executable8f8d1e3 the full combined backend passed1184 tests, zero skips, two
existing warnings in69.82s. Ruff lint/format191files and diff checks pass. No live student data or external providers are
used. Previous #137 publication CI41288720692 and41288717315 completed SUCCESS on
exactafc42c9; that CI is separate from this increment's local evidence.

## Remaining gates

Counterpart review is required for cleanup and the preceding staging/finish/
publication increments. M retains the actual HTTP/extractor/extension consumer
assembly and inactive-by-default host foundation. Shared support is not live Canvas
collection or a completed24/7 academic agent. Installed/session recovery, full source
coverage and runtime/supervision acceptance remain separate work orders.

Only disposable tests received019. No retained migration, cleanup invocation on
retained data, live source/model/send/spend/grant/install/worker/deploy/main merge.
A backlog stays bounded and quotas remain enforced; this is not a published-content
retention/deletion policy. P0/P1 remain open and Outlook stays optional/paused.
