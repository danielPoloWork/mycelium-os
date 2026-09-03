#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""What projection costs: the same queries over Markdown and over its ingested twin.

    python tools/measure_projection_cost.py [--set release.jsonl]

The question roadmap 4.10 exists to answer — *is an evidence document projected
from a binary source as retrievable as the Markdown a human would have written?* —
is a paired one, and this is the pairing.

Both corpora hold the same 81 upstream documents. One holds them as the Markdown
their authors wrote; the other holds what came back out of `mycelium ingest`
after they were rendered into DOCX, HTML and PDF. The judgements are the same
frozen ones on both sides, carried across by
`tools/build_ingested_cases.py` — so the query, the grade and the slice are held
fixed and the *document* is the only thing that varies.

**Only cases present on both sides are scored.** Two anchors did not survive the
carry, and scoring 16 cases against 14 would make the difference an artefact of
which cases each side happened to have. The intersection is printed, and so is
what it excluded.

**Per format, too.** A case is attributed to a format when every anchor it
carries lands in a document of that format, using `provenance.json`. The three
formats lose different things — a PDF loses its headings entirely — so an
average over all three would hide the only interesting variation in the result.

What this cannot tell you: whether the *difference* generalises. 14 cases across
three formats is a handful per format, and the mapping rule is not neutral —
`build_ingested_cases.py` picks the twin chunk with the most word overlap with
the judged passage, which is mildly favourable to the ingested side. Any reading
of this table has to carry that sentence with it.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.build import build  # noqa: E402
from mycelium.chunking import estimate_tokens  # noqa: E402
from mycelium.eval.cases import load_cases  # noqa: E402
from mycelium.eval.harness import run_evaluation  # noqa: E402
from mycelium.sdk.types import EvalCase, MetricSummary  # noqa: E402
from mycelium.store import SqliteStore  # noqa: E402

MARKDOWN_CORPUS = ROOT / "eval" / "corpora" / "uv-docs"
INGESTED_CORPUS = ROOT / "eval" / "corpora" / "uv-docs-ingested"

METRICS = (
    ("nDCG@10", "ndcg_at_10"),
    ("MRR", "mrr"),
    ("R@10", "recall_at_10"),
    ("R@50", "recall_at_50"),
)


def formats_by_document() -> dict[str, str]:
    """Evidence document path → the source format it was projected from."""
    manifest = json.loads((INGESTED_CORPUS / "provenance.json").read_text(encoding="utf-8"))
    return {entry["evidence"]: entry["format"] for entry in manifest.values()}


def format_of(case: EvalCase, by_document: dict[str, str]) -> str | None:
    """The one format a case's anchors all live in, or ``None`` when they differ."""
    found = {by_document.get(relevant.anchor.partition("#")[0]) for relevant in case.relevant}
    if len(found) == 1:
        only = found.pop()
        return only
    return None


def score(root: Path, cases: Sequence[EvalCase], case_set: str) -> MetricSummary:
    return run_evaluation(root, cases, case_set=case_set).overall


def row(label: str, before: MetricSummary, after: MetricSummary, count: int) -> str:
    cells = []
    for _, field in METRICS:
        was, now = getattr(before, field), getattr(after, field)
        cells.append(f"{was:.3f}  {now:.3f}  {now - was:+.3f}")
    return f"{label:<14} {count:>3}   " + "   ".join(cells)


def _report_target_sizes(
    markdown: Sequence[EvalCase],
    ingested: Sequence[EvalCase],
    attribution: dict[str, str | None],
) -> None:
    """How big the judged passage is on each side — the confound, made visible.

    `build_ingested_cases.py` carries an anchor across by picking the twin chunk
    with the most word overlap. When the twin's chunks are larger, the carried
    target is larger too, and a larger target is easier to rank highly. So any
    ranking gain has to be read next to this table: if the ingested target is
    several times the size of the Markdown one, the gain is partly the size.
    """
    with (
        SqliteStore.open(MARKDOWN_CORPUS, read_only=True) as source_store,
        SqliteStore.open(INGESTED_CORPUS, read_only=True) as twin_store,
    ):

        def mean_tokens(cases: Sequence[EvalCase], store: SqliteStore, ids: set[str]) -> float:
            sizes = [
                estimate_tokens(chunk.text)
                for case in cases
                if case.case_id in ids
                for relevant in case.relevant
                if (chunk := store.get_chunk(relevant.anchor)) is not None
            ]
            return sum(sizes) / len(sizes) if sizes else 0.0

        print("\nmean tokens in the judged passage (the size of the target):")
        for fmt in ("docx", "html", "pdf"):
            ids = {case_id for case_id, value in attribution.items() if value == fmt}
            if not ids:
                continue
            was = mean_tokens(markdown, source_store, ids)
            now = mean_tokens(ingested, twin_store, ids)
            ratio = f"{now / was:.1f}x" if was else "n/a"
            print(f"  {fmt:<6} markdown {was:6.0f}   ingested {now:6.0f}   {ratio}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", dest="case_set", default="release.jsonl")
    args = parser.parse_args()

    markdown_cases = load_cases(MARKDOWN_CORPUS / "eval" / args.case_set)
    ingested_cases = load_cases(INGESTED_CORPUS / "eval" / args.case_set)
    shared = {case.case_id for case in markdown_cases} & {c.case_id for c in ingested_cases}
    excluded = sorted({case.case_id for case in markdown_cases} - shared)

    markdown = tuple(case for case in markdown_cases if case.case_id in shared)
    ingested = tuple(case for case in ingested_cases if case.case_id in shared)
    if not markdown:
        print("no cases in common; run tools/build_ingested_cases.py")
        return 1

    build(MARKDOWN_CORPUS, pin_identity=False)  # a committed corpus (ADR-0046)
    build(INGESTED_CORPUS, pin_identity=False)  # a committed corpus (ADR-0046)

    by_document = formats_by_document()
    attribution = {case.case_id: format_of(case, by_document) for case in ingested}

    header = f"{'slice/format':<14} {'n':>3}   " + "   ".join(f"{name:^21}" for name, _ in METRICS)
    print(f"\nthe same {len(markdown)} cases, twice: Markdown -> ingested\n")
    print(header)
    print(f"{'':<14} {'':>3}   " + "   ".join(f"{'md    ing    delta':^21}" for _ in METRICS))
    print("-" * len(header))
    print(
        row(
            "overall",
            score(MARKDOWN_CORPUS, markdown, args.case_set),
            score(INGESTED_CORPUS, ingested, args.case_set),
            len(markdown),
        )
    )

    for fmt in ("docx", "html", "pdf"):
        ids = {case_id for case_id, value in attribution.items() if value == fmt}
        subset_md = tuple(case for case in markdown if case.case_id in ids)
        subset_in = tuple(case for case in ingested if case.case_id in ids)
        if not subset_md:
            print(f"{fmt:<14}   0   (no case's anchors land in this format alone)")
            continue
        print(
            row(
                fmt,
                score(MARKDOWN_CORPUS, subset_md, args.case_set),
                score(INGESTED_CORPUS, subset_in, args.case_set),
                len(subset_md),
            )
        )

    _report_target_sizes(markdown, ingested, attribution)

    mixed = sorted(case_id for case_id, value in attribution.items() if value is None)
    if mixed:
        print(f"\nnot attributed to one format: {', '.join(mixed)}")
    if excluded:
        print(f"excluded — no anchor survived the carry: {', '.join(excluded)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
