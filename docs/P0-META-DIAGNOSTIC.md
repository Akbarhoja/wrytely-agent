# P0-A2 Meta diagnostic — October 30, 2026

Issue [#49](https://github.com/Akbarhoja/wrytely-agent/issues/49).
Code tested: c8cadbb (inherits baseline9bbea97). Local operator only; no deployment.
Time: October30 at18:01 America/Denver (October31 00:01 UTC).

## Approval and bounds

Akbar explicitly approved at most two synthetic diagnostic calls, capped at$0.06
within the existing$2 total ceiling, preserving the earlier unknown-use$1.32
reservation. This is a separate diagnostic from the original bounded M2 workflow.
No new WhatsApp send, connector access, retained migration or continuous service.

The ignored private operator uses the existing MetaModelClient and authorized
local development key. No key, request/response IDs or private content is published.
Requests use documented https://api.meta.ai/v1/responses, muse-spark-1.3, store=false,
encrypted reasoning replay,2048 output-token limit,30-second timeout and zero SDK
retries. No model/endpoint change, alternate protocol or fallback was needed.

Each call reserves$0.03 in the ignored0600 ledger before network dispatch. It
bounds the ASCII JSON history/tools at8192 bytes and checks the total ceiling.
At standard$1.25/M input and$4.25/M output, the reservation includes margin over
that bounded text/tool input plus2048 output tokens. No paid built-in tools exist.
The operator refuses reruns of this probe identifier and stops on unexpected usage,
invalid tool selection, unknown outcomes or input limits. It is a bounded local
operator, not the future production cumulative budget service.

## Result: real tool loop passed

| Turn  | Observed result                                                                                                             | Input tokens | Output tokens | Conservative uncached cost |
| ----- | --------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------- | -------------------------- |
| 1     | Completed; exactly one get_probe_context function call with empty arguments                                                 | 573          | 245           | $0.00175750                |
| 2     | Replayed saved output and synthetic function result; completed expected P0_TOOL_OK acknowledgment with no further tool call | 855          | 138           | $0.00165525                |
| Total | Two calls; tool selection, checkpoint and continuation succeeded                                                            | 1428         | 383           | $0.00341275                |

The tool only returned a fixed synthetic status, without external access. The first
response contained reasoning, message and function_call items. All were replayed
using the existing adapter's output representation and the matching call result.
The operator persisted a private checkpoint before continuing. This proves the
current local adapter/key/model route and stateless tool continuation, not the
database worker, academic planner, source ingestion, draft quality or WhatsApp.

Both calls returned known positive usage. Their temporary reservations were replaced
by actual token-based cost. The previous M2 unknown reservation was not changed.
Known cumulative token-based cost is now$0.01114350; plus$1.32 reserved unknown usage
makes$1.33114350 charged/reserved against$2. Available unreserved total:$0.66885650.
The diagnostic's two-call allowance is consumed even though it spent less than its
cost cap; no extra calls are implied. This accounting is not a provider invoice.

## Usage dashboard and unresolved404

With browser access restored, the selected team's Oct24–30 Usage page showed two
requests,697 input tokens, rounded1.6k output and$0.00 spend before this diagnostic.
Filtering the dedicated wrytely-m1-development key showed the same totals. The input
sum matches the two earlier successful calls; no identifiable third failed M2 call
was available. The page warns metrics are limited availability and can lag up to
one hour. CSV export did not yield a usable report. Rounded aggregate/credit-covered
spend is not sufficient evidence to release the failed-call reservation.

The earlier failure remains historical and unexplained. Success now rules out a
persistent failure of this exact local route, but does not prove the original404
was caused by a model retirement, LLC information, protocol mismatch or a transient
provider problem. No speculative application fix was made.

## Next gate

1. Keep previous reservation until request-level/provider reconciliation supports a
   settlement. Do not classify failed requests as zero cost by assumption.
2. Obtain review of combined baseline #46 and shared interface #48. Do not bypass
   protected-main approval or activate workers because the small diagnostic passed.
3. Prepare a separately bounded real planner/academic run through the existing task
   path. Reconcile its retained ledger, blocked task/source freshness, conservative
   per-call allowance and approved recovery scope before another M2 attempt.
4. Retain current live limitations: no Canvas/Outlook collector, no live checked
   academic artifact/delivery, no continuous worker. The user vision remains revision7.

## References

- [Meta quickstart](https://dev.meta.ai/docs/quickstart)
- [Responses stateless tool/reasoning replay](https://dev.meta.ai/docs/protocols/responses)
- [Standard Muse Spark pricing](https://dev.meta.ai/docs/pricing-rate-limits)
- [Original failed academic attempt](M2-RUN-2026-10-29.md)
