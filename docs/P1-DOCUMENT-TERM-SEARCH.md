# P1 bounded literal-term discovery

A/Codex runtime retrieval slice under
[claim6565366351](https://github.com/Akbarhoja/wrytely-agent/issues/4#issuecomment-6565366351).
Branch codex/p1-document-term-search from #157
`bc717cf64fa6e51241e379e029583ba59bdb9acf`.

## Implemented scope

runtime/document_term_search.py adds find_document_terms and
find_document_terms_for_task. Unlike the existing known-quote search, a caller can
find literal terms such as policy/rubric in stored original sections without knowing
their exact original capitalization. The caller then reads a hit's pinned original
section through the existing section reader before interpreting its requirements.
Search returns the matching original substring and exact existing citation proof,
not invented surrounding text or a model summary.

Both helpers reuse the existing quote-search pager's bounds, strict pinned identity,
section validation, final scoped authorization and honest freshness/history metadata.
A small internal matcher hook replaces only match discovery; existing exact-quote
behavior, output shape and caller signatures are preserved. No competing Store,
authorization or paging implementation was introduced.

Terms are a list/tuple of1–8 distinct normalized nonblank literal strings, each
1–128 Unicode code points. Exact boolean case_sensitive defaults false. Escaped
Python re.IGNORECASE matching preserves original spans rather than finding offsets
in a case-folded copy; it does not promise full Unicode case-fold equivalence (ß
is not ss). Regex metacharacters are literal, not a caller-supplied regex program.
Matching is substring-based, not word-boundary or semantic search. At a shared
start the longest term wins, deterministic lexical tie-break; overlapping starts
are retained. A next offset advances one original code point, preserving overlaps.
Matches never cross stored section/PDF page boundaries.

Existing first_slot0–512, local offset0–24000, max_pages1–8/default2 and
max_matches1–30/default10 apply. Each original read retains at most20sections and
40000codepoints. Continuation is explicit {first_slot,offset}, not an authorization
token. Repeat the same pinned IDs, terms and mode when continuing; every invocation
reauthorizes. The final one-section read rechecks current access and propagates
coverage/freshness/history to every earlier hit. Wrong roots never fall back to
latest, revocation fails, task pause/lease fences still apply.

A result labels match_scope=single_section_literal_terms and echoes terms/mode.
range_complete means only that the requested stored search suffix was scanned;
no-match cannot establish absence of policy/rubric or complete course extraction.
Partial, stale and historical originals remain honestly labeled, not newly usable.
A match is not drafting permission or assurance of semantic relevance/completeness.

## Validation

- Combined new term and existing exact-quote suites:61passed/zero skips/4.45s,
  including27new cases. Tests use synthetic text and fresh disposable Postgres.
- Exact capitalization/Unicode original proofs independently round-trip through
  verify_document_citation. Literal metacharacters, longest/overlapping terms,
  no expanding-fold offset corruption, later-page hits, split-boundary misses,
  strict limits before IO and wrong-root/account denial pass.
- Real final-read revocation, task binding and pause denial, post-hit historical
  downgrade and actual document-only publication with no fake legacy version pass.
- Two initial new fixture scenarios incorrectly tried to rebind an immutable
  document observation and resume a responsibility invalidated after work began.
  They were split into independent valid fixtures; Store protection was preserved.
- Full combined fresh disposable backend:1,449passed, zero skips, two existing
  warnings,106.71s. All404extension Node tests pass.
  Ruff lint/format227files and diff checks pass. New evidence document format/links
  are checked before publication. Candidate CI remains separate.

## Limits and next dependencies

This is an internal reusable retrieval function, **not a registered model tool,
public route, supervisor or website feature**. It does not wire autonomous paged
policy investigation or remove the existing80000codepoint drafting-context hold.
Those consumers must deliberately retrieve originals, establish complete scoped
requirements and retain final mandatory checks. No existing grant is widened.

M's #157 private artifact consumer agreement is still pending; its dependent
implementation was not started. M retains #149 document-parts producer and owned
HTTP/UI/extension assembly. No M file, shared contract, schema or DTO was changed.
P0/P1 remain open; no source/model/send/spend/grant/install/retained migration,
continuous worker, deployment or main merge occurred.
