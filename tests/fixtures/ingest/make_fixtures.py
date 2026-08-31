# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Regenerate the ingestion fixtures. Run by hand; the outputs are committed.

    python tests/fixtures/ingest/make_fixtures.py

The fixtures are committed rather than generated at test time for two reasons.
They must be *identical bytes* on every machine — a DOCX produced by whichever
pandoc a contributor happens to have would move the digests a test asserts — and
CI must be able to exercise the parsers without the tool that produced the input.

`source.md` is the source of truth: DOCX, HTML and reStructuredText are pandoc's
renderings of it, so the same document reaches four parsers and the differences
between their KIR are the adapters' own, not the corpus's.

`text-layer.pdf` is written here by hand, not by a converter. It is 964 bytes of
uncompressed PDF with a real text layer and no compression, no fonts embedded and
no metadata — small enough to read in a hex dump, which is what a fixture for an
untrusted-input parser should be. Producing it with a real PDF writer would have
meant committing a kilobyte of opaque, unreviewable, timestamp-carrying binary.
"""

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent

_PARAGRAPH = (
    "Webhook deliveries are retried five times, and the "
    "[delivery log](https://example.com/log) records each attempt."
)
"""One unwrapped line, on purpose.

markdown-it keeps a soft line break as a newline inside a paragraph's text, while
every other engine here sees a rendered document and produces a space. Wrapping
this line would make the four parsers disagree about a paragraph for a reason
that has nothing to do with any of them."""

SOURCE = f"""\
# Retry Policy

{_PARAGRAPH}

## Backoff

Backoff doubles after every failed attempt.

- first retry after 1 s
- second retry after 2 s

| attempt | delay |
|---------|-------|
| 1       | 1 s   |
| 2       | 2 s   |

```python
delay = 2 ** attempt
```

> Deliveries stop after the fifth failure.

Term
:   A definition, which GFM cannot express and pandoc's Markdown writer would drop.
"""

PDF_LINES = [
    ("/F2 18 Tf", 72, 720, "Retry Policy"),
    ("/F1 11 Tf", 72, 690, "Webhook deliveries are retried five times."),
    ("/F1 11 Tf", 72, 672, "Backoff doubles after every failed attempt."),
    ("/F2 14 Tf", 72, 630, "Limits"),
    ("/F1 11 Tf", 72, 606, "The maximum payload size is 256 KiB."),
]


def write_pdf(path: Path) -> None:
    """Write a minimal, uncompressed, single-page PDF with a real text layer."""

    def escape(text: str) -> str:
        return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    content = (
        "BT\n"
        + "".join(
            f"{font}\n1 0 0 1 {x} {y} Tm\n({escape(text)}) Tj\n" for font, x, y, text in PDF_LINES
        )
        + "ET\n"
    )
    stream = content.encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n".encode()
    out += b"%%EOF\n"
    path.write_bytes(bytes(out))


def main() -> int:
    source = HERE / "source.md"
    source.write_text(SOURCE, encoding="utf-8", newline="\n")
    write_pdf(HERE / "text-layer.pdf")

    pandoc = shutil.which("pandoc")
    if pandoc is None:
        print("pandoc is not installed; source.md and text-layer.pdf were written")
        return 1
    # No `--standalone`: a standalone HTML file gets a `<title>` from the input
    # filename, which docling reads as the document's title and emits as a
    # heading. The fixture would then differ from its own Markdown source by an
    # artefact of how it was generated, which is the one thing a fixture must not
    # do. DOCX and reStructuredText carry no such wrapper.
    for target, name in (("docx", "source.docx"), ("html5", "source.html"), ("rst", "source.rst")):
        subprocess.run(  # fixed argument vector, no shell
            [
                pandoc,
                "--sandbox",
                "--from",
                "markdown",
                "--to",
                target,
                "--output",
                str(HERE / name),
                str(source),
            ],
            check=True,
        )
    print(f"wrote {', '.join(p.name for p in sorted(HERE.glob('*')) if p.suffix != '.py')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
