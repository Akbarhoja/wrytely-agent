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

## Approved synthetic live check — November 3

Akbar approved one development key and at most two synthetic requests, capped at
0.03USD within the existing 3USD aggregate ceiling. The key was created in the
Wrytely Fireworks account and saved only in ignored local credentials (mode0600),
not Railway or source. Billing showed1USD prepaid credit, auto-reload off.

Exact adapter51ad506 completed BOTH requests: first tool call676input/100output
tokens, then continuation825input/30output tokens. The fictional tool returned a
Friday deadline; final answer correctly reported Friday. This proves the live
adapter's two-turn text/tool replay for synthetic data, not an academic decision,
student-content authorization, continuous service or end-to-end user journey.

Token-derived estimated cost is0.00242875USD at1.25input/4.25output per million;
it is not a reconciled provider invoice. Keep the entire0.03USD approval reserved
locally, in addition to the prior1.87838375 liability: conservative aggregate
1.90838375/3USD. Actual computed request maxima totaled0.02144025. The durable
one-shot local record prevents an accidental rerun. The existing Railway budget
remains disabled and still contains its original liabilities; the additional local
0.03 hold MUST be included in aggregate accounting before any subsequent activation.
Do not silently release it, reset old holds, or treat account credit as permission.
No further call, student content, deployment, rescan or WhatsApp send occurred.

## Combined candidate and next bounded acceptance

Executablebb626d3 combines adapter51ad506 with M's servicefd7f6fb, acceptance
packetc2b3f4d and private-control recoveryfb8b8a6, preserving authorship. Combined
75 focused backend and5 affected UI tests pass; Ruff/301-file format/diff pass.
Full exact-head CI is running; deployment is not yet authorized or performed.

Official Fireworks data-handling documentation states that open-model inference
has no persistent prompt/generation storage by default; transient prompt caches and
billing metadata are distinct. Enterprise enforcement of an account-wide policy is
a separate feature, not something verified on this account. This adapter uses Chat
Completions, not stored Responses, training, batches or dataset upload. Sources:
[baseline handling](https://docs.fireworks.ai/guides/security_compliance/data_handling)
and [enterprise enforcement](https://docs.fireworks.ai/accounts/zero-data-retention).
No provider-side account toggle was changed. New student-data destination needs
Akbar's scoped consent before sending saved course content.

Prepared next scope (NOT authorization): once exact candidate CI and counterpart
review clear, configure this existing key only on the isolated agent development API,
select Fireworks explicitly and keep API-only start. No migration is added by this
adapter. Preserve original global ledger/history, include the external0.03 hold,
and bound at most two manual ECE253 supervisor turns to0.40USD additional liability
within3USD aggregate. Maximum aggregate after that allowance would be2.30838375.
Use only the existing approved newest connection/course; source fields, saved
instructions and previous/current inspection excerpts may reach Fireworks. No
rescan, HTMLv2 enablement, new course, assignment draft, offer enqueue, external
send or continuous worker. Pause the monitor and disable the budget after the run,
including failures. Preserve unknown outcomes and stop at the first concrete error.
A valid inspect/wait decision is progress; partial evidence still cannot authorize
an assignment offer or draft. The operator must preflight live ledger and scope
instead of relying on historical script assertions or resetting call counters.
