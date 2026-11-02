# Combined document pipeline acceptance

A/Codex owns this cross-layer scenario under TEAM.md and
[claim6567643601](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6567643601).
Branch codex/p1-document-pipeline-acceptance from #160
`3ae1fc6776ff05f2823adefa5d363b07448ca1c1`.
Only the new tests/test_document_pipeline_acceptance.py, this evidence and STATUS
change. Existing M producer, HTTP, journal, tests and fixtures remain untouched.

## What the combined scenario exercises

Actual local Node runs M's prepareDocumentParts over synthetic text/pages. Those
exact manifest/parts/totals are sent through FastAPI's real private document
begin/parts/finish routes, using the real disposable Store and configured synthetic
extractor version. These are ASGI/TestClient requests, not a deployed/live network.
Finish leaves a ready staged root with no observation. Publication is then performed
**explicitly through existing Store.commit_sync_batch**, followed by resource/scan
completion and original-section retrieval. This internal bridge is visible in the
test; it does not pretend there is a wired document-publication HTTP client.

One positive scenario continues through explicit Canvas-object delegation, exact
policy/rubric/citation references and the existing planner/generator/check workflow.
The model is scripted; no Meta call occurs. A checked internal v2 artifact is saved
with no fake source_versions. Existing v1 result projections still hide it; no
unagreed private-result consumer is enabled.

Nine persistent acceptance cases cover that positive chain; real commit-then-lost
HTTP responses for each of begin/parts/finish and exact replay with a recreated
app; actual PDF page gaps with partial evidence; partial evidence blocking before
any model call; unchanged sync versus changed due-date root/event semantics;
revocation after staging preventing publication; and other-account original-read
denial. They verify connected boundaries rather than replacing provider modules.

## Observed missing HTTP assembly

A one-time synthetic capability diagnostic also sent a genuine schema2 document
publication batch to the existing /v1/source-connections/canvas/academic/batch route.
It returned422/no-store and created no observation: AcademicBatchIn.envelope accepts
schema1 AcademicBatch only. The unchanged internal Store publication accepts that
same document batch and produces the pinned original. Staging finish is not source
publication. The diagnostic was removed from permanent tests so future correct
publication assembly is not required to keep failing.

[Finding6567672597](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6567672597)
was handed to M with the next owned wiring request: claim the journal/upload/
publication scope, reuse existing request replay and current Store fences, preserve
schema1 behavior and agree an exact document-publication route/error boundary
before adding it. No source authorization or parser is weakened to disguise the gap.
This is a concrete next integration dependency, not a shared-store failure.

## Validation and limits

- Final nine new focused cases pass on fresh disposable Postgres, zero skips,
  one existing warning,2.44s. Earlier temporary diagnostic also observed the HTTP
  schema gap locally; it is not counted among the final nine.
- First full combined run:1,471passed and one existing typed-workflow failure
  (test_bad_quote_never_reaches_semantic_assessment_or_readiness could not claim
  its academic task before the quote-check assertion), two existing warnings,108.19s.
  Targeted plus adjacent typed/pipeline rerun:34passed, one existing warning,13.64s.
  No runtime/test workaround was applied; the cause is not established. A full
  fresh disposable rerun passed all1,472tests, zero skips, two existing warnings,
  107.54s. The earlier failure remains recorded as unreproduced, not attributed to
  a proven cause or hidden by a retry/skip. All460extension Node tests pass.
- Ruff lint/format232files, diff and scoped new-document format/link/path checks
  apply. New candidate CI and counterpart provider-realism review remain separate.

No installed browser, Canvas download/parser, real journal recovery, deployed HTTP,
Meta model quality, WhatsApp delivery or continuous agent operation is proved by
these cases. The actual producer remains unbundled/unwired. M retains that assembly
and HTTP/UI ownership; #157 private-result agreement remains pending. Only explicit
supervisor reassignment can transfer his implementation files. No duplicate journal
or new runtime/source interface was created on A's side.

P0 baseline independent human approval/protected merge and WhatsApp delivery remain
open; Canvas technical classification has already been recorded and Outlook stays
optional/paused. P0/P1 remain open. No live source/model/send/spend/grant/install,
retained migration, continuous worker, deployment or main merge occurred.
