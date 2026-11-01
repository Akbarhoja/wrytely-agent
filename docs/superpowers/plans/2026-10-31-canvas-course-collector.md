# Canvas course collector implementation plan

> **For agentic workers:** Use superpowers:executing-plans with TDD and a fresh whole-branch review.

**Goal:** Collect current-course metadata through the existing durable journal, without manual course IDs or false academic completion.

**Architecture:** Reuse #106's bounded reader, #56's canonicalizer and #96's journal operations. A private operation set runs beneath one shared outer pairing lock; existing public methods retain the same lock behavior. The collector selects one bounded action per call: begin, recover, renew, fetch/commit one page, close courses or finish if all resources are closed.

**Spec:** [#100](https://github.com/Akbarhoja/wrytely-agent/issues/100), [P1-M1](../../WORK-ORDERS.md).

**Global constraints:** M-owned files only; no new durable schema, shared methods, provider calls, installed host or scheduler. Preserve pending keys/pages and existing control fences. Output only controlled status/counts. No grant/send/spend/deploy/main merge. P0 Canvas/Outlook live work stays with A.

## Task 1 — mapping and collector integration

- [x] Write mapper tests for exact C2 projection, NFC/line endings, missing/oversize/nonportable metadata, enrollment ambiguity and invalid IDs/duplicate pages. Watch missing implementation fail.
- [x] Implement `collector.mjs` using inherited `canonicalSourceBytes`, no body/HTML/grade fields. Missing fields become explicit partial metadata; invalid IDs invalidate the entire page.
- [x] Extend existing discovery test fixture for actual bounded Canvas responses. Write collection, pending replay after worker recreation, resume, account/scope changes, failure preservation, locking, multi-page gaps and open-academic-resource tests; watch missing method fail.
- [x] Move existing methods into a private unlocked operation set with a single public lock wrapper; add private collector inspection and inject the existing page reader from client.mjs. No separate journal or lock.
- [x] Run all Node suites and actual client/API interoperability. Run required Ruff/format/full disposable backend, web/TypeScript, formatting/diff checks.
- [ ] Fresh review, one regression fix pass if needed, then commit/push draft PR with exact evidence and remaining CI/review/live gates. Leave #100 open for academic resources/host/recovery acceptance.

## Review focus

- Metadata gaps on an early page must survive a later complete page; use the existing conservative scan-incomplete flag, never a new journal schema.
- A pending upload must not refetch or discard captured provider data.
- Context/profile must bracket capture and final delivery; nothing invokes unlocked operations outside the private outer lock.
- Recovery must remain bounded and receipt-key based, including a lost resume acknowledgment.
- Unsupported metadata or provider failure must remain visible; no source text, URL/cursor, subject, bearer or writer lease in collector results.
