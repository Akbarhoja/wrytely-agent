# Canvas browser host foundation

Owner: Murtazo (murtazokhon-tech). Claim: [#136](https://github.com/Akbarhoja/wrytely-agent/issues/136).
Base: #132 at `00dad2ac`. This slice adds an inactive controller and trusted Chrome
event adapter, reusing the existing pairing client and its private discovery journal.
It does not install or enable an extension. Popup/options UI and packaging follow.

## Required behavior

- Fresh registration creates no alarms and performs no backend or Canvas reads.
- Only explicit private commands pair, bind or enable. Origins are pinned by the
  caller, never supplied in messages; device identity is generated locally.
- Persist enabled/pause state before alarm hints. Preserve only preferences here;
  pairing credentials and source checkpoints remain in the existing client.
- One bounded operation per event. Reuse collectAssignmentPage pending-first
  recovery. A finished scan begins a fresh scan on its next opportunity.
- Use named 30-minute periodic and 30-second continuation alarms. Repair lost
  alarms on worker startup only when persisted preferences enable collection.
- Persist transient backoff from five minutes to six hours. Auth/context/journal
  failures pause; unknown errors pause rather than guessing retry safety.
- Serialize preference updates. A control epoch fences completion after pause or
  re-enable. Pause cannot recall a request that was already dispatched.
- Pair/bind require paused, nonbusy state and are never automatically retried.
- Project only controlled status, course count and coverage state. Do not expose
  bearer, identifiers, origin, checkpoint, leases, raw source or exception messages.
- Accept exact extension popup/options senders only, rejecting tab/content script
  and foreign senders. Validate exact message keys. Register listeners once.

## Scope and remaining milestones

P0 Canvas access belongs to A under #104; WhatsApp delivered-reply proof remains
M's open gate after the recorded 131031 failure. Outlook is optional and paused.
P1 two-course synthetic HTTP proof #132 is independently accepted by A in #134;
this does not prove installed MV3 operation, all resource types or live collection.
A owns document staging/finish/publication. M retains source consumers, browser
UI/package, remaining academic resources and later messaging/web assembly.
P2 continuous operation, P3/P4 interactive work and P5/P6 pilot/release remain
unfinished. No new live calls, installation, sends, spending or deployment occurs.

## Verification

Implemented controller and event adapter, inactive until called by a future worker.
All **389 extension tests pass**, including **24 host/controller/event tests**.
Controller and event files each failed with missing modules before implementation;
two epoch/pairing races and both final review findings had observed failing tests
before correction. Tests cover lost alarms, persisted cooldown, pause storage and
alarm failures, stale completion, duplicate events, strict senders/messages,
generated device identity, safe status and actual default-client inactivity.

A fresh read-only reviewer found the real collector coverage string contract was
misprojected. Partial/complete regressions now preserve those exact strings. The
reviewer's minor identity rejection finding was treated as important because a
false disabled flag could mislead users; rejected pair/bind commands now omit a
claim that collection stopped. No other critical/important finding was reported.
An author audit also found completed-step replies retained running:true; an
observed RED→GREEN regression now ensures completed replies report running:false
while concurrent in-flight status remains accurate. All389 tests pass after it.
Required `uv run pytest -q` completed on a fresh disposable local Postgres database:
**966 passed**, no skips, two existing warnings, **1377.77s** on native Windows.
This includes the existing 19 actual synthetic HTTP scenarios; no backend code
changed in this host slice and no timezone or provider behavior was overridden.
Ruff check and format check pass (178 Python files). Source tests use fake
Chrome/client objects except one inactive/default real-client construction check;
they do not add new actual HTTP collector coverage beyond the existing #132 proof.

Actual service worker termination and browser alarm delivery remain untested. Alarm persistence
and timing are best effort; startup repairs are needed per the
[Chrome alarms documentation](https://developer.chrome.com/docs/extensions/reference/api/alarms).
The event adapter uses literal true for asynchronous replies per
[Chrome messaging documentation](https://developer.chrome.com/docs/extensions/develop/concepts/messaging).

## Review limits and next eligible step

The author reviewed current GitHub ownership and Akbar's #134 acceptance of #132.
A's document publication work stays separate. M's next eligible implementation is
the private popup/options and installable worker/package consuming this foundation,
followed by authorized real-browser lifecycle acceptance and remaining resources.
This slice remains a draft until counterpart review; it does not complete P1.
If pause persistence fails, durable:false reports only a current-worker hold;
a recreated worker can read the prior enabled state. Clear-alarm failure after a
successful persisted pause reports alarm_cleanup:false; future events still read
disabled preferences. No already dispatched source request can be recalled.
The pause boundary is a collector step, not an AbortController for each internal
request: an already-running bounded client step may finish its remaining source,
extraction or receipt requests. Future UI must describe pause as stopping new
steps and show the running step; per-request interruption is not established here.
Counts/coverage are projections of the last step in this worker, not a durable
source-health report; after worker recreation, ready state has not measured them.

## Counterpart coordination during verification

Akbar's exact #133 `c107b682` archive received independent focused Windows review
without editing his branch: 151 root/section tests passed in0.70s with native
cp1252/UTF8 mode0, 105 freshness/evidence tests in211.08s on a separate disposable
database, and 44 upload-transaction tests in154.06s on that now-idle review database.
These are scoped carried-head checks, not a full backend acceptance of his stack.
Reports: [#129](https://github.com/Akbarhoja/wrytely-agent/pull/129#issuecomment-6560918044),
[#131](https://github.com/Akbarhoja/wrytely-agent/pull/131#issuecomment-6560975209) and
[#133](https://github.com/Akbarhoja/wrytely-agent/pull/133#issuecomment-6561027630).

M separately agreed the internal object-delegation/document-reference proposal at
exact #142 `e9a8fe44` in [design review](https://github.com/Akbarhoja/wrytely-agent/pull/142#issuecomment-6560955094).
That permits the described A-owned internal design work; design agreement alone
does not agree a new HTTP/UI wire or accept the recovery implementation.
Separately, scoped #142 recovery verification at that exact head passed its eight
new scripted-model tests in64.08s on the isolated review database. This verifies
the two terminal evidence-error changes, not its inherited #141 provenance stack
or document-only generation. The synthetic legacy bridge remains explicit.
No production source, provider, model, messaging or deployment action occurred.
