# Team and review responsibilities

| Role | Person | Responsibility |
|---|---|---|
| Supervisor/product owner | Akbar | Product direction, account access, releases and priorities |
| Lead engineer | Codex working with Akbar | Architecture, shared contracts/runtime, integration review and evidence |
| Engineer | Murtazo | Messaging, connected sources and student-facing app under agreed work orders |

Akbar will invite Murtazo himself. His GitHub username is not yet provided; no
invitation or message has been sent by Codex. His first assignment is prepared in
`docs/stages/B1-murtazo.md`, not claimed as in progress. While Akbar arranges his
invitation, Codex is preparing the B1a interface scaffold. Murtazo should extend
the reviewed scaffold and verify real development integrations, avoiding a second
frontend implementation.

Murtazo branches from main after the foundation is merged, reads the contract,
then opens a draft PR. Each PR includes acceptance evidence and known limitations.
Codex reviews the diff and reruns the relevant integrated path before recommending
merge. Akbar can inspect the PR and STATUS.md at any time. Critical auth/data and
external-action changes need review; green unit tests alone do not establish that
an actual provider integration works.

CODEOWNERS routes initial review to Akbar's GitHub account. Main protection is
configured and verified: passing `foundation` checks, an up-to-date branch, one
approving review and resolved conversations are required; force pushes and branch
deletion are disabled. Akbar retains the administrator override. The new `web`
job runs on the frontend PR and should become required after that workflow lands.
Codex is an engineering assistant, not a distinct GitHub user who can approve
Akbar's own PR. Murtazo can supply the independent review after his invitation.
