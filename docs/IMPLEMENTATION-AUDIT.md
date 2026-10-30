# Implementation audit for revision 7

Inspected October 30, 2026. Local clean baseline before edits: bf5d321 on
codex/restore-autonomous-scope, based on integration a8cac79. GitHub #4 and open PR
heads were checked. No live provider retest, deployment or new application code in
this audit. This is a reuse/gap map, not an estimate of percent complete.

## Evidence and branch state

- #36 integration: a8cac79; combines source intake/private delegation/results with
  bounded runtime. Main does not yet contain the combined product.
- #40 diagnostics: ddd5ab1, separately reviewed; safe provider failure/usage evidence.
- #42 pause recovery: 224bc96 (executable a7db006), separately reviewed; 385 backend /
  113 web reported in its CI. Not a current combined-head test result.
- M #28: a383782 adds Canvas proposal to a344642 implementation; 114 local web tests
  reported for that implementation. Proposal is documentation, not a connector.
- #44: plan revision only. #24/A4 remains parked; migration008 excluded. Development
  ledger last confirmed001–007 +009. Recheck ledger before any future migration.
- Last live M2 attempt: first assessment failed with NotFoundError; no checked artifact.
  Last WhatsApp send failed131031 after provider acceptance; no successful live delivery.
  Continuous workers remain stopped. See [run report](M2-RUN-2026-10-29.md).

## Keep and reuse

| Existing files/component                                                                     | Verified role in code                                                         | Limit and next step                                                                                 |
| -------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| shared/auth.py, app/main.py, web/ Clerk flow                                                 | Verified identity and private account provisioning                            | Preserve; extend connection onboarding (M)                                                          |
| shared/db.py, runtime/worker.py                                                              | Leased durable tasks, checkpoints and bounded Meta tool loop                  | Not a semester supervisor; integrate reviewed recovery fixes (A)                                    |
| shared/model_client.py                                                                       | Meta Responses transport through OpenAI SDK                                   | SDK is transport, not OpenAI inference; diagnose live404 (A)                                        |
| shared/responsibilities.py, runtime/planner.py                                               | Model chooses next step of an existing responsibility                         | Keep as task planner under new supervisor (A)                                                       |
| shared/academic_memory.py                                                                    | Versioned sources, exact evidence quotes, source-bound duties                 | Extend freshness, coverage and retrieval; do not replace DB (A)                                     |
| shared/bound_responsibilities.py, shared/draft_intents.py                                    | Atomic private delegation and source binding                                  | Reuse for WhatsApp acceptance after new consent contract (A); M assembles                           |
| runtime/draft_requirements.py, drafting.py, verification.py, draft_format.py                 | Requirement assessment, draft/review/revision and deterministic format checks | Mostly scripted proof; fallible extraction; real end-to-end quality unpassed (A)                    |
| shared/artifacts.py, shared/academic_reads.py                                                | Private immutable artifacts and read projections                              | Add file rendering and scoped delivery, not public links (A/M boundary)                             |
| shared/delivery_store.py, template_policy.py; integrations/whatsapp*; app/whatsapp_worker.py | Delivery authorization, receipt states, templates, adapters                   | Proactive/button/document paths need extensions; actual delivery blocked (A contracts, M transport) |
| web/ connections, snapshots, private result views                                            | Working candidate UI and manual development intake                            | Keep controls/results; automatic connectors become normal onboarding (M)                            |
| contracts/ SQL, tests/, .github/workflows/ci.yml                                             | Scoped schema, isolated tests and CI                                          | Preserve; add migrations/tests for new behavior (A schema, owner-specific tests)                    |

## Change — concrete behavior found in code

| Finding                                                                                                                           | Required change                                                                                                                                        | Owner/order                    |
| --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------ |
| observe_source returns the old version on identical revision; retrieved_at never refreshes                                        | Separate last_checked from immutable version and use one freshness policy across readers/preflights/final commit                                       | A P1-A1/A2                     |
| _academic_memory exposes at most eight sources and 6,000-character excerpts; SourceObservation/BoundEvidence cap content at24,000 | Segmented full-source storage/retrieval, explicit completeness and bounded query budgets; never just remove limits and load a semester into one prompt | A P1-A2; M supplies extraction |
| _invalidate_memory blocks duties/tasks and revokes leases                                                                         | Retain stale-write protection, add reassessment and consent-aware continuation                                                                         | A P4-A1; inspect parked#24     |
| PlannerDecision is work/blocked/done; DraftPlannerDecision adds draft within explicit intent                                      | New semester supervisor/actions/goal state; preserve internal task planner                                                                             | A P2-A1                        |
| Conversation instructions explicitly exclude connectors, external work and automatic responsibility activation                    | Update dispatch/tools/prompts only when actual capability and authorization exist                                                                      | A P2/P3; M routes inbound      |
| Default worker runs a polling loop but no continuous deployed reasoning service is active                                         | Deploy/observe controlled continuous processes with budgets/recovery                                                                                   | M P2-M2; A P2-A2 limits        |
| Existing outbox authorizes completed replies; approved template requires complete reply_text                                      | Add distinct proactive offers, buttons, files and matched approvals; do not misuse reply-only contract                                                 | A C4; M P2-M1/P3-M1            |
| Private draft intent authorizes private work, not WhatsApp delivery; changed source revision blocks reuse                         | Explicit recipient delivery scope and reviewed revision/rescope rules                                                                                  | A C5/C6/P4; M consumer         |
| UI makes manual source entry and explicit web delegation central                                                                  | Connection-first experience and WhatsApp decisions; retain manual diagnostics                                                                          | M P1-M3/P3-M1                  |
| Tests and evidence are distributed across stacked PRs                                                                             | Consolidate reviewed commits and test the actual combined head                                                                                         | A P0-A1, M review              |

## Add — missing capabilities

| Capability                 | Required implementation                                                                                             | Owner                                          |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| Canvas extension           | Pairing, same-session reads, resumable paginated course/document/discussion collection, restricted host scope       | M                                              |
| Outlook                    | Delegated OAuth, refresh, notifications/renewal, delta catch-up, attachments and revocation                         | M; A encrypted storage/contract                |
| Sync protocol              | Versioned batches, scoped credentials, generations, coverage, cursors, idempotency and deletions                    | A store/schema, M provider/HTTP                |
| Course understanding       | Source-backed obligation extraction, cross-source matching, original-document retrieval                             | A                                              |
| Autonomous ownership       | Commitments, goals, investigative tools, semester supervisor and continuation                                       | A                                              |
| Scheduling                 | Persistent next checks, coalescing, adaptive follow-ups, cancellation, fairness and hard cost caps                  | A                                              |
| WhatsApp decisions/results | Buttons, free text, current-offer mapping, approved proactive messages and private documents                        | A intent/authorization, M transport/assembly   |
| Output                     | Checked Word/PDF rendering and immutable revisions                                                                  | A renderer; M file IO/delivery                 |
| Adaptation                 | Replanning, affected-draft revision, grade reasoning, submission tracking                                           | A reasoning/state; M fresh provider evidence   |
| Operations                 | Continuous process topology, health, shutdown/recovery, deployment rollback                                         | M; A runtime/cost semantics                    |
| Pilot readiness            | Account/credential/data deletion and retention, malicious-content tests, source failures, soak and student feedback | A shared invariants, M connector/UI/operations |

## Retire or remove from the active plan

- Remove manual-paste-as-completion and chatbot-first onboarding, not the useful snapshot
  code or fixtures. M changes student flows after automatic ingestion works.
- Remove institutional Canvas cloud OAuth as the initial critical path. It is a later
  option. Preserve M's proposal: its pagination, coverage, identity/digest and last_checked
  findings remain applicable. No rewriting or deletion of M's document in this task.
- Remove the blanket24-hour freshness rule only after its replacement reaches every
  consumer and tests; never remove stale-version/permission fences to unblock drafting.
- Remove Hermes migration, Teams/group chat, calendar API, handwriting and iMessage from
  the first-version dependency chain. Preserve them as named future work, not promised features.
- Remove stale base-branch and dated freeze instructions. Do not delete branches or mass
  merge historic PRs; verified consolidation and protected review come first.
- Remove unsupported80%-complete/code-reuse estimates, 'knows everything' promises and
  template approval assumptions. State exact tested coverage and blocked live behavior.
- Archive old long status/build-plan notes; keep brief evidence links and executable
  contracts. Do not archive away current blockers, spending limits or ownership rules.
- No application files are deleted by this planning revision. Any later code retirement
  must identify callers, migration/compatibility impact and replacement acceptance first.

## Cost and live evidence to carry forward

Recorded bounded total allowance is $2, not the available$150 credit balance. Last record:
known usage$0.00773075 plus unknown-use reservation$1.32 = $1.32773075 charged/reserved.
These are historical local records, not a fresh billing statement. Reconcile before
new calls; do not release a reservation just because a request failed or credits exist.
Earlier M2 approval was one synthetic workflow, at most10 requests/$1.50 within the
same$2 ceiling, no WhatsApp sends, continuous workers stopped. It is not permission
for an always-on pilot. Build cumulative hard limits before proposing that activation.

## Source references

- [Murtazo Canvas proposal, exact reviewed source](https://github.com/Akbarhoja/wrytely-agent/blob/a383782fd4835cb739b43270982b49be2f9ab33b/docs/stages/B2-CANVAS-PROPOSAL.md)
- [Current coordination](https://github.com/Akbarhoja/wrytely-agent/issues/4)
- [Claude plan reviewed by founder/Codex](https://claude.ai/artifact/SYcUqEpMsGYR1mADTgTL5N#461f6ac1-7203)
- [Chrome network requests](https://developer.chrome.com/docs/extensions/develop/concepts/network-requests)
- [Chrome background worker lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle)
- [Canvas resources](https://developerdocs.instructure.com/services/canvas/resources)
- [Microsoft mail notifications](https://learn.microsoft.com/en-us/graph/outlook-change-notifications-overview)
- [Microsoft mail delta](https://learn.microsoft.com/en-us/graph/api/message-delta)
- [Microsoft user consent controls](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/configure-user-consent)
- [WhatsApp policy](https://whatsappbusiness.com/policy/)

These support feasibility/design; they do not prove access to a specific school or
certify hackathon eligibility. Source/account behavior must be verified in P0.
