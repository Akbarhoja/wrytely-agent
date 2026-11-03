# Connected P1 completion candidate — November 2, 2026

Owner: Akbar/Codex under the explicit remaining-P1 reassignment in [TEAM.md](../TEAM.md).
Branch: `codex/p1-completion`, based on #164 `31f3f8b`; prior progress `a8915a8`.
This is a connected implementation and validation candidate, **not completed P1**.
[Work-order acceptance](WORK-ORDERS.md#p1--automatic-collection-and-usable-memory)
remains required. Outlook is optional/paused; P0 WhatsApp remains Murtazo's.

## Current installed acceptance run

### Combined scope, control and scheduling correction0.3.0

Re-pairing intentionally resets the old generation's scope. Preserve that boundary:
do not automatically reuse another identity's selections. The worker now distinguishes
catalog-only completion from content work and requests selection instead of reporting
complete content; an unchanged finished empty scope does not begin another scan.
For a finished journal, current context is checked before deciding whether selected
content now permits a new scan. The web view labels empty scope as course discovery
only, provides selection guidance and warns that pairing again clears course choices.
Transient dashboard bootstrap failures no longer hide authenticated connector controls;
the connector still authorizes each request and real session expiry clears access.

Package uses a45-second soft between-step budget rather than15seconds, still at
most100original durable steps per callback. Factory default stays15seconds; budgets
above45seconds reject.30-second continuation delay,30-minute periodic opportunity,
per-request deadlines, original journal/receipt recovery, control epochs and pause
checks are unchanged. No keep-alive loop, second scheduler or parallel upload system.
[Chrome lifecycle reference](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle)
documents the event/idle limits; this remains bounded work and must survive worker
termination. A virtual-clock regression with1.5-second durable steps measures10steps
per45seconds versus30per75seconds including continuation waits, a1.8x simulated rate.
It does not establish real Canvas throughput or a completion ETA.

All587Node/134webPASS plus TypeScript/Ruff/format. Local disposable Postgres could
not initialize due sandbox shared-memory/process restrictions; no local integration
pass is claimed for this head. CI and installed proof remain separate. The corrected
empty-scope website was inspected in Chrome; private selection/results stay ignored.
Next: one same-folder0.3.0reload, positive pause/version check, independently read saved
scope, bounded content collection, actual throughput/counters, unchanged repeat,
recovery and isolation. Stop beforeP2. No new backend deploy or migration is required.

Diagnostic0.2.7 follows another unresolved collector_failed stop. Unexpected errors
now retain one fixed processing-stage code; known discovery_request_rejected and
discovery_state_changed also survive the collector boundary. Original messages and
stacks are not persisted or displayed. All574NodePASS including stage/redaction and
request-rejection regressions. Read-only shape checks and a synthetic empty-body
conversion did not reproduce a submission-state failure; do not claim that as the
cause or a fix. Same-folder update permissions unchanged; controlled resume and
actual diagnosis remain pending. P1 remains open.

Performance follow-up0.2.6 reuses the projection returned by each persisted,
final-checked document operation. The old caller immediately inspected again only
to produce the same display summary, adding another context/profile round trip per
continuation, page commit and resource close. Initial inspection and all operation
preflight/finalCheck identity/scope/receipt fences remain unchanged. All567NodePASS,
including updated-result reuse with one inspection and rejection of final-check
account changes. This is a verified redundant-request reduction, not a measured
live speedup or large-course benchmark. Owner-paused collection requires same-folder
reload/live proof; manifest permissions and existing pairing/checkpoints are unchanged.

Lease-race fix0.2.5: document inspection can see a valid lease that expires during
provider IO/conversion before a commit or continuation. Instead of making that
ordinary expiry terminal, route only discovery_lease_expired through the existing
pending-first recovery operation. Accepted primary receipts replay before renewal;
original checkpoints, server ownership and lease-replaced fencing are preserved.
No new scheduler, lease duration, credential or parallel upload path. All565NodePASS
including commit-time expiry, continuation expiry and replaced-writer rejection.
Local full integration setup remains sandbox-blocked as recorded below. Prepared
same-folder package permissions unchanged; live recovery and performance are pending.

Root-cause fix0.2.4: discussion requests used only_announcements=false. A controlled
read reproduced announcement rows for that selector and a discussion response when
omitted. The response-type guard correctly rejected announcements as discussions;
keep that guard, change the request to the documented default, and reject announcement
selectors in discussion pagination/continuations. Announcement reads still request
true. No extra origin/scope/credential or weakened source-type check. All562NodePASS.
Focused actual-JS/HTTP tests hit sandbox setup errors in pgserver's cache/process
inspection before running; no integration pass is claimed for this head. Same-folder
0.2.4 package is ready with identical manifest permissions; installed recovery remains
pending. Primary API reference:
https://developerdocs.instructure.com/services/canvas/resources/discussion_topics

Diagnostic follow-up0.2.3 preserves the document collector's fixed validation and
scan-conflict codes through the host boundary instead of collapsing them to
host_failed. UI displays only a fixed allowlist of diagnostic codes, never arbitrary
provider/source error text. All559NodePASS, including host/restart propagation and
UI redaction. Same-folder package permissions are unchanged. The underlying live
failure remains unresolved; previous generic error cannot be decoded retroactively.

Collector diagnostic follow-up0.2.2 fixes lost stop reasons: a terminal collection
error used to disable the host durably but keep its reason only in worker memory.
Status after worker recreation could therefore show only paused. The host now stores
an allowlisted stop code with its preferences and returns blocked after recreation;
explicit pause/enable clears the diagnostic. Legacy preferences remain readable,
unknown/source-supplied text fails closed, and no automatic retry or access expansion
is introduced. All557Node tests pass, including restart/status/no-retry and legacy
preference checks. This cannot recover an earlier lost reason or prove the underlying
live interruption resolved. Same-folder0.2.2 package is prepared with identical
permissions; owner reload and bounded live recheck remain pending.

Installed acceptance is in progress. Detailed academic observations remain in ignored
local evidence, not this public report. Full collection, unchanged-repeat, installed
recovery and isolation acceptance remain open.

Murtazo's scoped review of exact7a3ef7a reports no blocking findings and independent
555Node/132web/127focused backend+WhatsApp/9JS-HTTP scenario passes plus TypeScript/Ruff:
[counterpart handoff](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6594170818).
This completes the requested review scope, not a full backend/parser/live audit or
the required human merge approval. No P2, Meta calls, WhatsApp sends or scope expansion.

The preparation notes below are historical where superseded by this installed run.

## Installed metadata discovery and options-page repair

Installed P1 continuation: owner reports0.2.0 installed/paired/identity verified.
Authenticated connection refresh confirms connected. The real extension has already
completed metadata-only discovery: UI shows7courses, explicit-set scope,0selected
courses and0content-resource rows. This is live catalog proof, not full collection.
The popup indicated an enabled finished scan, so a pause must be positively verified
before content scope is selected; the owner's paused report alone is not acceptance.

The full options page showed unknown status while the popup worked. Chrome documents
that an extension options tab can carry sender.tab/frameId metadata. The old blanket
"tab" rejection is replaced only for the exact own top-level options.html sender:
same extension ID, exact page, frame0, safe tab ID, matching origin and optional tab URL.
Content scripts/web pages/other extensions/child frames/popup tabs still reject.
Two new positive/negative cases and all555NodePASS. Live recheck is pending.
Version0.2.1 updates only host-events/manifest in the same installed v020 folder;
manifest permissions/configuration/storage identity are unchanged. Native management
control was interrupted by active Chrome use; owner is asked to reload and confirm
Pause in full Settings. Two-course choice is also pending. No course content may be
collected until those steps are confirmed. No new credential, backend deploy, Meta
call, WhatsApp send, scope expansion or P2. Primary sender documentation:
https://developer.chrome.com/docs/extensions/reference/api/runtime#type-MessageSender

## Approved live-preparation update

November2 approved live preparation supersedes the earlier candidate-only snapshot.
Akbar approved the scoped development deploy/migrations/configuration, Canvas notice
amendment and bounded read-only two-course/restart/session test. Approved privacy
notice is published at2f30819. Exact development deployment6c8bfbc9-0ba2-481c-9d83-ce68100dccd4
of2f30819 is SUCCESS; bounded logs show migration-command completion and API-only
startup, health200 and authenticated Canvas setup/listing work in Akbar's correct
Chrome account. The migration runner's existing atomic checksum/advisory-lock fences
ran during predeploy; no separate SSH ledger enumeration was available without a
new SSH key, and none was added. This is startup proof, not collection acceptance.

CSU login recovered and its dashboard shows7published courses. New inactive package
0.2.0 is at .local/canvas-packages/p1-live-20261102-v020. Akbar is asked to load it,
pair and verify identity while leaving collection paused. Content scope must remain
empty until the owner chooses2courses; do not use all-active for this bounded test.
No course collection run is accepted yet. P0 WhatsApp and optional Outlook remain
untouched; model/delivery workers stopped, no Meta calls/sends/spend and no P2.

Browser-only follow-up abdd6ff adds at most100original durable steps per callback,
with a soft15-second between-step budget. It stops on finish/pause/backoff/failure;
single flight, epoch fences, existing checkpoints and30-minute refresh remain.
Factory default stays1step. All553NodePASS including8new lifecycle/bound cases.
The existing Linux CI at a8915a8 failed two3-scan discussion subprocesses at45seconds
(1608others passed). Three-scan automatic-document drivers now have180seconds;
ordinary cases stay45seconds. Production deadlines/assertions/retries/skips unchanged.
Three focused combined/reply cases pass28.94s. All four Linux CI jobs pass atabdd6ff in both push/PR runs41546216664 and41546223520. This test and
browser change needs no backend redeploy; the deployed API remains2f30819.

## What this candidate adds

The original host, paired client, durable discovery/upload journal, document producer,
Store and publication boundary are reused. There is no second agent/runtime/journal.

| Source                    | What is collected                                                                            | Explicit limits                                                                                                      |
| ------------------------- | -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Courses                   | Paginated active-course discovery, no manual course IDs                                      | Selected account/origin only; disappeared rows need confirmation                                                     |
| Assignments               | Authoritative instructions, rubric fields and effective dates                                | No submission/write; hidden/external requirements remain gaps                                                        |
| Syllabus/pages            | Original inert HTML text with provenance                                                     | Linked, image or external content is not inferred from visible text                                                  |
| Announcements/discussions | Prompts, paginated entries and full reply pages                                              | Never post to unlock; author roles/attachments may remain unknown                                                    |
| Modules                   | Paginated modules plus separately paginated item lists                                       | References do not launch quizzes or external tools; inline item sample is insufficient                               |
| Submissions               | Own status and read-only detail, inert body text and comment text/timestamps                 | No other students or author IDs; quiz bodies/attempts are skipped; attachments/external submissions stay gaps        |
| Grades                    | Original own-assignment marks, points possible and current/previous/unverified attempt basis | Null means unknown; no invented course total, weighting or pass prediction                                           |
| Files                     | Paginated authorized course-file list and each file's contents within limits                 | PDF/plain text/HTML; inaccessible or unlisted linked files cannot be certified read; DOCX/images/OCR not implemented |

Files use exact approved Canvas storage hosts only, omitted credentials, one approved
file-host-to-CDN redirect, strict MIME/size/signature checks and identity checks
before network and before returning bytes. Signed URLs/bytes do not enter the local
upload journal. The production package includes `webRequest` plus the two exact
storage hosts; this expands the older diagnostic/package permissions and requires
operator review and user installation consent.

Conversion is credential/generation/scope-fenced before and after work. PDF parsing
runs in a child with an 8-second CPU limit, 12-second parent deadline, bounded pypdf
decoding and at most 200 pages/200,000 characters from a 5 MiB file. Linux has a
512 MiB address-space limit; macOS uses a sampled RSS watchdog because that OS
rejects the hard address-space limit. It is not an absolute macOS RAM guarantee.
Blank/image pages and layout remain gaps. No executable document content, external
decoder, source URL fetch or OCR is enabled.

Unknown MIME files can be published only as empty unsupported documents with an
explicit unsupported-format gap. Restricted unsupported files remain unsupported,
not falsely parsed. Existing schema-1 inline resource routes still reject modules
and files; new document resources close through the schema-2 document boundary.

## Student interface and private reads

The Connections view now has Canvas pairing, account connection metadata, all-active
or explicit course/content scope, paginated discovered courses, scan/discovery times,
resource coverage and retained incomplete-item counts. It distinguishes a finished
scan from complete content and current knowledge. The agent cannot read new Canvas
changes while Chrome is stopped or the Canvas session is unavailable. Optional
Outlook is visibly disconnected/paused. Manual snapshots moved to source troubleshooting.

New session-only routes:

```text
GET /v1/source-connections?limit=20&cursor=<owned connection UUID>
GET /v1/source-connections/canvas/setup
GET /v1/source-connections/<UUID>/canvas/coverage?limit=20&after=<course ID>
```

They return no ingestion bearer, provider subject, private body or signed download URL.
The existing same-origin web proxy allowlists these reads, pairing/scope/revoke and
private v2 reads. Ingestion bind/redeem/context/document operations are not forwarded
through the student session proxy. Ownership is always the verified session.

Document-backed results use the existing private v2 list/detail/evidence APIs.
The view shows saved checks separately from current evidence and renders draft and
original text inertly. Citation and pinned-check policy/rubric reads page the same
original source; a 409 authority change clears displayed content. Account/component
changes abort old requests. Strict Mode cleanup/replay is tested; linking expiry has
a timer only while a challenge is displayed, rather than rerendering courses forever.

Operator configuration is default-off:

```text
AGENT_CANVAS_ORIGINS=["https://colostate.instructure.com"]
AGENT_CANVAS_DOCUMENT_EXTRACTORS=["canvas.html.v1","canvas.json.v1","canvas.text.v1","canvas.pdf.v1"]
```

Settings only accept the four local extractor identifiers. No source can choose a
parser or grant a scope. Explicit factory overrides used by tests remain separate.
New bounded ingestion operations are `/documents/file-extract` and `/documents/resource`.
A file-extract request is schema2/operation `extract_file` with origin, connection,
generation, scope_revision, course_id, file_id, content_type and base64 data. It is
not an arbitrary URL-fetch endpoint. Maximum transport is 8 MiB and decoded file 5 MiB.

## Local evidence

Tests use synthetic source responses, real JS production clients, loopback FastAPI
and disposable Postgres. No provider/model API, real course upload or WhatsApp send
is needed for them.

- The combined nine-resource scenario discovers two courses and runs three scans,
  recreating clients on each tick. It verifies **156 observations, 57 immutable
  roots/events and 99 committed batches**; unchanged data dedupes, and changed
  deadline/reply/grade/two file texts create only their expected new roots/events.
- A separate real JS/HTTP PDF case verifies actual synthetic PDF bytes through
  isolated conversion, publication and stored original page text: 36 observations,
  13 roots/events, 33 batches; two unchanged PDF roots across all three scans.
- Module tests enforce separate item pagination and parent/continuation validation,
  with quiz references never visited. File tests cover host/redirect/MIME/size,
  account changes, PDF signature and restricted unsupported formats. A revocation
  during PDF extraction must discard the converted private result.
- Coverage HTTP tests verify private ownership, controls, strict pagination and
  no secret/content projection. Web tests cover scope/pairing account changes,
  Strict Mode recovery, source paging and content clearing after authority loss.
- Final complete suite results are recorded in [STATUS.md](../STATUS.md).

The first full run found schema-1 modules were accidentally widened by the shared
resource map: 1 failure/1,634 pass. Keeping the original inline resource literal
fixed that regression; focused compatibility/module/coverage checks pass. A PDF
acceptance assertion initially used a nonexistent metadata column; the existing
format column is now used. These are not provider failures or permission workarounds.

## Concrete development target; not activated

Read-only CLI inventory confirms project `wrytely-agent-development`
`b089bb4d-23a5-4897-9ecb-084965e498ba`, environment named `production`
`7ab2c8b9-a691-49bc-9922-a0a912cb51e2`, service `agent-api`
`4e3d17a0-a8ce-4563-9509-11caf14ad6fa`. The environment's name is Railway's default;
the project is the isolated agent development project, not the handwriting product.
Its existing endpoint is `https://agent-api-production-409f.up.railway.app`.

The deployed service still runs the older M2 candidate and has a predeploy migration
command. A new deploy would apply pending 010–022 agent-schema migrations after
checking its actual ledger. There is no migration008 in this candidate. Additive
schema rollback must preserve data; do not drop the schema to revert an app build.
Model/delivery workers remain stopped, and this API deployment does not start them.

An inactive local package is prepared at `.local/canvas-packages/p1-completion-20261102`
for the exact development API and CSU Canvas origins. It has not been installed,
paired, granted permissions or enabled. Regenerate it after any runtime changes.
No retained migration, service change, public signup or protected-main merge occurred.

The browser visual check used the existing local frontend and current second
participant session. It correctly reports that the new Canvas backend setup is not
installed. This is an error-state layout check, not live coverage/result acceptance.
Do not pair Akbar's Canvas account under that second participant's Wrytely account.

## Remaining P1 acceptance — next execution, not assumed passed

1. Complete candidate review/CI. M reviews delivered code; he does not resume overlapping
   P1 implementation. Main approval/merge protections stay in place.
2. Obtain scoped approval for the isolated development deploy, pending agent migrations,
   exact Canvas origin/converter configuration, and the real course-data test below.
3. Review/publish the factual Canvas privacy amendment before real pilot ingestion;
   the current approved notice still says Canvas is not connected. The prepared
   [amendment](P1-CANVAS-PRIVACY-AMENDMENT.md) is a draft, not the effective notice.
4. Sign into Wrytely with the actual source owner's account. Review/load the prepared
   unpacked package in Chrome. Pair and verify Canvas identity without exporting
   passwords, cookies or session credentials.
5. Discover courses, choose two controlled courses in the UI, then read them through
   the extension. Inspect actual syllabus/assignment/rubric/thread/file/submission
   results and gaps, not only successful course counts. A restricted listing/linked
   file or institution-specific response may require further code; do not mark it read.
6. Repeat unchanged sync and verify no new immutable content/events. Use a controlled
   changed item or a consenting controlled course for change proof; never alter a real
   academic deadline or discussion to manufacture test evidence.
7. Verify installed worker suspension/browser restart and expired-session recovery,
   disconnect/scope-change fencing and two-account isolation with the actual paired
   host. Coordinate disruptive Chrome/session tests and human Duo sign-in.
8. Record live and local evidence separately. Keep model/delivery workers stopped and
   collection paused after the bounded acceptance run. Only mark P1 complete after
   its required checks and reviews are resolved; stop before P2 per Akbar's instruction.
