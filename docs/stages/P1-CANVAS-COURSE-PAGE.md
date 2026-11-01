# Canvas course page reader

M-owned first increment of [#100](https://github.com/Akbarhoja/wrytely-agent/issues/100), on tested client/API acceptance head `1e294753`. P0 Canvas/Outlook live acceptance returned to Akbar in [coordination](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6548991501); this increment performs no live run or installed diagnostic change.

## Interface and bounds

`makeReader(origin, fetchImpl).coursePage(cursor = null)` reads one course page and returns `{data, next_cursor}`. `data` contains private intermediate provider rows, not public diagnostics or validated C2 evidence. The subsequent collector must map fields, bracket identity/context, persist the exact page through the paired journal and resume pending intents before refetching. This method alone does not authorize collection, bind an account or close resources.

The initial request lists active courses with `per_page=50`. A supplied continuation must be an absolute URL at the exact configured HTTPS origin and `/api/v1/courses`, with exactly one active enrollment filter and per-page value50 and optionally one nonempty opaque `page` value. Other query variants fail visibly; nothing is rewritten into an invented next page. Cursors are bounded to4000 Unicode characters. Authentication remains the existing browser session; token query parameters are refused.

The shared reader uses GET, credentials include, redirect error, no-store, JSON Accept, a15-second Fetch abort signal and a1MiB streamed body cap. Strict page mode additionally requires HTTP200 and exact final response URL, fatal UTF-8 decoding, an array of at most50 object rows, a Link header at most16KiB, complete header parsing, at most one next relation and no direct self-cycle. Cross-tick cycles/page totals remain the durable journal's responsibility. Legacy `get/list` retain their behavior through the same extracted Link parser.

Provider/login/permission/rate/network/format/limit failures throw existing controlled `ProbeError` codes. They never become successful empty pages; no provider failure text is propagated. Cleanup rejection now preserves the intended controlled failure in both strict and legacy readers instead of leaking a raw cancellation exception. No retries are automatic. No raw source/cursor is logged or included in public evidence.

## Evidence and remaining work

TDD initially failed because `coursePage` did not exist. Independent review reproduced a cancellation-error leak; five new regressions failed before the cleanup fix and passed afterward. Final Node verification passed164 cases:45 new page cases and119 existing pairing/journal/diagnostic cases, no skips. The reviewer independently ran the pre-fix52 focused cases; final fix verification was performed by the implementer, not a second independent run. Other final verification is recorded in the implementation PR; fixture counts do not establish live provider access.

The unchanged backend suite passed673 cases on disposable local PostgreSQL in384.22seconds, with two existing warnings. Web regression passed114 cases; TypeScript, Ruff check/format, changed-file Prettier and diff checks passed. After the final JavaScript fix, all8 actual client/API interoperability scenarios passed again in14.01seconds. Remote CI remains separate.

This increment does not implement the collector tick, C2 metadata mapping, durable checkpoint writes, host/alarms, full academic resources or browser suspension recovery. Those remain required under P1-M1; raw metadata rows are not an academic source or a completed scan. Current body/row/cursor/query limits produce explicit failures, never clipped records or false completeness.

Akbar-owned CI must include `extension/canvas-feasibility/page.test.mjs` in the root Node job after this file exists on its base. The foundation job also needs its previously requested explicit Node24 prerequisite for the Python/Node interoperability tests. Neither workflow nor shared STATUS is edited here.

Official protocol references checked October31: [Canvas pagination](https://developerdocs.instructure.com/services/canvas/basics/file.pagination) specifies absolute opaque links; [courses](https://developerdocs.instructure.com/services/canvas/resources/courses) documents the current-user course endpoint. Opaque tokens are preserved; the supported query shape is deliberately bounded and untested against the live institution.
