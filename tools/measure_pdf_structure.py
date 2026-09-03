#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Re-run the evidence behind ADR-0040: what docling's ML pipeline would buy for PDF.

    pip install docling                       # ~1 GB of packages, torch included
    python -m docling.utils.model_downloader  # ~1.4 GB of weights, into ./docling-models
    python tools/measure_pdf_structure.py --artifacts docling-models

(If that module is not runnable in your docling version, `download_models(output_dir=...)`
from `docling.utils.model_downloader` is the same thing with the path spelled out.)

v1 reads a PDF's text layer and nothing else (ADR-0032): characters, page numbers,
no headings, no tables. The structure lives in docling's ML pipeline, and roadmap
4.9 asked whether to ship it. The answer was no, and this is the harness the answer
rests on — kept runnable, because every reason to say no is a *measurement*, and a
measurement that cannot be repeated is an opinion with a date on it.

It reports four things, over the PDF documents of `eval/corpora/uv-docs-ingested`
— a corpus whose Markdown originals are right next door, so the true structure of
every document is known rather than guessed (roadmap 4.10):

1. **Structure recovered** — headings and code blocks found, against the Markdown
   twin's own count, against the text layer's zero.
2. **Cost** — seconds per page, after the one-time model load.
3. **Determinism** — the same document converted twice by two fresh converters.
   Same machine and same versions only: that is necessary, not sufficient, and it
   is why a shipped parser would still have to declare `deterministic = False`
   (the rule ADR-0017 set for the embedder).
4. **Retrieval** — the frozen judgements carried onto an ML-parsed corpus and
   scored against the text-layer arm *and* the Markdown control. The control is
   what makes the comparison readable: the text-layer arm's numbers are inflated
   by a target ten times too big (ADR-0039), so "worse than the text layer" and
   "worse than Markdown" are different claims and only the second one counts.

Nothing here writes into the repository. The variant corpus is built in a
temporary directory and thrown away.
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.build import build  # noqa: E402
from mycelium.chunking import estimate_tokens  # noqa: E402
from mycelium.eval.cases import load_cases, write_cases  # noqa: E402
from mycelium.eval.harness import run_evaluation  # noqa: E402
from mycelium.ingest.parsers.builder import KirBuilder  # noqa: E402
from mycelium.ingest.projection import project  # noqa: E402
from mycelium.markdown.adapter import parse_markdown  # noqa: E402
from mycelium.sdk.identity import digest_bytes  # noqa: E402
from mycelium.sdk.types import (  # noqa: E402
    EvalCase,
    KirDocument,
    NodeKind,
    RelevantAnchor,
)
from mycelium.store import SqliteStore  # noqa: E402

CORPUS = ROOT / "eval" / "corpora" / "uv-docs-ingested"
TWIN = ROOT / "eval" / "corpora" / "uv-docs"
DOC_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"
MIN_COVERAGE = 0.5
_TOKEN = re.compile(r"[A-Za-z0-9_]+")
METRICS = (
    ("nDCG@10", "ndcg_at_10"),
    ("MRR", "mrr"),
    ("R@10", "recall_at_10"),
    ("R@50", "recall_at_50"),
)


def converter(artifacts: Path, *, ocr: bool = False):  # type: ignore[no-untyped-def]
    """Build docling's PDF pipeline, pinned offline and with OCR off.

    `do_ocr=False` is not a tuning choice. Out of the box — no `artifacts_path` —
    converting a PDF fetches OCR weights from `modelscope.cn` at conversion time,
    and `HF_HUB_OFFLINE=1` does **not** stop it: that downloader is a transitive
    dependency's own, and it does not read HuggingFace's switch. Pre-fetched
    artifacts make the whole pipeline silent, which is the only way the offline
    posture D-017 requires can be had here — by us having fetched everything, not
    by the library honouring a flag.
    """
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions(artifacts_path=artifacts)
    options.do_ocr = ocr
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )


def kir_of(document: object, data: bytes) -> KirDocument:
    """Map a `DoclingDocument` into KIR with the adapter that already ships.

    The mapping is not new work: the docling adapter written at 4.1 for DOCX and
    HTML consumes a `DoclingDocument`, and the ML pipeline produces the same type.
    That is worth knowing on its own — the cost of this feature is the engine, not
    the adapter.
    """
    from mycelium.ingest.parsers.docling import _item, _Nesting

    builder, state = KirBuilder(), _Nesting()
    for ref in document.body.children or ():  # type: ignore[attr-defined]
        _item(builder, ref.resolve(document), document, state, parent=None)
    return KirDocument(
        doc_id=DOC_ID,
        source_digest=digest_bytes(data),
        nodes=tuple(builder.nodes),
        warnings=tuple(builder.warnings),
    )


def truth_of(markdown: Path) -> tuple[int, int]:
    """The document's real structure, from the Markdown it was rendered from.

    Counted through the Markdown adapter rather than with a regular expression: a
    `# comment` line inside a shell fence looks exactly like a heading, and this
    corpus is full of them — a naive count reported 36 headings for a document
    that has 12.
    """
    kir = parse_markdown(markdown.read_text(encoding="utf-8")).kir
    headings = sum(1 for node in kir.nodes if node.kind is NodeKind.HEADING)
    code = sum(1 for node in kir.nodes if node.kind is NodeKind.CODE_BLOCK)
    return headings, code


def pdf_entries() -> dict[str, dict[str, str]]:
    manifest = json.loads((CORPUS / "provenance.json").read_text(encoding="utf-8"))
    return {name: entry for name, entry in manifest.items() if entry["format"] == "pdf"}


# ---------------------------------------------------------------------------
# 1-3: structure, cost, determinism
# ---------------------------------------------------------------------------


def measure_conversion(artifacts: Path) -> dict[str, KirDocument]:
    convert = converter(artifacts)
    entries = pdf_entries()
    parsed: dict[str, KirDocument] = {}
    totals = [0, 0, 0, 0]
    print(f"\n{'document':38} {'pages':>5} {'s/page':>7} {'headings':>16} {'code':>12}")
    print(f"{'':38} {'':>5} {'':>7} {'ML  md  text':>16} {'ML  md':>12}")
    print("-" * 82)
    for name, entry in sorted(entries.items()):
        source = CORPUS / entry["source"]
        data = source.read_bytes()
        start = time.time()
        result = convert.convert(str(source))
        elapsed = time.time() - start
        kir = kir_of(result.document, data)
        parsed[name] = kir

        pages = max(1, len(result.document.pages))
        headings = sum(1 for node in kir.nodes if node.kind is NodeKind.HEADING)
        code = sum(1 for node in kir.nodes if node.kind is NodeKind.CODE_BLOCK)
        true_headings, true_code = truth_of(TWIN / name)
        totals[0] += headings
        totals[1] += true_headings
        totals[2] += code
        totals[3] += true_code
        label = name.removeprefix("docs/")
        print(
            f"{label:38} {pages:5} {elapsed / pages:7.1f} "
            f"{headings:5}{true_headings:4}{0:5}   {code:6}{true_code:5}"
        )
    print("-" * 82)
    print(
        f"{'total':38} {'':>5} {'':>7} {totals[0]:5}{totals[1]:4}{0:5}   {totals[2]:6}{totals[3]:5}"
    )
    print(
        f"\nheadings recovered: {totals[0]}/{totals[1]} "
        f"({totals[0] / max(1, totals[1]):.0%}); code blocks: {totals[2]}/{totals[3]} "
        f"({totals[2] / max(1, totals[3]):.0%}); the text layer recovers none of either."
    )
    return parsed


def measure_determinism(artifacts: Path, parsed: dict[str, KirDocument]) -> None:
    name, first = next(iter(sorted(parsed.items())))
    entry = pdf_entries()[name]
    data = (CORPUS / entry["source"]).read_bytes()
    again = kir_of(converter(artifacts).convert(str(CORPUS / entry["source"])).document, data)
    digests = [
        hashlib.sha256(document.model_dump_json().encode("utf-8")).hexdigest()[:16]
        for document in (first, again)
    ]
    verdict = "identical" if digests[0] == digests[1] else "DIFFERENT"
    print(
        f"\ndeterminism: {name.removeprefix('docs/')} converted twice by two fresh "
        f"converters -> {verdict} ({digests[0]}, {digests[1]})."
    )
    print(
        "  Same machine, same versions. That is necessary and not sufficient: a claim of "
        "reproducibility\n  that holds only where it was measured is not reproducibility "
        "(ADR-0017), so a shipped parser\n  would still declare `deterministic = False` and "
        "stay out of the G6 golden."
    )


# ---------------------------------------------------------------------------
# 4: retrieval, against the text-layer arm and the Markdown control
# ---------------------------------------------------------------------------


def tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def chunks_of_path(store: SqliteStore, doc_path: str) -> tuple[object, ...]:
    document = store.get_document_by_path(doc_path)
    return () if document is None else store.chunks_of(document.doc_id)


def judged_text(store: SqliteStore, anchor: str) -> str:
    if not anchor.endswith("/"):
        chunk = store.get_chunk(anchor)
        return chunk.text if chunk is not None else ""
    doc_path, _, prefix = anchor.partition("#")
    return "\n".join(
        chunk.text  # type: ignore[attr-defined]
        for chunk in chunks_of_path(store, doc_path)
        if chunk.anchor.partition("#")[2].startswith(prefix)  # type: ignore[attr-defined]
    )


def write_variant(destination: Path, parsed: dict[str, KirDocument]) -> dict[str, str]:
    """A copy of the ingested corpus whose PDF documents were parsed by the ML pipeline."""
    shutil.copytree(CORPUS, destination, ignore=shutil.ignore_patterns(".mycelium"))
    manifest = json.loads((destination / "provenance.json").read_text(encoding="utf-8"))
    replaced: dict[str, str] = {}
    for name, kir in parsed.items():
        entry = manifest[name]
        data = (destination / entry["source"]).read_bytes()
        projection = project(
            kir,
            source_uri=f"file:{entry['source']}",
            source_digest=digest_bytes(data),
            knowledge_dir="knowledge",
        )
        (destination / entry["evidence"]).unlink()
        (destination / projection.path).write_text(projection.text, encoding="utf-8", newline="\n")
        entry["evidence"] = projection.path.as_posix()
        entry["parser"] = "docling-layout"
        replaced[name] = entry["evidence"]
    (destination / "provenance.json").write_text(
        json.dumps(dict(sorted(manifest.items())), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return replaced


def carry(destination: Path, manifest: dict[str, dict[str, str]]) -> None:
    """Carry the frozen judgements onto the variant, exactly as roadmap 4.10 does."""
    with (
        SqliteStore.open(TWIN, read_only=True) as source_store,
        SqliteStore.open(destination, read_only=True) as twin_store,
    ):
        for name in ("dev", "release"):
            carried: list[EvalCase] = []
            for case in load_cases(TWIN / "eval" / f"{name}.jsonl"):
                anchors: list[RelevantAnchor] = []
                for relevant in case.relevant:
                    entry = manifest.get(relevant.anchor.partition("#")[0])
                    if entry is None:
                        continue
                    wanted = tokens(judged_text(source_store, relevant.anchor))
                    best, score = None, 0.0
                    for chunk in chunks_of_path(twin_store, entry["evidence"]):
                        found = len(wanted & tokens(chunk.text)) / len(wanted) if wanted else 0.0  # type: ignore[attr-defined]
                        if found > score:
                            best, score = chunk.anchor, found  # type: ignore[attr-defined]
                    if best is not None and score >= MIN_COVERAGE:
                        anchors.append(RelevantAnchor(anchor=best, grade=relevant.grade))
                if case.answerable and not anchors:
                    continue
                carried.append(case.model_copy(update={"relevant": tuple(anchors)}))
            write_cases(destination / "eval" / f"{name}.jsonl", tuple(carried))


def pdf_only(cases: Sequence[EvalCase], documents: set[str]) -> tuple[EvalCase, ...]:
    return tuple(
        case
        for case in cases
        if case.relevant
        and all(item.anchor.partition("#")[0] in documents for item in case.relevant)
    )


def target_size(corpus: Path, cases: Sequence[EvalCase]) -> float:
    with SqliteStore.open(corpus, read_only=True) as store:
        sizes = [
            estimate_tokens(chunk.text)
            for case in cases
            for item in case.relevant
            if (chunk := store.get_chunk(item.anchor)) is not None
        ]
    return sum(sizes) / len(sizes) if sizes else 0.0


def measure_retrieval(destination: Path, parsed: dict[str, KirDocument]) -> None:
    replaced = write_variant(destination, parsed)
    manifest = json.loads((destination / "provenance.json").read_text(encoding="utf-8"))
    build(TWIN, pin_identity=False)  # a committed corpus (ADR-0046)
    build(destination)
    carry(destination, manifest)
    build(destination)

    base_manifest = pdf_entries()
    arms = (
        ("markdown", TWIN, set(base_manifest)),
        ("text layer", CORPUS, {entry["evidence"] for entry in base_manifest.values()}),
        ("ML layout", destination, set(replaced.values())),
    )
    for case_set in ("release", "dev"):
        selections = {
            label: pdf_only(load_cases(corpus / "eval" / f"{case_set}.jsonl"), documents)
            for label, corpus, documents in arms
        }
        shared = set.intersection(*({case.case_id for case in c} for c in selections.values()))
        if not shared:
            print(f"\n{case_set}: no case is answered by a PDF-rendered document in all arms")
            continue
        print(f"\n{case_set}: {len(shared)} cases whose answer is in a PDF-rendered document")
        header = f"  {'arm':<12}" + "".join(f"{name:>9}" for name, _ in METRICS) + f"{'target':>9}"
        print(header)
        for label, corpus, _ in arms:
            cases = tuple(c for c in selections[label] if c.case_id in shared)
            summary = run_evaluation(corpus, cases, case_set=f"{case_set}.jsonl").overall
            cells = "".join(f"{getattr(summary, field):9.3f}" for _, field in METRICS)
            print(f"  {label:<12}{cells}{target_size(corpus, cases):9.0f}")
        print(
            "  The Markdown row is the control. The text layer's numbers carry a target ten "
            "times\n  too big (ADR-0039), so only the distance to *Markdown* is a claim about "
            "structure."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifacts",
        type=Path,
        required=True,
        help="Directory holding docling's pre-fetched models. Nothing is downloaded.",
    )
    parser.add_argument("--skip-retrieval", action="store_true")
    args = parser.parse_args()

    try:
        import docling  # noqa: F401
    except ImportError:
        print(
            "this harness needs docling's ML pipeline: `pip install docling` "
            "(~1 GB of packages, and 1.4 GB of weights to fetch afterwards)"
        )
        return 1
    if not args.artifacts.is_dir():
        print(f"{args.artifacts} does not exist; fetch the models first — see the module docstring")
        return 1
    if not (CORPUS / "provenance.json").is_file():
        print(f"the ingested corpus is missing: {CORPUS}")
        return 1

    parsed = measure_conversion(args.artifacts)
    measure_determinism(args.artifacts, parsed)
    if not args.skip_retrieval:
        with tempfile.TemporaryDirectory() as temporary:
            measure_retrieval(Path(temporary) / "ml-layout", parsed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
