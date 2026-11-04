# One-course assembly acceptance handoff

Owner: M integration track. Use with the [service runbook](ONE-COURSE-SERVICES.md),
[shared delivery plan](../docs/ONE-COURSE-DELIVERY.md) and
[recording worksheet](../docs/ONE-COURSE-DEMO.md). This packet supplies the assembly
checks and evidence fields; it does not authorize live execution or publication.

## Order of work

1. Freeze an exact combined candidate after A imports/reviews M's changes. Record
   application SHA separately from documentation and PR merge-check SHAs. Require
   successful exact-candidate CI; do not substitute an earlier green run.
2. Resolve the selected provider through A's published budgeted factory. M reviews
   the service consumer. A owns adapter, prices, configuration and budget history.
   Do not replace the adapter or start a second diagnosis from the integration track.
3. Establish current course evidence readiness. A verifies required original sources
   and gaps; a readable partial body is insufficient for work authorization. A new
   converter cannot relabel old saved evidence or justify a scope change.
4. Establish channel readiness independently: account clearance, correct approved
   template purpose, linked consenting recipient and separate proactive consent.
   If unavailable, Akbar must decide the disclosed fallback before recording a
   replacement journey. The engineering track cannot mark simulated delivery live.
5. Only after a concrete bounded activation is approved, execute the applicable
   rows below and collect evidence once. Existing tests and this document are not
   activation permission. A failure can end the run without a second provider call.
6. Stop and reconcile; then record the demonstrated journey and its remaining gaps.

## Checks that require no live activation

Use an existing isolated worktree and a disposable test database. Read the active
local checkpoint before starting any database-reset suite; never share its database
with another running suite. Keep environment values and logs private.

| Check                              | Existing entrypoint                                                                     | Evidence and limit                                                                    |
| ---------------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Service startup, stop and recovery | `uv run pytest -q tests/test_course_service.py`                                         | Includes real Store restart and unknown-outcome fencing; mocked model/transport       |
| Connected signed journey           | `uv run pytest -q tests/test_signed_course_journey.py`                                  | Real Store and signed HTTP commands/receipts; scripted model/provider                 |
| Private student actions            | `uv run pytest -q tests/test_course_supervision_api.py tests/test_course_result_api.py` | Session ownership, offer decision, private file and revision boundaries               |
| Required regression                | `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest -q`               | Record exact SHA, actual totals and platform failures; no skipped-failure green claim |

Do not repeat unchanged passing suites solely for recording. Reuse their actual
results and label them as automated evidence. Installed extension, real inference,
native Word layout and phone receipt need their own observations.

## Bounded live acceptance record

Fill this table privately during an approved run. Store opaque IDs, source content,
account details, hashes and screenshots in ignored local evidence, not this public
file. A synthetic replacement must be labeled in every resulting demo claim.

| Step                  | Required observation                                                                                                      | Stop or handoff condition                                                                           |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Session and selection | Current verified owner, intended connection and explicitly selected course; actual coverage visible                       | Owner/scope mismatch or required missing source: stop; A owns source readiness                      |
| Supervision control   | Read-only lookup does not enable/refill; explicit enable/pause state persists across refresh                              | Unexpected enable, reservation refill or stale owner state: M app/web fix                           |
| Model decision        | Exact selected model/provider, one authorized reservation and a usable persisted typed result                             | Incomplete/error/unknown: retain hold, stop; A runtime/provider follow-up                           |
| Offer delivery        | Separate proactive consent and authorization; one outbox action; actual phone message plus matched signed delivery status | Provider acceptance alone is insufficient; unknown result is not retry permission                   |
| Student acceptance    | Signed linked reply or verified-session decision binds the intended current offer                                         | Replay must return the same action; wrong account/context must not create work                      |
| Checked file          | Private authenticated download opens in Word; intended text/layout and check identity observed                            | Unchecked/stale source or unusable document: stop; A renderer or M download consumer as appropriate |
| Phone file            | Explicit student request, correct immutable file and matched receipt                                                      | Upload success is not document delivery; uncertain upload/send remains unknown                      |
| Revision              | Explicit feedback yields a new checked version while original remains available                                           | Overwrite, wrong artifact or replay-created duplicate: stop and report owning boundary              |
| Changed evidence      | Authorized new source version invalidates stale offer/work and triggers reassessment                                      | Never edit real course content to manufacture a change; use a labeled synthetic fixture             |
| Restart and pause     | Measured start/end, persisted due time/reservations, no duplicate action; pause fences subsequent work                    | A brief offline test is not a laptop-closed or continuous-operation duration claim                  |

## Stop and reconciliation

- Stop only the processes started under the bounded approval. Pause the intended
  monitor and disable its budget without resetting reservations or historical holds.
  Record authoritative status after cleanup; process exit alone is insufficient.
- Preserve uncertain inference, upload and send outcomes. Do not release holds,
  retry, change provider or raise the ceiling to make the demonstration finish.
- Recheck the intended service health and protected unauthenticated rejection if
  the approved activation changed that service. M must not change A's active
  deployment/configuration during his run.
- Record actual known/held liabilities, remaining allowance, final monitor state,
  active processes and unresolved actions privately. Do not infer billed charges
  from conservative reservations.
- Publish a redacted summary only after review. Link the exact CI and technical
  handoff; identify each row as passed, blocked or untested and synthetic or live.

## Completion rule

M implementation delivered, combined CI green, a usable checked document and a
live end-to-end phone journey are separate outcomes. Mark the prototype accepted
only when the required journey has actual evidence and Akbar accepts remaining
limits. Do not label original P0–P6, broad semester supervision or a 72-hour pilot
complete from this one-course run. Submission, deployment, spending and business
decisions remain separate authorized actions.
