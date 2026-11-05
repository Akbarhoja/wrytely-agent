# One-course service preparation

This describes code entrypoints. It does not authorize deployment, retained
migrations, new allowances, model calls or WhatsApp sends.

Use the [assembly acceptance handoff](ONE-COURSE-ACCEPTANCE.md) for check order,
evidence fields and cleanup criteria before a separately approved live run.

Keep these separate processes in the approved development environment:

- Existing authenticated API: `uv run uvicorn app.main:app --host 127.0.0.1`.
- Course checks: `uv run python -m app.course_service --once` for one bounded
  scheduling pass. Continuous mode requires explicit `--run` instead of `--once`.
- Existing academic draft/revision execution: `uv run python -m runtime.worker --once`.
- Existing authorized outbox dispatch: `uv run python -m app.whatsapp_worker --once`.

Every command that can invoke a provider needs its own applicable bounded activation.
Never launch them just because this document exists. No process migrates on startup.
The course service requires configured database/model key, verified prices and a
budget key; it uses `BudgetedMetaRouter`, never an unguarded model. Global/student
budget setup remains an operator-only action under separate approval. Preserve
historical spent and unknown liabilities and the existing total development cap.

The shared budgeted factory validates credentials for its selected provider. The
service does not require an unrelated Meta credential before consulting that
factory. Missing or invalid provider configuration stops startup before scheduling
and returns a generic configuration error. This does not select or activate an
alternative provider; only a published, explicitly configured shared factory can
do that. No automatic provider fallback is introduced.

Use `--limit 1` for a one-course scheduling pass. Poll cadence is an opportunity to
check persisted due work; the model chooses intervention and next check times.
Restart reuses the same Store leases, reservations, due times and holds. Unknown
inference is not retried. Notification queueing is off by default; `--queue-offers`
requires approved proactive activation and each student's separate opt-in. It never
sends directly. Dispatch remains in the original durable outbox worker.

The WhatsApp worker uses the same trusted `AGENT_CANVAS_ORIGINS` configuration as
the API and course service. It must pass that allowlist into its Store when
rechecking Canvas-backed offer and artifact authority. An empty allowlist still
rejects those sources; transport credentials never authorize an origin.

Health preparation: set `--health-file` to an existing private operator directory.
The atomically replaced JSON contains state, UTC time and counts only. A supervisor
can treat a stale timestamp as unhealthy; a present file alone is not liveness.
`SIGINT`/`SIGTERM` stop between bounded operations. `--stop-file` stops further work
when the operator creates that file; remove it explicitly before an approved restart.
An in-flight external call cannot be recalled. Do not retry its unknown outcome.

When explicitly enabled, offer enqueue recovery uses A's independent bounded
pending-offer selector after the scheduling pass. A saved offer can recover even
when no model check is due. Any existing outbox row, including an unknown outcome,
excludes requeue; enqueue still rechecks current source/control/consent fences.
Recovery needs no additional model call and introduces no separate message queue.

WhatsApp business verification is submitted and under review; no successful phone
delivery is claimed. Native Word/phone file acceptance and bounded laptop-closed
live operation remain separate gates. Document transport uploads checked immutable
bytes only after one-use authorization, repeats the current file/control read after
upload and before send, and retains unknown outcomes without retry. Explicit student
file requests are required; the service never auto-sends a completed artifact.
