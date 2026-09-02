# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Regenerate the ingestion fixtures. Run by hand; the outputs are committed.

    python tests/fixtures/ingest/make_fixtures.py

The fixtures are committed rather than generated at test time for two reasons.
The bytes must be *the same on every machine* — a DOCX produced by whichever
pandoc a contributor happens to have would move the digests a test asserts — and
CI must be able to exercise the parsers without the tool that produced the input.

This script is therefore not byte-reproducible, and does not need to be: the ZIP
containers it writes embed a modification time, so re-running it produces
different bytes for the same content. Regenerating a fixture is a deliberate act
whose diff a reviewer reads; `git checkout` is the way back for the ones that only
churned.

`source.md` is the source of truth: DOCX, HTML and reStructuredText are pandoc's
renderings of it, so the same document reaches four parsers and the differences
between their KIR are the adapters' own, not the corpus's.

`corpus/` extends that to the kinds `source.md` never reaches, and every file
here is declared in `inventory.json` — the hand-written count of what each source
contains, which the M4 exit gate compares each engine's output against
(ADR-0038). Adding a fixture means adding its declaration: an undeclared file
fails the gate, because a fixture nobody declared is a fixture nobody checks.

`hostile/` is the suite the M4 exit gate names: malformed, bomb-shaped and
mislabelled files that must each produce **one typed failure**, fast, and never a
hang, a crash, or an unhandled exception. Every one of them is generated here, so
a reviewer can see exactly what makes it hostile instead of trusting an opaque
binary. Sizes are kept small on purpose — `bomb.docx` is 51 KB that declares 50 MB,
and `nested.html` is 55 KB that took docling 45 seconds before the guards existed
(ADR-0033).

`text-layer.pdf` is written here by hand, not by a converter. It is 964 bytes of
uncompressed PDF with a real text layer and no compression, no fonts embedded and
no metadata — small enough to read in a hex dump, which is what a fixture for an
untrusted-input parser should be. Producing it with a real PDF writer would have
meant committing a kilobyte of opaque, unreviewable, timestamp-carrying binary.
"""

import io
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
HOSTILE = HERE / "hostile"

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


def write_pdf(path: Path, lines: list[tuple[str, int, int, str]] | None = None) -> None:
    """Write a minimal, uncompressed, single-page PDF.

    An empty `lines` writes a page with **no text layer** — a valid PDF that
    PDFium opens and finds nothing in, which is what a scan looks like to a text
    extractor.
    """

    def escape(text: str) -> str:
        return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    drawn = PDF_LINES if lines is None else lines
    content = (
        "BT\n"
        + "".join(
            f"{font}\n1 0 0 1 {x} {y} Tm\n({escape(text)}) Tj\n" for font, x, y, text in drawn
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


def write_hostile() -> None:
    """Write the hostile suite. Each file has one job; the comment says which."""
    HOSTILE.mkdir(parents=True, exist_ok=True)

    # A decompression bomb: 50 MB of zeros in 51 KB. Invisible to a byte ceiling,
    # obvious to the ratio check in `mycelium.ingest.safety`.
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("[Content_Types].xml", b"<?xml version='1.0'?><Types/>")
        archive.writestr("word/document.xml", bytes(50 * 1024 * 1024))
    (HOSTILE / "bomb.docx").write_bytes(buffer.getvalue())

    # Billion laughs inside a plausible container. The archive guard passes it —
    # the declared sizes are honest — and the engine refuses it, which is the
    # point: the guards are layers, not a single gate.
    laughs = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
 <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">
 <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
 <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
 <!ENTITY lol5 "&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;">
 <!ENTITY lol6 "&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;">
 <!ENTITY lol7 "&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;">
 <!ENTITY lol8 "&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;">
]>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body><w:p><w:r><w:t>&lol8;</w:t></w:r></w:p></w:body></w:document>"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b"<?xml version='1.0'?><Types/>")
        archive.writestr("_rels/.rels", b"<?xml version='1.0'?><Relationships/>")
        archive.writestr("word/document.xml", laughs)
    (HOSTILE / "laughs.docx").write_bytes(buffer.getvalue())

    # A container whose member name climbs out of it (zip slip).
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../../escaped.xml", b"<?xml version='1.0'?><x/>")
    (HOSTILE / "escaping.docx").write_bytes(buffer.getvalue())

    # 5 000 nested elements. docling took 45 s on this before the depth guard;
    # at 50 000 it had not returned after five minutes.
    (HOSTILE / "nested.html").write_bytes(b"<div>" * 5000 + b"deep" + b"</div>" * 5000)

    # A DOCX that is not a ZIP, and a PDF that stops after its header.
    (HOSTILE / "notazip.docx").write_bytes(b"plain text pretending to be a docx\n")
    (HOSTILE / "truncated.pdf").write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\n")
    (HOSTILE / "empty.pdf").write_bytes(b"")

    # A PDF whose only page carries no text layer at all — a scan, in effect.
    # Every element is lost, so the loss budget refuses its projection: this is
    # the fixture that makes `[ingest] max_failed_elements` a knob that bites
    # rather than a knob that is merely documented (ADR-0034).
    write_pdf(HOSTILE / "no-text-layer.pdf", lines=[])

    # An extension that lies: PDF bytes under a .md name. Parsed as the extension
    # claims (the operator's pinned parser list was written against names), with
    # the contradiction recorded as a warning (roadmap 4.1).
    (HOSTILE / "mislabelled.md").write_bytes(b"%PDF-1.4\nnot markdown at all\n")


CORPUS = HERE / "corpus"

ELEMENTS = """\
# Element Coverage

This paragraph carries an ![architecture diagram](diagram.png) and a footnote.[^note]

## Ordered steps

1. first step
2. second step
   - a nested detail
   - another nested detail

### A level-three heading

Prose beneath a level-three heading.

#### A level-four heading

Prose beneath a level-four heading.

## Code and quotation

```
a code block with no language
```

```sql
SELECT count(*) FROM deliveries;
```

> A quotation that stands on its own.

---

## After the break

The thematic break above is dropped by policy: it carries no content at all.

[^note]: Footnotes belong to pandoc's Markdown, not to CommonMark.
"""
"""The kinds `source.md` does not reach.

Deliberately built from constructs the four routes can be *compared* on — deeper
headings, an ordered list with a nested one inside it, a code block with a
language and one without, an image, a quotation, a thematic break. The footnote
is the exception, and it is here on purpose: CommonMark has none and the Mycelium
Markdown Profile adds none, so the Markdown route sees the definition as prose
while pandoc and docling see a footnote. That is a real, durable difference
between the routes, and a corpus that avoided it would be avoiding the thing the
inventories exist to record.
"""

PROFILE = """\
# Profile Constructs

The Mycelium Markdown Profile (D-022) adds syntax no other format has, so this
family has one route and makes no claim about the others.

See [[retry-policy]] and [[retry-policy#Backoff|the backoff section]].

![[architecture-diagram]]

Tagged #ingestion and #profile/v1.

> [!warning] An embed links, it never inlines
> Transclusion would copy a document into another document's chunks, and the
> citation would then point at the wrong one.
"""
"""Wikilinks, an embed, tags and a callout — the vocabulary only `markdown` reads."""

TWO_PAGE_LINES = [
    [
        ("/F2 18 Tf", 72, 720, "Quarterly Report"),
        ("/F1 11 Tf", 72, 690, "Deliveries rose by eleven per cent this quarter."),
        ("/F1 11 Tf", 72, 672, "The retry budget was not exhausted in any region."),
    ],
    [],
]
"""Two pages: one with a text layer, one without.

The second page is what a scanned sheet looks like to a text extractor — a valid
page PDFium opens and finds nothing in. Having both in one document is the point:
it produces a page locator and an opaque `lost` node from the same parse, which is
the pair the loss accounting has to get right (ADR-0034).
"""


def write_two_page_pdf(path: Path) -> None:
    """Write a two-page uncompressed PDF, one page with text and one without.

    Deliberately not a generalisation of :func:`write_pdf`. Threading a page list
    through that function would renumber its PDF objects, which would rewrite
    `text-layer.pdf` and `hostile/no-text-layer.pdf` byte for byte — churning two
    committed binaries to avoid twenty lines here.
    """

    def escape(text: str) -> str:
        return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    streams = [
        (
            "BT\n"
            + "".join(
                f"{font}\n1 0 0 1 {x} {y} Tm\n({escape(text)}) Tj\n" for font, x, y, text in page
            )
            + "ET\n"
        ).encode("ascii")
        for page in TWO_PAGE_LINES
    ]

    # 1 catalog, 2 pages, 3..4 page objects, 5..6 contents, 7..8 fonts.
    page_ids = [3, 4]
    content_ids = [5, 6]
    kids = " ".join(f"{number} 0 R" for number in page_ids)
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode(),
    ]
    for content_id in content_ids:
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 7 0 R /F2 8 0 R >> >> /Contents "
            + str(content_id).encode()
            + b" 0 R >>"
        )
    for stream in streams:
        objects.append(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream"
        )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

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


DIAGRAM_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000b4944415478da636000020000050001e9fadcd80000"
    "000049454e44ae426082"
)
"""A 1×1 transparent PNG, 68 bytes, written out literally.

It exists because pandoc *embeds* an image when it writes DOCX, and cannot embed
one it cannot open: without a real file beside the source, the DOCX would arrive
with no picture and the corpus would record a generator accident as a parser
difference. A fixture must never make a tool look worse than it is.
"""


def write_corpus(pandoc: str | None) -> list[str]:
    """Write the inventory corpus and return the paths written, for the log."""
    CORPUS.mkdir(exist_ok=True)
    (CORPUS / "diagram.png").write_bytes(DIAGRAM_PNG)
    (CORPUS / "elements.md").write_text(ELEMENTS, encoding="utf-8", newline="\n")
    (CORPUS / "profile.md").write_text(PROFILE, encoding="utf-8", newline="\n")
    write_two_page_pdf(CORPUS / "two-pages.pdf")
    if pandoc is not None:
        render(pandoc, CORPUS / "elements.md", CORPUS, "elements")
    return [f"corpus/{p.name}" for p in sorted(CORPUS.glob("*")) if p.is_file()]


def render(pandoc: str, source: Path, into: Path, stem: str) -> None:
    """Render one Markdown source into the three formats pandoc writes for us.

    ``--resource-path`` is not optional here: pandoc resolves an image relative to
    its *working directory*, so without it the DOCX writer silently omits a
    picture it could not open, and the corpus would record where the script was
    run from as a difference between parsers.

    ``--sandbox`` is deliberately **absent**, which is the opposite of the rule
    the pandoc *parser* follows (ADR-0032). The sandbox exists to fence an engine
    reading untrusted bytes at build time; this script reads a source in this
    repository, by hand, and the sandbox would stop it opening the image it is
    supposed to embed — leaving a DOCX with no picture and an inventory recording
    a generator restriction as a parser difference.
    """
    for target, suffix in (("docx", "docx"), ("html5", "html"), ("rst", "rst")):
        subprocess.run(  # fixed argument vector, no shell
            [
                pandoc,
                "--resource-path",
                str(into),
                "--from",
                "markdown",
                "--to",
                target,
                "--output",
                str(into / f"{stem}.{suffix}"),
                str(source),
            ],
            check=True,
        )


def main() -> int:
    write_hostile()
    source = HERE / "source.md"
    source.write_text(SOURCE, encoding="utf-8", newline="\n")
    write_pdf(HERE / "text-layer.pdf")

    pandoc = shutil.which("pandoc")
    corpus = write_corpus(pandoc)
    if pandoc is None:
        print("pandoc is not installed; only the files it does not render were written")
        print("wrote " + ", ".join(corpus))
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
    written = [p.name for p in sorted(HERE.glob("*")) if p.suffix != ".py" and p.is_file()]
    written += [f"hostile/{p.name}" for p in sorted(HOSTILE.glob("*"))]
    written += write_corpus(pandoc)
    print("wrote " + ", ".join(written))
    return 0


if __name__ == "__main__":
    sys.exit(main())
