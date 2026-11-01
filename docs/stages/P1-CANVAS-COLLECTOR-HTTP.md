# Collector-driven HTTP and Store acceptance

M single-editor continuation [#108](https://github.com/Akbarhoja/wrytely-agent/issues/108), explicitly agreed by A in [6549371845](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6549371845). Base #107 `4106dc88`; no production implementation changed.

## Actual boundary and assertions

The two new scenarios invoke production `collectCoursePage()` against actual loopback FastAPI routes and a disposable PostgreSQL Store. Existing test identity/storage scaffolds and subprocess isolation are retained. The synthetic Canvas adapter refuses every URL except the exact profile and two bounded course URLs. It does not call a provider, Chrome or any signed-in account.

The verified synthetic session selects `all_active`, an empty manually entered course list and assignments scope. Collector ticks begin and capture two different pages without manual course IDs. The lost-ack scenario discards the first response only after the actual batch has committed, recreates the worker using the same synthetic private storage and recovers the identical saved body/key without another course data fetch. The second page then commits once.

After courses close, two assignment resources remain open. Repeated ticks report `awaiting_resources` without additional course fetches. Both the public client's guard and a direct authenticated request to the actual server reject aggregate finish; no finish receipt is created. SQL checks two catalog courses, two unique batch receipts, complete metadata, active scan/checkpoint2, two open assignments and zero academic source versions.

The previous eight manual-client scenarios remain intact. These new cases close a specific collector/HTTP/Store scripted acceptance gap, not all academic resource collection or live operation.

## Verification and limits

Both new scenarios failed RED at controlled driver configuration before implementation. The first actual run passed both cases. All ten actual HTTP/Store scenarios passed in15.53seconds, including the direct server finish denial. The full backend suite passed675 tests on disposable local PostgreSQL in398.61seconds with two existing warnings. All233 Node tests,114 web tests, TypeScript, Ruff check/format, changed-file Prettier and diff checks passed.

Fresh static review found no code blockers and confirmed the receipt/refetch/resource assertions. Its ownership-documentation correction was addressed with links to the newer supervisor record below. The reviewer ran syntax/diff checks, not the database or provider cases; database evidence above is the implementer's run. Remote CI/counterpart acceptance remain separate.

The actual API uses a synthetic session verifier; provider profile/metadata and trusted storage are fixtures. The fixture maps the configured HTTPS API origin to loopback HTTP without changing production origin checks. This is not TLS, real Clerk, installed MV3, cross-realm coordination, browser suspension/restart or live Canvas acceptance. Neither private provider content nor signed URLs/credentials are published. Child configuration remains stdin-only with an OS-only environment; generated pairing secrets stay in test memory. The driver emits only the existing fixed diagnostic schema, no stack or raw exception text.

P0 Canvas access remains A-owned under the [supervisor reassignment](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6548991501) and [M handoff](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6549014013). The later [optional-email amendment](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6549522832) pauses live Outlook access attempts and removes email as a core Canvas/agent acceptance dependency; retain opt-in evidence without claiming connection. These decisions are recorded in the separate #105 documentation stack; the older TEAM/STATUS/work-order copy on this implementation base predates them. Academic resource collectors, host/alarms, continuous service and full semester supervision remain unfinished. No live account/source read, grant, installation, send, provider spend, deployment/main merge or new automation is authorized by this test increment. Chrome stays open.

Akbar's separate P0 known-PDF operator report is not rerun here and is not equivalent to a paired P1 file collector. New root Node-suite inclusion/foundation Node24 setup and serialized shared STATUS remain A-owned follow-ups; remote CI and counterpart acceptance are separate from local test results.
