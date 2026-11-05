# P1 integration candidate — October 31, 2026

Owner A; [coordination claim](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6554049287).
This is an isolated development candidate, not protected-main integration or deployment.

## Exact inputs and scope

- A parent42cb2f7 (#120): existing shared storage/read/freshness fixes,014 change details,
  bounded P0 diagnostics and proposed #118/#119 interfaces. Those separate proposal
  agreements are not implied by this candidate.
- M merged parent47d076d8866a04c7d4f533070832d14a950dbfc0 (#114): existing pairing,
  source-connection/discovery/academic API, course collector, assignment mapper and
  durable assignment upload journal. Its prerequisite #110 includes10 synthetic
  actual-client HTTP scenarios. #116's7 additional assignment scenarios are NOT in
  this candidate; that PR remains separate pending its harness correction.
- The A shared/contracts/store-ledger test trees remain byte-identical to42cb2f7.
  Incoming app/extension trees remain byte-identical to47d076d. No ownership takeover,
  collector implementation rewrite or test-harness workaround occurred.
- A CI change pins Node24 in foundation for actual-client tests, and extends the
  existing extension job from3 to all8 actual test files. No missing-file skip or
  disabled failure assertion. Existing bounded diagnostic CI job stays separate.

## Independent component review

A inspected #112 DTO/route bounds, credential ownership, controlled errors, canonical
NFC sizing and partial/replay/rollback/denial checks. Its app/canvas_sync_api.py and
API tests match exact7d400010 Git blob IDs in the tested #116 archive. Academic and
source-connection API run:74PASS on disposable Postgres (one existing warning).

A inspected #114 mapping/provenance, canonical page validation, v1→v2 journal
migration, same durable lock/pending-first recovery, exact receipt/digest checks,
incomplete progress and resource completion guards. Seven journal/mapper source/test
files match exact47d076d Git blobs in the tested archive.310 extension cases pass.
No scoped blocker found in those component boundaries; actual HTTP compatibility
and installed browser behavior remain separately unproved on this computer.

## Combined verification

- Full disposable local backend:804PASS,10FAIL,2 existing warnings in43.27s. All10
  failures occur in the actual-client test's configuration phase, before client/API
  transaction execution. They are not hidden or skipped.
- Node24 extension tests:310PASS across all8 files.
- Separate operator diagnostic Node tests:64PASS.
- Web:114PASS across9 files; TypeScript passes. No web source change.
- Ruff lint and format (159 files), changed CI formatting and diff checks pass.

Migration014 ran only in disposable tests. No retained migration, connector grant,
installed extension update, live source read, model request, WhatsApp send, worker
activation or deployment. Existing production and Chrome are untouched.

## Blocking evidence and next handoff

On this Mac Node adds __CF_USER_TEXT_ENCODING after the parent passes only allowed
LANG/LC_ALL/PATH names. The driver then rejects it under its strict environment guard.
A reproduced this in #116 and [reported the exact cause](https://github.com/Akbarhoja/wrytely-agent/pull/116#issuecomment-6553629521).
The candidate's inherited10-scenario harness has the same guard. M remains editor;
A did not broaden the whitelist, wrap/remove the variable or fake a passing run.
M should supply a narrow reviewed platform policy preserving credential/canary
exclusion; A then reruns all actual cases and reviews #116's additional assignment
proof. Linux CI may differ and is reported separately, never substituted for this run.

M's active assignment-collection slice has not been handed off. This candidate
can accept mapped, already-extracted assignment pages but is NOT full permission-aware
assignment fetching/parsing. Installed host, two real courses, recurring sync, changed
deadline through actual collector→HTTP→Store, and complete source kinds/documents
remain required. No manual source paste or direct-Store test substitutes for them.

After the harness correction and collector handoff, A reviews exact code/fixtures,
combines accepted changes, verifies two-course initial/repeat/changed-deadline flows,
then separately plans consenting live access. #118 document wire and #119 operations
agreements, P0 reviews and WhatsApp delivery remain their own gates. Do not merge
this known-failing candidate into protected main or declare P1 complete.
