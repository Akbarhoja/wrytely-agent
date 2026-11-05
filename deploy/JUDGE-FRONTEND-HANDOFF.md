# Isolated agent frontend: release preparation

M claim [6652182735](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6652182735)
implements A's judge-entry assignment6651657301. This is a reviewable handoff,
not deployment approval. The existing handwriting product, project, domain, auth
configuration and environment remain untouched. No new project, DNS entry, auth
origin, provider, worker, webhook or retained migration was created by this work.

## Exact source and build

Reviewed assembly candidate: `d6591ec459696dc38a63a8c2e1a3371b8a3c14db`,
[PR186](https://github.com/Akbarhoja/wrytely-agent/pull/186), including the separately
reviewed practice helper and saveable checked DOCX adapter. Its exact full CI passed.
A's main-target consolidation is [PR182](https://github.com/Akbarhoja/wrytely-agent/pull/182),
last inspected at `1813d84d0d37c5671250b8cc0f26e4202adebdda`; it does not automatically
include every later feature. A must select the final coherent release SHA, import
this documentation and record its own checks before requesting activation. Do not
deploy M's historical consumer branch or assume default main contains these features.

The `web/` application source at M666f49a and A d6591ec is identical. Existing
215 web tests, TypeScript and webpack build passed locally; A d6591ec full web/build
CI passed independently. This handoff changes documentation only. The Windows
worktree's shared dependencies prevented the default Turbopack build from resolving
Next.js; webpack passed. A clean hosted build is still an acceptance check.

| Field                           | Prepared value                                                                 |
| ------------------------------- | ------------------------------------------------------------------------------ |
| Repository                      | `Akbarhoja/wrytely-agent`, exact A-approved SHA                                |
| New isolated service root       | `web`                                                                          |
| Runtime                         | Node24, matching CI                                                            |
| Dependency installation         | `npm ci`                                                                       |
| Build                           | `npm run build` in a clean checkout; stop on failure                           |
| Local production start          | `npm start` binds loopback for local QA                                        |
| Node host start, after approval | `node node_modules/next/dist/bin/next start --hostname 0.0.0.0 --port "$PORT"` |
| Native Next hosting             | Use its Next.js runtime; no static-export deployment                           |
| Services started by web         | Web/session proxy only; no model or delivery worker                            |

`PORT` must be the host's assigned port. The explicit host start avoids reusing the
local loopback-only npm start on a network service. No host command above has been
run against a hosting account. Native Next hosting manages its own start command.
The proxy and verified sessions need a server runtime; static files alone cannot
provide the private workspace. See the [Next self-hosting reference](https://nextjs.org/docs/app/guides/self-hosting).

## Configuration names and exact-origin handoff

Owner values belong only in the isolated hosting service's private configuration.
Use the existing approved Clerk development instance; do not create a new instance
or borrow production configuration. A must confirm the selected frontend origin
and compatible API origin before any auth or hosting changes. Neither has been
selected or live-verified by M in this handoff.

| Names                                                                                                | Placement / acceptance                                                                      |
| ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`                                                                  | Build and runtime; publishable key only. Rebuild when changed.                              |
| `CLERK_SECRET_KEY`                                                                                   | Web server only, matching existing approved instance.                                       |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL`, `NEXT_PUBLIC_CLERK_SIGN_UP_URL`                                     | `/sign-in`, `/sign-up`. No signup/public-pilot authorization implied.                       |
| `NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL`, `NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL` | `/`; owner checks actual approved account access.                                           |
| `AGENT_API_URL`                                                                                      | Web server only; exact compatible isolated HTTPS API origin, not a public browser variable. |
| `AGENT_CLERK_ISSUER`, `AGENT_CLERK_JWT_KEY`                                                          | API verifies the same approved Clerk instance; no values in this packet.                    |
| `AGENT_AUTHORIZED_PARTIES`                                                                           | API exact frontend-origin allowlist, configured by A after scoped approval.                 |

Let `W` be the owner-approved agent web origin and `B` the approved agent API origin.
These symbols are unresolved choices, not literal configuration values.

| Boundary          | Exact required relationship                                                             | Current status                                 |
| ----------------- | --------------------------------------------------------------------------------------- | ---------------------------------------------- |
| Judge entry       | A selects one isolated HTTPS `W`, distinct from the existing product                    | Pending owner selection/activation             |
| Clerk             | Existing instance accepts the actual `W` through its applicable dashboard configuration | Not changed or verified here                   |
| API session       | `AGENT_AUTHORIZED_PARTIES` contains the exact `W`, including scheme/port when present   | Pending A private configuration                |
| Browser mutations | Request `Origin` equals the web request URL origin `W`                                  | Enforced by existing proxy; no wildcard/bypass |
| Server proxy      | Web `AGENT_API_URL=B`; bearer token comes from verified Clerk session                   | No direct browser identity fields              |
| Local QA          | `http://127.0.0.1:3000` only when explicitly configured for local development           | Not interchangeable with `localhost`           |
| Collector         | Existing package's exact API/Canvas origins match approved backend/source scope         | A owns package and activation                  |

Only the Clerk publishable key may be exposed as a public variable. Model, bot,
Clerk server and database secrets do not belong in browser code, the collector,
screenshots or public issue comments. Do not add those model/bot/database settings
to the web service. HTTPS/reverse-proxy forwarding must preserve the real `W`;
do not disable Origin or session checks to work around a mismatch.

## Existing collector handoff

A reports the matching collector0.3.4 ZIP is already built in ignored staging:
31 files,104932 bytes, SHA-256
`2c2cb8eb9d974e6f27aa3567ee635e4890f90f42427fe9eee952a4c21268d46a`.
This is A's reported package identity, not an independent M archive inspection or
published download. A must supply the approved artifact location and confirm the
embedded API/Canvas origins, install instructions and authorized distribution.
Reuse that bundle; no duplicate collector build or installation was performed.
The existing [local setup](LOCAL-SETUP.md) and
[collector package guide](../docs/stages/P1-CANVAS-BROWSER-PACKAGE.md) explain the
separate pairing/identity/scope steps. An HTTPS backend and successful pairing
alone do not prove complete readable course coverage. Keep the installed Chrome
session/collector untouched until separately authorized operator action.

## Smoke checks and evidence to record after approval

| Layer                         | Required observable outcome                                                     | Evidence scope now                                                   |
| ----------------------------- | ------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Public entry                  | HTTPS `/` and `/sign-in` load on selected `W`                                   | Prior credential-free local production shell200 only; hosted pending |
| Unconfigured private route    | `/api/agent/telegram` fails closed503/no-store                                  | Prior local QA passed, not a configured sign-in test                 |
| Untrusted mutation            | Foreign-origin POST to `/api/agent/telegram/link` returns403/no-store           | Prior local QA passed                                                |
| Configured signed-out request | No private data;401 or Clerk login mediation, no-store                          | Actual hosted/session QA pending                                     |
| Existing approved account     | Sign in, restore same agent, read private connections/results                   | Live Clerk-to-API proof pending                                      |
| Account isolation / expiry    | Another account and expired session cannot read the prior account's data        | Existing scripted tests; actual two-account acceptance pending       |
| Checked file                  | Owned/current/passed artifact downloads; stale/paused/other-owner access denied | Scripted connected proof, real hosted acceptance pending             |
| Supervision / Telegram        | Refresh reads state; link/consent explicit; no implicit model/send activation   | Existing scripted checks; observe exact deployed service separately  |

Record exact SHA, hosted URL, config names/origin identities, HTTP status/cache
headers and passed/failed/blocked/untested state in private operator evidence.
Do not put tokens, course content or source/account findings into screenshots or
public reports. Opening the app, linking or installing a package does not authorize
a paid model call, outward send, background collection or continuous operation.

## Remaining owner decisions

A reviews the final source/package selection, supplies the artifact location and
chooses the isolated hosting target and exact origins. The owner must approve
project creation/deployment/auth-origin changes and the concrete smoke-test scope
before activation. This handoff grants none of those actions. Existing cumulative
liabilities and unknown outcomes remain preserved. Required human protected-main
review remains separate. Real coursework permission/source gaps, live checked-file
revision receipt, and sustained operation remain open gates, not hidden fallbacks.
