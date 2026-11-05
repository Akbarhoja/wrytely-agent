# Canvas literal HTML extraction v2 — opt-in candidate

This changes only conversion of newly supplied bytes. It is not deployed or enabled
by this document and never promotes an existing partial observation. No migration.
The P1 completion owner maintains HTTP/collector assembly; use the existing journal,
document segmentation, scoped publication and immutable evidence identities.

`canvas.html.v1` remains unchanged: its text output is always partial. The separate
`canvas.html.v2` identifier must be explicitly operator-allowlisted. If configured,
the existing schema2 `/documents/extract` and `/documents/file-extract` select v2
server-side and return that exact version. Source/browser text cannot select a parser.
The extension accepts only known versions, propagates the returned version into
metadata, and rejects v1 claims of complete HTML text. Schema1 extraction is unchanged.

V2 permits `complete` only for nonempty supplied literal text and a narrow fragment
vocabulary: p/div/span/br, h1–h6, strong/b/em/i, with no attributes. Paragraph/line
boundaries are preserved by the existing inert text parser. This means the supplied
text fragment was read; it does not certify course requirements, a syllabus, an
assignment's rubric/dates/constraints or any other resource.

Every unhandled tag/attribute retains a gap. Links, images, hidden/embedded content,
code, lists, tables, superscripts/math, external styling/classes, comments,
declarations, numeric character references and unclosed markup cannot become
complete. Malformed or excessive input is blocked with empty text. Existing UTF8,
byte/character/event/depth limits apply unchanged; no fetching, executing or logging
course content. This intentionally leaves many valid rich Canvas pages partial.

Both conversion routes check current identity/generation/scope before and after
parsing. Missing/null body cannot become complete. The extension requires nonempty
text and no extraction gaps for a v2 complete projection, but still runs the existing
assignment metadata mapper. Missing rubric, unmapped constraints, locked content,
author roles, module links and other resource-specific gaps remain independent.
Any added gap downgrades a complete extraction to a partial document. A complete
body must never close an incomplete scan/resource or bypass freshness/work gates.

Old clients accept only v1; do not enable v2 on an API used by an old installed
collector. Prepare and validate the matching extension first. No new permissions,
scan, scope change, provider calls or retained deployment are implied. Future live
acceptance needs a bounded fresh scan, exact version and true coverage evidence;
current saved partial assignments remain partial. Resource-level completeness and
other unread requirements remain potential blockers even when one body is complete.

Tests cover v1 stability, complete literal fragments, dependency/structure rejection,
bounds, HTTP version selection/revocation/no source writes, file versioning, extension
version/gap validation and independent rubric/constraint/author gaps. Synthetic
success is separate from installed-collector and real-course acceptance.
