# M1 live test pack

Status: **Prepared — every live case is Not run.** Owner: Murtazo; Akbar operates
development accounts/services. This sheet supports the
[integration acceptance plan](https://github.com/Akbarhoja/wrytely-agent/blob/be01bd1631dc604db6fc2bc7ef57d3dd19317e88/docs/M1-ACCEPTANCE.md).
It does not authorize live usage or replace that plan. Reviewed candidate at
preparation: `be01bd1631dc604db6fc2bc7ef57d3dd19317e88`.

## Readiness and authorization

Akbar confirms these fields before a worker starts or a test message is sent.

| Gate       | Required confirmation                                                                | Current result                          |
| ---------- | ------------------------------------------------------------------------------------ | --------------------------------------- |
| Revision   | Actual tested revision; human approval separately if merging                         | Not verified for live run               |
| Clerk      | Existing development instance works with web/API and two test accounts               | Pending                                 |
| Database   | Designated isolated agent development DB; intended migrations reviewed/applied       | Pending                                 |
| WhatsApp   | Test account/number, signed HTTPS webhook, subscription and public destination match | Partial setup reported; webhook pending |
| Model      | Development model/key and permitted model available to worker                        | Pending                                 |
| Recipients | Two consenting number owners, verified for this test account                         | One reported; second pending            |
| Usage      | Explicit spend, model-request/message limits and operator                            | Pending                                 |

Secrets stay in local/hosting secret controls. Record aliases and readiness only.
Keep codes, tokens, full phones, emails, DB URLs and raw provider bodies out of Git
and shared screenshots. Configuration presence alone is not live proof.

### Proposed bounded run — approval still required

| Phase                             | New reply tasks | Maximum model requests |                                Manual inbound messages | Outbound dispatch attempts |
| --------------------------------- | --------------: | ---------------------: | -----------------------------------------------------: | -------------------------: |
| Core: both students               |               2 |                     12 |                    4: two link messages, two questions |                          2 |
| Controls: pause/resume and unlink |               2 |                     12 | 3: paused question, unlink question, post-unlink check |                          1 |
| Full proposed run                 |               4 |                     24 |                                                      7 |                          3 |

These are proposed operational limits, not an implemented global spending cap.
The model bound assumes AGENT_MAX_EPISODE_TURNS is at most 6, one worker attempt
per listed reply task, no unrelated queued work/responsibilities, and no retry
after failure. Model transport retries are disabled. One question can require
several billable model turns.

| Authorization field                     | Approved value |
| --------------------------------------- | -------------- |
| Maximum spend                           | Pending        |
| Approved phases and numerical limits    | Pending        |
| Consenting recipient aliases / operator | Pending        |
| Approval evidence and date              | Pending        |

Keep continuous reasoning/delivery workers stopped during this controlled run.
The operator checks queue provenance and processes one expected task at a time
with the existing commands below. Reconcile unrelated queued work first; do not
delete retained development work to make the test fit. **--once is not a dry run.**

```sh
# Repository root; operator has reviewed the intended development environment.
uv run --env-file .env python -m runtime.worker --once
uv run --env-file .env python -m app.whatsapp_worker --once
```

Run reasoning once for each authorized question, inspect its persisted result,
then run delivery once. A zero exit code does not prove completion or delivery.
Stop on unexpected work, error/retry, unknown send, missing evidence or a budget
limit. Never repeat delivery to force an uncertain message through.

## Students and exact inputs

Use separate browser profiles/sessions. These are synthetic scenarios, not actual
college records. Each student uses their own consenting WhatsApp test number.

| Alias     | Scenario                                | Private synthetic marker |
| --------- | --------------------------------------- | ------------------------ |
| A / Cedar | Twenty minutes to review fractions      | CEDAR_PRACTICE_A         |
| B / Maple | Thirty minutes to review photosynthesis | MAPLE_PRACTICE_B         |

Choose a nonsecret run label (example: m1-20261029-a) and replace {RUN}. Obtain
linking messages from the actual Connections page and send them exactly as shown;
never fabricate, save or reuse a code from this document.

**A1 — Cedar's question**

> M1-A {RUN}. I have 20 minutes to review fractions. Suggest three short practice steps in under 120 words. Include CEDAR_PRACTICE_A once. Use only this message; no external actions are requested.

**B1 — Maple's question**

> M1-B {RUN}. I have 30 minutes to review photosynthesis. Suggest three short practice steps in under 120 words. Include MAPLE_PRACTICE_B once. Use only this message; no external actions are requested.

**A2 — paused work**

> M1-PAUSE {RUN}. Suggest one short fractions practice exercise in under 80 words. Include CEDAR_PAUSE_A once.

**A3 — queued reply before unlink**

> M1-UNLINK {RUN}. Give one short tip for reviewing fractions in under 80 words. Include CEDAR_UNLINK_A once.

**U1 — after unlink, workers still stopped**

> M1-IGNORED {RUN}. This synthetic message checks that an unlinked sender is ignored.

Markers check visible separation; they are not credentials. Score answer quality
separately from transport: useful steps/length are content checks, while ownership,
persistence and delivery have separate criteria. Unexpected content never grants
permission for another send.

## Core sequence

| ID  | Action                                                                               | Observable pass criteria                                                                                                                                                     |
| --- | ------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C1  | Sign in as A and B; open each workspace                                              | Two distinct private agents; each sees only their own work.                                                                                                                  |
| C2  | Refresh and log out/re-login as A                                                    | Same agent returns; no duplicate provisioning or lost saved work.                                                                                                            |
| C3  | Generate each link message; send from that student's number; Check connection        | Mask/reveal/copy work and expiry is displayed. Ownership is confirmed only after signed inbound; each page shows its own last four digits. Linking creates no academic task. |
| C4  | Save consent=true, timezone=UTC, quiet start=0/end=0 for each                        | Values survive refresh and affect only that account. Equal hours explicitly disable quiet hours for this test.                                                               |
| C5  | A sends A1; operator processes that task, then outbound action, once each            | One saved input/task/result and one attempt to A. Website result matches outgoing answer. B sees neither A task nor result.                                                  |
| C6  | B sends B1; follow the same sequence                                                 | One B task/result and one attempt to B. A cannot read B task/result.                                                                                                         |
| C7  | Inspect authenticated provider status for C5/C6                                      | Acceptance remains separate from delivery. Pass delivery only with correlated delivered/read evidence and observed reply; otherwise mark Blocked and note missing evidence.  |
| C8  | Reopen/re-login both; inspect the other task through normal authenticated API access | Saved results/connections restore; another student's task returns 404 without its content.                                                                                   |

Run A/B sequentially so queue provenance is clear. Use fresh inbound questions
within the conversation window; template capability remains off. Public business
destination and Meta internal phone-number ID are distinct configuration values.

## Control sequence

| ID  | Action                                                                       | Observable pass criteria                                                                                                               |
| --- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| R1  | Workers stopped: pause A in website; send A2; run reasoning once             | Task persists ready, no model request occurs, no outgoing message.                                                                     |
| R2  | Resume A; process that same A2 task once, then delivery once                 | Original work completes without duplicate input; one reply attempt, actual status recorded.                                            |
| R3  | Stop delivery; A sends A3; process reasoning once                            | Saved result and queued outbound exist; dispatch has not occurred.                                                                     |
| R4  | Unlink A with confirmation before authorizing dispatch; invoke delivery once | Queued action cancelled, no provider call, mapping cleared, result retained. Already authorized/in-flight requests cannot be recalled. |
| R5  | Send U1 while unlinked; inspect task/outbound evidence                       | No academic task/reply for U1, no model call; B remains linked.                                                                        |

Do not inject live network failures, replay private bodies or force crashes in
this initial bounded run. Offline regressions cover ambiguity, restart, callback
order/replay and control gates. A separate live fault exercise needs agreed scope
and budget. If an unknown send occurs naturally, retain evidence and stop.

After evidence capture, stop both workers and review remaining consent/link state
with the test-number owners. Retain the development results for review; do not run
test-schema reset commands against that retained database.

## Blank execution record

Copy this section to an ignored local evidence note for the run. Share a redacted
summary after checking it for secrets/personal data. Use references such as E-A-01;
keep any raw identifier mapping private. Record observations rather than intentions.

| Field                                                     | Value   |
| --------------------------------------------------------- | ------- |
| Run label / date and timezone                             | Not run |
| Exact tested commit                                       | Not run |
| Operator / approved phases                                | Not run |
| Readiness and authorization evidence                      | Not run |
| Model/API configuration provenance (no secrets)           | Not run |
| Model requests / inbound / outbound attempts              | Not run |
| Actual usage/spend and remaining approved budget          | Not run |
| Saved-work/provider evidence locations (redacted aliases) | Not run |

Allowed statuses: **Not run, Pass, Fail, Blocked**. Worker success or offline CI
alone does not establish real delivery.

| Case                                       | Status  | Observed result / redacted evidence reference |
| ------------------------------------------ | ------- | --------------------------------------------- |
| C1 Two private agents                      | Not run |                                               |
| C2 Agent restoration                       | Not run |                                               |
| C3 Verified phone linking                  | Not run |                                               |
| C4 Explicit preferences                    | Not run |                                               |
| C5 A round trip / answer quality           | Not run |                                               |
| C6 B round trip / answer quality           | Not run |                                               |
| C7 Confirmed delivery evidence             | Not run |                                               |
| C8 Restored results / cross-account denial | Not run |                                               |
| R1 Paused task retained, no model call     | Not run |                                               |
| R2 Resume original work                    | Not run |                                               |
| R3 Saved result before dispatch            | Not run |                                               |
| R4 Unlink cancels queued dispatch          | Not run |                                               |
| R5 Unlinked sender ignored                 | Not run |                                               |

Final disposition: **Not run**. Document failures, unobserved delivery and setup
gaps. Claim live M1 only after the required real path succeeds and Akbar accepts
the evidence. Feature freeze, human merge approval and release remain separate.
