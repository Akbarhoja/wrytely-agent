# Canvas HTML text preparation

M-owned independent slice [#65](https://github.com/Akbarhoja/wrytely-agent/issues/65),
based on own pairing HTTP #64 at `57ca6ea`. New pure adapter only; no existing
Store, mapper, source contract, API, extension or runtime consumer changes.

`integrations.canvas.html_extract.extract_html(content: bytes, *, max_bytes=1048576,
max_chars=200000, max_events=20000, max_depth=128)` returns immutable
`HtmlExtraction(text, status, reasons)`. Limits may only lower fixed ceilings.
Input is supplied UTF-8 bytes. No URL, credential, user ID, fetch callback or file
path is accepted. The helper performs no IO, rendering, scripting, persistence or logging.

Nonempty text always has `status="partial"` and `html_text_only`. Reasons distinguish
linked resources not fetched, nontext/embedded resources not read, explicit hidden
content omitted, and unclosed markup. A consumer must preserve those limitations;
text presence cannot establish complete content, readiness, authorization or policy.
No shared C2 status field is changed or inferred from this local result.

Block elements and explicit breaks retain line boundaries; table cells separate words.
Entities decode, horizontal whitespace collapses, and Unicode normalizes to NFC.
This is a bounded text approximation, not browser layout: CSS, generated content,
preformatted spacing, tables, equations, images and documents can lose meaning.
Conservative exclusions include active/script/style/head/template/noscript content,
iframe/object/embed, SVG/math/canvas and audio/video subtrees. Explicit hidden,
aria-hidden=true, display:none and visibility:hidden are omitted with their descendants.

Malformed nesting, duplicate attributes and selfclosing nonvoid elements are blocked
instead of guessing browser visibility. Valid HTML with omitted optional end tags
may therefore be rejected or marked unclosed; rejection must remain a coverage gap.
Invalid input/encoding/limits, malformed markup and exceeded bounds return empty text
and controlled reason codes. No prefix survives a limit failure. Parser events include
tags, data, comments, declarations and processing instructions. Input-byte limits also
bound huge attributes and comments; character limits include parser-added separators.

Tests use only inline synthetic HTML. The initial missing-module RED preceded the
implementation. Five additional RED regressions exposed selfclosing script/hidden
tags, duplicate style attributes and marked declarations; fixes reject the ambiguous
forms rather than expose hidden text. Exact final test/lint evidence is in the PR.

PDF, Word, OCR, external links, downloads, live source reads, provider identity,
scope/checkpoint/sync transactions and UI integration are future handoffs. Existing
P0 live acceptance, #58 shared scope/context implementation and #64 counterpart
review remain separate gates. A shared packaging request for a maintained PDF parser
was sent to Akbar; no dependency, environment, production configuration, deployment,
retained migration, model call or external send is added here. Chrome stays open.
