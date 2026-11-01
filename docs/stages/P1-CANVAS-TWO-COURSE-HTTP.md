# Two-course collector lifecycle through actual HTTP and Store

Owner: Murtazo (`murtazokhon-tech`), [#127](https://github.com/Akbarhoja/wrytely-agent/issues/127), [claim6554737880](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6554737880). Original component base was own #126 `e7558f7`; final acceptance uses reviewed A integration #128 `1cbb61d` on `codex/canvas-two-course-integration`, recorded in [6554905173](https://github.com/Akbarhoja/wrytely-agent/issues/127#issuecomment-6554905173). The existing M sole-editor harness agreement was explicitly retained by Akbar in [6554573050](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6554573050) and [6554707805](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6554707805).

## Actual boundary and scenarios

The Node driver calls production `collectAssignmentPage()` using synthetic, paginated Canvas course responses and two synthetic assignment HTML responses. Course scope is `all_active` with no posted course IDs. Collection obtains course/assignment IDs from those responses and the existing journal ledger; no manual metadata or extracted text is supplied to the upload operation. Only the Canvas provider/session verifier are synthetic. The private HTML extraction endpoint, inert parser, mapped capture, ingestion routes and Store transactions are the actual implementations.

The existing fixture rewrites only allowlisted Wrytely requests to an ephemeral127.0.0.1 service; source responses are returned locally and never fetched externally. The driver is recreated on each tick against the same private fake storage, exercising the production durable state. No alternate parser, Store, credential authority or upload path exists in this test.

Both new scenarios perform three complete scan cycles:

| Cycle                             | Immutable versions | Events      | Observations/checks | Objects     |
| --------------------------------- | ------------------ | ----------- | ------------------- | ----------- |
| Initial two-course collection     | 2                  | 2           | 2                   | 2           |
| Identical repeat                  | 2, same IDs        | 2, same IDs | 4                   | 2, same IDs |
| One changed deadline on course101 | 3                  | 3           | 6                   | 2, same IDs |

The unchanged repeat creates new observation/check evidence without a new content version or event. The changed deadline retains identical title/body but creates exactly one new immutable version and one `source_changed` event for the changed assignment; the other course retains its version. A `source_changed` event must reference both that exact object and its new observation.

The second scenario additionally loses the first successful academic HTTP response **after actual server commit and response consumption**. A fresh client replays the original full pending body/key, and both assignment-read and extraction-request counts stay unchanged during recovery. Final counts remain the same as the no-loss lifecycle: six distinct academic batch keys, twelve total course/academic batch receipts and no duplicate observation/version from retry. This is transaction-receipt recovery, not permission to retry unknown external messages.

## Independent parent evidence

After each successful actual finish transaction, the fixture reads committed database state before returning the HTTP response. The parent inspects all three snapshots, rather than trusting child-reported counts or final totals alone. It checks:

- Exact initial/repeat version and event ID equality, and exactly one added ID after the deadline change.
- Raw object count and stable course/provider/object identity, actual owner/origin and observation-to-version reference/content linkage.
- Exact normalized payloads and canonical digests, including effective dates, unchanged text and explicit HTML gaps.
- Every immutable version's retained `canvas_evidence_payloads` content/digest and matching `external_revision`, including the old deadline metadata after the new version exists.
- Changed-event object/observation linkage, three finished checkpoints, retained resource counts and stored partial finish receipts.
- All academic source pointers remain unpromoted and no complete-version pointer is invented from partial extraction.

The HTML deliberately contains a script and link. The real parser omits script text and returns `html_text_only`, `linked_content_unread` and `nontext_content_unread`. Both assignments and aggregate scans remain partial. A passing lifecycle does not mean linked materials or full academic coverage were collected.

## Verification and review

The two new scenario names failed RED before driver support. Initial focused lifecycle/loss execution passed 2 cases in 22.07 seconds; all 19 existing/new HTTP cases subsequently passed before assertion strengthening. Independent review then requested direct changed-event and immutable-metadata assertions; those were added rather than inferring linkage from counts. The strengthened cases passed 2/2 in 22.03 seconds. All 365 extension Node tests pass with the reused #125 environment policy. Required Ruff check/format and scoped formatting/diff checks pass.

The original component full run passed 781 cases and failed the existing equal-instant source-revision conflict test during the Denver DST overlap. That failure also reproduced on unchanged #125. Akbar had already fixed the shared comparison in `ec6f0c9`; independent candidate memory/storage/section verification passed 96 cases in a Denver-timezone database. The final branch uses that exact reviewed candidate without editing shared code or changing the full-run database timezone. Final combined `uv run pytest -q` passed 966 cases, including all 19 actual HTTP scenarios, in 700.27 seconds with two existing warnings and no skips. The focused 19-case run passed in 58.28 seconds. Required Ruff check/format and all 365 extension tests passed on this exact candidate plus the owned test delta.

Fresh independent review checked the real boundary, snapshots, loss timing and recovery, and independently ran syntax/diff plus21 environment-policy cases. It did not run the database/provider suites; database results are the implementer's execution. Final stage documentation and exact evidence updates are checked separately. Remote CI, real macOS combined rerun, Akbar counterpart review and live acceptance remain distinct.

This PR changes only four claimed harness/scoped-document files. The #125 environment helper/test/doc prerequisites and #126 collector already exist unchanged in the reviewed #128 base; original component reuse via `3c162c8` is historical context, not additional final PR changes. Production source, schemas, runtime, shared files, CI and STATUS are unchanged. Parent environment filtering and canary exclusion remain strict; the existing child policy permits only the exact Darwin runtime-added name on Darwin. No test is skipped to pass a platform.

## Remaining milestone work

This proves the synthetic two-course initial/repeat/changed-deadline path through the actual collector, HTML API and Store. It does not prove real browser suspension or restart, installed-host operation, live Canvas access, automatic unattended scheduling, remaining academic kinds or complete linked-document extraction. Those remain P1/P2 acceptance work. No live account/provider call, grant, message send, model spend, install, deployment or main merge occurred; Chrome stays untouched and automation stays off.

Akbar's exact document wire revision `7f4f09f` and C4–C7 wire revision `3b86710` were re-reviewed and agreed as DESIGN after the named clarifications. This does not implement or activate their upload/action methods. Schema1 remains the only collector path in this slice; future document/delivery consumers need their respective implemented boundaries and validation. P0 WhatsApp delivered-reply proof and eligible human baseline approval remain separate; Outlook remains optional/paused.
