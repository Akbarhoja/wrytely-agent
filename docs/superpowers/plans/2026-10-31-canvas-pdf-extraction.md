# Bounded PDF extraction implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement task by task.

**Goal:** Prepare supplied PDF bytes as partial page text without parsing in the calling process.

**Spec:** docs/contracts/PDF-EXTRACTION-BOUNDARY.md and M agreement on #76/6541158295; claim #87.

**Architecture:** Existing #66 Canvas package is reused unchanged. A bytes-only parent launches a fixed fresh Python child on Linux. The child installs and verifies hard memory/CPU caps before importing pypdf or reading the supplied document. Parent streams bounded pipes against a wall deadline, terminates/reaps on failure, and permits one child at a time. Windows/macOS fail closed. Returned page text is private partial evidence; no ingestion or document contract is created.

**Tech Stack:** Python standard library subprocess/selectors/resource; locked pypdf6.21.4.

## Constraints

10MiB input;200 pages;200,000 normalized characters;1GiB address space;5 CPU seconds;10 seconds wall. Lower caller limits only. Parent stdout cap2MiB, stderr8KiB. No source-supplied URL/path/command, network, decryption, OCR, attachment extraction, parser retry or in-process fallback. Generic blocked reasons contain no text or exceptions. No shared/configuration/CI/STATUS edits or activation.

## Tasks

- [x] Write failing tests in tests/test_canvas_pdf_extract.py: strict ceilings, unsupported platform, partial page provenance, malformed/encrypted/empty/mixed/image pages, normalized limits, actual Linux memory/CPU caps, wall termination/reaping, pipe bounds, and concurrency.
- [x] Verify missing-module failure before implementation.
- [x] Implement integrations/canvas/pdf_extract.py parent, immutable local result/limit types and fixed subprocess supervisor; no pypdf import.
- [x] Implement integrations/canvas/_pdf_child.py: verified OS caps before parser import; no logging/raw errors; normalized page text and honest gaps.
- [x] Run focused Windows checks and full locked backend/lint/format on disposable Postgres.
- [x] Obtain actual Linux CI results; code2c2e2ca CI41201265440 reports673 passed/no skips, including all14 Linux-only checks.
- [x] Independent read-only review, handoff doc and draft PR #88 linked to #87; no completed P1/live capability claim.
- [ ] Akbar counterpart review and integration acceptance; protected-main approval and activation remain separate.

## Review focus

Normalization expansion must not defeat character limits. Full stdin pipes must not defeat wall time. Both output pipes are bounded before retention. Every timeout/failure reaps the child and discards prefixes. Partial extraction never certifies layout, image/equation fidelity or complete source coverage.
