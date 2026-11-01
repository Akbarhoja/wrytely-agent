# Durable assignment upload in the paired worker

Owner: Murtazo (`murtazokhon-tech`), claim [#113](https://github.com/Akbarhoja/wrytely-agent/issues/113), coordination [6552110946](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6552110946). Stacked on own #112 academic HTTP adapter, exact `7d400010`; counterpart acceptance of #112/#110 remains separate from their successful CI.

## Behavior

`commitAssignmentPage` accepts at most50 identity-bound raw assignment records with **already extracted text**. It reuses the existing assignment mapper and canonical source helper, strips raw/provider-only fields, and builds exact C2v1 assignment items. Course, assignment and extracted identity must agree. Normalized title300/content24000 limits reject oversized text without clipping. Dates require explicit requesting-student context or retain missing evidence. Inputs cannot supply credentials, leases, cumulative counts or alternate references.

The existing paired client now routes `academic/batch` and `academic/resource` through the same trusted bearer transport and per-storage operation lock. It persists captured intent before dispatch, validates receipts and persists acknowledgment before delivery. Explicit recovery reuses the same key and captured payload; lease renewal changes only the lease token. An accepted page whose acknowledgment was lost can reconcile only its exact advanced resource checkpoint. No timer or generic external-send retry is added.

Journal version2 adds one bounded assignment progress record alongside the existing required/closed resource ledger. Strict legacy version1 migration preserves captured course/finish/resume intents and rejects academic state disguised as version1. Assignment resources run sequentially, with up to100 pages/5000 items each and global sequence10000. Counts reset for each selected course; course metadata counts remain separate. The envelope bound includes server JSON spacing so a locally accepted page cannot be stranded by that serialization difference. Existing8MiB journal and1MiB envelope bounds remain.

An academic receipt must match captured identities, observation coverage, canonical content digests, UUIDs and exact nonnull source-version tuples. Missing, duplicate, substituted or malformed receipts leave the original pending intent recoverable. Account, generation, scope and credential fences remain in the common prepare/delivery path. Results expose safe status/checkpoints, not text, subjects, credentials or leases.

Complete resource closure requires a terminal complete page and no earlier incomplete or historical observations. Honest partial/restricted/unsupported closure remains possible without a page. A manifest acknowledgment must match resource/count/checkpoint and include a digest for complete closure. Every required resource must still close before the scan finishes. This does not promote staged source versions or enable model freshness.

## Verification

Helper and journal tests first failed for missing implementation; final focused suite and full verification are recorded in the PR handoff. Synthetic tests cover exact replay before/after dispatch loss, resume after accepted lost acknowledgment, legacy migration, storage failures, per-course isolation, selection/terminal/page limits, scope/account/expiry fences, incomplete/historical evidence, malformed/substituted receipts and manifest requirements.

Implementer verification passed310 extension tests,114 web tests, TypeScript, required Ruff check/format149 files and changed-file Prettier/diff checks. Full `uv run pytest -q` passed714 tests in454.22seconds on designated disposable local Postgres, with two existing warnings. That includes the ten old actual course-client/HTTP/Store scenarios; it is not actual assignment-client HTTP acceptance. Initial sandbox cache/temp access failures prevented Ruff/web test discovery; normally approved reruns passed. Those runner restrictions are separate from application evidence.

Fresh independent review reproduced three defects before correction: numeric persisted course identity, coordinated receipt-digest substitution and compact-versus-server JSON envelope size. Regression tests were observed failing before fixes. The reviewer ran synthetic Node checks and read existing Store/API contracts; database and provider evidence are separate.

The reviewer independently reran306 extension cases and found no remaining blocker after fixes, including the added begin-resource receipt guard. Four additional legacy pending migration tests passed in the implementer's final310-case run; no implementation changed after review. Remote CI and Akbar counterpart acceptance are separate pending gates.

## Remaining product work

This closes durable assignment-upload linkage for already extracted short text. It does **not** fetch assignment pages, parse HTML, install/host an extension, collect all required academic kinds, execute browser suspension acceptance or provide live Canvas proof. The unchanged assignment mapper/test and historical #60 stage/plan files are reused; those older records do not supersede current scope or authority. Actual assignment client-to-HTTP/Store acceptance is the next scoped verification slice; the old course-only loopback scenarios remain regression coverage.

Long-document-only schema2 wire/vectors/orphan cleanup remain the #78 counterpart gate. Other academic kinds, permission-aware collection, installed-host recovery, activation/runtime consumption and full semester supervision remain required. A's accepted #98 shared normalization fix must stay in consolidation. Shared STATUS/CI and pending API/collector counterpart reviews remain Akbar requests, not edits in this slice.

P0 Canvas access is A-owned under [6548991501](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6548991501). Outlook is optional with live work paused under [6549522832](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6549522832); old TEAM/work-order text on this stacked base predates those decisions. No live source/account read, provider call, OAuth grant, message send, spend, install, production migration, deployment or main merge is performed. Chrome stays open and untouched; automation remains off.
