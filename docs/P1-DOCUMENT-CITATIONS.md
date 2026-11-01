# P1 exact original-document citations — November 1, 2026

Owner Akbar/Codex; [claim6555748140](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6555748140).
Branch codex/p1-document-citations, base #1392b29546; executable0c43df1.
This implements the accepted #78 original-section citation architecture internally;
it is not a new M consumer wire, model tool or source activation.

## Behavior and reuse

The helper calls existing read_canvas_document_sections or its current-lease/task-
bound variant with exact object/observation/root and one explicit slot. It checks
section ID/page, UTF8 hash, global Unicode offsets and exact normalized quote.
A quote is nonblank and at most4000 code points; no clipping, approximate match,
latest-version fallback or model-supplied source excerpt is used. Duplicate text is
resolved by its explicit occurrence offsets. Quotes crossing section boundaries
need separate section references rather than fabricated combined provenance.

The trusted Store retains all ownership/generation/selection/credential/lease/pause/
task-source checks. Helper input cannot name a user/agent/credential or broader
scope. No second Store/query/parser/extractor is introduced. Return contains only
citation/hash and original coverage/missing/historical/inspection freshness; unquoted
text, provider references/subjects/credentials and leases are not returned.

Literal containment does not prove the model's interpretation. A matching quote
from partial/stale/historical evidence is retained for inspection and never becomes
complete/current evidence. The explicit inspection usability field is not a draft/
action permission: future academic/dispatch consumers must apply their own purpose
policy and rerun controls/references at final commit. No runtime tool list changes,
model requests, fact writes or automatic work are introduced.

## Verification

All40 focused cases pass against real scoped reads/disposable Postgres, with synthetic
sources only. Tests include exact NFC/emoji/code-point offsets, repeated occurrences,
a later slot in long text, PDF page provenance, malformed types/keys/bounds, wrong
quotes/IDs/pages/offsets/roots and stored-body corruption. Cross-account, unbound-task,
paused-lease, revocation/scope/credential-expiry denials use the existing Store fences.
Partial/historical/stale/latest-failed evidence stays inspectable but unusable.
A protocol root published through the full begin/put/finish/publication path verifies
without a fabricated legacy text version; an unbound task still cannot inspect it.

At executable0c43df1 the full combined backend passed1224 tests, zero skips, two
existing warnings in76.31s. Ruff lint/format197files, document formatting, links and
diff checks pass. No old
fixture, existing runtime/Store behavior, SQL or M-owned extension/app code changed.

## Team and remaining work

Fresh #4/#136 check found no new M handoff. M remains sole editor of his inactive
Chrome host/controller/event foundation, source/HTTP/UI and later installed/live
checks. This work does not duplicate his claim or require him to be online.
M counterpart review is requested when available. Existing non-WhatsApp P0 closure
#139 and baseline#46 human approval remain pending, not waived by this P1 increment.

No schedule/monitor, browser/session change, source/provider/model call, spend/send,
credential grant, install, retained migration, continuous worker, deployment or main
merge. P1 remains incomplete; this helper is a foundation for later checked work,
not the completed semester supervisor or drafting workflow.
