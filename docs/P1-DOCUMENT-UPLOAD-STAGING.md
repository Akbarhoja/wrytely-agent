# P1 private document staging — November 1, 2026

Owner Akbar/Codex; branch `codex/p1-document-upload-staging`, base #131 `4b52c6a`.
Claim [6554981907](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6554981907).
Executable implementation `a0b0ac9`. Agreed design: #118 exact `7f4f09f`.

## Implemented

Internal Store methods begin_document_upload and put_document_parts reuse the
existing actor/agent/connection/scan authorization and transaction locks. Exact
schema2+operation bodies forbid publication's batch_type and all unknown fields.
UUIDs, generation, replay keys, request size and configured extractors are checked.
A factored header validator reuses existing academic-field canonicalization and
root/section invariants; all original ten root vectors remain byte compatible.

Migration016 adds unpublished headers, immutable text parts and original operation
receipts. Composite foreign keys bind uploads to the same owned connection and
scan/generation. Begin fixes expiry at min(scan expiry,begin time+30minutes).
No request, receipt or resumed lease extends it. Parts arrive in batches of1–50
unique slots and must match the declared normalized text, offsets and SHA256.
Identical slot text is idempotent; changed text conflicts even under a new key.

The existing connection lock serializes writers with control changes and quota
checks. At most4 unexpired uploads are allowed. Retained staged text, including
expired uploads awaiting separately reviewed cleanup, is capped at8MiB per
connection. This is deliberately conservative: expiry alone does not erase bytes
or silently release storage quota. Requests are bounded to1MiB UTF8 JSON.

Receipt replay is scoped to scan/operation/request key and the original request
hash, excluding only lease_token. The current credential/generation/subject/scope,
active scan/current lease, unexpired upload and open resource are checked before
recovery. Changed payload conflicts; responses preserve the original cumulative
received_slots, never a current mutable progress query. New receipt commits recheck
current authority and expiry after parts are staged, so late failures roll back.
No text, credential or provider subject is returned in receipts.

## Verification

All44 focused disposable-Postgres cases pass. They cover restart/replay, changed
keys/slots, strict shapes/types/size/manifest/part rejection, out-of-order slots,
cumulative original receipts, cross-account/scan/connection identity denial,
revocation/scope/generation/credential/scan/upload/lease expiry, lease rotation,
terminal resource replay rejection, begin/put final-lease rollback and concurrency.
Six simultaneous begin calls commit exactly four uploads. Ten legitimately staged
200000-emoji documents accumulate8000000 retained UTF8 bytes; the next body cannot
cross8MiB, expired bodies remain counted and no partial insert/receipt is committed.
Scan-bounded expiry and unchanged expiry after put are checked.

First staging run exposed a test-fixture assumption that generation was1; the
existing discovery fixture advances it, so tests now use the actual authorized
context. No product authorization was relaxed. Header factoring briefly exposed
a missing local page-count variable; unchanged root-vector tests caught it and
all98 root/53 section tests pass after correction. An intermediate full run with
40 upload cases passed1117 backend tests in64.69s (two existing warnings).
Final committed full backend at a0b0ac9: **1121 passed**, zero skips, two existing
warnings in60.42s. Ruff check/format, unchanged vector tests and diff checks pass.

After that run, M reported the existing #129 fixture test depended on Windows
default encoding. A fixed only the fixture read to explicit UTF8 on original #129
commit82697f5, then merged that test-only change as5daffed. All151 root/section
cases pass after merge; runtime files and fixture bytes remain unchanged from the
1121-pass revision. Native-default Windows rerun is requested, not claimed.
Final Ruff lint/format181 files and relative documentation links pass.

## Remaining work and gates

Begin/put are private durable staging, not a ready document or public endpoint.
Finish must reassemble all parts, verify whole-text normalization/root identity and
materialize a ready root. Publication must atomically create observations/events/
checks/checkpoints and receipts under current authority; no observation or legacy
empty version is manufactured here. Whole-text NFC across section boundaries is
still a finish-time check even though individual parts are validated now.

Finish, publication and safe bounded cleanup are subsequent A slices. M retains
HTTP/extractor/extension consumption and active #127 two-course harness. No M file
is edited or parallel collector introduced. Counterpart review remains required;
#124/#128/#129/#131 reviews are separate. P0/P1 are not declared complete.

Only disposable tests received016. No retained database migration, live student
content/provider/model call, message, spend, account grant, install, continuous
worker, deployment or protected-main merge occurred. Outlook remains optional/
paused; WhatsApp delivered-reply proof remains M-owned.
