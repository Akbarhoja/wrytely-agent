# M integration evidence

This is a review and demo handoff for the one-course prototype. It separates
implemented behavior, synthetic acceptance and live prerequisites. It is not a
release approval or a claim that the complete academic agent works live.

## Independent work checklist

| Work item                                 | Actual disposition                                                                                                                                                                                         |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Finish regression and CI                  | Worker fix `5978ae6` has 63 related delivery checks passing; its full local suite and current-head CI remain pending at this checkpoint                                                                    |
| Review and fix app, web and transport     | Worker origin configuration, interrupted-action recovery and malformed authentication-response handling reproduced and fixed; newest web snapshot `6cb452f` passes 157 tests, TypeScript and webpack build |
| Exercise downloads, revisions and restart | Real disposable Store, signed HTTP commands, authenticated original/revision downloads, immutable original, stale-source rejection and simulated dispatch/restart checks pass; providers are scripted      |
| Prepare demo evidence                     | Synthetic HTTP response files, native Word previews and hashes are included below; operational sequence remains in the existing acceptance runbook                                                         |
| Review counterpart changes                | Adapter, diagnostic boundary and corrected linked-file candidate reviewed; new preparation projection has been requested and is not implemented on M's side yet                                            |

The pending full run uses the same Python snapshot as `5978ae6`; later web changes
are verified separately. Earlier green combined-candidate CI cannot be transferred
to a newer executable head. The previous local full run at `fd7f6fb` had 1827 passing
tests and three known Windows PDF failures, not an all-green result.

## Synthetic download to native Word proof

The existing [signed journey](../tests/test_signed_course_journey.py) reuses the
[original one-course journey](../tests/test_one_course_journey.py). An ignored local
observer captured successful file GET responses without replacing authentication,
Store actions or response results. The test session verifier and every model and
provider response remain fixtures. The check report is scripted, not an independent
academic assessment.

At reviewed candidate `d3d0ff1`, the journey passed one test in 16.78 seconds with
one existing Starlette warning. Six signed command requests/replays and two signed
callbacks reached the real Store. The journey verifies:

- Explicit acceptance and revision replay retain the existing action identities.
- Original and revised downloads return private, non-cached bytes matching their
  response hashes; the stored original remains immutable.
- Source changes reject a stale download with HTTP 409.
- Simulated upload/send and restart behavior do not create another dispatch.

The exact original and revision response bytes opened read-only in Microsoft Word
16.0 and exported to one page each. Both rendered pages were inspected: readable
text, no clipping, and visible AI disclosure and fictional source reference. Opening
them did not alter the original DOCX hashes.

| Synthetic fixture  | Download                                                              | Native Word preview                                             |
| ------------------ | --------------------------------------------------------------------- | --------------------------------------------------------------- |
| Original           | [Original Word file](evidence/m-integration-20261104/download-1.docx) | [Original page](evidence/m-integration-20261104/download-1.png) |
| Persisted revision | [Revised Word file](evidence/m-integration-20261104/download-2.docx)  | [Revised page](evidence/m-integration-20261104/download-2.png)  |

[Machine-readable evidence and hashes](evidence/m-integration-20261104/manifest.json)
identify the exact files. These contain only existing synthetic fixture content.
No real course documents, account data, credentials or native PDF metadata are
included. The previews show a short example, not the complete student interface.

An additional ignored serializer-only test opened two longer synthetic inputs of
1146 and 1242 words, five pages each, with Unicode, disclosure and fictional
references preserved. That test does not exercise persisted revisions or HTTP.
Literal body paragraphs can leave section labels at page bottoms; semantic heading,
table and equation layout is not proved by these exports.

## Recording and reproduction

Use the [shared demo worksheet](ONE-COURSE-DEMO.md) for the product narrative and the
[assembly acceptance handoff](../deploy/ONE-COURSE-ACCEPTANCE.md) for prerequisites,
test entrypoints, evidence fields and cleanup. Do not start a provider worker to
reproduce this packet. Use only an explicitly designated disposable test database,
and do not run a reset suite while another owns it.

If these fixtures appear in a video, label them **synthetic data and simulated
providers**. A native Word window demonstrates file usability only. It cannot
stand in for real source readiness, a live model decision, a student phone message
or a measured laptop-closed run. Do not imply response latency from an edited cut.

## Outstanding gates and ownership

- **A collector track:** actual linked file bytes, extraction and publication,
  assignment provenance, and remaining source gaps from the bounded real refresh.
  M's corrected `d3d0ff1` review is complete; no real-file result is supplied by it.
- **A runtime track:** a tested, owner-bound projection for the newly requested
  private preparation workflow. Preparation must retain source pins and missing
  reasons and remain distinct from a checked draft or submission-ready result.
- **M integration track:** finish the current worker regression/CI, consume actual
  published preparation and file-readiness handoffs, and fix concrete app/channel
  findings. Do not build a parallel runtime, source reader or persistence model.
- **Account owner:** current WhatsApp business, template and webhook readiness,
  consenting recipient and a concrete bounded delivery approval. Historical unknown
  sends are not retry candidates. Telegram has not been approved as a fallback.
- **Shared acceptance:** a real appropriate checked draft/revision, actual phone
  receipt plus matched signed delivery evidence, and measured operational duration.

No paid calls, deployment, collection, new permissions, external sends or protected
main merge are authorized by this document. The original P0–P6 roadmap and broader
semester/pilot acceptance remain separate.
