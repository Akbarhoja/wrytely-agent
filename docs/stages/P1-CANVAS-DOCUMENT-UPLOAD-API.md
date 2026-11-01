# Private document upload HTTP assembly

Murtazo claim [#154](https://github.com/Akbarhoja/wrytely-agent/issues/154), branch
codex/canvas-document-upload-api from A-approved #135 `019d6c7`.
Authority: [exact HTTP design/base agreement](https://github.com/Akbarhoja/wrytely-agent/pull/148#issuecomment-6563512653).
No shared/runtime/contracts/schema/settings/fixtures/extension/CI/STATUS changes.

## Required behavior

POST /v1/source-connections/canvas/documents/begin, /parts, /finish each accept
only the matching existing schema2 operation body. Call the existing Store method
once with the ingestion bearer; current authority, exact replay, parts/root integrity
and transaction rollback remain Store-owned. Finish materializes a private ready
root, not publication, extraction completeness or permission to draft.

Reuse CanvasRoute for streamed1MiB bound, application/json, fixed validation errors
and no-store. Document-only validation maps to400, leaving old schema1 routes422.
Opaque unavailable/nonowned upload returns empty404. Current state conflict409 is
allowlisted; quota429 uses Retry-After30 as minimum pause, no capacity promise or
automatic retry. Unexpected failures are redacted500 with unknown outcome preserved.
Query parameters and posted account/config fields cannot change the operation.

New create_app keyword-only canvas_document_extractors tuple defaults empty/off.
Trusted normalized server-selected versions and existing Canvas origin configuration
are required; body metadata never configures the server. Existing deployment Settings
stay unchanged. No credentials, body, source content or exceptions are logged/echoed.

## Acceptance and remaining work

- RED observed before implementation: missing factory keyword, 1 failed in5.90s.
- Real-Store focused API suite: 53 passed/zero skips/140.57s. It covers all three
  operations, recreated-app immutable replay, wrong account/session credentials,
  revoked credentials, changed scope/subject/generation/scan/connection, expired
  upload/lease, trusted/default-off configuration, exact body validation, unknown
  upload empty404, real quota and controlled errors, and committed response loss
  plus final-lease rollback for each operation. Unknown scan uses Store's401;
  the initial409 test expectation was corrected without changing authorization.
- Additional raw multi-message ASGI test: 1 passed/1.58s; false Content-Length
  cannot bypass1MiB and the unread remainder is never consumed.
- Base extension regressions: 365 passed/zero skips/3.05s. This approved API base
  predates the separately integrated browser package; no package files were removed.
- Full disposable backend: 1190 passed/zero skips/2existingwarnings/1687.78s
  (Windows, isolated local Postgres; `.venv/Scripts/python.exe -m pytest -q`
  in the uv-managed environment). No retained database or live provider was used.
- Ruff lint/format189files, scoped Prettier, owned local links and diff checks passed.
- Fresh read-only final review: no remaining Critical/Important/Minor findings.
  Reviewer inspected Store authorization/replay/final fences; executable evidence
  remains the author's responsibility.

Independent counterpart work: reviewed A#153 exactf62fb0c; all16 delivered M files
are byte-identical. Its exact new CI Node command passed404tests/zero skips/3.08s;
CI41354438852 reports success separately. The first sandbox Node run failed at
Windows symlink permission; normal reviewed rerun passed without exclusions. Old
green CI did not run the host/UI/package suites omitted by the old static list.
[Scoped counterpart review](https://github.com/Akbarhoja/wrytely-agent/pull/153#issuecomment-6564595290).
Read A#152 internal typed citation DTOs and projection filters;16pure contract cases
passed, not a runtime/workflow rerun. A versioned private-result consumer remains a
[separate interface request](https://github.com/Akbarhoja/wrytely-agent/pull/152#issuecomment-6564664188).

No installed browser or live source/provider/model call. Producer #149 and later
publication/journal/cleanup remain separate; ready staging creates no course
observation or source version. P1 and the full academic agent remain incomplete.
Chrome remains untouched; automation stays off. No new provider spending, source
permission, external send, production migration, deployment or main merge.
