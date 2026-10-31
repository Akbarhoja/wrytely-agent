# Private connection list HTTP handoff

Claim: [#80](https://github.com/Akbarhoja/wrytely-agent/issues/80), M integration track.
Base: A6237f1c, plus unchanged reviewed M lifecycle scaffold57ca6eae (#64),
reused asfd0886a. The list change does not alter A-owned stores or contracts.

`GET /v1/source-connections` uses the existing verified-session dependency and
`Store.list_source_connections(user.user_id, limit=20, cursor=None)`.

- Optional `limit`: ASCII decimal integer,1–20; default20.
- Optional `cursor`: opaque next cursor returned by the preceding response.
- Response: `connections` containing the existing six-field safe C1 projection,
  plus `next_cursor` or null. Disconnected connections remain visible.
- Unprovisioned accounts receive an empty list; no Canvas origin configuration
  is required to read existing connections.
- Unknown or repeated query fields and invalid limits produce generic422.
  Malformed, nonexistent and another account's cursors all produce generic404.
- A verified Wrytely session is required; a device ingestion bearer does not
  authenticate this route. All responses inherit `Cache-Control: no-store`.

## Evidence

New15 API cases first failed because the route was absent. After implementation,
all36 lifecycle/list API cases pass against disposable local Postgres. Full locked
Ruff check and format pass;621 backend tests pass in333.45 seconds (two preexisting
test-library warnings). Read-only code review found no scoped blocker. Tests use synthetic accounts
and records only. No live source data or credentials are part of this change.

## Remaining boundaries

This is backend assembly for future connection onboarding. The reviewed web proxy
is a separate #68 slice; this PR adds no web or installed extension UI. No scope,
discovery, sync, source-body retrieval or continuous collection endpoint is added.
The older-empty-enumeration defect reported on #71 remains an A-owned blocker for
catalog/academic ingestion acceptance. No deployment or live connector activation.
