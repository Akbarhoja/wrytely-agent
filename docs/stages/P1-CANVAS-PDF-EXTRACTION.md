# Bounded PDF source preparation

M claim [#87](https://github.com/Akbarhoja/wrytely-agent/issues/87), branch
`codex/canvas-pdf-extraction`, accepted A base581a9f5. Reuses reviewed M HTML
package/scaffold #66 as8ee9246, with the narrow compatibility correction below.
Shared parser dependency and execution
boundary are supplied by #76; M agreed the boundary in6541158295.

## Local interface

`integrations.canvas.pdf_extract.extract_pdf(bytes, limits=PdfLimits())` accepts
supplied authorized bytes. It accepts no source-supplied filename, URL, credential
or command. The provider's download/auth/origin checks remain separate.

The immutable local result has `status` (partial/blocked), controlled `reasons`,
and private `pages` tuples containing one-based `page` and normalized `text`.
Page text is excluded from dataclass repr. Successful extraction always remains
partial with `pdf_text_only` and `layout_unverified`; blank/image-only pages are
retained as empty page records with `empty_pages_or_unread_images`. This preserves
provenance without inventing OCR, equations/layout fidelity or completeness.
No C2 envelope/document manifest or C3 ingestion/read contract is constructed.

## Process bounds

- Linux only. Other platforms return unsupported_platform before starting a child.
- Fixed fresh isolated Python child, hard address-space1GiB and CPU5s caps installed
  and verified before pypdf import or document input. No in-process fallback.
- Input10MiB, pages200, normalized text200k characters (including potential page
  separators), wall10s. Valid lower caller limits only.
- Nonblocking stdin/stdout/stderr supervision; actual stdout2MiB and stderr8KiB
  limits checked before retaining data. One child at a time per caller process.
- Child environment contains only fixed locale settings; caller credentials and
  environment configuration are not inherited.
- Failure/timeout terminates the child group, reaps the child and discards prefixes.
  Raw parser exceptions/stderr never enter the returned result. No parser retries.
- Encrypted/malformed documents are controlled failures. No passwords, scripts,
  external references, attachments, network fetch or filesystem source path is used.

## Verification and limits

New test collection failed on the missing module before implementation. The parent
protocol additionally had a reproduced lone-surrogate failure; it now rejects that
input before returning page text. An environment-inheritance test also failed before
the fixed child environment was supplied. Windows focused checks:17 passed,14 Linux-only
checks skipped. Read-only independent review found no remaining scoped code blocker.
Final locked Ruff/format pass. Full Windows backend verification:659 passed,
14 Linux skips and two existing test-library warnings in681.84 seconds, against
disposable Postgres. Actual Linux CI evidence remains required; Windows skips cannot
establish Linux cap/pipe/parser acceptance. No WSL installation was attempted.

Fixtures are synthetic generated text, encrypted, blank, image and mixed-page PDFs.
Linux tests exercise actual memory/CPU failure, wall timeout with a full stdin pipe,
termination/reaping, stdout/stderr overflow, missing effective caps before parser
import and child concurrency. Production readiness and extraction fidelity remain
separate from these bounded-process checks.

The reused HTML scaffold exposed two existing failures under Python3.14: its
HTMLParser routes unknown declarations through bogus-comment handling rather than
unknown_decl. A narrow M-owned declaration-dispatch guard now rejects those forms
before version-specific handling, preserving comments/doctypes and discarding all
prefixes. Both original cases failed before the correction; all45 HTML cases pass.
The scope extension was recorded in #87 before editing. Combined extraction checks
are62 passed/14 Linux skips; no shared or packaging file was changed.

No real course PDF, provider/model call, connector grant, source/model activation,
retained development/production migration, service configuration or deployment.
#86 Unicode reader acceptance remains blocked independently. P0 access, long-document
publication/segments and complete academic-agent behavior remain unfinished.
