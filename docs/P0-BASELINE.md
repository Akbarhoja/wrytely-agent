# P0-A1 combined baseline

Work item [#45](https://github.com/Akbarhoja/wrytely-agent/issues/45).
Branch: codex/p0-baseline. This combines reviewed candidates; it is not a release.

## Constituents

- a8cac79: previous M2 integration, including Murtazo's a344642 implementation.
- bddd7e8: revision7 plan, precise work orders, audit and preserved historical evidence.
- ddd5ab1 / #40: controlled Meta failure metadata and known unsuccessful usage.
- 224bc96 / #42 (executable a7db006): pause lease revocation and separate failure allowance.
- a383782 / #28: Murtazo's Canvas proposal and B2 scope note, preserved verbatim.

All are ancestors of the combined candidate. No parked A4 or migration008 is included.
M's application code is unchanged from the previous integration. Revision7 supersedes
the proposal's initial cloud-OAuth assumption; its coverage/freshness research remains
useful. No plan proposal has been made an executable contract by this integration.

Conflicts resolved: keep the concise current STATUS, preserve both contract sections,
and retain all worker tests from both fixes. Historical status evidence remains linked
in the archive and the original commits. Added one interaction regression: a provider
failure after Pause cannot commit a late failure event or exhaust the resumed task;
the task finishes through a fresh monotonic claim. This combines both behavioral fixes.

## Validation

Local Python lint/format pass;31 non-database adapter/format/planner tests pass.
Full backend attempt was blocked by macOS sandbox access to pgserver's cache lock;
not a test pass or application failure. Isolated Postgres CI is required. Frontend
checks and exact candidate CI results are recorded below when available.

Counterpart review and independent human protected-main approval remain pending.
No retained database migration, deployment, live model request, WhatsApp send or
continuous worker activation. Existing budget/permissions remain effective.
