# Saved Canvas gap audit — November 4

Read-only audit of the completed one-course development scan. Owner confirmed
collection paused. Railway's existing database viewer ran bounded SELECT queries
scoped to the unique previously verified owner, newest Canvas connection, current
generation and selected course. No database exposure, SSH key, deployment, model
call, source mutation or new collection round was introduced.

## Actual assignment blockers

| Saved assignments | Exact missing reasons |
| --- | --- |
| 10 | `attributes_not_interpreted`, `linked_content_unread`, `unsupported_text_structure` |
| 9 | `assignment_constraints_unmapped`, `assignment_locked`, `description_not_observed`, `rubric_not_observed` |
| 3 | `description_not_observed`, `rubric_not_observed` |
| 2 | `no_text` |

The ten readable assignment records have canonical rubric absence recorded. That
verifies the narrow reader correction for these observations; it does not fill
linked instructions or certify the full assignment. No assignment has complete
required evidence. Loosening coverage labels would conceal the actual gaps.

The next unlocked lab is the best investigation candidate: a future due date,
known submission type/points, and no attached Canvas rubric. Its entire saved
assignment text consists of labels for a manual and starting source file. The
manual and starter bytes are absent from this scan. Exact titles, provider IDs
and the owner's saved source text remain in ignored local audit files.

## Other resource gaps

- All five announcements record locked content, unobserved description and
  unobserved author role. Their generic resource label alone was insufficient
  to diagnose a parser failure; the exact rows now establish unread bodies.
- Grades: 24 records. All lack course-total/grading-policy/visibility evidence;
  additional excusal/score/grade gaps vary. No grade-recovery claim is justified.
- Modules: eight module records plus 31 item records. They explicitly identify
  their content as separate; enumerating an item did not collect its target.
- Submissions: nine unread external submissions, seven unread attachments, and
  eight other unobserved descriptions. No unread student result is invented.
- Syllabus: saved text exists, but attributes, links, module relationships and
  unsupported structure remain unresolved. No explicit AI-drafting permission
  was established by this audit.
- Discussions returned zero records; pages returned zero with partial coverage;
  the course files listing was restricted. These outcomes remain unchanged.

## Concrete integration defect and next repair

The collector starts file collection from the course-wide files listing. It does
not discover and collect assignment-linked file dependencies when that listing is
unavailable. HTML extraction preserves link labels as text and flags unread links;
the saved assignment therefore does not contain the linked manual's instructions.

A normal signed-in Canvas assignment page exposes direct course-scoped links to
the candidate's manual and starter. The manual's Canvas file page exposes its
download link and preview container. A download attempt reached a Chrome block
(`ERR_BLOCKED_BY_CLIENT`); no PDF bytes, successful extraction or unrestricted
download is claimed. That browser block was not bypassed.

Next A-owned P1 work should discover same-course file dependencies from selected
assignment/module/syllabus links, reuse bounded identity-checked file transport,
and publish those files through the existing journal. Preserve the parent link
and dependency identity so the agent can distinguish a collected target from an
unread label. Keep denied/external/unsupported links explicit and never use file
enumeration failure to certify a parent as complete. Verify one manual and its
starter before another broad scan. Retain independent course-policy, actual lab
results, freshness and private-draft authorization checks.

No attachment capture patch or additional live activation is claimed here. No
full P1 completion, ready offer, real-course draft or phone receipt is established.
