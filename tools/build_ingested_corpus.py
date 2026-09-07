#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Build the third judged corpus: the second one, ingested from binary sources.

    python tools/build_ingested_corpus.py [--check]

The corpus this writes is the *twin* of `eval/corpora/uv-docs`: the same 81
upstream documents, the same content, rendered into DOCX, HTML and PDF and put
back through the real evidence lane — acquire, parse, account, project. What
comes out under `knowledge/evidence/` is what `mycelium build` then compiles and
`mycelium eval` scores, beside its Markdown original.

**Why a twin rather than a new corpus.** The M4 exit gate asks for an
ingestion-heavy corpus in the eval set; the question worth asking of it is
whether projection costs retrieval, and that is a *paired* question. A corpus of
different documents with new judgements could not answer it, and new judgements
written by the same agent that built the parsers is exactly the trap ADR-0027
was written about. Here nothing is judged at all: the judgements are the ones
already frozen for the Markdown corpus, and `tools/build_ingested_cases.py`
carries them across by matching text, not by re-reading the documents.

**Format assignment is mechanical, fixed before anything is measured, and
append-only.** The documents a judgement points at take `docx`, `html`, `pdf` in
rotation. Every other document is HTML: its format cannot change a judgement —
it is a distractor either way — and a PDF costs seven times the bytes of the
Markdown it came from. HTML also makes those distractors *strong* (their headings
survive), which is the conservative choice: it cannot flatter the judged
documents.

The rotation runs over a **recorded order**, `format-rotation.json`, rather than
over the judged paths re-sorted on every run. Sorting was the original rule and
it made the corpus unable to grow: a document newly judged sorts *between*
existing ones, shifts every index after it, and re-rolls the format of documents
already rendered — whose renderings are committed provenance that cannot be
re-derived, because typst embeds a build identifier (ADR-0039). So an assignment,
once made, is never remade. A newly judged document appends, takes the next
format in the cycle, and nothing already rendered moves. A document that stops
being judged keeps its slot for the same reason: the file on disk is the
evidence, and the order is the record of how it got there (roadmap 4.26,
ADR-0056).

**Rendering.** pandoc writes the DOCX and the HTML. For PDF it writes typst
markup, which the `typst` package compiles — chosen because it is one pip install
with no LaTeX distribution behind it, and because a PDF has to come from a real
typesetter if the text layer it produces is going to resemble a real document's.
Images become their alt text first, uniformly for all three formats: the vendored
corpus dropped the image files, so a reference to one is a dangling path that
typst refuses and the other two writers silently keep.

**The rendered binaries are committed, and they have to be.** typst embeds a
build identifier, so compiling the same markup twice produces two different PDFs
— measured, and not fixable with `SOURCE_DATE_EPOCH`. A corpus whose inputs
cannot be re-derived byte-for-byte is a corpus that has to *keep* its inputs, so
`--render` is a one-time provenance act and `sources/` is vendored beside the
evidence, the same way the Markdown it came from is vendored (ADR-0039).

Which leaves the default path doing the part that must stay reproducible:
ingesting the committed bytes. `--check` does it into a temporary tree and
compares, so a change in docling, pandoc, PDFium or the projector shows up as a
named difference rather than as a corpus that quietly stopped matching its own
provenance.

`--render` is therefore *incremental*: it writes the renderings the plan asks for
and disk does not already have, and it removes a stale rendering of the same
document in another format. A deliberate full re-render is `rm -rf sources/`
followed by `--render` — a provenance act with a per-format cost table to
re-measure behind it, not something a routine invocation should do by accident.
"""

import argparse
import filecmp
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.ingest import (  # noqa: E402
    EVIDENCE_DIRNAME,
    IngestError,
    Registry,
    ingest_source,
    write_projection,
)
from mycelium.sdk.identity import new_ulid  # noqa: E402

SOURCE_CORPUS = ROOT / "eval" / "corpora" / "uv-docs"
CORPUS = ROOT / "eval" / "corpora" / "uv-docs-ingested"
KNOWLEDGE = "knowledge"

ROTATION_FILE = "format-rotation.json"
"""The order judged documents took their formats in — the record the rotation runs over.

Committed, because it is the only thing that makes the assignment append-only:
without it the order is recomputed by sorting, and a document newly judged shifts
every format after it (roadmap 4.26)."""

FORMATS: tuple[str, ...] = ("docx", "html", "pdf")
DISTRACTOR_FORMAT = "html"

_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
"""An image reference, replaced by its alt text before rendering.

The vendored corpus is prose — the upstream image files were not copied — so the
path in an image reference points at nothing. typst refuses to compile one that
escapes its root, and the DOCX and HTML writers keep it as a broken link. Neither
is the document. The alt text is what a reader gets and what the Markdown twin's
KIR already stores for an image node, so replacing the reference with it keeps
the two sides comparable.
"""

_EXTENSION = {"docx": ".docx", "html": ".html", "pdf": ".pdf"}
_EXTENSION_FORMAT = {value: key for key, value in _EXTENSION.items()}


def judged_documents() -> tuple[str, ...]:
    """The corpus-relative paths a frozen judgement points at, sorted."""
    import json

    seen: set[str] = set()
    for name in ("dev.jsonl", "release.jsonl"):
        path = SOURCE_CORPUS / "eval" / name
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                for relevant in json.loads(line)["relevant"]:
                    seen.add(relevant["anchor"].split("#", 1)[0])
    return tuple(sorted(seen))


def rotation_order() -> list[str]:
    """The committed order judged documents took their formats in, oldest first."""
    import json

    path = CORPUS / ROTATION_FILE
    if not path.is_file():
        return []
    recorded = json.loads(path.read_text(encoding="utf-8"))
    return [str(item) for item in recorded]


def rotation_of(judged: tuple[str, ...] | None = None) -> list[str]:
    """The recorded order, with any newly judged document appended in path order.

    Append-only: an entry is never moved and never dropped, so every format
    already rendered stays the format on disk. New entries go on the end, sorted
    among themselves, so two people adding the same cases compute the same plan.
    """
    order = rotation_order()
    known = set(order)
    order.extend(path for path in sorted(judged or judged_documents()) if path not in known)
    return order


def assignment(judged: tuple[str, ...] | None = None) -> dict[str, str]:
    """Which format each document is rendered into. Mechanical, stated, unchosen."""
    order = rotation_of(judged)
    plan = {path: FORMATS[index % len(FORMATS)] for index, path in enumerate(order)}
    for path in sorted(markdown_documents()):
        plan.setdefault(path, DISTRACTOR_FORMAT)
    return plan


def write_rotation(order: list[str]) -> None:
    """Record the order. Written by `--render`, which is when a slot is actually taken."""
    import json

    body = json.dumps(order, indent=2)
    (CORPUS / ROTATION_FILE).write_text(body + "\n", encoding="utf-8", newline="\n")


def markdown_documents() -> Iterator[str]:
    docs = SOURCE_CORPUS / "docs"
    for path in docs.rglob("*.md"):
        yield path.relative_to(SOURCE_CORPUS).as_posix()


def render(source: Path, destination: Path, fmt: str, *, typst_root: Path) -> None:
    """Render one Markdown document into `fmt` at `destination`."""
    text = _IMAGE.sub(r"\1", source.read_text(encoding="utf-8"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "pdf":
        markup = destination.with_suffix(".typ")
        _pandoc(text, markup, "typst")
        try:
            import typst
        except ImportError as error:  # pragma: no cover - a generator-only dependency
            msg = "PDF rendering needs the `typst` package: pip install typst"
            raise SystemExit(msg) from error
        typst.compile(str(markup), output=str(destination), root=str(typst_root))
        markup.unlink()
        return
    _pandoc(text, destination, "docx" if fmt == "docx" else "html5")


def _pandoc(text: str, destination: Path, writer: str) -> None:
    argv = [
        "pandoc",
        "--sandbox",
        "--from",
        "markdown",
        "--to",
        writer,
        "--output",
        str(destination),
    ]
    completed = subprocess.run(  # fixed argument vector, no shell
        argv, input=text.encode("utf-8"), capture_output=True, check=False
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        msg = f"pandoc failed writing {destination.name}: {detail}"
        raise SystemExit(msg)


def render_sources(sources: Path) -> list[str]:
    """Render what the plan asks for and disk does not already have.

    Incremental, and that is the point: a rendering already committed is
    provenance (the module docstring says why), so re-making it would replace the
    bytes a measurement was taken on with different bytes saying the same thing.
    Returns the documents actually rendered, so a caller can report exactly what
    a provenance act touched.
    """
    written: list[str] = []
    for relative, fmt in sorted(assignment().items()):
        stem = sources / Path(relative).relative_to("docs")
        target = stem.with_suffix(_EXTENSION[fmt])
        if target.is_file():
            continue
        # A document whose assigned format changed leaves its old rendering
        # behind, and the corpus would then hold the same document twice.
        for extension in _EXTENSION.values():
            stale = stem.with_suffix(extension)
            if extension != _EXTENSION[fmt] and stale.is_file():
                stale.unlink()
        render(SOURCE_CORPUS / relative, target, fmt, typst_root=sources)
        written.append(relative)
    return written


def build(corpus: Path, *, sources: Path) -> int:
    """Ingest every committed source into `corpus`. Returns the number of failures."""
    evidence = corpus / KNOWLEDGE / EVIDENCE_DIRNAME
    if evidence.exists():
        shutil.rmtree(evidence)
    manifest: dict[str, dict[str, str]] = {}

    # No `pandoc`: docling reads the DOCX and the HTML and `pdf` reads the PDF, so
    # pinning a parser nothing dispatches to would make `--check` need a binary it
    # never calls — and resolution refuses a pinned parser that is not installed
    # (spec 05 §4.2), which is the right rule and the wrong requirement here.
    registry = Registry.resolve(
        parsers=["markdown", "docling", "pdf"],
        connectors=["file"],
        roots=[corpus, sources],
    )
    mycelium_dir = corpus / ".mycelium"
    failures = 0
    for source in sorted(sources.rglob("*")):
        if source.is_dir():
            continue
        try:
            ingested = ingest_source(
                mycelium_dir,
                registry,
                str(source),
                doc_id=new_ulid(),
                knowledge_dir=KNOWLEDGE,
            )
        except IngestError as error:
            failures += 1
            print(f"  FAILED {source.relative_to(sources).as_posix()}: {error}")
            continue
        written = write_projection(corpus, ingested)
        manifest[relative_of(source, sources)] = {
            "format": _EXTENSION_FORMAT[source.suffix],
            "source": source.relative_to(corpus).as_posix(),
            "evidence": written.relative_to(corpus).as_posix(),
            "parser": ingested.parser_id,
            "source_digest": ingested.original.digest,
        }
    _write_manifest(corpus, manifest)
    return failures


def relative_of(source: Path, sources: Path) -> str:
    """The Markdown document in the twin corpus that `source` was rendered from."""
    stem = source.relative_to(sources).with_suffix(".md")
    return (Path("docs") / stem).as_posix()


def _write_manifest(corpus: Path, manifest: dict[str, dict[str, str]]) -> None:
    """Record which document became which file, in which format, through which parser.

    The corpus is derived, so the derivation has to be legible: this is what lets
    `tools/build_ingested_cases.py` find a judged document's twin, and what lets a
    reader check that the format assignment is the rotation this file claims
    rather than one chosen after seeing a result.
    """
    import json

    path = corpus / "provenance.json"
    body = json.dumps(dict(sorted(manifest.items())), indent=2, sort_keys=True)
    path.write_text(body + "\n", encoding="utf-8", newline="\n")


def check(corpus: Path) -> int:
    """Re-ingest the committed sources into a temporary tree, and diff the result.

    No renderer runs here — the sources are the fixed input — so a difference is
    always a change in ingestion: a parser, the projector, or the fidelity budget.
    """
    committed = corpus / KNOWLEDGE / EVIDENCE_DIRNAME
    with tempfile.TemporaryDirectory() as temporary:
        scratch = Path(temporary) / "uv-docs-ingested"
        scratch.mkdir()
        # The committed sources are copied in rather than read in place: the
        # connector writes a URI relative to the corpus root (BUG-0017), so a
        # comparison across two different roots would differ in every frontmatter
        # block and prove nothing.
        shutil.copytree(corpus / "sources", scratch / "sources")
        if build(scratch, sources=scratch / "sources"):
            print("re-ingestion failed; see above")
            return 1
        rebuilt = scratch / KNOWLEDGE / EVIDENCE_DIRNAME
        names = sorted(
            {path.name for path in committed.glob("*.md")}
            | {path.name for path in rebuilt.glob("*.md")}
        )
        drift = [
            name
            for name in names
            if not (committed / name).exists()
            or not (rebuilt / name).exists()
            or not filecmp.cmp(committed / name, rebuilt / name, shallow=False)
        ]
    if drift:
        print(f"{len(drift)} of {len(names)} evidence documents differ from a fresh ingestion:")
        for name in drift[:20]:
            print(f"  {name}")
        print(
            "\nIngestion changed what it projects. Re-run "
            "`python tools/build_ingested_corpus.py` and review the diff — it is the "
            "change, and it belongs in the PR. If the judged anchors moved with it, "
            "`python tools/build_ingested_cases.py` carries them across again."
        )
        return 1
    print(f"{len(names)} evidence documents match a fresh ingestion of the committed sources")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare, do not write.")
    parser.add_argument(
        "--render",
        action="store_true",
        help="Re-render sources/ from the Markdown corpus. A provenance act, not a refresh.",
    )
    args = parser.parse_args()

    sources = CORPUS / "sources"
    if args.render:
        if shutil.which("pandoc") is None:
            print("pandoc is not installed; the sources are rendered with it")
            return 1
        if not (SOURCE_CORPUS / "docs").is_dir():
            print(f"the corpus this one mirrors is missing: {SOURCE_CORPUS / 'docs'}")
            return 1
        # The order is recorded *before* anything is rendered, so a run that
        # fails halfway leaves the record of what was claimed rather than a plan
        # nobody can reconstruct.
        write_rotation(rotation_of())
        rendered = render_sources(sources)
        plan = assignment()
        counts = {fmt: sum(1 for value in plan.values() if value == fmt) for fmt in FORMATS}
        if rendered:
            print(f"rendered {len(rendered)} document(s): {', '.join(rendered)}")
        else:
            print("nothing to render; every document already has its assigned format")
        print(f"assignment now {counts}")

    if not sources.is_dir():
        print(f"no sources at {sources}; run with --render first")
        return 1
    if args.check:
        return check(CORPUS)

    failures = build(CORPUS, sources=sources)
    written = sorted((CORPUS / KNOWLEDGE / EVIDENCE_DIRNAME).glob("*.md"))
    print(f"projected {len(written)} evidence documents from {sources.name}/")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
