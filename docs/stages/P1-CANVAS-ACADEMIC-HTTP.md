# Staged C2v1 academic HTTP assembly

Murtazo (`murtazokhon-tech`) integration increment [#111](https://github.com/Akbarhoja/wrytely-agent/issues/111), based on tested collector acceptance #110 `c82b996`. Existing Store academic transactions and types are consumed; no shared schema or persistence is added.

## Routes and authority

`POST /v1/source-connections/canvas/academic/batch` accepts the existing strict generation/scan/writer lease/batch key/checkpoint wrapper with an `AcademicBatch` envelope. It calls existing `commit_sync_batch`; the Store owns account/subject, selection/generation, resource progression, leases, exact replay, reference validation and atomic source/check/event writes. Browser owner IDs or session tokens cannot substitute for an ingestion credential.

`POST /v1/source-connections/canvas/academic/resource` calls existing `finish_resource`. Only the seven implemented C2 academic kinds are supported. A complete outcome requires no failure reason and the Store's complete resource manifest. Partial/restricted/unsupported outcomes require an existing controlled reason. Modules/files/document roots and schema2 are excluded until their separate interface/implementation gates pass; the older discovery API retains its behavior.

Both routes reuse the existing private/no-store wrapper, generic validation/auth/notfound/storage errors and allowlisted conflict codes. Batch wrappers are streamed under2MiB; actual serialized envelopes retain the Store's1MiB cap. Resource controls retain64KiB. No new public field/credential projection or arbitrary provider fetching exists.

## Text and staging limits

Typed C2v1 permits at most50 already-extracted items, with exact resource-specific fields, title300/content24000 limits and explicit coverage/missing fields. The HTTP DTO additionally checks those title/content limits after NFC/newline normalization without changing input or computing another digest. This protects the historical partial/blank-title path on this base. It does not replace A's accepted #98 shared validation fix; that fix must remain in the consolidated shared stack. Canonicalization, digests and stored payloads stay Store-owned. Oversized input rejects atomically; nothing is clipped.

This endpoint assumes an adapter has already extracted supported text. It is not an HTML/PDF parser or permission to label raw HTML complete. Long documents still need the exact schema2/document-only wire, vectors and cleanup agreement on #78. Source versions created here remain staged: existing `academic_sources.latest_version_id` is not promoted, and no model freshness/readiness consumer is enabled.

## Evidence and remaining work

The seven supported-resource cases failed RED before routes existed. All39 new actual Store/API cases passed in42.29seconds. The full backend suite passed714 tests on disposable local PostgreSQL in425.19seconds, with two existing warnings. All233 Node and114 web tests, TypeScript, required Ruff check/format, changed-document Prettier and diff checks passed.

Fresh independent static review found no blocking defect and checked the Store delegation/authority, normalized HTTP bounds, resource manifests and discovery compatibility. The reviewer ran diff checks, not the executable/database/provider suites; executable evidence above is the implementer's run. Remote CI/counterpart acceptance remain separate.

Tests use synthetic course/content/session/credential fixtures and disposable local PostgreSQL. They check staged versions and safe receipts, exact replay without check-time refresh, changed-body conflicts, authority and lease/scope/revocation fences, supported kinds, normalized bounds, atomic envelope limits, streamed wrapper cutoff, private errors and resource completion. No live Canvas, Clerk, extension academic collector, browser suspension, source activation or full semester agent is claimed.

P0 Canvas access remains A-owned under [6548991501](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6548991501). Outlook is optional and live requests paused under [6549522832](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6549522832); old planning text on this stacked base predates those decisions. No provider call, account read, install, grant/send/spend, production migration/deployment/main merge or new automation occurs. Chrome remains untouched.

Next integration work is a resource-aware durable extension consumer using these accepted routes, followed by actual collector/HTTP acceptance. Paired collection, full resource/linked-document coverage, installed host/recovery and live gates remain unfinished. Shared STATUS and CI serialization/review remain A-owned requests.
