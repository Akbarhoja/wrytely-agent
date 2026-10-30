# M2 combined review checkpoint

Work #35; branch codex/m2-integration-review, executable candidate 1dcb4d3.
This supersedes the earlier 0d47e40 unmounted-consumer checkpoint. It combines
Murtazo's final #28 consumer061c389, reviewed #38 runtimefab095f, and reviewed
format-viewer8268e27. No teammate implementation was rewritten. Protected main
has not been merged; independent human approval remains required.

## Connected behavior

- Authenticated immutable manual snapshot create/list/detail.
- Explicit selected-source private-draft confirmation, authenticated POST,
  idempotent retry identity and responsibility status consumer.
- Atomic source binding, private drafting intent, source-backed policy/rubric
  assessment, model-selected planning and mandatory draft verification.
- Private artifact/check viewing with stale precedence and account/session fencing.
- Supported exact quoted numeric word ranges and explicit separate disclosure
  checked deterministically; optional saved evidence is shown with narrow limits.
- Unsupported numeric wording blocks; semantic assessment and extraction remain
  fallible. A passed check is neither submission nor instructor approval.

## Validation

Candidate1dcb4d3 foundation/web CI40998132458 and40998137577 succeed. Included
runtime#38 was independently reviewed by Murtazo; final consumer delta8268e27 was
read and reviewed by Codex. Local113 frontend tests and webpack build pass.
Murtazo reports376 backend passes against disposable Postgres at8268e27; prior
format CI also passed376 backend. Local full DB suite remains sandbox-blocked.

The API→Store→worker→ready-artifact automated test uses scripted models. It proves
assembly and isolation behavior, not real Meta quality or live connector access.

## Approved bounded development run

Akbar approved isolated Railway development agent-api deployment, migration009,
one fictional M2 student workflow, at most10 Meta requests and $1.50 within the
existing $2 total ceiling. No WhatsApp sends, continuous workers, production changes
or Meta business setup. Migration008/A4 is absent and excluded.

Candidate1dcb4d3 deploymentbc66b077-e209-49c7-b3ca-6fcd24530ba9 succeeded;
healthz returns200. All four fictional snapshots and one explicit private-draft
request were saved through the real signed-in student interface. The UI correctly
shows waiting for policy/requirement checks before any worker result.

The controlled worker records budget reservations before calls in the private
ledger; unknown usage retains its worst-case reservation. It refuses unrelated
pending work. Provider and artifact outcomes are recorded separately in the run
report; deployment/intake alone do not satisfy live M2 acceptance.

M1 remains incomplete while business/delivery and remaining controls are open.
Manual snapshot intake does not prove automatic commitment discovery or Canvas/
Teams monitoring. M3 requirement adaptation and A4 remain outside this run.

The live attempt stopped at the first Meta requirements call with NotFoundError;
no draft was generated. Migration009 is confirmed applied, zero workflow outbound
rows, $1.32 retained reservation with unknown usage. Ordinary migration command
restored; deployment9765a5ae healthy. See [run evidence](M2-RUN-2026-10-29.md).
Live M2 remains incomplete.
