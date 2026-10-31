# Canvas HTML extraction implementation plan

> Use superpowers:executing-plans inline and test-driven-development.

**Goal:** Prepare inert plain text from supplied Canvas HTML without asserting complete source coverage.
**Architecture:** Pure standard-library HTMLParser adapter; immutable result with text, partial/blocked status and controlled reasons. No network, storage, rendering or dependencies.
**Tech stack:** Existing Python 3.12+ and pytest.
**Spec:** docs/WORK-ORDERS.md P1-M1; claim #65; scoped design below.

## Global constraints and design

Accept UTF-8 bytes only. Bound input at 1 MiB, output at 200,000 characters,
parser events at 20,000 and tag depth at 128. Optional lower limits aid callers/tests;
they cannot exceed these ceilings. Never return truncated successful text after a
limit violation. Exclude active/nontext and explicitly hidden elements. Preserve
block/line separation, entities and NFC Unicode. No DOM/CSS evaluation, fetching or
proof that text corresponds to visible pixels. Every nonempty result is partial,
including structurally clean HTML. Linked/embedded content stays explicitly unread.
Failures return empty blocked results and fixed reason codes without source echoes.

## Task 1: Pure adapter and acceptance tests

Files: integrations/canvas/**init**.py, integrations/canvas/html_extract.py,
tests/test_canvas_html_extract.py, docs/stages/P1-CANVAS-HTML-EXTRACTION.md and this plan.
Consumes supplied bytes, no authentication or shared interface. Produces
extract_html(content, *, max_bytes, max_chars, max_events, max_depth) -> HtmlExtraction
with text/status/reasons. Callers retain authorization/provenance independently.

- [x] Write tests for visible structure, Unicode/entities, hidden/active text,
      malformed nesting, embedded/linked gaps, empty/invalid bytes and all bounds.
- [x] Run focused suite RED before creating implementation.
- [x] Implement the adapter and run focused suite GREEN.
- [x] Add handoff doc; run required Ruff/format/full backend on disposable Postgres.
- [x] Independent review, commit only claimed synthetic/code files, publish draft.

## Review focus

Hidden nested descendants cannot leak through mismatched tags. Entity output must
count toward character limits. Huge attributes still count toward byte limits.
Malformed or unclosed markup cannot claim completeness. Image/math/link omission
must remain visible to consumers. PDF/Word/image/OCR and C2 readiness are excluded.

Pre-flight: no shared interfaces. Base57ca6ea; unrelated private course evidence
remains in the original checkout and is excluded from this worktree/PR.

Validation:45 focused synthetic tests and full550 backend tests passed on isolated
Postgres port55489. Ruff check/format, Prettier and diff checks pass. Independent
review found the same malformed markup bugs now covered by five RED-to-GREEN cases,
then independently reran45 tests with no remaining scoped blocker. No source data
or live configuration was included. Counterpart review and merge remain pending.
