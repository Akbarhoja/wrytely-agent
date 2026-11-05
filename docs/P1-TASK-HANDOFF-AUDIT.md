# P1 planner handoff investigation and safe failure evidence

A/Codex work under [claim6568126842](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6568126842)
and [implementation amendment6568159262](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6568159262).
Branch codex/p1-task-handoff-audit from #161
`e696be0f05609c47a96fa0a5a3b2b8ad88bd79d6`. A changes only runtime/planner.py,
new tests/test_task_handoff.py, this evidence and STATUS. No M implementation or
shared/schema/interface changes.

## Investigation result: cause not established

The first #161 full run had one existing typed-workflow failure: after planning,
the test could not claim its next academic task. Its own targeted/adjacent rerun
and subsequent full1,472-case rerun passed without a workaround. That history remains
in [pipeline evidence](P1-DOCUMENT-PIPELINE-ACCEPTANCE.md).

This investigation repeated100isolated synthetic document-only planner→academic
handoffs against fresh disposable Postgres. All100passed in18.86s. The diagnostic
called run_episode directly after claiming the planning lease so an underlying
exception could surface instead of becoming the worker's generic execution_failed.
No failure recurred. This does not prove a cause or a scheduling fix. The temporary
100-case stress probe was replaced by focused permanent regression scenarios;
it is not counted as100new product tests.

## Implemented observability

The existing planner now wraps named operations with a private _at_stage helper.
If an unexpected exception escapes an instrumented operation, it attempts one
existing fenced Store.event write of kind planner_failure with only:

```text
{stage:<fixed server stage>, category:<fixed exception category>}
```

Stages cover context/intent/source loading, heartbeat, requirement assessment,
assessment commit, saved-plan recovery, model selection, plan decode/checkpoint,
plan application and source-block commit. They are server literals, never selected
by a model/source. Categories are model_call_failed, invalid_result for ValueError,
missing_reference for LookupError, and unexpected_failure for other exceptions.
These are broad diagnostic categories, not established root causes. No exception
string/class name, prompt, credentials, source text, provider body or traceback is
persisted by this event. Previously authorized workflow events are unchanged.

Expected LeaseLost, SourceRefreshRequired and EvidenceContextLimit propagate with
no planner_failure event. Existing source-block handling remains in place. A
successful operation writes no new diagnostic and executes once. Failed diagnostic
persistence is best-effort: the original exception is re-raised so existing worker
ModelCallFailed usage evidence, retry limits and lease/control handling survive.
The diagnostics cannot bypass the event fence or make a committed task ready twice.
They do not retry an operation, alter scheduling or add provider requests.

The existing strict plan parsing was moved into a private helper solely to label
its failure stage; model tool schemas/decisions/public signatures are unchanged.
Not every possible interpreter/process failure can be persisted, especially after
lease loss or unavailable storage. This is additional evidence when safe, not an
uptime or complete tracing guarantee.

## Validation

- Final focused planner/worker/typed-workflow suite:58passed, zero skips,9.28s.
  Thirteen new cases cover real stage fault injection, redaction, preserved worker
  failure state, model-call evidence, invalid plan decode, diagnostic-write loss,
  expected lease/source stops, checkpoint errors, no diagnostic on success and
  saved-plan recovery with one child/no repeated model call.
- Full combined fresh disposable backend:1,485passed, zero skips, two existing
  warnings,109.49s. No retained database selected.
- All460extension Node tests pass; Ruff lint/format234files, diff and new-document
  format/link/scoped-path checks apply. New CI/counterpart review remain separate.

## Remaining boundaries

The original intermittent issue remains unresolved/unreproduced; it is not marked
fixed or used to pass a live gate. If it recurs during an instrumented operation,
inspect the scoped planner_failure plus existing task/model evidence before choosing
a correction. A claim=None with no exception needs separate queue/control timing
evidence; these events do not infer why a task is absent.

M has no new handoff/#157 agreement at the session's initial check. He retains
journal/upload/publication HTTP and private UI assembly; #157 dependent consumer
implementation was not started. The publication-route gap from #161 remains open.
P0/P1 remain open; no live source/model/send/spend/grant/install/retained migration,
continuous worker, deployment or protected main merge occurred.
