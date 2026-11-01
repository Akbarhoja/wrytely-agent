# Canvas browser UI/package implementation plan

> Use superpowers:executing-plans inline; fresh final review uses requesting-code-review.

**Goal:** Package private student controls over the existing inactive Canvas host.

**Architecture:** Native popup/options share ui.mjs; boot sends existing private
messages, worker registers existing host. prepare.mjs copies an exact allowlist,
pins origins and derives CSS tokens from the existing web canonical source.

**Tech:** ES modules, native HTML/CSS, Node test runner, Chrome MV3.

**Spec:** [stage](../../stages/P1-CANVAS-BROWSER-PACKAGE.md) and its linked UX/design.

## Constraints and review focus

Claim145. New extension/canvas-browser directory and these two scoped docs only.
No host/web/backend/shared/CI/STATUS edits. Default inactive, no installation,
account/source/provider/model calls, permission grant or Chrome operation.
Review stale replies after pause, unknown mutation outcomes, code clearing, exact
origin/CSP/dependency closure, symlink/output overwrite refusal and false coverage.

## Task 1: UI

- [x] Write ui.test.mjs for safe projection, malformed/private replies, explicit
      identity/consent, duplicate commands, pause interruption, stale replies and codes.
      Run node --test extension/canvas-browser/ui.test.mjs; expected missing-module RED.
- [x] Implement ui.mjs shared state/controller and native DOM mount, popup/options,
      boot and stylesheet. Run focused tests; expected GREEN. No state persistence.

## Task 2: Package

- [x] Write prepare.test.mjs for origins, fresh output/path/symlink refusal, exact
      manifest/CSP, import closure and inactive worker startup. Expected module RED.
- [x] Implement allowlisted package and worker; vendor existing OFL font/license.
      Generate a synthetic-origin package and verify imports/default inactivity.
- [x] Verify synthetic preview states/keyboard/narrow layout if a browser is
      available, static UI audit, full Node, Ruff/format/full disposable pytest.
- [x] Fresh final reviewer, fix important findings with observed regressions;
      document actual evidence/limits. Delivery: commit/draft PR/handoff, no installation.

## Ledger

Base945d1c5. User opted for determine-and-act; retain current identity and scope.
The existing web token source is reused by generation, not manually duplicated.

Task1/2 component evidence: missing-module RED for both test files, then13GREEN;
fresh final review ran9UI tests independently and found two important issues.
Both new regression tests observed RED before correction. Final focused15/all404
extension tests pass. Strict UI audit0 findings; native Windows junction case needs
normal test escalation (sandbox EPERM, not a product failure). Static audit used
UTF8 output mode to avoid cp1252 path-reporting failure, not to mask product tests.

Final: fixed action-specific response validation and stale success feedback — both
RED→GREEN, final15focused/404full Node pass. Author visual audit fixed a reproduced
10px scrollbar overflow, then measured no overflow at280/360 and settings620at900.
No second reviewer and no deferred minors. Full required backend:966 passed,
zero skips/two existing warnings in1546.59s on a fresh disposable Postgres database.
All404 extension tests pass on final source; Ruff lint/format182, strict UI audit0,
Prettier/links/diff checks pass. No backend/web/host code changed.

Final: Ruling: real Chrome sender/CSP/MV3/session/suspension/alarms remain separate
acceptance; actual UI DOM/keyboard/narrow layout were exercised in a synthetic
in-app browser, not an installed extension. Cost if wrong: this evidence cannot
prove live operational collection or certify accessibility. Backend/full Node/
Ruff/audit and current GitHub claims are independently checked by the author.

Final: Ruling: hostile concurrent filesystem replacement is outside a trusted
local builder's boundary; ordinary output/path/symlink refusal is tested. Cost if
wrong: do not run the builder as a privileged service against attacker-writable
directories. No privileged builder or production deployment is added.
