# Canvas assignment mapping — offline readiness

Owner Murtazo/local assistant; [claim #57](https://github.com/Akbarhoja/wrytely-agent/issues/57).
Branch `codex/canvas-assignment-mapping`, stacked on own #56 at `33e4b94`.
The parent compatibility implementation still requires counterpart review; stacking
does not supply that review or close the live P0-M1/P1-A1 gates.

## Scope and interface

`extension/canvas/assignment-observation.mjs` provides one pure function:

```js
mapAssignmentObservation(raw, {
  courseId: "101",
  dateContext: "requesting_student", // or unverified; default is unverified
  extracted: {
    courseId: "101",
    assignmentId: "17",
    text: "Already extracted source text.",
    coverage: "partial",
    missing: ["linked_file_unread"],
  },
});
```

The result is `{providerIdentity: {course_id, provider_id}, digestPayload}`. Only the
content envelope enters the hash. The caller must eventually add verified connection,
institution/origin and generation namespace through actual shared APIs; these two
provider IDs do not constitute ownership or a globally unique source identity.
No source hash, posted course ID or evidence label grants access or permission.

The helper validates course/assignment labels on both the raw object and supplied
extraction result. It cannot independently prove where those inputs came from. Future
trusted assembly must derive session/connection scope rather than accepting browser
claims as authority. No network, session read, account connection, upload, storage,
runtime task, policy decision or readiness change is implemented here.

## Mapped representation

The digest payload has exactly v1 `kind=assignment`, title, supplied extracted content,
coverage/missing and the agreed seven field names: due_at, unlock_at, lock_at,
points_possible, submission_types, rubric, published. Unknown provider metadata is not
copied wholesale into canonical fields. No observed_at/updated_at, source URL, owner ID,
policy verdict or caller-supplied readiness enters the content digest.

The existing canonicalizer handles NFC/LF, UTC microseconds, safe JSON and final 1 MiB
canonical-byte bounds; this helper does not implement a second digest algorithm.
Supplied content is bounded to 24,000 Unicode code points; longer text requires
segmentation rather than clipping. Title bound is 500 characters. Positive decimal
Canvas identifiers accept safe integers or up to 20-digit strings without guessing
rounded IDs. These are conservative mapper bounds pending real-provider validation.

Points become normalized base-10 strings, including expansion of numeric exponent
notation. Nonfinite or unsafe numeric values and overlong decimals reject. Assignment
points cannot be negative; source rubric penalties can retain negative decimal points.
Points possible are neither a course weighting nor a prediction of final grades.

Submission types form a sorted unique set. Rubric criteria and ratings preserve source
order and reject duplicate IDs after C2 NFC/LF normalization. Omitted description/point
properties and omitted criterion ratings add explicit coverage gaps; observed null or
empty values remain distinct from omission. A missing/null rubric stays unknown (`null` plus a gap),
while an observed empty array stays known empty. Nested criterion data preserves id,
description, long_description, points, ratings, range/scoring flags and learning-outcome/
vendor references; ratings preserve id, descriptions and decimal points. Unrecognized
rubric fields reject rather than vanish. These nested fixture conventions and bounds
(100 criteria/50 ratings) require counterpart review before production consumers.

## Dates, extraction and coverage

Canvas documents assignment date fields as applying to the requesting user when
overrides exist, and describes the assignment body as an HTML fragment. This mapper
therefore does not choose dates from all_dates or parse the HTML description itself.
[Canvas assignment reference](https://developerdocs.instructure.com/services/canvas/resources/assignments).

Dates enter canonical fields only when trusted future assembly establishes the
requesting-student context. With the default `unverified` label, all three remain null,
coverage stays partial and the missing list records the gap. Missing fields differ
from an explicitly observed null date. The label is only an adapter input and never
replaces actual session/identity verification.

Extraction is a separate required input, bound to the same course and assignment.
No body is fabricated from raw HTML or a linked filename. A complete extraction with
unread dependencies remains partial, and a known lock forces restricted coverage.
Source-like instructions remain ordinary text; none can create runtime authority.

Known constraints outside the agreed field map produce
`partial / assignment_constraints_unmapped`: allowed file types or bounded attempts,
nonempty rubric settings, peer/group work, non-points grading and external-tool work.
No new shared fields are silently introduced. The coverage regression was observed
failing (complete despite an unmapped file constraint) before the correction.

This marker is not full capture of those constraints, and their changing values are
not independently represented in the v1 digest. Such partial observations must not
support full readiness. Their representation requires a reviewed contract/mapper
extension and original evidence retrieval before production collection relies on it;
the precise request is posted in coordination #4. This list is conservative, not a
claim that every possible Canvas requirement is recognized.

## Verification and next gate

The fixture tests cover stable identity, cross-course/assignment binding, unknown dates,
missing/empty rubric, decimal normalization, ordered criteria, unchanged metadata,
changed due/rubric evidence, malformed values, immutable input, locks and partial gaps.
Only synthetic data is used; no actual university content or credentials were read.

Run:

```sh
node --test extension/canvas/source-digest.test.mjs extension/canvas/assignment-observation.test.mjs
```

Current Node evidence is 32 mapper + 28 digest cases. Required repository lint/format
and full isolated-Postgres validation pass: **60 Node cases and 415 backend tests**, plus
Ruff lint/format, Prettier and whitespace checks. The fresh local test database was stopped
after validation. Two existing dependency/test-key warnings remain. Python/backend files
are unchanged; this backend count belongs to the contract-based branch, not the separate
Outlook #54 branch.

Independent read-only review found two defects before publication: rubric IDs could
collide after normalization, and omitted rubric fields could retain complete coverage.
Five focused regression cases failed before the fixes; the final 60-case suite passes,
and the reviewer confirmed both fixes with no remaining concrete blocker in this scope.
Opposite-owner review and the live/provider gates remain separate.
No new web build or live-provider validation is implied.

Next: opposite-owner review, selected contract-field decisions and implemented P1-A1
storage. Actual course discovery, HTML/file extraction, pagination/checkpoints,
two-course collection and session/restart tests remain future integration and live
acceptance. STATUS stays serialized through Akbar's active claim. Existing #52/#54
diagnostics and #56 compatibility remain separate reviewable checkpoints.
