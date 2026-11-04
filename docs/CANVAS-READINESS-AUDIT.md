# Canvas assignment-readiness audit

Owner A, `codex/p1-canvas-readiness`. This is offline code/provider-documentation
analysis, not a fresh ECE 253 scan. It does not change the one-course plan, approve
collection or replace the already-approved bb626d3 Fireworks candidate.

## Findings and prepared correction

| Layer                      | Confirmed behavior                                                                                                                                 | Next action                                                                                                                                                                       |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| HTML body                  | Deployed HTML v1 always marks extracted text partial.                                                                                              | The already-tested opt-in v2 API and matching collector need separate bounded activation and a fresh scan. Existing observations cannot be relabeled.                             |
| Rubric absence             | Generic mapper treats omitted/null rubric as unknown. Canvas full assignment-detail responses omit rubric fields when no associated rubric exists. | New reader fix interprets this documented omission only after the exact full-detail GET, matching assignment/course identity, normal session checks and explicit unlocked status. |
| Assignment constraints     | Attempts, extension limits, groups, peer review and certain grading modes can introduce unmapped requirements.                                     | Preserve `assignment_constraints_unmapped`; inspect actual affected assignments before choosing the next mapping change.                                                          |
| Linked/embedded content    | Links, files, tables, images and unsupported HTML structures can still contain instructions.                                                       | Read permitted required documents or retain the gap. A text conversion cannot certify unread linked requirements.                                                                 |
| Course resources/freshness | An individual readable object does not close a partial resource, unfinished scan or stale observation.                                             | Verify real coverage and timestamps after any approved fresh collection. No model decision can declare these complete.                                                            |

The saved summary remains104 sources/90 inspectable for ECE253 at the previous
operator check, with partial/restricted/open resources. This audit did not requery
those counts or read actual assignment bodies. It therefore does not claim that
rubric omission is the only, or even the observed, blocker for a particular assignment.

## Narrow reader fix

Instructure's assignment serializer includes associated rubric fields when a rubric
exists. The reader already requests each authoritative assignment detail separately
from listing rows and requests no rubric exclusion. For an unlocked full-shaped
response with all rubric indicators omitted, the candidate returns a copied detail
with the existing canonical empty-rubric representation. No schema change or generic
mapper default changes. The provider response object is not mutated.

Explicit null, settings/usage/presence/comment indicators, missing full-detail fields,
and locked/unknown access do not trigger this normalization. Listing rows cannot
supply this evidence. Present rubrics are preserved. Independent extraction and
assignment-constraint gaps remain partial. This records no attached Canvas rubric;
it does not assert there are no grading requirements in the syllabus or instructions.

Primary references, checked November3:
[assignment API](https://developerdocs.instructure.com/services/canvas/resources/assignments),
[Instructure assignment serializer](https://github.com/instructure/canvas-lms/blob/master/lib/api/v1/assignment.rb).
Compatibility with CSU's live deployment still requires the bounded fresh check.

## Validation and next live order

The new regression fails against the previous reader. Candidate focused reader/mapper
checks pass; the full four-directory extension suite passes621 tests, zero skips.
Ruff/format, changed JS formatting and diff checks pass. GitHub candidate CI and
counterpart review remain separate. No new permissions, installation, scan, saved
observation mutation, model call or deployment occurred.

1. Keep this candidate separate from the approved bb626d3 model-only deployment.
2. Review the narrow omission semantics and full CI. Prepare the matching extension
   package only after combining reviewed source changes; do not silently replace the
   installed package or enable API v2 for an older incompatible collector.
3. Obtain scoped activation for compatible HTML v2 and the reader fix, then collect
   ECE253 under the existing account/scope without adding courses or opening quizzes.
4. Inspect the actual missing reasons and select one suitable assignment only when
   its instructions, required linked material, policy and constraints are available.
5. Preserve all unresolved gaps. A real inspect/wait decision can pass independently;
   a help offer, accepted draft and file delivery need their own readiness evidence.

## Combined collector package 0.3.3

M counterpart review6626273183 clears exact8cd3151 narrow reader interpretation;
it does not establish CSU live compatibility or authorize collection. The collector
candidate now incorporates the successful reviewed supervisor executablefe196c6 and
later evidence docs, while retaining the independently tested HTMLv2 implementation.
Package version0.3.3 distinguishes this preparation from prior inactive0.3.2.

Combined checks:621 extension tests/zero skips and163 focused Python tests pass,
including HTML conversion, supervisor protocol, providers/config/output limits.
Ruff/304-file formatting, changed JS formatting and diff checks pass. Fresh ignored
local package preparation verified identical permissions/host allowlist/CSP to0.3.2,
exact reader bytes and no credential files. Installed collector was not overwritten,
reloaded, paired, enabled or scanned. Full exact-candidate CI remains separate.

Prepared next activation for Akbar's review (not yet authorized): after fullCI and
review, deploy only this API candidate, retain model/draft/delivery shutdown, add
canvas.html.v2 to the existing extractor allowlist and load the matching0.3.3 local
collector. Select ECE253 only for this scan (preserve/review prior scope explicitly),
verify the same Canvas identity and run one resumable collection round with finite
request/time bounds. Store only the selected course's authorized readable content in
the existing isolated database; no quiz attempts, course writes or model/send calls.
Pause collection afterward and inspect original per-object/per-resource missing
reasons, not just the finished badge. Stop on login/scope mismatch or concrete errors;
no repeated full scans. Existing saved evidence is not rewritten or upgraded in place.
