# Selected Canvas linked files v1 — candidate

Owner: A, `codex/p1-linked-files`. This extends the existing document pipeline;
no migration, alternate store, scheduler, browser login or new permission is added.
Deploy the compatible backend before loading collector0.3.4. Existing installed
packages and live settings are unchanged by preparing this candidate.

## Discovery and scope

Only an initial course-files listing denied by Canvas enables the fallback. Later
pagination loss, file-detail errors, login/account changes and network failures do
not select this fallback. Files and each parent category must already be selected
for that same course. The existing context/profile checks fence reads and commit.

The fallback enumerates links from selected syllabus and assignment bodies, skipping
locked assignments and quiz objects. It recognizes quoted anchor hrefs for exact
same-origin, same-course Canvas file paths. Script/comments, unrecognized markup,
external/cross-course links, credentials, traversal and unexpected query parameters
are not followed. It never evaluates or executes linked content.

Durable continuation uses `wrytely-linked-files-v1:` plus bounded canonical JSON:
version/course/selected parent categories, parent-list paging, numeric file IDs,
parent references and the next file offset. Limits:100 assignment pages,64 unique
file IDs,32 parents per file,4000 cursor characters,4 files per step. Limit overflow
stops explicitly. No original HTML, signed storage URLs, bytes or credentials enter
this cursor. Existing journal replay, upload expiry and context fencing are reused.

Direct file metadata uses Canvas's course-scoped file endpoint. Downloads retain
the existing two approved storage hosts,5MiB bound, MIME/PDF-signature checks and
identity checks. Individual denied/not-found files do not prevent other discovered
files from being read. The denied enumeration is still a partial resource outcome;
there is no claim that all course files were discovered.

## Additive file fields

Existing `filename` and `content_type` remain required. New observations may include:

```json
{
  "filename": "manual.txt",
  "content_type": "text/plain",
  "linked_from": ["assignment:31", "syllabus:101"]
}
```

`linked_from` is optional for legacy compatibility; when present it is a nonempty,
sorted, unique list of at most32 canonical `assignment:<numeric-id>` or
`syllabus:<current-course-id>` strings. It records where a link was observed, not
instructor authority, completed dependency resolution or permission to draft. It is
part of the immutable canonical document root and digest. The backend checks parent
category selection at upload begin and subsequent upload/publication operations.

`text/x-c` and `text/x-csrc` use the existing bounded UTF-8 text converter, with
invalid encoding/NUL rejection. Source code is stored as text and never executed.
Unrecognized binary MIME types remain unsupported; extensions alone do not choose
the converter. PDF extraction still retains its layout/image gap.

## Readiness and activation

Parent `linked_content_unread` and all other coverage/policy/constraint/freshness
checks remain unchanged. A collected target does not automatically make its parent
complete. Runtime consumers can inspect the file and its parent reference; automatic
dependency-readiness certification is not implemented by this change.

Tests are synthetic. Review/full CI and a separately approved bounded development
refresh must establish actual manual/starter access. Chrome's blocked manual
download is not bypassed or claimed fixed by this implementation. No real source
is recollected, no Meta call is made and no WhatsApp/Telegram transport is enabled.

Provider reference: [Canvas Files API](https://developerdocs.instructure.com/services/canvas/resources/files).
