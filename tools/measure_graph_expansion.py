#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Run spec 04 §5's ablation: does graph expansion earn the default? (roadmap 5.3)

    python tools/measure_graph_expansion.py              # every corpus, both sets
    python tools/measure_graph_expansion.py --cases r-0018
    python tools/measure_graph_expansion.py <corpus-root>
    python tools/measure_graph_expansion.py --check      # the shipped default is the
                                                         # one this measurement supports

**The gate, verbatim from spec 04 §5:** graph expansion ships enabled-by-default
only if the ablation shows **≥ +3 % nDCG@10 on the `relationship` slice with no
overall regression**; otherwise it stays an opt-in flag until it earns the
default. Two arms, one difference: `mycelium` is the shipped lexical ranking and
`graph` is that ranking with the expansion leg switched on. Nothing else differs
between them, which is the only way the number means what it says.

**Why this is a tool and not a `--gate` flag.** Gate G3 enforces "no slice
regressed" against a *blessed baseline*; this asks a different question — the
difference between two configurations measured in the same run, on the same
corpus, at the same moment — so a baseline cannot express it. It is the shape
gate G2 needed for the same reason (ADR-0068), minus G2's problem: expansion
needs no embedding model, so this runs anywhere, including CI, and it is
deterministic, so the numbers can be compared as numbers.

**`--check` fails on a disagreement between the code and the measurement, never
on the ablation's outcome.** "Stays opt-in" is a legitimate result — the
milestone goal says so in as many words — so a runner that exited non-zero on it
would be red on every correct build. What it refuses is
`[retrieval] graph_expansion` shipping *on* while the measurement says it has
not earned it, or shipping off while it has. That is a mistake someone can act
on; losing an ablation is not.

**What it deliberately does not print is latency.** Spec 04 §5 budgets the
expansion at 30 ms and `mycelium search --explain` reports it per query, which
is where a number that moves 10x between two runs of the same tree belongs
(the lesson `tools/measure_hybrid_gate.py` learned the hard way). Gate G5
measures the end-to-end budget where the product actually runs.
"""

import argparse
import statistics
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium import retrieval  # noqa: E402
from mycelium.config import RetrievalConfig  # noqa: E402
from mycelium.eval.cases import load_cases  # noqa: E402
from mycelium.eval.metrics import credit_judgments, ndcg_at_k  # noqa: E402
from mycelium.eval.retrievers import build_retriever, resolvable_anchors  # noqa: E402
from mycelium.retrieval import GRAPH_DISCOUNT, GRAPH_NODES, GRAPH_SEEDS  # noqa: E402
from mycelium.sdk.types import EvalCase  # noqa: E402
from mycelium.store import STORE_DIRNAME, STORE_FILENAME, SqliteStore  # noqa: E402

CORPORA: Final = (
    ("ours", ROOT),
    ("uv", ROOT / "eval" / "corpora" / "uv-docs"),
    ("uv-ingested", ROOT / "eval" / "corpora" / "uv-docs-ingested"),
)
SETS: Final = ("dev", "release")
DEPTH: Final = 10
"""The k every judged metric in this project is taken at."""

SLICE: Final = "relationship"
"""The slice the gate is stated on: the queries expansion exists to serve."""

SLICE_MIN: Final = 0.03
"""Spec 04 §5: ≥ +3 % nDCG@10 on the relationship slice."""


@dataclass(frozen=True, slots=True)
class Scores:
    """One retriever on one case set."""

    overall: float
    per_slice: dict[str, float]
    per_case: dict[str, float]


def _score(cases: Sequence[EvalCase], retriever: object, resolvable: set[str]) -> Scores:
    per_case: dict[str, float] = {}
    by_slice: dict[str, list[float]] = {}
    scored: list[float] = []
    for case in cases:
        if not case.answerable:
            # An unanswerable case has no judgments to rank, so nDCG cannot
            # speak about it; gate G4 owns that half and this ablation does not
            # pretend to (the blind spot `measure_ranking.py` also declares).
            continue
        judged = {anchor.anchor: anchor.grade for anchor in case.relevant}
        retrieved = retriever.search(case.query, DEPTH)  # type: ignore[attr-defined]
        value = ndcg_at_k(credit_judgments(retrieved, judged), judged, DEPTH)
        per_case[case.case_id] = value
        scored.append(value)
        for name in case.slices:
            by_slice.setdefault(str(name), []).append(value)
    return Scores(
        overall=statistics.fmean(scored) if scored else 0.0,
        per_slice={name: statistics.fmean(values) for name, values in sorted(by_slice.items())},
        per_case=per_case,
    )


def _relative(after: float, before: float) -> float:
    if before == 0:
        return 0.0 if after == 0 else 1.0
    return (after - before) / before


def _verdict(base: Scores, expanded: Scores) -> tuple[bool, str]:
    """Spec 04 §5's rule, and the sentence that says which half of it decided."""
    slice_delta = _relative(expanded.per_slice.get(SLICE, 0.0), base.per_slice.get(SLICE, 0.0))
    overall_delta = _relative(expanded.overall, base.overall)
    earns = slice_delta >= SLICE_MIN and overall_delta >= 0.0
    if earns:
        return True, f"{SLICE} {slice_delta:+.1%} (needs +3%), overall {overall_delta:+.1%}"
    reasons = []
    if slice_delta < SLICE_MIN:
        reasons.append(f"{SLICE} {slice_delta:+.1%} (needs +3%)")
    if overall_delta < 0.0:
        reasons.append(f"overall regressed {overall_delta:+.1%}")
    return False, "; ".join(reasons)


def _report(
    name: str, set_name: str, base: Scores, expanded: Scores, cases: Sequence[EvalCase]
) -> bool:
    earns, why = _verdict(base, expanded)
    label = f"{name}/{set_name}"
    print(
        f"{label:<20} lexical {base.overall:.4f}  expanded {expanded.overall:.4f}  "
        f"{'EARNS' if earns else 'no  '}  {why}"
    )
    for slice_name in sorted(set(base.per_slice) | set(expanded.per_slice)):
        before = base.per_slice.get(slice_name, 0.0)
        after = expanded.per_slice.get(slice_name, 0.0)
        if abs(after - before) < 1e-9:
            continue
        moved = [
            f"{case_id} {base.per_case[case_id]:.4f}->{expanded.per_case[case_id]:.4f}"
            for case in cases
            if (case_id := case.case_id) in expanded.per_case
            and slice_name in [str(s) for s in case.slices]
            and abs(expanded.per_case[case_id] - base.per_case[case_id]) > 1e-9
        ]
        print(
            f"    {slice_name:<14} {before:.4f} -> {after:.4f}  "
            f"{_relative(after, before):+.1%}   {', '.join(moved)}"
        )
    return earns


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, help="One corpus, instead of all three.")
    parser.add_argument("--cases", nargs="*", help="Only these case ids.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the shipped default disagrees with the measurement.",
    )
    parser.add_argument(
        "--discount",
        type=float,
        help=(
            "Override the discount for one run. It exists to *characterise* the "
            "mechanism - ADR-0075 reports the whole curve - not to find a value that "
            "passes: the shipped constant is derived from RRF's arithmetic, and "
            "picking the best of a sweep is the move this project has refused fifteen "
            "times."
        ),
    )
    parser.add_argument(
        "--nodes",
        type=int,
        help="Override the node budget for one run, for the same reason as --discount.",
    )
    args = parser.parse_args()

    corpora = [("corpus", args.root)] if args.root else list(CORPORA)
    discount = GRAPH_DISCOUNT
    if args.discount is not None:
        discount = args.discount
        retrieval.GRAPH_DISCOUNT = discount  # type: ignore[misc]
    nodes = GRAPH_NODES
    if args.nodes is not None:
        nodes = args.nodes
        retrieval.GRAPH_NODES = nodes  # type: ignore[misc]
    print(
        f"graph expansion ablation: seeds {GRAPH_SEEDS}, nodes {nodes}, "
        f"discount {discount} (spec 04 §5; ADR-0075)\n"
    )

    any_earns = False
    measured = 0
    for name, root in corpora:
        if not (root / STORE_DIRNAME / STORE_FILENAME).exists():
            print(f"{name}: not built; run `mycelium build {root}`")
            continue
        eval_dir = root / "eval"
        with SqliteStore.open(root, read_only=True) as store:
            resolvable = resolvable_anchors(store)
            base_retriever = build_retriever("mycelium", store)
            expanded_retriever = build_retriever("graph", store)
            for set_name in SETS:
                path = eval_dir / f"{set_name}.jsonl"
                if not path.exists():
                    continue
                cases = [
                    case
                    for case in load_cases(path)
                    if not args.cases or case.case_id in args.cases
                ]
                if not cases:
                    continue
                base = _score(cases, base_retriever, resolvable)
                expanded = _score(cases, expanded_retriever, resolvable)
                measured += 1
                any_earns |= _report(name, set_name, base, expanded, cases)

    if not measured:
        print("nothing measured")
        return 1

    shipped = RetrievalConfig().graph_expansion
    print(
        f"\nverdict: expansion {'earns' if any_earns else 'does not earn'} the default on "
        f"{'at least one' if any_earns else 'any'} set; "
        f"[retrieval] graph_expansion ships {'on' if shipped else 'off'}"
    )
    if args.check and shipped != any_earns:
        print(
            "\nThe shipped default and this measurement disagree. Spec 04 §5 decides the "
            "default from the ablation, so one of them is wrong: re-read the table above, "
            "and change either the flag in `RetrievalConfig` or the reason in ADR-0075."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
