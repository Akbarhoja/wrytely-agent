# Actual paired assignment client / HTTP / Store acceptance

Owner: Murtazo (`murtazokhon-tech`), [claim #115](https://github.com/Akbarhoja/wrytely-agent/issues/115), [coordination comment 6552289221](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6552289221). Branch `codex/canvas-assignment-http-acceptance`, based on own #114 exact `47d076d`. #114 CI run 41264749881 passed; Akbar counterpart acceptance of #114/#112/#110 is separate and remains pending.

## Boundary under test

The existing Node driver calls the production pairing client, assignment mapper/journal and trusted transport. Its fixture transport rewrites only allowlisted Wrytely paths to an ephemeral 127.0.0.1 FastAPI service. The service uses the existing actual HTTP DTOs/routes and Store transactions on disposable local Postgres. Canvas profile/course responses, session verification, identities and extracted assignment text are synthetic. No provider fetch, authentication bypass in production, alternate ingestion code or live evidence is introduced.

This test-only PR changes the existing two M-owned interoperability files plus this stage note and the scoped implementation plan. Standing single-editor agreement [6548726117](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6548726117), [6548849672](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6548849672) and retained P1 cross-layer ownership [6548991501](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6548991501) apply; the fresh claim checked for conflicting editors. No production interface changed or shared owner was replaced.

## Added scenarios

- Two mapped assignment pages become exactly two staged immutable versions/observations, then a complete assignment manifest and scan finish.
- Before-dispatch loss preserves the full captured request/key and recovers through a recreated client without duplicate storage.
- After-commit acknowledgment loss occurs after consuming the actual successful HTTP response. A recreated client resumes the scan at the exact advanced assignment checkpoint and replays the captured request with only the new lease token. There remain exactly two observations/versions and three total batch receipts including course metadata.
- An early missing rubric remains partial despite a later complete page. Both client and direct HTTP reject complete resource closure; explicit partial closure produces a partial aggregate and null complete-manifest digest.
- Scope/revoke controls change after client preparation, immediately before academic Store mutation. No assignment versions/objects/observations or finish receipts are created. Scope changes preserve catalog history in two generations rather than duplicating assignments; the existing scan is aborted.
- Bob's legitimate ingestion bearer cannot submit or close Alice's captured scan. Denials expose no Alice identifiers/text/bearer; Alice's original pending request still recovers and completes.

The parent independently checks durable counts, exact normalized payloads and source digests, requesting-student dates, course/assignment/provider identity, Alice/origin/subject ownership, actual observation-to-version reference/content linkage, source versions remaining unpromoted, resource coverage/count/checkpoint and stored finish receipts. For complete closure, the resource items must be exactly assignments 17 and 18 with their expected canonical digests; the parent constructs the expected manifest SHA256 independently of the stored receipt. A constant, subset or mismatched manifest cannot satisfy that assertion.

## Evidence and review

All seven new scenario names failed RED at the old driver's unsupported-scenario boundary. The actual driver flows subsequently passed; initial parent assertions were corrected to join provider identity from the existing object table and account for preserved catalog generations. Those were test-authoring mistakes, not production defects.

Final focused actual client/HTTP/Store verification passed 17 scenarios in 31.25 seconds, preserving all ten prior course/discovery cases. Full `uv run pytest -q` passed 721 tests in 440.70 seconds on designated disposable local Postgres, with two existing warnings. All 310 extension Node tests passed; required Ruff check/format on 151 files and changed-file formatting/diff checks pass. Web/application code is unchanged; the base #114 has 114 web/TypeScript validation, separate from this test-only delta.

Fresh independent static review identified a weak manifest-format-only assertion and suggested stronger observation/version linkage. Both were strengthened and re-reviewed with no remaining blocker. The reviewer checked syntax/diffs and existing contracts/schema, not database or live execution; the actual database results are implementer evidence. Remote CI and Akbar counterpart acceptance remain distinct.

## Remaining product work

This closes the actual assignment upload client/API/storage compatibility gap for **synthetic already-extracted short text**. It does not fetch or parse assignments, install or host the extension, exercise real browser suspension, collect all academic kinds or provide live Canvas proof. Source fetching/extraction must next reuse the existing reader/extractor scaffolds, including the existing bounded reader and M's HTML/PDF extraction work on #88 (`e3eb239e`), rather than duplicate those modules. That extractor stack is separate from this branch and is not silently consolidated here. Installed-host recovery and required source/document coverage remain unfinished. Long-document-only schema2 wire/vectors/orphan cleanup remain the #78 agreement gate, and source versions stay staged rather than model-active. A's accepted #98 shared normalization fix remains required in consolidation.

P0 access remains Akbar-owned and Outlook optional/paused under the latest #4 decisions, despite older base planning text. No source/account read, provider call, OAuth grant, message send, spend, install, production migration, deployment or protected-main merge occurred. Chrome stays open/untouched and automation stays off. Akbar retains shared STATUS/CI serialization and counterpart review; no requested shared update is silently replaced here.
