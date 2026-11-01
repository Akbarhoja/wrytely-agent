# Canvas extension digest compatibility

Owner Murtazo/local assistant; claim [#55](https://github.com/Akbarhoja/wrytely-agent/issues/55).
Branch `codex/canvas-digest-compatibility`, base `3780025` (same protocol/reference
code as reviewed `ccf84dc`; only STATUS differs).

## Contract review and agreement

Rechecked the two reported C1/C2 issues at `ccf84dc`. All 24 Python reference tests
pass on native Windows with `-X warn_default_encoding -W error::EncodingWarning`.
The fixture explicitly decodes UTF-8 without changing its original bytes or hashes.
Terminal partial/restricted/unsupported receipts now have explicit outcome/reason,
current-lease checks, replay handling and no complete-manifest promotion. Expired or
disconnected scans remain aborted history rather than manufactured successful scans.

Explicit M consumer agreement is recorded in
[#48](https://github.com/Akbarhoja/wrytely-agent/pull/48#issuecomment-6537274371).
Akbar retains shared connection/sync persistence, contract/schema and migration ownership;
the coordination handoff asks him to claim P1-A1. C3–C7, human main approval, credentials,
live provider access and deployment remain separate gates.

## Client readiness slice

The C2 spec explicitly permits M to port its reference and run identical vectors in
JavaScript. `extension/canvas/source-digest.mjs` is that browser-compatible helper:

- `canonicalSourceBytes(payload)` validates the v1 envelope and returns canonical UTF-8.
- `sourceDigest(payload)` uses Web Crypto SHA256 and returns lower-case hexadecimal.

No network, storage, credentials, host settings, pairing or ingestion is added. There
is no new fetch client or parallel Store/runtime. This does not replace the existing
counts-only extension diagnostic in #52 or the Outlook checkpoint in #54. The published
shared vectors are read directly from `tests/fixtures/source_digest_v1.json`; no fixture
fork or shared-owner edit is introduced.

Client digests are a portability/readiness check. Under the agreed upload contract,
clients omit authoritative content_digest and the server recomputes it. Matching a hash
never proves ownership, consent, provider truth, freshness or complete course coverage.

## Important compatibility details

Normalize strings and keys to NFC/LF, reject normalized-key collisions and lone Unicode
surrogates. Preserve content whitespace and ordinary list order; normalize `missing`
as a sorted unique string set. Keys sort by Unicode scalar values, including astral
characters. The encoder writes object members explicitly: JavaScript's JSON.stringify
would otherwise reorder numeric-looking keys despite insertion sorting.

Permit safe JSON integers/null/boolean/string/list/object only, rejecting floats,
NaN/infinity, BigInt, undefined, sparse arrays, non-JSON objects and object symbol/accessor
properties. Dates use explicit RFC3339 offsets, retain all six microsecond digits and
normalize to UTC; Date's millisecond precision must not round away source evidence.
Check actual calendar validity and years 1–9999. Depth is capped at 16; encoded content
at 1 MiB. Oversized evidence is rejected rather than clipped. Inputs are not mutated.

The helper rejects invalid RFC3339 offset minutes/hours. The current Python reference
delegates offset parsing to datetime.fromisoformat; any difference on invalid offsets
is a reference-validation question for Akbar, not permission to accept them in a client.
Valid protocol inputs retain the agreed canonical form.
The numeric timezone grammar is defined in
[RFC3339 section 5.6](https://www.rfc-editor.org/rfc/rfc3339#section-5.6).

## Validation and remaining gates

Node tests read the two original published vectors and verify both exact bytes/hash.
They also cover Unicode/numeric-key ordering, key collision, line/date normalization,
microsecond/early-year/day rollover, input preservation, invalid values/dates, size/depth
and prototype-sensitive evidence keys.

A separate ignored deterministic cross-check generated 128 synthetic payloads, varying
Unicode/control text, line endings, key ordering, safe-integer bounds, date offsets and
missing sets. The unchanged Python reference and browser helper produced identical
canonical bytes and hashes for all 128. These are logic/portability results, not a claim
of Canvas access. Supplemental scratch scripts/data are not shipped.

Run `node --test extension/canvas/source-digest.test.mjs`. Required repository lint,
format and isolated-backend evidence is recorded on the published PR checkpoint.
Final observed results on this contract-based branch: **28 Node tests**, **128 generated
cross-language comparisons**, and **415 backend tests** pass, plus Ruff lint/format,
Prettier and whitespace checks. The backend run used a fresh disposable local Postgres
instance, stopped after validation, with two existing dependency/test-key warnings.
No new web suite/build is claimed because web files are unchanged. The Outlook #54
tests belong to its separate branch, not this backend count.

An independent read-only reviewer reran all 28 Node tests, probed exact depth/byte
acceptance boundaries and found no blocking defect for this limited offline helper.
Adding those successful boundary probes to the committed suite was an optional test
improvement, not a reproduced implementation failure. Actual browser operation, provider
collection and production authorization were outside that review.

No browser installation, provider call, migration or production change occurs here.
Actual browser support/session/content behavior still requires P0-M1 access and install
scope. Production sync wiring waits for implemented/reviewed P1-A1 methods and the
remaining P0-M1 acceptance; do not connect this helper to an invented upload API.

Next: opposite-owner review of this small module; continue provider/collector fixtures
under a new exact claim, and consume actual storage methods only after the owner lands
them. STATUS updates stay serialized through Akbar's current claim.
