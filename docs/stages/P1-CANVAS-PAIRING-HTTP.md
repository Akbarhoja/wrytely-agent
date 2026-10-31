# Canvas pairing HTTP handoff

M-owned lifecycle slice, [work #63](https://github.com/Akbarhoja/wrytely-agent/issues/63),
stacked on reviewed operator configuration #62 at `682ce16`. Reuses existing Clerk
session verification, Settings, Store and migration 010; no new storage or provider client.

| Route                                              | Authority                  | Body / result                                                          |
| -------------------------------------------------- | -------------------------- | ---------------------------------------------------------------------- |
| POST /v1/source-connections/canvas/pairing         | Verified Clerk session     | `{origin}`; one-use challenge/code and expiry                          |
| POST /v1/source-connections/canvas/redeem          | Possession of pairing code | `{code, device_public_id}`; safe connection plus ingestion bearer once |
| POST /v1/source-connections/canvas/bind            | Ingestion bearer           | `{origin, provider_subject}`; safe connection                          |
| GET /v1/source-connections/{connection_id}         | Verified owner session     | Safe projection or indistinguishable404                                |
| POST /v1/source-connections/{connection_id}/revoke | Verified owner session     | Empty body or `{}`; disconnected projection                            |

Operator `Settings.canvas_origins` is passed to the single existing Store constructor.
Its default empty tuple disables issuance, redemption and binding with 503; owner
read/revoke remain available. Actual origin configuration and database rollout require
their own authorization. No real institutional origin or environment file is changed.

Private routes derive ownership from verified sessions. Device IDs and provider
subjects cannot select an owner. Binding records same-session adapter evidence;
this route does not independently verify a Canvas login or establish source readiness.
The future extension must obtain the subject from the actual same-session identity
read, handle login changes and hold collection until the remaining scope/sync gates.
An ingestion bearer cannot authenticate private reads; a Clerk token cannot bind.

All route bodies have a 16 KiB actual received-byte bound, including chunked or lying
Content-Length requests. Nonempty bodies require application/json. Unknown fields
and invalid schemas produce generic 422 without input echoes. Responses and controlled
errors use Cache-Control:no-store. Codes/bearers/subjects are not logged by these
handlers. External proxy/access-log policies must preserve that boundary at rollout.

Store outcomes map to fixed errors: invalid/used/expired pairing 400, rate cap 429,
invalid credential 401/reconnect, unknown/nonowned ID 404, unprovisioned account 409,
unavailable storage/config 503. Subject mismatch retains Store's committed generation
increment and revocation before 401. A lost redemption response requires fresh
authenticated pairing; callers must not retry expecting bearer recovery.

The existing persistent Store redemption cap applies to schema-valid attempts only.
Deployment-level HTTP/IP throttling, slow-request handling and capacity review remain
mandatory before public rollout. This slice does not implement or authorize rollout.
No sync/scope/upload endpoints, source ingestion, collector, provider call, model task,
outbound delivery, live grant, retained migration or deployment is included.

Validation uses synthetic identities/origins and a separate disposable local Postgres.
The dedicated API suite covers the real Store lifecycle, account/credential separation,
replay/expiry/rates, account-switch revocation, default disablement, redacted failures
and actual request size. Exact final checks and commit are recorded in the PR/#4.
Live Canvas origin/course/install/session checks remain open in P0-M1.
