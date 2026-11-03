# One-course service preparation

This describes code entrypoints. It does not authorize deployment, retained
migrations, new allowances, model calls or WhatsApp sends.

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

Use `--limit 1` for a one-course scheduling pass. Poll cadence is an opportunity to
check persisted due work; the model chooses intervention and next check times.
Restart reuses the same Store leases, reservations, due times and holds. Unknown
inference is not retried. Notification queueing is off by default; `--queue-offers`
requires approved proactive activation and each student's separate opt-in. It never
sends directly. Dispatch remains in the original durable outbox worker.

Health preparation: set `--health-file` to an existing private operator directory.
The atomically replaced JSON contains state, UTC time and counts only. A supervisor
can treat a stale timestamp as unhealthy; a present file alone is not liveness.
`SIGINT`/`SIGTERM` stop between bounded operations. `--stop-file` stops further work
when the operator creates that file; remove it explicitly before an approved restart.
An in-flight external call cannot be recalled. Do not retry its unknown outcome.

Current limitation: queueing of freshly observed offers occurs after course ticks.
Crash recovery between saved offer and enqueue must consume A's independent pending
offer selector once published; do not spend another model call merely to recover
that handoff. This is not complete proactive service acceptance yet. WhatsApp is
restricted pending owner business verification; no successful phone delivery is
claimed. Native Word/phone file acceptance and bounded laptop-closed live operation
remain separate gates.
