# P1 elapsed-time correctness — November 1, 2026

Owner Akbar/Codex; branch `codex/p1-freshness-utc`, base #129 `d70c9a8`.
Claims [6554869747](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6554869747)
and [6554884147](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6554884147).
Executable commits `f5a2f34` (freshness) and `c29aba6` (Canvas observation ordering).

## Trigger and scope

Murtazo's #130 independently reproduced the source-version ambiguity during the
November1 Denver repeated hour. That original issue was already fixed by A's
`ec6f0c9`, included in #128 and #129. A supplied the exact commit to unblock M's
#127 full run, without editing his branch or suppressing the failure.

The requested follow-up audit found two additional concrete defects in A-owned code:

- Freshness added TTL durations to local wall time and compared/min/maxed datetime
  objects without normalizing instants. Across autumn/spring clock changes, a nominal
  1/6/24-hour duration could expire an hour early or late. The repeated hour could
  evade the five-minute future check and choose the newer of observation/receipt
  as the supposedly older source time. The urgent30-minute bound was affected too.
- Canvas evidence staging directly compared database datetime values with observed
  timestamps. Equal physical instants in different zones during either DST fold
  could evade `ambiguous_observation_time`; same-zone ordering could reverse history.

Both reproduce with fixed2025 Denver instants, independent of machine clock/timezone.
No production timezone setting or external provider data is used as a workaround.

## Change

Freshness normalizes the policy clock and evidence timestamps to UTC before elapsed
addition, comparison and min/max selection. Existing24-hour legacy and24/6/1-hour
Canvas bounds, urgent30-minute limit, five-minute future tolerance and all identity/
generation/scope/coverage fences remain. Returned checked_at/expires_at use aware UTC
rather than retaining the input display zone; they represent the same instants.

Canvas's existing staging transaction normalizes current/prior observation instants
before ambiguity/history comparison. Equal-instant changed content rejects and rolls
back; older evidence never replaces the current pointer or emits a new change event.
The existing store, receipts, schema and collection path are reused.

## Verification

The new freshness cases first reproduced nine failures, then all45 policy cases
passed after the UTC change. Thirteen new cases cover both autumn folds, spring
forward, all1/6/24-hour TTLs, mixed timestamp representations, exact boundary plus
one microsecond, future observations, reversed observation/receipt order and urgent
half-hour expiry. That intermediate full backend passed1075 tests in52.03s.

Two new Canvas transactional cases first failed for absent same-instant conflict,
then passed after the fix. Each uses a real disposable Store in America/Denver with
historical synthetic observation timestamps, invoking the staging helper to isolate
ordering from the separate current scan-window gate. It asserts atomic rollback
across objects/versions/payloads/observations/events, and correct distinct-instant
history/promotion/event behavior when wall-clock order reverses. No public scan-time
window was weakened or bypassed in application code.

Focused existing evidence + academic memory + freshness:119 passed before strengthening
those same two Canvas cases with distinct-instant ordering; final two-case rerun also
passed. Final full backend at c29aba6: **1077 passed**, zero skips, two existing warnings
in52.92s against disposable Postgres.
Ruff lint/format177 files and diff checks pass. Schema/HTTP/extension/transport/web
code and existing fixtures are unchanged. No full system or live access claim follows.

## Remaining work

M retains #127 actual two-course collector/extraction/API/Store acceptance and all
integration source edits. He should review/reuse the original ec6f0c9 source fix and
review this follow-up separately. #124/#128/#129 counterpart reviews remain independent.
Document staged transactions/publication remain next A work after this correctness
slice. P0/P1 are not complete and the24/7 supervisor is not claimed built.

No live source/provider/model call, message, credential grant, retained migration,
installed extension change, continuous worker, deployment or protected-main merge.
