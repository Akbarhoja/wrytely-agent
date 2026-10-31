# Canvas assignment fixture mapping plan

Execute directly under the existing provider-fixture readiness work; claim
[#57](https://github.com/Akbarhoja/wrytely-agent/issues/57).

**Goal:** Map a synthetic Canvas assignment and explicitly extracted content to the
agreed C2 v1 source fields, with provider identity separate from content hashing.
**Base:** Own `33e4b94` (#56), which remains pending counterpart review.
**Files:** New assignment-observation module/test and scoped spike/plan only.
**Contract:** [C1/C2](../../contracts/CONNECTION-SYNC-v1.md), agreed at `ccf84dc`.
**Architecture:** Pure browser-side mapper; reuse the existing canonicalizer. No fetch,
storage, auth, extraction engine, task creation or proposed Store/API consumer.

- [x] Read active claims/current coordination and official Canvas assignment shape.
- [x] Claim exact new files before edits and notify Akbar.
- [x] Write fixtures and observe missing-module failure.
- [x] Implement `mapAssignmentObservation(raw, options)` with explicit course/content
      binding, known fields, decimal strings and ordered rubric data.
- [x] Preserve null/unknown versus known empty, require requesting-student context for
      effective dates and force partial/restricted evidence for gaps/known locks.
- [x] Verify content-affecting changes alter digest; receipt/update metadata do not.
- [x] Run Node, required Ruff/format/full disposable backend and scoped formatting checks (60 Node / 415 backend).
- [ ] Publish a stacked draft and request review/serialized STATUS row.

Caller-provided evidence labels are not verified identity or consent. Production
collection still waits for P0-M1 access checks and implemented/reviewed P1-A1 persistence.
