# Canvas pairing client implementation plan

> Execute inline with test-driven-development and a final independent code review.

**Goal:** Explicit extension code redemption, private credential persistence and same-session identity binding.
**Architecture:** A worker-only client consumes #64 HTTP routes and reuses the existing
diagnostic checkedOrigin/makeReader. Injected Chrome local storage is restricted to
TRUSTED_CONTEXTS before access. Credentials never leave the client through return values.
**Spec:** WORK-ORDERS P1-M1; accepted C1 lifecycle/#64 HTTP handoff; claim #69.
**Base:** reviewed f1e0d9b/#52, isolated worktree; unrelated stacked PRs excluded.

## Global constraints and interface

createPairingClient({apiOrigin, canvasOrigin, storageArea, fetchImpl, canvasFetch}) exposes
redeem({code, devicePublicId}), bindCurrentSession(), readCachedConnection(). Config origins
must be exact canonical HTTPS origins. Browser owner IDs/Clerk tokens are never accepted.
Every API call is one POST attempt with credentials:omit, no-store, redirect:error,
15s timeout, narrow payload/headers and a16KiB actual response-byte cap. Returned schema,
origin, provider, generation, UUID, expiry and secret length must validate before storage.

Redemption clears the old local credential before the request. A lost/invalid success
response requires a fresh code; no automatic retry. Persist only a narrow known record,
under an API/Canvas-origin-specific key, and return a copied safe C1 projection.
Storage/network uncertainty attempts local cleanup and blocks this instance if cleanup
fails. No remote revocation is promised by local cleanup. Serialize by storage object
within one worker realm; cross-context ownership remains an integration gate.

Binding derives subject exclusively from the same-session Canvas profile reader, not a
method argument. Recheck profile after the bind. On account change, attempt the accepted
changed-subject bind to fence the server, clear local state and return a controlled error.
An uncertain fence outcome must not be called confirmed revocation. Cached state is never
server authorization/readiness. No source reads, C2 sync, manifest/UI/permission changes.

## Task 1: Pairing client and acceptance

Four new files: extension/canvas-pairing/client.mjs and client.test.mjs;
docs/stages/P1-CANVAS-PAIRING-CLIENT.md; this plan.

- [x] Write RED tests for role-specific requests, private storage ordering, bad replies,
      bounds, code replay uncertainty, expired/revoked credentials and account changes.
- [x] Implement client and get GREEN, including cleanup and concurrency failure cases.
- [x] Run combined Node, required backend/Ruff checks and new-file formatting.
- [x] Independent review; publish draft and counterpart handoff with exact evidence.

Review focus: commit-then-error storage, cleanup failure/recreation, async overlapping
clients, body cancellation masking size errors, and login change between the two profile
reads. No private provider evidence, live grants/calls, deployment, migration or sends.
Chrome stays open. #58 context/scope and future UI/packaging remain separate gates.

Validation:53 combined Node cases (41 client+12 unchanged probe) pass; reviewed-base
backend391 pass on a new disposable database, with Ruff check/format and new-file
Prettier/diff checks. Independent review found a credential-generation acceptance
issue; its RED regression preceded exact equality, with lower/higher cases passing.
Additional malformed response/origin and null-input regressions also went RED to GREEN.
No final independent GREEN suite is claimed from the reviewer; author checks above
verify the fixes. Counterpart review and real installed binding remain pending.
