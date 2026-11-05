# Canvas feasibility implementation plan

> Execute directly in this session. P0-M1 is a disposable diagnostic spike under
> the existing revision 7 work order, not the production collector.

**Goal:** Determine which Canvas session reads work before implementing paired sync.
**Architecture:** A locally prepared MV3 service worker makes bounded GET requests
to one authorized HTTPS origin. It reports counts and controlled failures only.
**Tech stack:** Browser Fetch, JavaScript modules, Node's built-in fixture runner.
**Spec:** [P0-M1](../../WORK-ORDERS.md); claim [#51](https://github.com/Akbarhoja/wrytely-agent/issues/51).
**Base:** `9bbea970b7485b5286dd4d50c1c7fe64af56bdf1`.

## Tasks

- [x] Inspect current coordination, work orders, baseline and interface proposals.
- [x] Claim only extension feasibility files; preserve Akbar's shared/runtime ownership.
- [x] Implement exact-origin, GET-only, bounded JSON reads and opaque pagination.
- [x] Check session identity around each resource; discard reports after a switch.
- [x] Read course discovery plus scoped inline syllabus, assignment/rubric and
      discussion-view samples; label unsupported documents and partial scope.
- [x] Add fixtures for pagination, unsafe links, limits, login HTML, account switch,
      restricted resources and redacted output.
- [x] Provide an ignored unpacked build generator with only one host permission.
- [x] Run required repository checks and report exact evidence.
- [x] Publish technical reviews of #46/#48 without claiming human approval.
- [ ] Confirm exact origin, consenting course scope and extension installation permission.
- [ ] Run tab-open/closed, restart, expired-login and account-switch live matrix.
- [ ] Read an actual syllabus document and record extraction gaps before claiming P0-M1.
- [ ] Obtain opposite-owner review and record the completed acceptance evidence.

## Constraints and next steps

No shared APIs, migration, cloud upload, cookies/password export, paid inference,
scheduler, production configuration or send is added. Diagnostic course IDs restrict
consenting reads; production P1 must discover courses without manual IDs. A successful
fixture or course list cannot close P0-M1. File attachments/PDF extraction and resumable
sync remain unimplemented. P1 waits for agreed C1/C2 and implemented shared persistence.

After the Canvas access result: claim P0-M2 Outlook OAuth/consent/delta feasibility,
then P0-M3 WhatsApp account recovery and actual signed delivery evidence. Claim one
slice at a time. Later work follows the ordered P1–P6 Murtazo work orders.
