# Local P0 access completion — October 31, 2026

Owner: Akbar/Codex. Claim: [#104](https://github.com/Akbarhoja/wrytely-agent/issues/104).
Base: 59c074e8c9cb8a8cb902a4fa6631b5fbd86fcfe6; branch: codex/p0-local-access.
This record contains redacted access classifications, not source data or credentials.

## Current supervisor decision: optional email

Outlook is now optional. Keep the existing registration/probe and future connection
path; pause live CSU access and duplicate approval requests. The owner reports an
existing request without a response; this is not proof of rejection. Do not submit
another request. P0-M2 stays unverified/paused as an optional track, not a core gate.
Canvas, own Meta supervisor and WhatsApp development proceed with their original checks.
Advertising must qualify university permission and actual implemented/live availability.

## Ownership and handoff

Latest [supervisor reassignment](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6548991501)
returns P0 Canvas #51 and Outlook #53 to A. M
[acknowledged](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6549014013)
and paused duplicate P0 live runs. WhatsApp remains M under the earlier exclusion.
P1 integration claims remain M; this does not transfer their implementation.

## Outlook account discovery

Read-only Entra inspection showed only the school directory in All Directories.
The remembered account menu showed school accounts, no company administrator.
Earlier Wrytely registration/enterprise-app searches in that directory returned no
match. This does not prove absence of differently named apps or external tenants.

The connected company mailbox was searched for Wrytely/Microsoft/Azure/Entra setup
records and vendor welcome/subscription/tenant messages. No Microsoft organization
setup record was found. Searches returned either unrelated messages or no results.
Other unconnected mailboxes/accounts have not been searched.

No company home tenant/admin has been identified. The supervisor was asked whether
to identify another existing administrator account or prepare a new company setup.
No organization/app was created; no Graph permission, token, message, attachment,
delta or notification access was obtained. #54 remains mocked probe evidence only.
The proposed PKCE harness is not implemented or approved live execution.

## Outlook registration follow-up

The supervisor subsequently authorized preparing a new company setup and completed
Microsoft email verification, Azure profile/card verification and account terms.
The company-controlled default workforce directory now exists. Subscription ownership
was visible; this is distinct from proving every Entra administrator permission.
Azure lists a usage-based Microsoft Azure Plan with monthly billing and a separate
Microsoft Entra ID Free item. Free-trial credit/hard spending protection remains
unverified. No billable Azure compute/storage resource or paid upgrade was created.

With explicit action-time approval for registration and Microsoft Platform Policies,
A created **Wrytely Agent Development** in the company directory. Verified activated
application/service principal, organizational multitenant audience (personal accounts
excluded), and one Mobile and desktop callback: `http://localhost:8765/`.
Configured delegated Graph `User.Read` and `Mail.Read`; configuration is not consent.
No admin consent, mailbox token, refresh grant, client secret or mail read occurred.

The app overview warns that end users cannot consent to new multitenant applications
without verified publishers. Publisher verification/university administrator approval
must be resolved through supported flows; the actual CSU consent outcome is untested.
Local PKCE acquisition harness, identity-bound Graph test and full Outlook access
acceptance are still pending. Registration alone does not complete P0-M2.

## Actual CSU consent test and operator harness

A built `scripts/p0_outlook_signin.py` under #104 and reused M's exact #54
`integrations/outlook/read_probe.py` and its 32 mocked tests unchanged. The operator
SDK requirements are isolated in `scripts/requirements-outlook-probe.txt`; deployed
runtime dependencies and services were not changed.

The probe binds exclusively to 127.0.0.1:8765 before requesting a URL. MSAL 1.39.0
creates authorization-code/PKCE S256 state with a five-minute deadline. The callback
checks host/path/state/duplicates/expiry and accepts one response; tokens remain in
memory, no broker/cache persistence or client secret. The private ignored URL file
contains temporary request state only and is removed when the run ends. Logging is
suppressed; only fixed classifications/counts are returned. The default run performs
no Graph mailbox read. `--read-inbox` is a separately authorized one-page read mode;
verified tenant/subject/scope checks precede the reused identity-bound Graph probe.
No background access or refresh grant is requested; `offline_access` is excluded.

Operator setup from repository root (ignored isolated environment):

```sh
.venv/bin/uv venv --python .venv/bin/python .local/outlook-signin-venv
.venv/bin/uv pip install --python .local/outlook-signin-venv/bin/python -r scripts/requirements-outlook-probe.txt
.local/outlook-signin-venv/bin/python -m scripts.p0_outlook_signin --client-id APP_CLIENT_ID --expected-tenant SCHOOL_TENANT_ID --url-file .local/outlook-authorization-request.json
```

Identifiers come from the approved app and verified school directory; no IDs or
secrets belong in public reports. Open the generated HTTPS Microsoft authorization
URL through approved browser controls; never copy callback codes/tokens into chat.
If consent is blocked, record the UI classification without treating it as success.
The issuer can retain an approved consent grant even though the probe clears local
tokens; memory-only operation is not automatic permission revocation.

**Live result:** selecting the consenting CSU account for this exact app returned
`AADSTS90095`: administrator consent required. Microsoft's page displays **Approval
required**, app **unverified**, and a justification/request-approval form. No request
was submitted, authorization callback/token acquired or mailbox read performed.

The visible admin request additionally lists **Maintain access to data you have given
it access to**, although the generated SDK request excluded offline_access and the app
configured only User.Read/Mail.Read. This discrepancy is recorded for administrator/
publisher review; do not silently approve ongoing access or enable refresh to bypass it.
No raw request/correlation/session IDs, account identifiers or screenshots are published.

Synthetic evidence: 20 new sign-in cases + 32 reused probe cases pass; full disposable
local Postgres backend **685 passed** on the final listener hardening, Ruff lint/format
and diff checks pass. Real token exchange, Graph reads, attachments, delta completion,
subscriptions and refresh remain unproved. The operator harness needs counterpart review.

Suggested administrator request (not sent):

> Please review Wrytely Agent Development for a controlled student Outlook integration
> test. The app requests delegated User.Read and Mail.Read to sign in and read my mail;
> it does not request sending, editing or deleting email. The publisher is currently
> unverified. Please review the listed permissions, including the displayed Maintain
> access permission, and advise what verification or restrictions CSU requires.

## Canvas handoff and limits

M reports the installed diagnostic corresponds to reviewed #52 f1e0d9b, but the
installed package revision is not independently verified. Last controlled console
classification was blocked/login_required; a later operator READ badge means only
a bounded report returned. Detailed classifications have not been inspected.
No newer verified report was supplied. Earlier tab-closed/manual-start evidence does
not prove browser restart/recovery, expiry/account-switch or linked-file extraction.
Chrome must stay open; disruptive session tests require coordination.

## Other P0 gates

- Meta real tool call / saved result / continuation already passed in #50. No paid
  diagnostic was repeated; current budget/reservations remain unchanged.
- Baseline #46 is unmerged and needs the configured independent human approval;
  assistant comments cannot supply that approval. No protection bypass.
- Remaining C4–C7 decisions and precise document wire agreement remain separate.
- WhatsApp delivered-reply proof remains open and excluded from this takeover.

P0 is not complete. No deployment, migration, source activation, continuous worker,
new credential, paid model call or WhatsApp send occurred in this account check.

## Follow-up core P0 checkpoint

- #46 exact9bbea97: unmerged, merge-blocked, no formal review at fresh check. A formally
  requested murtazokhon-tech as reviewer. No assistant self-approval/protection bypass.
- Canvas dashboard is currently signed in; this is not extension API proof. A requested
  the existing local diagnostic's counts-only Console report from the operator because
  Chrome extension management is unavailable through browser controls. No restart/logout
  or account switch was performed; those matrix entries remain explicitly untested.
- A asked M for versioned C4–C7 and document-wire review and any new WhatsApp result.
  Existing Meta evidence already passes P0-A2; no new paid call was made.
- M's latest #107 course-metadata collector exact4106dc88 independently passed all six
  requested Node suites: 233 pass, zero skips. Scoped counterpart review found no blocker
  in that increment. Full academic collection/installed live behavior remain unfinished.
  M is implementing #108 collector/HTTP/Store acceptance; A does not duplicate that work.

Email is not a blocker for the above core work. This checkpoint does not mark P0 complete.

## Operator-supplied current-session Canvas report

The operator reported the diagnostic was not installed in this Chrome profile, then
followed the existing local package's Load unpacked instructions. Do not rely on the
older READ badge as evidence from this installation. The operator pasted this new
counts-only report; service-worker output/installed bytes were not independently inspected.

| Resource    | Reported result                                                      | Evidence limit                                                             |
| ----------- | -------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Courses     | 7 discovered, 1 selected                                             | Not proof every course's academic content is collected                     |
| Assignments | Read 22; 12 nonempty instruction bodies                              | Other items need source-specific interpretation, not invented instructions |
| Rubrics     | 0 nonempty rubric arrays                                             | No positive rubric-read proof; does not establish rubrics are inaccessible |
| Syllabus    | Read; inline body present                                            | Partial; linked documents not read                                         |
| Discussions | 21 topics listed; one visible topic view read with 1 top-level entry | One-topic sample, not every thread/reply                                   |

Schema1 explicitly labels this probe_output_not_acceptance / partial_probe. This is
useful current-session, operator-reported extension access evidence. It does not prove
linked-document extraction, all-topic coverage, browser restart/recovery, expired login
or account switching. Next repeat with Canvas tabs closed but Chrome running. An open
service-worker Console can keep that worker alive, so label that result manual-start/
debugger-attached rather than proof of unattended MV3 scheduling or suspension recovery.

## Operator-reported tab-closed repeat

After the requested closure of Canvas tabs with Chrome and the service-worker Console
left open, the operator supplied the same schema1 partial_probe results: 7 courses
discovered, 1 selected, assignments read22/instruction bodies12/rubrics0; syllabus
inline body readable but linked documents unread; discussion list21 with one sampled
view readable and 1 top-level entry. This is operator-reported manual-start access
with Canvas tabs closed, not independently observed browser/Console state.

For these sampled resources, an open Canvas tab was not required in this test while
the authenticated browser session remained available. An attached Console may keep
the worker alive: unattended invocation, worker suspension/recovery, Chrome restart,
expired login and account switching remain untested. Linked-document extraction and
positive rubric access remain gaps. No Chrome restart/logout, background scheduler,
source upload, model call, WhatsApp send or deployment is implied. P0 stays open.

## Linked-document follow-up (pending local save)

Read-only UI inspection of the first sampled syllabus found inline text and no linked
PDF/Word file anchors; its Files view displayed no rows. This UI observation is not
an API/extension file-collection classification. A second current course's normal
course page exposed an authorized syllabus PDF link. Its Canvas preview opened, but
no PDF contents were verified. Download attempts timed out in browser tooling.

Native Chrome inspection then showed a Save dialog waiting for a destination, so the
timeouts are not evidence that Canvas denied file access. Native controls failed during
save-dialog interaction. The operator was asked to complete a local Downloads save;
no downloaded bytes/text, extension-side file access or document extraction is passed.
No signed download URL, raw PDF, course identifier or private source content is published.
Chrome was not restarted/logged out. The manual tab-closed result above remains separate.

## Operator-completed syllabus download and local extraction

After the operator completed the native Save dialog, A verified the expected local
PDF existed (398346 bytes). Local pypdf inspection opened it successfully: 3 pages,
text present on all 3, 6935 extracted characters, not encrypted. Only these summary
measurements are recorded; PDF contents, course/file IDs, paths and signed URLs are
not published. No PDF bytes entered model/runtime storage or any cloud collector.

This confirms the normal signed-in browser/manual-download path and local text
extractability for one real syllabus PDF. It does not prove the extension can follow
that file's download/redirect chain, extract documents, or synchronize them. The
second course is a manual UI sample, not automatic two-course collector acceptance.
A still needs coordinated browser-restart/session-expiry testing; the standing
instruction to keep Chrome open is preserved until the supervisor explicitly changes it.

## Restart test: login required; recovery pending

The supervisor approved a brief Chrome restart and Canvas sign-out/in test window.
Native controls were unavailable, so the operator performed the requested full quit/
reopen and reported diagnostic `{state: blocked, reason: login_required}` before
reopening Canvas. Restored-tab behavior was not specified; do not infer it.

A independently observed a new Chrome connection after restart. Opening the normal
Canvas origin redirected to the public university landing page; choosing NetID Login
opened the official NetID username/password form. No existing signed-in dashboard or
seamless SSO restoration was observed. The operator was asked to sign in/complete Duo.
No credentials/codes are collected or exported. Post-login extension recovery remains
pending; this is not an account-switch test or a separately induced timeout-expiry test.

Observed limitation: this installation's tested browser restart did not preserve usable
Canvas access. An active-session tab-closed read is distinct from restart persistence.
The diagnostic fails closed as login_required rather than claiming successful empty data.
Future ingestion must preserve stored evidence and report stale/reconnect-needed status;
no automatic refresh while logged out is proved. No application behavior was changed.

## Post-login recovery confirmed by operator report

After completing the official NetID flow, A independently observed the signed-in
Canvas dashboard with 7 published courses. The operator then reran the installed
diagnostic and supplied the full resource summary: 7 discovered/1 selected; assignments
read22/instruction bodies12/rubrics0; syllabus read/inline body present/linked documents
not read/partial; discussion list21, one sampled view read, 1 top-level entry.

This passes the bounded operator-reported recovery sequence: browser restart ->
login_required -> explicit student sign-in -> sampled extension reads recover. It does
not pass seamless authentication persistence across restart, unattended scheduling,
separately induced timeout expiry, account switching or extension-side document reading.
No requirement to sign in after every restart for all students is inferred from one test.
The required product behavior is to expose reconnect-needed/stale evidence and resume
sync after login, never report a logged-out scan as empty success. That collector/runtime
behavior still requires its own integrated implementation/acceptance.
