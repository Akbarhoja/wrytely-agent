# Private Canvas lifecycle web proxy

M-owned claim [#67](https://github.com/Akbarhoja/wrytely-agent/issues/67), base
`bdb0e89` (#66), consuming implemented #64 C1 lifecycle assembly.

The existing `/api/agent/[...path]` route continues to use `web/lib/forward.ts` and
Clerk's server-side session token. This slice admits exactly three existing backend
operations:

| Method | Path after /api/agent/            | Backend purpose                        |
| ------ | --------------------------------- | -------------------------------------- |
| POST   | source-connections/canvas/pairing | Issue a private one-use pairing code   |
| GET    | source-connections/{UUID}         | Read the verified owner's safe status  |
| POST   | source-connections/{UUID}/revoke  | Revoke the verified owner's connection |

Path segment counts and values are checked before auth/forwarding, including UUID
syntax. Embedded slash segments, traversal and unsupported methods stay404.
Public code redemption and ingestion-bearer binding are extension-to-backend paths;
this proxy does not admit them. It also adds no scope/sync/admin/list route.

Canvas POSTs retain the existing same-origin check, server session verification and
application/json requirement. Actual streamed body bytes are limited to16KiB,
independent of Content-Length. Overflow stops consumption and forwards nothing;
reader cancellation failure cannot replace413. Invalid UTF-8 returns controlled422;
stream/transport failures return generic503. Successful and controlled-error responses
are no-store. The helper does not parse or log source/secret payloads; the existing
backend validates body fields and owns private connection authorization.

Browser Authorization, cookies, posted owner headers and query parameters are not
forwarded as authority. Only the server-obtained session token is sent upstream.
There is one upstream attempt with existing timeout and redirect:error behavior.
Existing non-Canvas route behavior and body limits remain unchanged.

Tests use synthetic sessions and mocked upstream responses. They exercise the proxy
boundary, not real Clerk login, extension pairing, live Canvas, production or an
end-to-end deployed browser flow. Existing backend route tests supply separate Store
lifecycle evidence; component results must not be relabeled as live integration.

No UI, dependency, environment, shared contract, Store, runtime or backend route is
changed. A future pairing UI still needs an agreed connection-discovery/status flow
and the reviewed extension consumer; this change alone does not present a connected
course or grant source collection. #58 scope/device-context and PDF parsing remain
separate owner handoffs. Counterpart review and protected-main gates remain; no
deployment/retained migration/provider call/model spend/send is included. Chrome is
untouched and private course evidence is excluded from this branch.
