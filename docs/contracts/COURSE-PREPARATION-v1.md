# Non-submission course preparation v1

Owner A: `codex/course-preparation`. Additive to the original supervisor/Store;
not a new runtime, draft pipeline or messaging outbox. Migration029 adds bounded
private preparation history to `course_supervisions`; activation remains separate.

## Model action

`record_course_decision` gains action `prepare`. The normal UUID `object_id` targets
an inspected ordinary assignment. `message=""`, `first_slot=0`; `preparation` is:

```json
{
  "excerpts": [
    {"object_id": "<inspected object UUID>", "quote": "<exact original excerpt>", "kind": "review"}
  ],
  "questions": ["Have you collected your actual measurements?"]
}
```

Excerpt kind is `review` or `student_action`. At most8 excerpts/1500characters each,
at most5 questions/500characters each. No generated solution/body/code/policy
permission fields exist. Questions request missing requirements/access/actual
student input; the model instructions prohibit graded answers and invented results.
Exact-quote verification is structural grounding, not a semantic quality guarantee.
Source text remains untrusted; UI must render literal text, never HTML/instructions.

Other actions have `preparation=null`; historical decisions omitting it remain
valid. Provider strict schema requires the nullable field on new model calls.

## Grounding, scope and persistence

Full drafting still requires existing complete/current evidence and policy checks.
Preparation may use original partial evidence only when `inspection_ready=true`.
Target and every cited object must already have a matching current pinned inspection.
All available syllabus objects must also have current inspections, without treating
their text as an assertion of permission. Other quoted sources must be files carrying
`linked_from=["assignment:<target provider ID>", ...]`. An unrelated file, assignment,
other course, stale/old/future/restricted/missing original cannot supply preparation.
Unknown submission types, quizzes and external tools cannot be preparation targets.

Every quote must match a contiguous original inspected section. Unread pages and
continuations remain explicit, along with original item/resource coverage and
missing codes. Target and syllabus are pinned even when not quoted. At most8 source
pins. Same evidence key deduplicates without replacing history; at most20 saved
checklists, within the existing hard20-call limit. No task/responsibility/artifact,
course offer, message or ready-for-submission state is created.

The existing exclusive monitor lease, identity/scope checks and snapshot fence are
rechecked inside the original finish transaction. Partial inline sources without
published versions now include observation identity in the snapshot digest, so
changed partial text cannot commit through an older decision.

## Consumer boundary for M

Existing `Store.course_supervision_status(verified_user, supervision_id)` and
`find_course_supervision(...)` add `preparations: []`. Existing authenticated HTTP
routes return that projection; no new route or browser-supplied owner is needed.
Each record has `id`, `created_at`, `key`, `object_id`, `title`,
`kind="preparation_checklist"`, fixed `notice`, `excerpts`, `questions`, `evidence`
and server-recomputed `current`. Each evidence pin contains object/observation/version
IDs, original coverage/resource coverage/missing and `unread_continuation`.
`current` means the pinned limited evidence is still inspectable, never completeness
or approval to submit. Pause, disconnect, expiry, changed scope or source pins make
it false. Retain the historical checklist visibly marked stale; don't offer accept,
draft, file-download or WhatsApp dispatch buttons for this kind.

M owns a private course-supervision checklist view and API/UI consumer tests. Display
the notice, gaps, review/student-action excerpts and clarification questions. Current
course-offer acceptance/drafting/channel interfaces remain unchanged. An existing
course-service tick can select this new action after explicit activation; no worker,
budget, model call, migration deployment or live student operation is enabled by code.
