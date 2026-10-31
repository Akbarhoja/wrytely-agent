# Outlook feasibility implementation plan

Execute directly under existing P0-M2; no live mailbox grant is included.

**Goal:** Prepare a bounded read/delta probe and precise consent/run evidence checklist.
**Spec:** [P0-M2](../../WORK-ORDERS.md), claim [#53](https://github.com/Akbarhoja/wrytely-agent/issues/53).
**Base:** `9bbea97`; branch `codex/outlook-access-feasibility`.
**Architecture:** A provider-only helper takes an injected existing HTTP client and
ephemeral token. It validates `/me`, resolves Inbox identity, reads bounded delta pages
and checks `/me` again. Returns redacted counts with private opaque checkpoints.
**Stack:** Existing Python, httpx, Pydantic SecretStr and pytest MockTransport.

- [x] Read current coordination and active claims; acknowledge Akbar's #48 revisions.
- [x] Claim one new owned slice while #51's saved live acceptance waits for access.
- [x] Write acceptance tests and observe missing-module failure before implementation.
- [x] Implement read-only network boundary, cursor/identity/error/size constraints.
- [x] Pass focused tests; inspect code and add any uncovered meaningful negative cases.
- [x] Document consent, state/PKCE, notifications/delta and attachment gaps with sources.
- [x] Run required Ruff/format/full isolated backend checks (423 passed; 32 new mocked cases).
- [ ] Commit/publish draft and request review; serialize STATUS through its owner.
- [ ] Only after approved access: real school consent, content/attachment/subscription,
      revocation and laptop-closed evidence. Keep P0-M2 open until observed.

No shared methods, schema, routes, token store, OAuth grant, subscription creation,
send/mail write, model call, deployment or scheduler. Checkpoints are internal provider
data, not an agreed C2 envelope. P1 integration waits for accepted implemented contracts.
