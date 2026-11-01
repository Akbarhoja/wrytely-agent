# Canvas private UI and browser package

Murtazo claim [#145](https://github.com/Akbarhoja/wrytely-agent/issues/145), branch
codex/canvas-browser-package from #144 at945d1c5. UI/package consumes the existing
host/client/journal; no backend, web, shared contract, CI or host edits.

Design and behavior: [design](../../extension/canvas-browser/DESIGN.md) and
[UX contract](../../extension/canvas-browser/UX-CONTRACT.md). Root design and tokens
remain canonical. Native popup/options share one controller and stylesheet.

Build uses exact validated HTTPS API/Canvas origins and a fixed runtime allowlist;
storage/alarms plus those two host origins only. No content script, remote script,
external messaging, installation, permission request, source activation or login.
Output must be a fresh path beneath .local/canvas-packages, with no overwrite.
Package config and generated tokens remain local ignored build artifacts.

## Implemented and verified so far

Native popup/options reuse one UI controller and stylesheet. Identical semantic
markup is checked in the package tests; only the popup/options body variant differs.
The popup declares360px width capped to available document width. Settings grows
to620px. Root web CSS tokens are extracted at build time, with local OFL font.

All **404 extension tests pass**, including **15 UI/package cases**. Both new
test files initially failed for missing modules. A fresh read-only reviewer found
two important issues: action success accepted missing/contradictory reply fields,
and refresh retained obsolete success text after controls changed in another view.
Both have observed RED→GREEN regressions. Action-specific outcomes are now checked;
busy is not successful enable, and authoritative refresh replaces old feedback.
No critical or deferred minor findings. Package tests cover exact permissions/CSP,
transitive imports, fresh output, ordinary symlink/junction refusal and real host
startup with fake Chrome: no fetches or alarms on a fresh disabled profile.

Strict scoped UI audit passes with zero findings; Prettier/link/diff checks and
required full backend evidence are recorded at handoff. Ruff lint/format passed
(182 Python files). Full `uv run pytest -q` on a new disposable Postgres DB:
**966 passed**, no skips, two existing warnings, **1546.59s** on native Windows.
The existing19actual synthetic HTTP cases are included; no timezone or source
behavior was overridden. Final UI/package tests use no third-party DOM dependency.
No backend/web/host code was changed. Base #144 CI41330046750 is independently
recorded SUCCESS; this new branch's CI is separate.

## Synthetic visual evidence

Actual UI/boot code rendered in the in-app browser against a loopback-only static
fixture using example.edu origins and a fake runtime. Validation focused the field;
dummy code reveal/Enter/clearing/remasking worked; enable remained disabled before
explicit identity+consent; pause stayed enabled while simulated collect was pending
and its late reply did not re-enable collection. Refresh correctly replaced feedback.
Keyboard Tab produced a visible solid focus outline. At360px and280px, measured
content width equaled client width; at900px settings retained its620px column.
An initially reproduced10px scrollbar overflow was fixed with available-width sizing.
Screenshot remains local in .local/canvas-browser/preview-paused-360.png.

While verification ran, M also independently reviewed A's #143 quote-search
helper at exact6e051715. Its34focused real-store cases passed in94.44s on another
disposable database. [Scoped handoff](https://github.com/Akbarhoja/wrytely-agent/pull/143#issuecomment-6561506099)
does not claim full inherited-stack, model/drafting or live-source acceptance.

This fixture sends no real pairing, identity, source or account requests. It is
not Chrome-extension installation, sender metadata, MV3 CSP enforcement or Canvas
session/restart/alarms proof. Full accessibility certification and forced-color/
reduced-motion runtime checks are not claimed from static CSS or screenshots.

## Build and handoff

From repository root, after review of approved development origins:

```text
node extension/canvas-browser/prepare.mjs API_ORIGIN CANVAS_ORIGIN .local/canvas-packages/FRESH_NAME
```

The path must not exist. No installer is called. The manifest is written last;
an interrupted partial directory is left for inspection and cannot be overwritten
by another build. No code/credential/source is accepted as a build input. Ordinary
path traversal/symlink guards are tested; this is a trusted local build tool, not
a privileged service protecting against another process replacing directories
concurrently. The generated example-origin fixture is not a usable live connection.

P1 remains incomplete: installed MV3/session/restart access,
remaining academic resource types/documents and continuous operation need separate
proof. P0 WhatsApp delivery remains open; Outlook is optional/paused. A retains
document/runtime/shared work. Chrome untouched and automation off.
