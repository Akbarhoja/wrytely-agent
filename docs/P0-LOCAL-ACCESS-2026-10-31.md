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

## Explicit Canvas sign-out check

Within the supervisor-approved session-test window, A clicked the normal Canvas
Logout link and observed the university session logout page. Before reopening Canvas,
the operator reran the installed diagnostic and reported `{state: blocked, reason:
login_required}`. This passes the bounded operator-reported explicit-sign-out rejection
check: no successful resource report was returned while the Canvas session was invalid.
It is distinct from natural timed expiry and from switching between two Canvas users.

The tested sequence now includes current-session reads, manual tab-closed reads with
Chrome/debugger available, restart requiring reauthentication, post-login read recovery,
and explicit sign-out rejection. Remaining Canvas gaps include positive rubric evidence,
extension-side document retrieval/extraction, unattended worker/suspension behavior,
account switching and separately timed expiry. The manually downloaded syllabus remains
separate evidence. Do not call the full Canvas collector or P0 complete from this probe.

## Session restored after explicit logout test

A reopened the normal Canvas origin, followed NetID Login, and independently observed
the signed-in dashboard again. The current university SSO session restored Canvas
without another password/Duo prompt. This does not contradict the earlier full-browser
restart requiring a fresh NetID login: Canvas logout and university-wide SSO termination
are different. The invalid-session diagnostic was run before starting this restoration.
No additional diagnostic recovery run is claimed after this second restoration.

The tested single-account authentication sequence is recorded; account-switch and
natural timed-expiry coverage remain separate. No further disruptive browser action
is implied by the earlier bounded restart/logout approval.

## Bounded document/rubric diagnostic v2 (prepared, not run live)

Supervisor explicitly requested continuing the P0 document/rubric check. Under #104,
`scripts/canvas-access/` reuses the existing reviewed core probe and its 12 tests
unchanged, adding a separate bounded detail module. It is operator-only and does not
implement M's P1 collector, source storage, scheduler or model tools.

- At most two selected consenting courses; details sampled from at most two assignments
  per course, preferring visible rubric candidates. Criteria require actual description
  text. No rubric found is explicitly no_rubric_observed_in_sample, not access denial.
- One known syllabus PDF gets metadata through the same-session course File API. Only
  the exact reviewed Canvas storage origin is accepted for file reads; redirects are
  rejected, file-host credentials omitted, stream capped at5MiB, PDF MIME/signature
  checked. SHA256 is compared privately with the already locally parsed sample. A byte
  match links retrieval to that known sample; the extension does not itself parse PDF text.
- Identity checks surround reads and fence the entire report on account change. Only
  counts/fixed status leave the worker; no source text, IDs, metadata URL, token or hash
  enters the report. Source/PDF bytes stay in memory; no cloud upload or model call.
- A local popup starts the check explicitly and displays JSON. It needs no storage,
  cookie, debugger or clipboard permission. Keep the popup open during the check.
  Closing/interruption is not completion; reruns are explicit read-only operations.
- The manifest adds exact Canvas file-storage host access. The supervisor/operator must
  review and approve installing/loading this local extension before any live read.
  The previous v1 package remains unchanged. New private scope and unpacked v2 output
  are ignored and inactive until loaded; no installed extension was silently replaced.

API references: [Canvas files](https://developerdocs.instructure.com/services/canvas/resources/files)
and [assignment details](https://developerdocs.instructure.com/services/canvas/resources/assignments).
Configured host permission is not proof that the file URL/redirect path will work; report
an actual controlled failure if the institution serves it differently. P0 stays open.

Synthetic Node evidence: 35 passed (12 inherited +23 new), including unauthorized sender,
exact prepared permissions, identity changes, unsafe file destinations, access failures,
redirects, PDF MIME/signature, size limits, content secrecy and sample mismatch. A new
isolated Node24 CI job runs both suites. No claim of live PDF/rubric access is made.

## v2 live report and narrow URL-resolution correction

The operator loaded/approved v2 and supplied:7 discovered/2 selected; assignment lists
22 and23, instruction bodies12 and9; two detail samples per course read with no rubric
criteria observed. First course discussion list21/one view read; second course list0.
Both inline syllabus bodies read. The one linked PDF failed as unsafe_file_url before
any file-host fetch. This is not evidence of institutional denial or inaccessible rubrics.

A independently inspected the known file's metadata through normal browser navigation,
returning only URL shape/origin classifications (no signed values). Metadata was an
unlocked PDF with a university Canvas `/files/ID/download?download_frd=1` wrapper, not
a direct storage URL. The documented read-only `/api/v1/files/ID/public_url` returned
the already-approved exact Canvas storage origin and `/files/` path. The signed URL
was not printed, retained, published or handed to another service.

v3 narrowly supports this observed two-step form: validate metadata file/access scope,
exact institution origin, matching file-ID download path and only download_frd=1;
request that fixed file's preview-link API; recheck identity; then apply unchanged exact
storage-host/path, credentials-omit, redirect rejection, size/signature/SHA256 checks.
Unexpected wrappers/hosts and locked files still reject. No new host permission and no
arbitrary redirect following. Code uses the existing authorized local operator scope.

Synthetic diagnostic tests now45 (12 inherited+33 new), including exact wrapper
resolution, wrong file/path/query, malicious resolver destination, locked metadata and
account switch during resolution preventing file download. The local package was rebuilt
as0.0.3 in the same ignored folder; operator reload/run remains required. No corrected
live PDF result or positive rubric-access proof has been claimed.

## v3 live result; v4 failure classification

The operator supplied a v3 report with the same7 discovered/2 selected courses,
assignment counts22/23 and instruction counts12/9. Four assignment details read;
none contained rubric criteria. Inline syllabus and bounded discussion results were
unchanged. The known linked PDF reached the storage-fetch stage but failed as
file_network_or_redirect_blocked. This does not prove a redirect, institution denial,
or working extension PDF access. The separately saved/local-parsed PDF remains
separate evidence. P0 remains open.

v4 keeps the same host grants and selected scope. The storage fetch now uses manual
redirect handling: an opaque redirect or3xx response is classified file_redirect_blocked
without following or reading its destination; a thrown fetch is file_network_failed.
Chrome's existing permissions.contains API adds only a fileHostPermissionGranted
boolean to the local report, without requesting permissions. This narrows diagnosis;
a granted host alone cannot prove successful file access. No private exception strings,
URLs, tokens, source text, storage or upload were added.

References: [Fetch redirect behavior](https://fetch.spec.whatwg.org/) and
[Chrome extension cross-origin requests](https://developer.chrome.com/docs/extensions/develop/concepts/network-requests).
Synthetic Node tests47 pass (12 inherited+35 new). v4 still requires operator reload
and live run; no live redirect classification is claimed yet.

## v4 live result: redirect confirmed

The operator supplied diagnosticVersion4 with fileHostPermissionGranted=true and
linkedPdf incomplete/file_redirect_blocked. Course discovery, two selected course
counts and four rubric-detail reads match the prior report, with no rubric criteria
observed. This isolates a redirect response rather than a missing existing file-host
grant or a thrown fetch. The redirect destination and chain remain unknown; no
institution denial, successful extension PDF retrieval or positive rubric proof follows.

A reopened the known file's normal Canvas preview through browser navigation and
confirmed the Download control remains available. Visible page asset inspection did
not identify the PDF redirect destination. Native Chrome inspection exposed no usable
window/DevTools controls, so A could not inspect the redirect headers directly. No new
hosts or webRequest permission were granted; no arbitrary follow mode was enabled.
Next evidence needed: the redirect Location hostname only from the diagnostic request
in the extension worker's Network panel. Do not share signed URLs, query values,
cookies, headers, HAR exports or course content. This is an inspection blocker, not
a reason to repeat unchanged diagnostic runs. P0 remains open.
