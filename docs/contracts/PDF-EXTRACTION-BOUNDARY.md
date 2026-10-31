# PDF dependency and proposed extraction boundary

A-owned packaging request [#75](https://github.com/Akbarhoja/wrytely-agent/issues/75)
responds to M's [#65 request](https://github.com/Akbarhoja/wrytely-agent/issues/65#issuecomment-6538446524).
Only the library is provided here. The extraction execution boundary below is a
proposal for M review, not an implemented helper or accepted consumer interface.

## Provided dependency

`pyproject.toml` allows `pypdf>=6.21.4,<7`; `uv.lock` records the exact resolved
version and distribution hashes. Install using `uv sync --locked`. No image,
OCR, encryption or other optional extras are requested. No unrelated dependency
upgrade is intended. The package is available to M's future isolated extractor,
not imported by the API or runtime as a result of this change.

Official references: [installation](https://pypdf.readthedocs.io/en/stable/user/installation.html)
and [text extraction](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).
The latter explains that parsing a complete content stream can require large
amounts of memory and that image-only PDFs need separate OCR. Download bytes and
page count alone cannot bound decompressed parsing memory.

## Proposed M-owned consumer

M implements and tests the extractor in `integrations/`, including its subprocess
entrypoint and parent supervisor. A owns packaging only. Agree/refine these proposed
ceilings and outcome fields in #65/#75 before consumer implementation:

- Accept only supplied, authorized PDF bytes; no URL, credential, shell command or
  arbitrary filesystem path supplied by source content. The provider adapter owns
  redirect/origin checks and bounded downloading separately.
- Initial ceilings: 10 MiB input, 200 pages, 200,000 output text characters, five CPU
  seconds and ten seconds total wall time. Lower caller limits may reduce ceilings.
  Exceeding a bound discards the result; never return a prefix as a whole document.
- Parse in a fresh child process. On Linux establish and verify a hard 1 GiB address
  space limit (`RLIMIT_AS`) and CPU limit before importing pypdf or inspecting the
  document. The parent must not parse metadata/pages or decompress a stream first.
  If effective OS caps cannot be established, return a controlled unsupported result;
  do not silently use in-process parsing. In particular, macOS success with a configured
  rlimit is not proof of Linux-equivalent enforcement.
- The parent bounds actual stdout/stderr bytes, closes unused descriptors, enforces
  wall time, kills/reaps a timed-out child, and limits concurrent children. Do not
  capture unlimited child output before checking its size. Child failure, memory
  exhaustion and timeout yield controlled codes without source text or raw exception
  details. No automatic parser retry or alternate unsafe fallback.
- Do not decrypt password-protected documents, execute embedded scripts, traverse
  external references, extract attachments or fetch anything. Reject encrypted,
  malformed and unsupported documents explicitly. Empty/image-only pages, images,
  equations/layout loss and unread sections remain coverage gaps. Plain extracted
  text is partial evidence, not a completeness or semantic-correctness certificate.
- Preserve page order and page provenance for the later agreed document-segment
  contract. No C2 payload, parent/slot manifest, completeness field or C3 reader is
  invented here. PDF parsing does not authorize ingestion, model use or delivery.

## Required evidence before activation

M's future PR needs synthetic text, encrypted, malformed, image-only and mixed-page
fixtures; output/page/input bounds; an actual Linux memory-limit failure; CPU and
wall timeout termination/reaping; bounded pipe output; unsupported-platform behavior;
and tests showing failures do not expose a prefix, private text or parser exceptions.
Real consenting file collection and complete source retrieval remain separate gates.

Packaging validation uses a trusted, generated one-page text PDF only. That smoke
check establishes compatible import/write/read behavior, not hostile-document safety,
extraction fidelity, OS confinement or live course access. No extractor, download,
OCR, schema migration, deployment or continuous worker is activated by this document.
