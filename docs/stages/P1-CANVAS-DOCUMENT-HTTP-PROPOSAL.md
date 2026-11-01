# Private document staging HTTP — M transport proposal

Owner/reviewer: Murtazo proposes HTTP assembly; Akbar owns shared transactions and
agrees the consumer boundary. Claim [#147](https://github.com/Akbarhoja/wrytely-agent/issues/147).
**Proposed only. No routes, configuration or activation are implemented here.**

This selects the next P1-M1 integration slice after #144/#146. Existing UI/host
CI passed, but installed-browser/P0 access and remaining source kinds are separate
gates. It reuses the agreed [exact v2 document protocol](https://github.com/Akbarhoja/wrytely-agent/blob/7f4f09f79dbc403d51347a0f8bba64ac52a5c319/docs/contracts/CANVAS-DOCUMENT-WIRE-v2.md)
at #118 `7f4f09f` ([M agreement](https://github.com/Akbarhoja/wrytely-agent/pull/118#issuecomment-6554751370)) and A's implemented begin/put/finish Store
methods. That protocol explicitly requires agreement on HTTP names and assembly.
This document changes no hash, manifest, receipt, authorization or quota semantics.

## Proposed endpoint map

All are private POST operations beneath the existing Canvas prefix:

| Path                                             | Exact body operation | Existing Store call                                                        |
| ------------------------------------------------ | -------------------- | -------------------------------------------------------------------------- |
| `/v1/source-connections/canvas/documents/begin`  | `begin_document`     | `begin_document_upload(actor, body, extractor_versions=trusted_versions)`  |
| `/v1/source-connections/canvas/documents/parts`  | `put_document_parts` | `put_document_parts(actor, body)`                                          |
| `/v1/source-connections/canvas/documents/finish` | `finish_document`    | `finish_document_upload(actor, body, extractor_versions=trusted_versions)` |

The route selects one operation; body.operation must match it. Every body retains
integer schema_version2 and the exact agreed keys. Publication's batch_type is
forbidden. Parts include1–50 declared unique slots; existing field/Unicode/manifest
bounds are validated by the shared implementation, not a second HTTP parser.
Unknown fields, posted account/user ownership IDs or extractor configuration are rejected.
No raw-file fetching, HTML conversion, model extraction or source execution occurs.

Return the agreed immutable operation receipt with HTTP200. Do not manufacture
latest progress on replay or expose text, provider subject, bearer or lease token.
Finish ready:true means a private protocol root is materialized; it is not an
observation, resource completion, source activation or drafting permission.

## Identity and configuration

- Reuse existing HTTPBearer parsing. The opaque ingestion bearer is passed to
  Store; current account/connection/generation/scope/subject/scan/resource/lease/
  expiry authorization stays authoritative there, including before receipt replay.
- A Wrytely session JWT is not interchangeable with an ingestion credential.
  Never derive actor ownership from body IDs, Origin headers or browser claims.
- Reuse the same configured Canvas origin set used to construct Store and existing
  routes. No request field changes it; no alternate cloud OAuth/account is added.
- Proposed M-owned factory addition: keyword-only
  `create_app(..., canvas_document_extractors: tuple[str, ...] = ())`.
  Pass trusted nonempty versions to a new M router registration function; empty
  versions or absent Canvas configuration yields503. The default app stays off.
  Versions must be server-selected normalized identifiers accepted by A's validator,
  never taken from upload metadata as configuration. No shared Settings edit yet.
- Before actual application configuration, agree the real extractor version and
  semantics with its M implementation. A configured name alone cannot certify
  complete extraction; existing HTML preparation remains explicitly partial.

## HTTP bounds and errors

Reuse CanvasRoute streaming bounds/redacted validation/no-store behavior. A new
document route class caps raw request bytes at1MiB before JSON decoding, accepts
application/json only, and rejects query parameters. Shared request JSON-size,
field/normalization and quota checks remain independently enforced. No cap is raised.
Preserve agreed document-wire section5 rather than copying schema1 conventions:
the document-specific adapter maps validation failures to400; existing schema1
routes keep422. Document404 responses have zero body bytes.

| Situation                                                | Status/projection                                     |
| -------------------------------------------------------- | ----------------------------------------------------- |
| Missing/rejected ingestion credential                    | 401 `Reconnect Canvas`, WWW-Authenticate Bearer       |
| Configuration unavailable                                | 503 generic document-not-configured message           |
| Body too large / media type                              | 413 / 415 using existing CanvasRoute behavior         |
| Malformed body, bounds, operation, key or unknown fields | 400 generic invalid Canvas request                    |
| Unavailable/nonowned opaque upload lookup                | 404 with an empty body                                |
| Current control/scan/lease/replay/resource/root conflict | 409 controlled `{code}` allowlist                     |
| CanvasDocumentUploadLimited                              | 429 controlled quota code and Retry-After30           |
| Unexpected operation failure                             | 500 redacted fixed failure code; outcome not inferred |

Conflict allowlist extends the current C2 transport codes only with implemented
document_conflict, document_expired and document_not_ready. Unknown conflict codes
project state_changed. Quota codes are document_upload_limit/document_bytes_limit;
unknown quota details are redacted. Propose a bounded header `Retry-After: 30`
(seconds), not an additional receipt/body field. It is a minimum pause before
another authorized attempt, not a promise that capacity will be available then.
Retained expired bytes need separately approved cleanup; no automatic retry or
expiry-based quota release is invented. A explicitly agrees/amends this30-second
transport hint with the route details before implementation.
All operation responses and controlled validation/auth failures use no-store.
No exception repr, body, secret or private source fragment is logged or echoed.

Call Store once per request, with no retry or async send queue. A lost/failed HTTP
response can follow a committed receipt; it is not proof of rejection. Future
extension consumption must persist the original key/body before dispatch and use
only exact authorized receipt recovery. Lease replacement follows the agreed hash
exception, not a new transaction key. No potentially delivered send is blindly retried.

## First implementation and acceptance

After explicit A agreement, M claims app/canvas_document_api.py, a minimal
app/main.py registration/factory delta and tests/test_canvas_document_upload_api.py.
Reuse existing CanvasRoute and Store methods. No new SQL, Store, credential store,
source journal, general middleware rewrite or second validation contract.

Tests must exercise real Store begin→parts→finish and immutable replay across a
recreated app; wrong account/session bearer/subject/generation/scan/scope; lease
rotation/expiry, malformed operation/version/fields, raw byte/media/query limits,
no-store and private error redaction, quotas and default-off configuration. Test
late rollback and response loss without provider refetch or new request identity.
Run focused checks and required Ruff/format/full disposable backend before review.
Integration uses an explicitly recorded reviewed A base containing the methods;
the current M branch does not pretend those methods exist in its older shared tree.

Publication/schema2 academic batch HTTP and extension document journal/collector
are subsequent separately claimed slices. This does not silently reduce full P1:
remaining resources, linked document extraction, installed lifecycle and actual
controlled-course collection still need proof. No live/deploy/main merge permitted.

## Requested A decision

Agree/amend the three paths, operation/body/receipt passthrough, errors/default-off
extractor injection and first implementation boundary above. Name the exact shared
integration head for that implementation. Agreement on the protocol or #135 code
alone does not imply acceptance of these new HTTP names or enabled configuration.
