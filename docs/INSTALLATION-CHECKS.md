# Installation checks

Added after the owner's submission report. These checks do not change the submitted
snapshot or establish a working live agent. Use the exact candidate revision with
the root README and the channel/service setup documents; protected main may be older.

After installing locked Python dependencies, load only your own intended development
configuration explicitly:

```sh
uv run --env-file .env python -m runtime.preflight
```

The command prints configuration names, fixed remedies and booleans, never actual
credentials, origins, database addresses or provider responses. It checks presence
and local compatibility, including the selected model provider, Fireworks reasoning
options, model-budget configuration and Telegram credential/webhook-secret syntax.
It does not verify key validity, sign-in, model availability, grants, webhook
registration, selected courses, user consent, file quality or actual delivery.
`live_agent_verified` always remains false. No network or database connection is
made by this default check. Settings are loaded from the process environment; the
command does not search for other product configuration files.

Check only the service being configured using `--profile api`, `--profile supervisor`
or `--profile telegram`. The default `all` requires configuration for all three.
API checks include Canvas configuration for this academic-agent installation;
an unconfigured public shell can still render without these settings.

To separately inspect the configured database's migration ledger:

```sh
uv run --env-file .env python -m runtime.preflight --database-check
```

This explicitly opens a connection and a read-only transaction, with bounded
connection/query timeouts. It reads only migration versions and checksums, never
student/course data. It compares against the SQL files in this checkout and reports
pending migrations, changed checksums, a database newer than the checkout, or an
unreachable/access-denied database. It never applies migrations or repairs a ledger.
Do not reset a database to fix a mismatch; use the matching checkout and review
the migration history. Database error bodies are not printed.

Exit status is zero only when the selected configuration checks pass and, if
requested, the database ledger matches. Otherwise it is one. Invalid environment
values produce a fixed error rather than a validation dump containing secrets.

Passing preflight does not activate anything. The API, course supervisor, task
worker and messaging dispatcher are separate processes. An enabled cumulative
budget, account grant, explicit student controls and verified source evidence
remain required by the existing runtime. A provider outage remains a live blocker;
this command performs no inference, paid diagnostic, retry, send, enrollment or scan.

## A stopped supervisor

New runtime failures retain a fixed reason in the existing private supervision
status rather than relying only on process logs:

| Reason | Meaning |
| --- | --- |
| `model_provider_unavailable` | Model endpoint returned a server error. |
| `model_rate_limited` | Model endpoint returned HTTP 429. |
| `model_access_denied` | Model endpoint returned HTTP 401 or 403. |
| `model_not_found` | Provider returned the recognized model-not-found code. |
| `model_response_incomplete` | Provider reported an incomplete response. |
| `model_request_failed` | Other controlled provider failure. |
| `episode_failed_or_unknown` | Existing fallback for other failed/unknown episodes. |

These are fixed classifications, not raw provider text or a determination of exact
root cause. Historical failed rows are not rewritten. A blocked monitor remains
blocked: none of these reasons authorizes a retry or releases held model costs.
The original verified-owner/lease/state checks fence failure persistence, so a late
failure cannot overwrite a later pause or a previously committed hold. The existing
`hold_course_supervision(user, claim)` call remains compatible; trusted runtime can
add the keyword-only allowlisted `reason` argument. No schema migration is needed.

The transport-diagnostic candidate additionally recognizes `model_request_timed_out`
and `model_connection_failed`. These distinguish the SDK's timeout/connection error
classes while retaining unknown token usage/full cost holds. Neither starts a retry.
`AGENT_META_REQUEST_TIMEOUT_SECONDS` is an explicit5–120-second network timeout
setting, default30. Both model adapters apply it with SDK retries disabled. It does
not increase episode deadlines, leases, output limits or budgets. Increasing it
requires the operator to leave enough room inside the separately approved live
test/worker deadline. A delayed response must never be represented as known zero cost.
