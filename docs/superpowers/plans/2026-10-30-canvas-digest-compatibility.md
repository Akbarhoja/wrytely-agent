# Canvas digest compatibility implementation plan

Execute directly in this session under the existing C2 portability requirement.

**Goal:** Give the extension a browser-compatible implementation of the agreed canonical
source bytes and SHA256, verified against Akbar's unchanged Python vectors.
**Spec:** [C1/C2 v1](../../contracts/CONNECTION-SYNC-v1.md), agreed at `ccf84dc`;
claim [#55](https://github.com/Akbarhoja/wrytely-agent/issues/55).
**Base:** `3780025`, protocol/code identical to `ccf84dc`, STATUS-only difference.
**Architecture:** Pure JavaScript normalization/serialization plus Web Crypto; no fetch,
storage, credentials, pairing, sync endpoint, mapper or consumer wiring.
**Stack:** Standard JavaScript, TextEncoder, Web Crypto, Node built-in test runner.

## Tasks

- [x] Verify all 24 reference tests on native Windows with encoding warnings as errors.
- [x] Inspect terminal partial/expiry/replay semantics and record C1/C2 agreement in #48/#4.
- [x] Claim only new extension compatibility files and scoped documentation.
- [x] Write Node tests reading original UTF-8 vectors; observe missing-module failure.
- [x] Implement `canonicalSourceBytes(payload)` and async `sourceDigest(payload)`.
- [x] Check exact vector bytes/hash, code-point/numeric-key ordering, Unicode validity,
      normalization collisions, safe integers/types, depth/size and microsecond dates.
- [x] Run Node, Ruff, format and required full disposable-Postgres checks (28 Node / 415 backend).
- [ ] Publish one draft PR and request opposite-owner review; serialize STATUS via Akbar.

No live Canvas access or production P1 collector is implied. P0-M1 session/content/install
checks and implemented P1-A1 persistence remain prerequisites for real ingestion.
Read shared vectors and Python code; do not edit/copy their fixtures or implementation.
Do not wire uploads or change existing diagnostics while protocol preparation is reviewed.
