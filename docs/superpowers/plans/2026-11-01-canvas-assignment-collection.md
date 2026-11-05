# Bounded assignment collection implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline, TDD and one fresh whole-branch review. No implementation delegation.

**Goal:** Fetch one selected assignment page, reuse existing inert HTML extraction and persist mapped evidence through the existing paired journal.

**Architecture:** Extend the existing strict reader with assignment pagination. An M-owned private HTTP adapter reuses the unchanged Python HTML extractor with ingestion-credential/current-context checks before and after conversion. The existing collector/journal lock chooses retained assignment resources, recovers pending receipts before fetching, binds extraction responses and calls existing assignment commit/finish methods. No second parser, storage or runtime.

**Spec:** [#117](https://github.com/Akbarhoja/wrytely-agent/issues/117), claim [6552448738](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6552448738), P1-M1/C2v1; base own #116 `36c17400`. Existing ten claimed paths plus three unchanged HTML prerequisites from `e3eb239e` only.

## Constraints

- One explicit page/tick, selected retained course only, same operation lock/journal/lease/control fences. Recovery never re-fetches a pending mapped page.
- Strict same-course pagination: `per_page=50`, `override_assignment_dates=true`, only opaque `page` continuation; 50 items, 1MiB provider body, existing 4000 cursor/16384 Link bounds.
- Existing extraction ceilings remain; adapter lowers output to24000 chars/item and aggregate HTML input to1MiB/50 items, wrapper2MiB. No clipping, HTML execution, server fetching or raw-source persistence.
- Extractor always partial; preserve `html_text_only`, linked/hidden/nontext/malformed/size gaps. Locked descriptions are not sent for extraction. Empty pages may terminalize as complete enumeration; nonempty HTML evidence cannot falsely close complete.
- Ingestion bearer resolves owner; posted connection/generation/scope/course must match current selected context before and after conversion. No new shared/contracts methods or source activation.
- No live/account/provider calls, grants, sends, spending, installation, scheduler, host, deployment or main merge. Chrome untouched/open, automationoff. P0 A-owned; Outlook optional/paused.

## Tasks

- [x] Add strict assignment-reader tests, observe missing method RED, implement using existing bounded transport and run reader regressions.
- [x] Add actual API/Store extraction tests, observe missing route RED, reuse unchanged HTML implementation and add bounded authenticated adapter; verify authority, controls, limits and zero source writes.
- [x] Add synthetic production-client collector tests RED for missing method; implement one-page/recovery/finish flow in existing lock, bind private extraction output, and verify account/scope/expiry/lock/error/partial cases.
- [ ] Run full Node and required Ruff/format/full pytest using disposable PG. Fresh independent review/fix, scoped evidence docs and draftPR/Akbar handoff. CI/counterpart and live acceptance separate.

## Review focus

- No extraction request can read unselected course content or accept stale credential/context; recheck after conversion before returning private text.
- No dropped/mismatched extraction row, raw HTML in journal/results, or false full coverage for linked/nontext content.
- Pending capture/recovery and terminal receipts take precedence over any provider fetch or lease replacement.
- Partial earlier observations, worker recreation and per-course checkpoint selection retain correct cumulative counts.
- Resource closure follows retained scan ledger even when live context removes a course; such removed resources must block/report honestly, never fetch them.

Canvas date-query semantics verified against [official assignments API](https://developerdocs.instructure.com/services/canvas/resources/assignments); no private account was accessed.
