# P1 document staging API integration review

November 1, 2026. A/Codex integration responsibility under
[claim6565242442](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6565242442).
Murtazo delivered [#155](https://github.com/Akbarhoja/wrytely-agent/pull/155), exact
`647c5032014af444eea114992773cbb3b438bb1c`, based on agreed #135
`019d6c7e6e62e4023dab72cb1fb3d4415a764c9e`. This integration branches from #153
`f62fb0c3a4ff908aaf3dad05b76cf34d863c3cbe`; all five delivered files, including
app/main.py, match M's head byte-for-byte. A changes only STATUS and this record.

## Boundary review

No blocking finding in the scoped read review. The three POST routes begin, parts
and finish call the existing Store operations with an ingestion credential. They do
not accept website sessions as source authority or introduce another persistence
layer. Current authority, exact-body replay, upload quota, section integrity and
final transaction fences remain in Store. Schema2 staging is not publication,
source completeness, permission to draft or a public artifact result.

The existing streamed CanvasRoute enforces a one-MiB limit despite absent/false
Content-Length and limits media types before handler parsing. Document-only
validation maps to400; existing schema1 validation remains422. Queries and operation
mismatches reject. Unknown uploads return empty404, conflicts have allowlisted409
codes, quotas return429 with Retry-After30 as a minimum pause rather than a promise
of capacity. Unexpected outcomes return redacted500 without an automatic retry.
The enclosing route adds no-store to success and controlled failure responses.

The new factory argument canvas_document_extractors defaults to an empty tuple.
Both configured Canvas origins and trusted normalized extractor versions are needed;
request metadata cannot enable the endpoint or choose server configuration. The
merge preserves default-off deployment behavior and existing versioned artifact
projection filters. No settings, Store, contracts, schema, runtime or extension
implementation changed in this integration.

## Independent checks on the combined candidate

- Focused real-Store API suite:54passed, zero skips, one existing warning,6.83s.
- Full fresh disposable backend:1,422passed, zero skips, two existing warnings,
  137.85s. No retained database selected.
- All404 extension Node tests passed, zero skips.
- Ruff lint/format passed (222 files); delivered document Prettier and diff checks
  passed. Exact delivered file bytes were checked against M's head.
- Existing #153 and #155 GitHub check runs reported success at inspection. These
  dependency results are separate from new candidate CI and local combined tests.

M's independent review of #153 is recorded in
[6564595290](https://github.com/Akbarhoja/wrytely-agent/pull/153#issuecomment-6564595290):
16 delivered files unchanged,404NodePASS and no blocker in the scoped integration/CI
delta. This is counterpart technical review, not human approval or a full backend
rerun. His [#152 typed contract review](https://github.com/Akbarhoja/wrytely-agent/pull/152#issuecomment-6564664188)
passed16pure cases; a versioned private artifact read interface remains a separate
design request, with no public v2 result exposure authorized by that review.

## Next dependencies and limits

M retains #149 document-parts producer and subsequent collector/journal/HTTP/web
assembly. The API has synthetic HTTP/Store evidence only; no installed extension
uploaded actual course content. Automatic full-course collection and continuous
semester supervision remain unfinished. P0 baseline independent approval/merge,
Canvas feasibility classification and WhatsApp delivery gates are unchanged.
Outlook remains optional/paused. P0/P1 remain open.

No live source/provider/model call, send, new spend, grant, installation, retained
migration, continuous worker, deployment or main merge occurred. New integration
review/CI remains separate; technical review does not substitute for required
independent human GitHub approval.
