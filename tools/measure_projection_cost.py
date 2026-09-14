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

**Per case, last, and that is the row that changes how the table is read.** An
average over seven PDF cases can move because projection cost something or
because one case moved a long way, and the two call for opposite conclusions.
Roadmap 5.26 is the worked example: `u-1003` sat **+0.27 above its own source**
for three milestones — a twin case cannot be easier than the Markdown it was
projected from unless something is wrong — and nothing here said so, because
nothing here printed a case. A corpus repair later moved it and it read as a
*regression*. The per-case block prints every shared case, widest gap first, with
no threshold and no verdict: a case above its source is a question about the
corpus, not a number to act on.

**And a case is marked when its passage did not land whole.** The carry records
`whole` per anchor — the share of the judged passage's word occurrences the
chosen chunk actually holds (roadmap 5.31) — and a case marked `split` has at
least one anchor below 1.0, meaning part of what it is judged on is in a
neighbouring chunk that nothing credits. That is the first thing to check on a
large negative, because it is what `u-1004` turned out to be: 0.000 on the twin
against 0.387 on its source, from a page boundary that fell mid-section and left
the sentence answering the query in the chunk before (ADR-0102). It is a reading
aid and not a verdict — the largest *gain* in this table is also a split passage.

**The share carries the grade of the anchor it is on (`0.509@1`), and it has to.**
The mark is the *minimum* across a case's anchors, so on a case whose anchors are
graded differently it names the worst split and not necessarily the one that moved
the score. `u-1019` is the worked example and the reason this column now prints a
grade: its 0.509 is the lowest share of any scored case and sits on a grade-1
anchor that ranks **first on both corpora** — it cost nothing — while the whole of
its −0.314 is the grade-3 anchor at 0.836 falling from rank 2 to rank 10. Read the
grade before concluding anything from the share (roadmap 5.39, ADR-0109).

**And a case is marked when its twin chunk answers somebody else's question too.**
`shared` is how many distinct judged units landed on the chunk this case is judged
on (roadmap 5.33). A headingless PDF is one page-sized block where the Markdown
had sections, so four cases can end up judged on the same chunk: a retriever that
returns it has answered all four, where on the source each had its own passage to
find. That is what a large *positive* gap usually is — the twin being easier
because the projection lost a distinction — and it is the counterpart of `whole`,
which is what to check on a large negative (ADR-0104).

What this cannot tell you: whether the *difference* generalises. Twenty-five
cases across three formats is a handful per format, and the mapping rule is not
neutral — `build_ingested_cases.py` picks the twin chunk with the most word
overlap with the judged passage, which is mildly favourable to the ingested side.
Any reading of this table has to carry that sentence with it.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

sys.path.insert(0, str(ROOT / "tools"))

from build_ingested_cases import CARRY_RECEIPT  # noqa: E402

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


def per_case(root: Path, cases: Sequence[EvalCase], case_set: str) -> dict[str, float]:
    """Each case's own nDCG@10, so the pairing can be read case by case."""
    manifest = run_evaluation(root, cases, case_set=case_set)
    return {result.case_id: result.ndcg_at_10 for result in manifest.results}


def row(label: str, before: MetricSummary, after: MetricSummary, count: int) -> str:
    cells = []
    for _, field in METRICS:
        was, now = getattr(before, field), getattr(after, field)
        cells.append(f"{was:.3f}  {now:.3f}  {now - was:+.3f}")
    return f"{label:<14} {count:>3}   " + "   ".join(cells)


def shared_chunks() -> dict[str, int]:
    """Per source anchor, how many judged units share the twin chunk it landed on.

    Read from the committed receipt's `collapsed` block rather than recomputed,
    for the reason :func:`split_passages` is: this table and `eval/carry.json`
    must not be able to disagree. A receipt written before roadmap 5.33 has no
    such block and yields nothing, so the marks vanish rather than being invented.

    It is the first thing to check on a large *positive* gap, the way `whole` is
    on a large negative: a twin chunk that four judged units landed on answers all
    four, where their source passages had to be found separately (ADR-0104).
    """
    receipt = INGESTED_CORPUS / "eval" / CARRY_RECEIPT
    if not receipt.is_file():
        return {}
    collapsed = json.loads(receipt.read_text(encoding="utf-8")).get("collapsed", {})
    shared: dict[str, int] = {}
    for landed in collapsed.values():
        units = len({item["source"] for item in landed})
        for item in landed:
            shared[item["source"]] = max(shared.get(item["source"], 0), units)
    return shared


def split_passages() -> dict[str, float]:
    """Per source anchor, the `whole` the carry recorded — below 1.0 only.

    Read from the committed receipt rather than recomputed, so this table and
    `eval/carry.json` cannot disagree about which passages were split. An older
    receipt has no `whole` key and yields nothing, which is the right behaviour:
    the marks vanish rather than being invented (roadmap 5.31).
    """
    receipt = INGESTED_CORPUS / "eval" / CARRY_RECEIPT
    if not receipt.is_file():
        return {}
    anchors = json.loads(receipt.read_text(encoding="utf-8")).get("anchors", {})
    return {
        source: row["whole"]
        for source, row in anchors.items()
        if isinstance(row, dict) and row.get("whole", 1.0) < 1.0
    }


def _report_per_case(
    markdown: Sequence[EvalCase],
    ingested: Sequence[EvalCase],
    attribution: dict[str, str | None],
    case_set: str,
) -> None:
    """Every shared case, widest gap first — the row the averages average away.

    Printed without a threshold on purpose. A gap is evidence about the corpus,
    and which way it points depends on the case: an ingested score *below* its
    source is projection costing something, which is what this tool exists to
    measure, while an ingested score *above* its source is the twin being easier
    than the document it was made from, which is not a result but a defect
    somewhere upstream of the measurement (roadmap 5.26). Naming a cut-off would
    turn that reading into arithmetic, which is the fitted parameter this project
    has refused every time it has been offered.
    """
    was = per_case(MARKDOWN_CORPUS, markdown, case_set)
    now = per_case(INGESTED_CORPUS, ingested, case_set)
    rows = sorted(
        ((case_id, was[case_id], now[case_id]) for case_id in was if case_id in now),
        key=lambda item: (-abs(item[2] - item[1]), item[0]),
    )
    split = split_passages()
    # The share *and the grade of the anchor it is on*, because the two together
    # are the reading and either alone is not. A split on a grade-1 anchor that
    # ranks first on both corpora moves nothing — `u-1019` is the worked example,
    # and its 0.509 is the lowest share in the table while the anchor that
    # actually cost it 0.314 is the grade-3 one at 0.836 (roadmap 5.39,
    # ADR-0109). Still the minimum, so the worst split is the one shown; the
    # grade is what tells a reader whether to keep looking.
    lowest = {
        case.case_id: min(
            (
                (split[relevant.anchor], relevant.grade)
                for relevant in case.relevant
                if relevant.anchor in split
            ),
            default=(1.0, 0),
        )
        for case in markdown
    }
    shared = shared_chunks()
    sharing = {
        case.case_id: max(
            (shared[relevant.anchor] for relevant in case.relevant if relevant.anchor in shared),
            default=0,
        )
        for case in markdown
    }
    print("\nper case, widest gap first (nDCG@10):")
    print(
        f"  {'case':<9} {'format':<6} {'md':>6} {'ing':>6} {'delta':>7}  {'whole':>9} {'shared':>6}"
    )
    for case_id, before, after in rows:
        fmt = attribution.get(case_id) or "mixed"
        share, grade = lowest.get(case_id, (1.0, 0))
        mark = f"  {share:6.3f}@{grade}" if share < 1.0 else f"  {'':>9}"
        units = sharing.get(case_id, 0)
        with_others = f" {units:>6}" if units > 1 else f" {'':>6}"
        print(
            f"  {case_id:<9} {fmt:<6} {before:6.3f} {after:6.3f} "
            f"{after - before:+7.3f}{mark}{with_others}"
        )
    marked = [case_id for case_id, *_ in rows if lowest.get(case_id, (1.0, 0))[0] < 1.0]
    if marked:
        print(
            f"  `whole` < 1.0 on {len(marked)} case(s): part of what they are judged on is in a "
            "neighbouring twin chunk that nothing credits"
        )
        print(
            "  `@n` is the grade of the anchor the share is on, and it is half the reading: a "
            "split on a low-graded anchor that ranks anyway costs nothing (roadmap 5.39)"
        )
    collapsed = [case_id for case_id, *_ in rows if sharing.get(case_id, 0) > 1]
    if collapsed:
        print(
            f"  `shared` > 1 on {len(collapsed)} case(s): the twin chunk they are judged on also "
            "holds another judged unit, so it answers both where the source needed two passages"
        )
    above = [case_id for case_id, before, after in rows if after > before + 1e-9]
    if above:
        print(
            f"  {len(above)} case(s) score higher on the twin than on the Markdown they were "
            f"projected from: {', '.join(sorted(above))}"
        )
        print("  a twin cannot be easier than its source; read those cases (roadmap 5.26)")


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
    _report_per_case(markdown, ingested, attribution, args.case_set)

    mixed = sorted(case_id for case_id, value in attribution.items() if value is None)
    if mixed:
        print(f"\nnot attributed to one format: {', '.join(mixed)}")
    if excluded:
        print(f"excluded — no anchor survived the carry: {', '.join(excluded)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
