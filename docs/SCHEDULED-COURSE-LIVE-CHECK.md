# Scheduled cloud course check — November 4, 2026

The owner approved one five-minute scheduling test on the already live-tested
`7abbefcd18798528f3a6b20dab83705fc3719838` backend in isolated Railway development:
one Meta request through Fireworks, at most $0.12 additional within the original
$3 cumulative ceiling, existing ECE 253 Lab 8 evidence only. No message, draft
worker, source collection, Canvas write, migration or continuous worker was allowed.

## Observed result

The operator persisted a check two minutes ahead, then launched a fresh Python
process. That process reconstructed the original Store and budgeted runtime,
verified that the saved check was due, and ran the original course supervisor.
The model selected an inspection; the runtime read the authorized saved evidence
and committed the decision. The operator did not supply a scripted model action.

All times below are UTC on November 5 (November 4 Mountain time).

| Event | Server time |
| --- | --- |
| Timer persisted | 06:11:09.424 |
| Persisted due time | 06:13:09.404 |
| Fresh-process due check | 06:13:12.637 |
| Real Meta request started | 06:13:12.825 |
| Model returned | 06:13:16.353 |
| Inspection decision persisted | 06:13:16.656 |
| Pause and budget cleanup confirmed | 06:13:17.109 |

The actual scheduled interval to the fresh-process check was approximately
123 seconds. The model returned known usage of 10,620 input and 258 output tokens.
Exactly one request ran; no send or retry occurred. Existing decision and inspection
history was retained. The initial two-minute due time was set by the operator;
this test does not claim the model chose that initial interval.

The owner reported closing and reopening the laptop. That physical interval and
its overlap with the decision were not independently instrumented. The server
record directly proves persisted scheduling and execution in a fresh cloud process;
owner-reported laptop closure is separate evidence, not a measured offline duration.

## Cost and restoration

New liability was $0.01437150. All previous $2.32163000 charges/holds remained
unchanged; cumulative known/held liability is $2.33600150 of $3. Unknown historical
reservations were not released. These amounts are conservative ledger evidence,
not a final provider invoice.

One-off deployment `ec0b35af-2b2f-4eec-bc7b-cc88f6a9594b` completed the seven safe
operator events. Supervision was paused and its dedicated budget disabled, with
read-back checks. Telegram preferences were untouched. The normal migration-only
predeploy command and API-only start command were restored and read back. Cleanup
deployment `b1195f7a-b9e6-4754-b728-74daa440dfb9` succeeded. Independent HTTP checks
returned 200 from `/healthz` and 401 from unauthenticated `/v1/me`.
The completed approval supplies no further model allowance or continuous activation.

## Remaining acceptance

This was a single scheduled inspection of stored course evidence. It does not
prove collection with Chrome closed, a crashed-worker recovery, a 24-hour service,
a 72-hour soak, or graded assignment readiness. The fresh process was a planned
restart boundary, not an unexpected crash.

Real checked Word-file/revision receipt remains open. The actual Lab 8 source and
policy gaps remain; this scheduling result does not permit graded drafting.
Connected synthetic JSON drafting and Telegram revision/file checks are recorded
separately in PR #185. Public-release approval and broader student onboarding
remain separate from this isolated development test.
