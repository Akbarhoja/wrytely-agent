# Cumulative model budget v1 — one-course activation prerequisite

A owns Store/runtime; M owns process assembly. Migration025 is candidate-only.
No model calls, real grant, deployment or increased allowance occurs from this code.

Operator-only Store methods (NEVER expose as student HTTP or model tools):

- configure_model_budget(key, ceiling_usd=decimal_string,
  opening_liability_usd=decimal_string): explicit global allowance; opening historical
  spent/unknown liabilities cannot reset on replay. Existing records must be
  reconciled and seeded before any new call; available credits are not allowance.
- grant_model_budget(key, verified_user, ceiling_usd=decimal_string): student share;
  repeated setup never clears liabilities. Global and student caps both apply.
- reserve_model_call(verified_user,key,maximum_usd) -> reservation UUID: serializes
  through the global row before any provider call, rejects missing/disabled budgets,
  missing student grants, paused agents or insufficient remaining allowance.
- settle_model_call(verified_user,reservation_id,actual_usd=...,input_tokens=...,
  output_tokens=...) records known usage once. Omitting usage retains the full
  liability as unknown. An overrun disables the global budget. Never delete/release
  unknown calls just because a timeout/error occurred.

M's service constructs BudgetedMetaRouter(store, Settings). For supervision pass
this router to run_course_supervision_once; it binds trusted verified owner. Original
runtime.worker main now uses this router too, and run_once binds lease.user_id.
Existing script-only tests may inject ModelClient stubs; deployed services must not
construct a raw MetaModelClient as a bypass. The router requires
AGENT_META_BUDGET_KEY, AGENT_META_INPUT_USD_PER_MILLION and
AGENT_META_OUTPUT_USD_PER_MILLION with independently verified model prices. No
pricing defaults, automatic credit grant or per-monitor allowance refill exists.

The wrapper bounds full JSON history+tools to250KB, reserves a conservative UTF8
byte token estimate plus4096framing tokens and2048output tokens (the existing Meta
Responses cap). Persist reservation before inference; no SDK or wrapper retry.
Known usage settles at configured rates, rounded up; missing/failed usage keeps
maximum held. Provider pricing/framing must be verified at activation: this is a
conservative application estimate, not a guarantee against provider billing errors.
Unexpected reported cost above reserve disables future calls, rather than silently
continuing. Preserve historical opening liabilities when configuring the real ledger.

The original $2 development ceiling remains until Akbar explicitly changes it.
Old allowances/reservations do not disappear with a new schema/budget name. Live
activation must specify one global key, model/prices, historical liabilities, test
student, total cap, duration, stop conditions and retained deployment/migrations.
No permission is needed to run the scripted isolated-Postgres tests for this code.
