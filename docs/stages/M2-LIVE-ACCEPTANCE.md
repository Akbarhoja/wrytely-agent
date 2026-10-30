# M2 development student-path acceptance

Status: **Prepared; every live case is Not run.** This is an operator checklist,
not authorization to use a provider or migrate retained data. Murtazo owns the
student path/evidence; Akbar owns existing development setup/runtime operation.
Prepared against #28 `8268e27344f3bbad1571f0e8f7959e6f4f49052c`.

Use the four fictional inputs and content criteria in
[M2-ACADEMIC-SCENARIO.md](M2-ACADEMIC-SCENARIO.md). The controlled run uses manual
snapshots through the actual student interface; it does not prove a real course
or group connector, automatic commitment discovery, WhatsApp delivery or A4.
The older scenario's direct Store setup is internal evidence, not the student
authorization path. Here, use the implemented consent form and atomic API.

## Preconditions — all must be confirmed

| Gate      | Required evidence                                                                            | Status  |
| --------- | -------------------------------------------------------------------------------------------- | ------- |
| Revision  | Exact reviewed combined head containing8268e27 and passing CI                                | Pending |
| Operator  | Named Akbar-side operator; existing isolated development services                            | Pending |
| Database  | Explicitly designated isolated development DB; migration009 application approved separately  | Pending |
| Identity  | Existing Clerk development setup; two consenting test-account aliases                        | Pending |
| Model     | Existing development credential/model permitted for this run; values stay in secret controls | Pending |
| Usage     | Explicit numerical request ceiling, operator invocation ceiling and any spend ceiling        | Pending |
| Isolation | Other queues/workers stopped; no unrelated pending duties; outbound worker stopped           | Pending |

Do not paste keys, DB URLs, phone numbers, email addresses or raw provider bodies
in this sheet, chat or issues. Record aliases and redacted outcomes. Configuration
presence is not acceptance. Setup/migration and real model usage are separate
actions; this sheet does not grant their approval.

## Concrete proposed run — approval and owner bound review pending

One fictional private duty, four snapshots, one authorizing account and one
read-only isolation account. No classmates/instructors, external messages, uploads
to third-party course systems, sharing or submission. Outbound dispatch budget:0.

Proposed ceiling:35 logical model requests and at most5 explicit single-claim
worker invocations. Proposed worker settings: max_episode_turns=6, max_attempts=1;
the existing API owns max_steps=6 and max_revisions=2. These are proposals, not
current approval or a new global spending limiter. Stop earlier on failure or a
ready result; reaching the ceiling without completion is a stopped/incomplete run.

The source-code bound to confirm with the runtime owner before approval is:
planning at most2 model calls (initial requirement assessment plus planning),
ordinary analysis at most6, and one drafting claim at most7 (one preflight plus
three generation/review pairs). The SDK has max_retries=0. Thus reserve7 calls
before each invocation; at most5 invocations would permit at most35 requests
under these exact assumptions. A changed model client, retry/turn/revision setting
or worker implementation invalidates that calculation. Persisted usage may omit
a response lost before recording; never treat the event count as a billing cap.

The existing command is `python -m runtime.worker --once` in the configured
development environment. It is a real provider action, may consume multiple
requests, and claims the next eligible task rather than a browser-selected ID.
Do not run the continuous loop or WhatsApp worker for this acceptance. Inspect
the saved transitions and remaining reservation after each explicit invocation;
do not invoke again without enough approved allowance. No command is run by
preparing this document. Obtain owner confirmation of the bound/invocation and
human approval of the concrete usage/setup scope before execution.

## Student flow and observable evidence

| Case            | Action and required observation                                                                                                                                                         | Live result |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| S1 sign-in      | Sign in as Cedar through existing Clerk; verify private workspace and account alias                                                                                                     | Not run     |
| S2 intake       | Paste each of the four fictional inputs separately; server records snapshot coverage/time/version; saving starts no task                                                                | Not run     |
| S3 decision     | Select all four snapshots, enter the scenario's private comparison objective and explicitly check consent once; save original receipt                                                   | Not run     |
| S4 continuation | Freeze inputs; operator permits bounded existing worker claims; inspect agent-selected useful next task and persisted continuation without manual task upgrade or extra student prompts | Not run     |
| S5 status       | Refresh controlled status with GET; distinguish saved/pending, blocked and ready; refresh itself creates no work                                                                        | Not run     |
| S6 review       | Read the private draft, both source quotes, citations, separate exact disclosure and saved checks; independently check every scenario criterion                                         | Not run     |
| S7 format       | Confirm saved count is250–300 inclusive under whitespace-token convention, disclosure matches the fixture exactly and is absent from body; inspect quoted range evidence                | Not run     |
| S8 isolation    | Second consenting account cannot list/open Cedar's sources, duty/status or artifact; absent and other-account detail are indistinguishable                                              | Not run     |
| S9 restore      | Reload/sign out and back in; same duty/result restores without new authorization/task; session changes clear unsaved private fields                                                     | Not run     |

For S4 record the selected task kinds, saved results and episode boundary. A
private draft returned by a direct model call, manual drafting configuration or
scripted test is not live student-path acceptance. A blocked or needs-revision
result is legitimate evidence, not a pass; preserve it rather than forcing ready.
Do not retry an ambiguous request with a new key. Reconciliation may re-use the
original consent request/key only when still within approved scope.

## Stop and record

Stop on unexpected identity/data, missing permission, migration mismatch, unknown
provider outcome, budget uncertainty, conflicting/stale policy, failed verification
or exhausted allowance. Inspect privately saved evidence and report the precise
failed gate. Do not add prompts or change sources merely to rescue the run; any
new duty/source revision or extra usage needs its own reviewed scope.

This manual-snapshot run does not complete every broad M2 scenario requirement.
Record automatic commitment discovery/real connector coverage as **Not tested**.
Keep M1 business lock131031/no-blind-retry and remaining delivery tests separate.
No ready artifact means instructor approval, external delivery or submission.

## Redacted result sheet

- Approved exact revision, date and operator: Pending.
- Existing environment/account aliases and approved setup scope: Pending.
- Approved numerical request/invocation/spend ceilings: Pending.
- Runtime-owner bound confirmation and approval references: Pending.
- Duty/source/version/artifact aliases: Not run.
- Observed worker claims/model requests, provider usage uncertainty: Not run.
- Useful autonomous continuation and saved checks: Not run.
- Scenario content/format criteria and second-account/restoration evidence: Not run.
- External messages/submissions:0 planned; execution not started.
- Outcome: Not run; no live M2 or M1 completion claimed.
