# Student-requested private revision v1

A owns runtime/Store; M owns authenticated HTTP/WhatsApp decision assembly.

Store.request_private_artifact_revision(verified_user, artifact_id, instructions,
request_key) -> {task_id,state,parent_artifact_id}. Instructions1–4000characters,
request key1–100; student owner comes from verified session/signed linked inbound,
not body/model fields. Explicit user request only, not automatic source permission.

Reuses original responsibility scope, private artifact proofs, policy/rubric, task
queue, drafting worker and verification. Original artifact remains immutable. Stable
parent+request key deduplicates repeated replies/crash recovery; changed instructions
under the same key conflict. Requires current checked schema2 artifact, current bound
sources, unpaused agent and active/done responsibility. Preserves original step/global
pending limits; no unbounded revision loop or authority expansion. Pending academic
work holds the revision request until that work finishes.

Creation atomically supersedes obsolete planning continuations (blocked with a
controlled superseded_by_revision reason), reopens an explicitly completed duty if
needed, creates one academic revision task and saves parent/check/body/instructions
in its existing drafting specification. No new body is accepted from the browser.
The worker passes the full prior draft and student feedback into the original
checked generation/revision pipeline; policy/source checks run again. A successful
revision creates a new artifact/check, never overwrites v1 and does not restart the
old planner. Superseded plan cancellations cannot themselves mark the new duty as a
model failure. Real failed academic work still blocks normally.

M can return the task ID and use existing responsibility artifact/private result
reads to find v2. Use the existing private DOCX renderer per artifact version;
rendering grants no WhatsApp/file delivery consent. No public stable artifact URL.
No model call, notification, provider send, deployment or migration is implied by
requesting a revision. Current scripts/real-Store tests are separate from live Meta
quality and phone/file acceptance.
