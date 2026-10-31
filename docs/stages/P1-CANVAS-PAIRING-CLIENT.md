# Canvas worker pairing client

M-owned claim [#69](https://github.com/Akbarhoja/wrytely-agent/issues/69). Base
`f1e0d9b` / reviewed #52; reuse checkedOrigin/makeReader without editing the diagnostic.
Consumes accepted C1 semantics and implemented [#64 HTTP routes](https://github.com/Akbarhoja/wrytely-agent/pull/64).
The API implementation is on a separate reviewed stack; integration must combine and
verify the exact heads before activation. This branch is not the consolidated product.

`createPairingClient({apiOrigin, canvasOrigin, storageArea, fetchImpl, canvasFetch})`
returns three worker-only methods:

- `redeem({code, devicePublicId})`: explicitly redeem a fresh one-use code, persist the
  narrow credential record and return only the safe C1 projection in pending_identity.
- `bindCurrentSession()`: obtain Canvas subject from the current same-session profile,
  bind with the stored ingestion bearer, re-read the profile and persist connected state
  only if identity, connection ID and credential generation still match.
- `readCachedConnection()`: return a copied local projection or null. Expiry projects
  reconnect_required. This is cached evidence, never server authorization or readiness.

Origins are trusted, pinned packaging/operator configuration, not webpage form inputs.
Both must be exact canonical HTTPS origins; paths/default ports/userinfo/query/fragment,
empty labels and trailing dots are rejected. The caller owns a stable nonsecret device
ID; it is not a student/account identity. No Clerk token or posted owner ID is accepted.
Only code/device ID goes to redeem; only configured Canvas origin/profile-derived subject
goes to bind with the ingestion bearer. The profile ID is not persisted or returned.

Backend requests use one attempt, credentials:omit, no-store, redirect:error and15s
timeout. API replies must have the expected URL, JSON type and an actual streamed body
of at most16KiB. UUID/provider/origin/state/generation/aware expiry/secret types validate;
invalid calendars and offsets fail closed. Only known projection fields and the bearer
are stored. No code, response extras, source text or provider error body is persisted.
No secret appears in exported errors, return values or logs. Canvas profile reads reuse
the bounded GET-only diagnostic reader, with its documented session/identity limits.

Chrome storage access is restricted to TRUSTED_CONTEXTS before any client access;
see [Chrome storage documentation](https://developer.chrome.com/docs/extensions/reference/api/storage).
Use the real chrome.storage.local area in a future reviewed worker entrypoint. The key
is scoped by both configured origins; storage.sync and page localStorage are not used.
This is extension-private storage, not an encryption-at-rest guarantee. The installed
P0 diagnostic requests no storage permission and remains unchanged by these modules.

Starting a new redemption clears the prior local record before the HTTP attempt.
Lost/malformed responses or uncertain persistence require fresh pairing, with no retry
loop. Commit-then-error writes trigger best-effort cleanup. Failed cleanup quarantines
the key for all client instances sharing that storage object in the current worker
realm. A later explicit redemption can proceed only after cleanup succeeds. This is
not a durable cross-process transaction marker: if cleanup failed, do not treat a
recreated worker's surviving cache as a confirmed result. Actual server verification
and cleanup/re-pair recovery remain required; local deletion does not revoke a server
credential. Only the existing verified-owner web route performs an explicit revoke.

On a login change between profile checks, the client attempts another bind with the
new observed subject, consuming the accepted server account-switch fence, then always
discards local state. A lost fence response remains unknown; no confirmed revocation
is claimed. A switch away and back between checks cannot be detected by this probe.
The server remains authoritative for token ownership, generation, expiry and revoke.

Concurrency is serialized by storage object within one worker JavaScript realm. Future
assembly must keep one trusted worker owner, verify message senders, and never expose
these methods/credentials to a page or content script. No cross-context locking, UI,
message listener, manifest/permission expansion, automatic startup, alarm or live
installation is added. C2 scope/context must be implemented/reviewed before any source
operation; a connected cached projection is not permission to collect or deliver work.

Tests use synthetic fetch/storage adapters only. New client recreation tests are not
actual MV3/browser restart evidence. The full Node suite includes the unchanged P0
probe tests. Code review found a generation-change acceptance bug; a failing regression
preceded exact generation matching. Additional RED cases pinned response type/calendar
and origin validation, and null input errors. Final counts are recorded in the PR.
Backend checks belong to this P0 base, not the newer uncombined #64/#66/#68 stack.

No source upload, academic work, live provider/model request, send, deployment, retained
migration or private course-derived fixture is included. Chrome remains untouched/open.
Counterpart review, real storage/permissions and end-to-end binding remain separate gates.
