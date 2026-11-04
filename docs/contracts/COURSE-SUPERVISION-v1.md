# One-course supervision v1 — executable candidate

A owns shared/runtime/contracts; M owns authenticated HTTP/WhatsApp/service assembly.
Additive migration023 is local/CI-only until deployment approval. No new runtime,
source store or message queue is introduced. Original planner/draft pipeline remains.

## Student-facing Store calls (trusted verified identity required)

- enable_course_supervision(verified_user, connection_id, course_id, call_limit=6)
  opts into one already selected connected course. Replay does not refill allowance.
- pause_course_supervision(verified_user, supervision_id) fences an in-flight decision;
  remains available after source disconnect. Enable replay is not an unknown-call reset.
- course_supervision_status(verified_user, supervision_id) returns persisted state,
  next_check_at, calls_reserved, call_limit, last_decision, reason and private offers.
- find_course_supervision(verified_user, connection_id, course_id) returns that same
  private status or None for a never-enabled course. Owned connection required;
  another student's connection returns Not found. This read-only lookup never
  enables/resumes a monitor, replenishes calls or clears holds; paused/disconnected
  historical status remains available for the owner's controls. M can expose it
  through strict session HTTP for website reload/cross-device recovery.
- decide_course_offer(verified_user, supervision_id, offer_id, accept=bool) persists
  an explicit current-source decision. On acceptance returns draft_request arguments
  for existing create_canvas_draft_responsibility(verified_user, **draft_request).
  Use those exact arguments: stable key deduplicates a repeated HTTP request/crash.
  The offer pins up to eight inspected current objects (assignment plus investigated
  course policy/context); acceptance rechecks every pinned version. Both steps
  recheck ownership/source scope. Do not accept model-generated user IDs.

These methods require authenticated assembly. Internal claim/finish/hold methods must
never be exposed as student RPCs. An offer/acceptance grants no WhatsApp delivery scope.
Original task authorization, policy/verification and private result gates still apply.

## Runtime and service

run_course_supervision_once(store, model, verified_user, supervision_id) claims one due
check, durably reserves one model call, supplies scoped metadata/investigations and
asks Meta for exactly one structured inspect/offer/wait action. Inspect uses existing
pinned evidence/document-section readers; next tick sees saved results. Offers require
an inspected, fresh current assignment. Model chooses next check between60s and24h;
inspection continuation is immediately due. Service ticks are scheduling opportunities,
not a fixed semantic task list. Model determines intervention and priority.

A claim is exclusive for5min. On expiry or exception, reserve remains held and the
monitor blocks; do not blindly retry an unknown inference. Restart after a committed
wait restores the due time. Student pause and changed scope/connection/source versions
fence a late commit. Identical object/version offers deduplicate; changed snapshots
clear cached investigations and obsolete pending offers become stale on next check.

This candidate has a hard cumulative1–20-call limit per supervision, default6. This is
not a dollar-budget approval or global-cost implementation; model activation remains off
until measured/reserved cost limits and bounded operator approval are configured.
Pending offers are PRIVATE intents. M must not dispatch them through reply-only consent.
Distinct proactive delivery authorization, provider template and signed receipts remain
required before outward messaging. No live duration, delivery or long-term reliability
is proved by scripted tests.

## Explicit current bounds

At most200 stored source objects per selected course per decision; larger catalog
fails visibly rather than silently truncating it. At most100KB investigated context;
inline page12000characters, document page2sections with explicit next_slot. Current
inspection replaces the previous page for that object; previous-page accumulation and
unbounded files are not claimed. No external tools, course writes, quiz attempts or
automatic drafting from a source. Updated source details must come from a new sync.
No DOCX/PDF rendering, revisions, proactive channel delivery or paid deployment is
claimed complete by this first supervisor candidate; those remain delivery work.

## Read-only inspection of incomplete sources

The supervisor snapshot now includes original `missing` codes and server-computed
`inspection_ready`. A current selected complete/partial original may be inspected
with its gaps retained when its connection/account/generation is current, it is not
historical/missing, both observation clocks are within the existing24h read bound,
and its resource is open/partial/complete. Restricted/unsupported/unknown resources,
old/future observations, changed scope and revoked identity cannot use this path.
The existing pinned readers and character/section/page limits are unchanged.

This is **read-only investigation**, not a completeness promotion. HTML extraction
deliberately reports html_text_only/linked-content limitations, so partial coverage
does not itself mean an HTTP/parser crash. The agent can read available originals
to understand these gaps and explain why work is blocked. `freshness.usable`, original
coverage and missing fields remain unchanged. Work offers, acceptance, draft/citation
checks, file readiness and dispatch keep their existing complete-evidence gates.
Invalid model work-offer decisions on incomplete evidence hold instead of retrying
another paid inference. Real-course action readiness still requires resolving the
actual required content gaps; this inspection change does not pass that live gate.

## Checked private Word output

A supplies runtime.artifact_rendering.render_private_artifact_docx(store,
verified_user, artifact_id) -> immutable RenderedArtifact(artifact_id, check_id,
filename, media_type, sha256, content). M's authenticated download/file-delivery
assembly consumes the bytes. Use no-store and attachment headers; never accept an
arbitrary body/draft from the browser, put it in a public bucket or equate rendering
with recipient delivery authorization. All filenames are fixed UUID-based names.

The helper reads the existing v2 private artifact projection, requires ready/current
passed checks and unpaused controls, renders inert text-only DOCX, then repeats the
same ownership/evidence/control read and compares artifact/check/content identity.
Content SHA256 is stable. Disclosure and quoted original evidence are included;
XML is escaped, no external relationships/macros/assets are emitted. Paragraph text
is literal; no Markdown/table/image/equation layout claim. Complex LaTex math is
explicitly unsupported. ZIP/XML/Unicode/control-fence tests are separate from actual
Word/phone visual acceptance, which remains required before calling export complete.

## Source-event wakeups

Additive026 stores the last observed source-event timestamp per monitor. New
course-scoped source/coverage events make a ready monitor due even before its
model-selected next check; unchanged sync cannot create a paid polling loop.
Claim records that event watermark with its existing call reservation and context.
A known source race after a model result can requeue a fresh decision, preserving
call/dollar limits and clearing obsolete investigations. Expired lease, pause,
changed account/scope/generation or unknown inference cannot use this path. No
source ingestion callback starts models directly; M's due service remains the only
reasoning process. New events while the laptop is off still require an actual sync.
