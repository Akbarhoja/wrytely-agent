# Browser document-part producer

Murtazo owns [#149](https://github.com/Akbarhoja/wrytely-agent/issues/149), branch
codex/canvas-document-parts, base A#135019d6c7. Existing API#155647c503 and browser
packages remain preserved. Five new claimed files only; no shared/schema/fixture/
app/host/UI/CI/STATUS edits. Reuse the approved v2 vectors and existing validators.

## Interface and limits

`await prepareDocumentParts({text, sectionCharacters?})` or
`await prepareDocumentParts({pages, sectionCharacters?})`. Exactly one source;
pages is a dense ordered array of1–200 extracted page strings, including empty
entries for pages without observed text. No PDF parser or fetching is included.
Default sectionCharacters24000, integer1–24000. Return manifest, parts,
total_characters, total_pages and derived unrepresented_pages; wire consumers use
the existing manifest/parts fields and choose coverage separately.

Validate primitive strings/Unicode and reject NUL. Bound raw input at400000 code
points and1MiB aggregate UTF8 before normalization; bound normalized joined text
at200000 code points, sections at512 and each section at24000. Normalize CRLF/CR
to LF and whole text to NFC before splitting. PDF pages retain their original
1-based indices; join nonempty pages with an LF attributed to the following page.
Empty pages contribute no fabricated section; return their original numbers as
unrepresented_pages, not a completeness/coverage judgment. Empty non-PDF text is
valid and has no sections. Reject any bound violation without returning a prefix.

Snapshot and split every page before the first awaited SHA256. Hash the exact
normalized section UTF8. Offsets count Unicode code points, never UTF16 units.
Output is fresh data with no references into mutable input. Source/extracted text
never appears in validation errors. No credentials, storage, retries or IO.

## Acceptance

Tests must reproduce all10 unchanged fixture manifests/parts/totals and original
canonical UTF8/root hashes using existing source-digest.mjs. Actual JS outputs
must pass existing Python section/root validators, including long astral text and
PDF gaps. Exercise normalization expansion, Unicode boundaries, empty text/pages,
each limit, malformed containers and mutation during hashing. Full Node, Ruff/
format, disposable backend and fresh final review are required.

## Observed evidence

- Initial focused RED: missing producer module before implementation.
- All10 unchanged approved vectors reproduce exact manifest/parts/totals,
  canonical UTF8 and original root SHA256. Python runs actual JS output through
  existing validators:14passed/zero skips/0.82s, including200000astral characters,
  long page sections, normalization, PDF gaps and the512slot boundary.
- Final full extension suite:421passed/zero skips/2.90s, including56producer cases.
  This base has365prior cases; the separate browser-package candidate has404 and
  was not removed or copied into this branch.
- Fresh final reviewer found one Important error-redaction gap: throwing proxy
  traps could expose arbitrary source-bearing exceptions. Eight new regressions
  observed RED before fixes. Reflection errors now use the fixed TypeError with
  no original cause; page counts are checked as integers before coercion. Final
  Node and Python checks above pass. The reviewer reported no other findings or
  minors; the author verified the fixes through those RED→GREEN regressions.
- Two partial backend runs were deliberately interrupted during that fix pass;
  neither is completion evidence. The final fresh disposable Postgres run after
  the complete fix passed1150tests/zero skips/2existingwarnings/1596.80s through
  `uv run pytest -q`. No implementation changed after that run started.
- uv Ruff lint/format188files, scoped Prettier, local links and diff checks passed.

The branch retains its approved019d6c7 implementation base. The draft PR targets
A's current complete #158385d5b2 chain, including API integration#156 and the
existing directory-glob CI. Merge-base019d6c7 means the PR adds only the five claimed files.
No direct push or implementation edit to A's branch occurs. The older base's static
CI list omitted this new file; local branch evidence above remains separate.

An ignored exactf62fb0c archive plus only the five M additions initially passed
460Node/14cross-language cases. After receiving A's #156–158 handoff, repeated
the scoped compatibility check on exact385d5b2 plus the same additions:460Node
tests/zero skips/3.08s and14actual JS/Python cases/1.06s. This is not a full combined
backend or HTTP producer acceptance run. Remote merge-candidate CI is separate.
All five #155 files were verified byte-identical in A's #156 integration. The
producer remains unbundled/unwired; A integration/review is still required.

This helper is unbundled/unwired. Parsing, upload transport/journal, publication,
source activation and live acceptance remain separate. P0/P1 remain open; Chrome
untouched and automation off. No live calls/spending/sends/grants/install/deploy.
