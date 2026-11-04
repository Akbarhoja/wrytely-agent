# Explicit Fireworks Muse Spark Open transport

A owns this adapter on `codex/p1-completion`. M owns its app/service consumer.
This preserves Wrytely's runtime, tool authorization, durable work and budget store.
It does not install a third-party agent or activate an automatic provider fallback.

## Configuration and boundary

`Settings.meta_provider` accepts `meta` (default) or `fireworks` only. Select through
`AGENT_META_PROVIDER=fireworks`, with `AGENT_FIREWORKS_API_KEY` supplied securely.
`BudgetedMetaRouter(store, settings).for_user(verified_user)` remains the shared
service factory. It validates the selected provider's credential; app consumers must
not independently require the Meta-hosted key. `Settings.readiness()['meta_model']`
reports credential presence for the selected provider, not live endpoint health.

The Fireworks client fixes the model to `accounts/fireworks/models/muse-spark-open`
and endpoint to `https://api.fireworks.ai/inference/v1`. `AGENT_META_MODEL` does not
override that model. Existing output-token configuration supplies the exact reservation
and provider cap; effort is unset, low, medium or high. No silent effort conversion,
transport retries, arbitrary model/endpoint selection or context-overflow truncation.
Verified provider prices, budget key and disabled-by-default operator allowance remain
required. Existing liabilities are preserved; a new provider is not a new budget.

Canonical text/function-call transcripts translate to Chat Completions messages and
nested tools, retaining exact tool-call IDs. Unknown/duplicate calls, orphan/missing
results, unsupported content, incomplete output and refusals fail closed. Known token
usage follows existing settlement; unknown usage remains held. Private Fireworks
reasoning, when returned, is retained only in private replay metadata and excluded from
`ModelTurn.text`; it is never a student result or a log message. This is not a change
to provider-side retention guarantees. Meta encrypted reasoning cannot be replayed
through Fireworks. Do not switch provider in an existing episode; use a new episode
or a fresh supervisor snapshot without old provider-specific replay state.

## Evidence and activation limits

72 focused mocked tests pass, including parallel tool replay, reasoning separation,
unknown usage, redacted 404/no retry, output cap, budget rejection before network,
explicit selection and runtime startup without a Meta-hosted key. Ruff and format
checks pass. Full local database regression was attempted but disposable Postgres
could not initialize under the current sandbox's shared-memory restrictions; it did
not run successfully. Normal GitHub CI includes the full non-live suite with Postgres18.

No live Fireworks response, student-data processing, deployment, key creation or
continuous operation is proved by these tests. Fireworks Wrytely billing currently
shows zero prepaid balance, auto-reload off and zero monthly spend. A payment method
is present; no credit purchase was performed by Codex. Baseten hackathon credit
application was submitted with Akbar's approval and acceptance email; access remains
unconfirmed. Meta's $150 credit does not transfer to Fireworks.

Next: complete account funding under Akbar's chosen purchase limit, approve/create a
scoped development credential, verify retention terms before student content, then
approve a small synthetic-only wire/tool replay check. Review full CI and M's consumer
before any scoped development deployment or real course turn. Keep course supervision,
drafting and outbound delivery stopped until their separate checks are authorized.

## Official references

- [Muse Spark Open model and rates](https://fireworks.ai/models/fireworks/muse-spark-open)
- [Function calling](https://docs.fireworks.ai/guides/function-calling)
- [Chat Completions parameters](https://docs.fireworks.ai/api-reference/post-chatcompletions)
- [Reasoning and replay](https://docs.fireworks.ai/guides/reasoning)
- [Meta deployment options](https://dev.meta.ai/docs/muse-spark-open/deploy)
