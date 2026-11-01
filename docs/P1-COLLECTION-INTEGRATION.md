# P1 collection integration — November 1, 2026

Owner Akbar/Codex; [claim6554707805](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6554707805).
Branch `codex/p1-collection-integration`; base #124 `bba479d`. This is a draft
integration candidate for counterpart review, not main or deployment.

## Exact inputs

- A #124 `bba479d`: shared event changes014, pure document sections and private
  pinned section storage015; #118/#119 clarified proposals remain unagreed.
- M #125 `45dbebf6e9e30a27543070586bd4069838b8418e`: inherited #116 actual
  HTTP/client/Store scenarios plus Darwin environment-name policy correction.
- M #126 `e7558f7fdc51858e3004ac8bc1e6f16bad255dcc`: permission-aware bounded
  assignment-page reader, private HTML extraction adapter and same durable journal.
- Prior #121 `75ee8ca` CI/evidence, retaining its historical failed run. Only STATUS
  required conflict resolution; both histories were retained.
- Source integration commits `be6999a` and `55e01b2`; prior evidence merge `804df68`.
  App/extension/integration code matches #126 except the three exact #125 harness
  files and the preexisting A-branch optional Outlook read probe. A shared/runtime/
  contracts and expected ledger015 were preserved through merges.

## Independent review and verification

Exact #125 on macOS:17 actual client/loopback API/Store tests pass in6.86s, one
existing Starlette warning;21 environment-policy tests pass. Only the exact
Darwin-added __CF_USER_TEXT_ENCODING name is admitted. Parent filtering and
credential/canary exclusions remain intact, and policy never reads values.

Exact #126:59 actual extraction API/parser tests pass in2.08s, one existing warning;
143 focused reader/discovery/course collector tests pass. Reviewed origin/course/ID/
pagination bounds, context checks around extraction, exact extracted IDs, locked
body omission, partial coverage, input/output limits, pending-first journal replay,
shared lock and page-limit preflight. No scoped blocking finding.

First combined backend:961 passed/1 failed in56.00s. The old equal-timestamp revision
test failed during the DST repeated hour because Python cross-zone equality can
reject equality for identical instants. A's separate claim6554751832 and commit
`ec6f0c92f74d1d777e957483b25fb296e0b44bde` normalize both ordering operands to UTC.
Both deterministic 2025 Denver folds reproduced red before the fix. Regression
checks retain rejection and rollback for same-instant revisions, and chronological
promotion/older-history handling when local wall-clock order reverses.

Final combined code at ec6f0c9, with the two CI test entries in the working tree:

- Full disposable Postgres backend: **964 passed**, zero skips, two existing warnings,
  51.53s. All17 actual HTTP scenarios are included; none bypassed or deselected.
- All10 extension suites on Node24: **365 passed**, zero skips.
- Separate bounded operator diagnostic: **64 passed**, zero skips.
- Web: **114 passed** across9 files; TypeScript passes. Web source is unchanged.
- Ruff lint/format173 files, changed CI Prettier and diff checks pass. CI foundation
  pins Node24; extension job includes each actual test file once, including both new
  assignment-reader and environment-policy suites.

## Remaining acceptance and handoff

The actual-client HTTP scenarios exercise mapped assignment upload, replay and
Store effects. The new collector's tests use a synthetic extraction transport;
the actual extraction API is tested separately. This is **not** proof that the whole
production collector→extractorHTTP→Store path works for two courses, repeated scans
and changed deadlines. M retains the next scoped edit of the existing harness and
its HTTP acceptance test. A has no competing source/harness editor.

M counterpart review is requested for this assembled candidate, the narrow UTC fix,
CI and #124 document storage. Final #118/#119 wire agreement, baseline human review,
remaining Canvas source kinds/documents, installed browser recovery and live proof
remain separate gates. Outlook is optional/paused; WhatsApp delivered-reply proof
remains M-owned and blocked by the last account/business131031 evidence.

Only disposable test databases received014/015. No private live source, credential,
provider/model call, WhatsApp send, install, connector grant, continuous worker,
retained migration, deployment or protected-main merge was performed. The existing
$2 total ceiling/unknown reservation and stopped-worker constraints are unchanged.
