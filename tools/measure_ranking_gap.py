#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""A perfect re-ranking is worth +34 % to +91 %. Where does that live? (roadmap 6.37)

    python tools/measure_ranking_gap.py              # the decomposition, every set
    python tools/measure_ranking_gap.py --placement  # where the judged passages sit
    python tools/measure_ranking_gap.py --check      # the recorded shape still holds

Roadmap 6.29 read the ceiling before tuning the heuristic it was filed for
(ADR-0094's discipline) and found something larger than the heuristic: ordering
the **same 50 fused candidates** by their judged grade is worth **+36 % to +86 %**,
against single-digit percentages for every ranking change this project has
shipped or refused. ADR-0144 recorded the number and filed the shape of it as a
follow-up rather than guessing. This runner is that measurement.

It proposes nothing. Spec 06 §3 defers a learned/LLM reranker until *"deterministic
pipeline plateaus on frozen sets AND budget exists for the latency/cost"*, and the
first half of that trigger is exactly what a characterisation can establish
honestly or assume dishonestly. What is measured here is where the loss **is**, so
that whatever is proposed next is priced against the right denominator.

## The three questions, and the arithmetic that separates them

A judged passage that does not score at depth 10 failed in exactly one of three
places, and they want different fixes:

- **it is not in the pool at all** - candidate generation missed it, and no
  re-ranking can recover it. The lever is BM25, chunking, or the query terms;
- **it is in the pool, below the fold** - ranks 11-50. Fusion had it and put it
  out of reach. The lever is the ranking, or a deeper pool;
- **it is in the ten already served, in the wrong order** - nDCG's log discount
  means a grade-3 passage at rank 4 scores 0.43 of the same passage at rank 1.
  No new candidate is needed; the lever is ordering alone.

The runner separates them by re-ordering **perfectly** from progressively wider
slices of one pool and reading how much of the ceiling each slice buys:
`reorder 10` sees only the chunks already returned, `rerank 50` the shipped pool,
`rerank 200` a pool four times deeper than anything ships.

## One search per case, at `PROBE` depth

The lexical leg is generated `max(limit, VECTOR_CANDIDATES)` deep
(`retrieval.search`), so a single search at `PROBE` yields every slice above by
truncation, and the arms are arithmetic on it. The shipped profile is
lexical-only (ADR-0017), which is what makes the deep probe meaningful: the
vector leg is fixed at `VECTOR_CANDIDATES` and would not answer "is it deeper
than the pool?" at all.

Measurements are taken under the **shipped** configuration, because the question
is where the shipped ranking loses. The control therefore reproduces ADR-0144's
control exactly on the three frozen **release** sets, which is the check that this
file measures the same thing that file did.

## The oracle sorts by the grade the *credit rule* awards

A judgment may name a chunk or a whole section (ADR-0029), and `credit_judgments`
satisfies a section judgment with any chunk under it. An oracle that sorts by
`judged.get(anchor, 0)` therefore scores a chunk under a judged section as
worthless and sinks it, understating its own ceiling. Sorting by
:func:`credited_grade` is the same rule the metric scores with, and it is worth
between +0.0 and +3.5 points of ceiling on the four sets that carry section
judgments (3-4 % of judgments; the two ingested sets carry none).

**`--check` fails when re-ordering the served ten stops carrying the majority of
the ceiling** on a release set - the one claim that decides what the next item is
about. It is a floor, not a target: the day candidate generation becomes the
binding constraint instead, this characterisation is stale and the follow-up
should be re-read rather than re-derived.
"""

import argparse
import statistics
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.eval.cases import load_cases  # noqa: E402
from mycelium.eval.metrics import credit_judgments, ndcg_at_k, section_of  # noqa: E402
from mycelium.retrieval import VECTOR_CANDIDATES, search  # noqa: E402
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

PROBE: Final = 200
"""Four times the shipped pool. Deep enough to distinguish "fusion buried it" from
"the lexical leg never generated it", which is the whole point of probing past
`VECTOR_CANDIDATES`."""

MAJORITY: Final = 0.50
"""`--check`'s floor: the share of the ceiling that re-ordering the served ten must
still carry for the recorded conclusion to describe the product."""

Judged = dict[str, int]
"""A case's judgments: anchor (chunk or section) to grade."""


def credited_grade(anchor: str, judged: Judged) -> int:
    """The grade `credit_judgments` would award this anchor.

    A chunk judgment is matched first, a section judgment second - the same two
    tiers, in the same order, that the metric scores with.
    """
    if anchor in judged:
        return judged[anchor]
    return judged.get(section_of(anchor), 0)


def first_ranks(anchors: Sequence[str], judged: Judged) -> dict[str, int]:
    """Judgment to the 1-based rank at which the credit rule first satisfies it.

    Derived from `credit_judgments` rather than re-implemented, because *once* is
    load-bearing: a section split into twelve chunks satisfies its judgment at the
    first of them and the other eleven are neither rewarded nor punished.
    """
    credited = credit_judgments(anchors, judged)
    return {anchor: rank for rank, anchor in enumerate(credited, 1) if anchor in judged}


def scored(anchors: Sequence[str], judged: Judged) -> float:
    """nDCG@`DEPTH` of an ordering, scored the way every judged metric here is."""
    return ndcg_at_k(credit_judgments(anchors, judged), judged, DEPTH)


def perfect(anchors: Sequence[str], judged: Judged) -> float:
    """The best nDCG@`DEPTH` obtainable by re-ordering `anchors` and nothing else."""
    best = sorted(anchors, key=lambda anchor: -credited_grade(anchor, judged))
    return scored(best[:DEPTH], judged)


def judgments_of(case: EvalCase) -> Judged:
    return {anchor.anchor: anchor.grade for anchor in case.relevant}


def pools(store: SqliteStore, cases: Sequence[EvalCase]) -> dict[str, list[str]]:
    """Every case's candidate list, `PROBE` deep, once.

    One search per case; every slice this runner reports is a truncation of it.
    Unanswerable cases are skipped - gate G4 owns that slice, and nDCG cannot
    speak about a case with no judgments to rank.
    """
    found: dict[str, list[str]] = {}
    for case in cases:
        if not case.answerable or not case.relevant:
            continue
        outcome = search(store, case.query, limit=PROBE)
        found[case.case_id] = [hit.hit.chunk.anchor for hit in outcome.hits]
    return found


@dataclass(frozen=True, slots=True)
class Decomposition:
    """What each progressively wider slice of one pool buys, on one case set."""

    control: float
    reorder_ten: float
    rerank_pool: float
    rerank_deep: float

    @property
    def ceiling(self) -> float:
        """The headroom the shipped pool holds: control to a perfect re-ranking."""
        return self.rerank_pool - self.control

    @property
    def inside_share(self) -> float:
        """The share of that ceiling reachable without a single new candidate."""
        return (self.reorder_ten - self.control) / self.ceiling if self.ceiling > 0 else 0.0

    @property
    def deeper_share(self) -> float:
        """What a pool four times deeper adds, as a share of the shipped ceiling."""
        return (self.rerank_deep - self.rerank_pool) / self.ceiling if self.ceiling > 0 else 0.0


def decompose(cases: Sequence[EvalCase], case_pools: dict[str, list[str]]) -> Decomposition:
    control: list[float] = []
    ten: list[float] = []
    pool: list[float] = []
    deep: list[float] = []
    for case in cases:
        anchors = case_pools.get(case.case_id)
        if anchors is None:
            continue
        judged = judgments_of(case)
        control.append(scored(anchors[:DEPTH], judged))
        ten.append(perfect(anchors[:DEPTH], judged))
        pool.append(perfect(anchors[:VECTOR_CANDIDATES], judged))
        deep.append(perfect(anchors[:PROBE], judged))
    mean = statistics.fmean
    if not control:
        return Decomposition(0.0, 0.0, 0.0, 0.0)
    return Decomposition(mean(control), mean(ten), mean(pool), mean(deep))


@dataclass
class Placement:
    """Where a set's judged passages sit, by the slice of the pool that holds them."""

    served: int = 0
    below: int = 0
    deeper: int = 0
    absent: int = 0
    ranks: list[int] = field(default_factory=list)
    best_rank: list[int] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.served + self.below + self.deeper + self.absent

    @property
    def missed(self) -> list[int]:
        """The ranks of the judgments the ten did not reach - "rank 11, or rank 45?"."""
        return [rank for rank in self.ranks if rank > DEPTH]

    def record(self, rank: int | None) -> str:
        if rank is None:
            self.absent += 1
            return "absent"
        self.ranks.append(rank)
        if rank <= DEPTH:
            self.served += 1
            return "served"
        if rank <= VECTOR_CANDIDATES:
            self.below += 1
            return "below"
        self.deeper += 1
        return "deeper"

    def row(self) -> str:
        total = self.total or 1
        return (
            f"served {self.served / total:6.1%}  below-the-fold {self.below / total:6.1%}  "
            f"past-the-pool {self.deeper / total:6.1%}  absent {self.absent / total:6.1%}"
        )


def placements(
    cases: Sequence[EvalCase], case_pools: dict[str, list[str]]
) -> tuple[Placement, dict[str, Placement], dict[int, Placement]]:
    """Overall placement, and the same split by slice and by judged grade."""
    overall = Placement()
    by_slice: dict[str, Placement] = {}
    by_grade: dict[int, Placement] = {}
    for case in cases:
        anchors = case_pools.get(case.case_id)
        if anchors is None:
            continue
        judged = judgments_of(case)
        ranks = first_ranks(anchors, judged)
        top = max(judged.values())
        best = [
            ranks[a] for a, g in judged.items() if g == top and ranks.get(a, PROBE + 1) <= DEPTH
        ]
        if best:
            overall.best_rank.append(min(best))
        for anchor, grade in judged.items():
            rank = ranks.get(anchor)
            overall.record(rank)
            by_grade.setdefault(grade, Placement()).record(rank)
            for name in case.slices:
                by_slice.setdefault(str(name), Placement()).record(rank)
    return overall, by_slice, by_grade


def lengths(
    store: SqliteStore, cases: Sequence[EvalCase], case_pools: dict[str, list[str]]
) -> tuple[list[int], list[int]]:
    """Chunk counts of the documents holding served judgments, and missed ones.

    The item's third candidate for where the loss concentrates. A long document
    competes with itself - every one of its chunks is a candidate for the same
    query - so if the misses were concentrated in long documents, chunking rather
    than ranking would be the lever.
    """
    sizes: dict[str, int] = {}

    def size_of(anchor: str) -> int | None:
        path = anchor.split("#")[0]
        if path not in sizes:
            document = store.get_document_by_path(path)
            sizes[path] = 0 if document is None else len(store.chunks_of(document.doc_id))
        return sizes[path] or None

    served: list[int] = []
    missed: list[int] = []
    for case in cases:
        anchors = case_pools.get(case.case_id)
        if anchors is None:
            continue
        judged = judgments_of(case)
        ranks = first_ranks(anchors, judged)
        for anchor in judged:
            size = size_of(anchor)
            if size is None:
                continue
            rank = ranks.get(anchor)
            (served if rank is not None and rank <= DEPTH else missed).append(size)
    return served, missed


def _report(label: str, found: Decomposition) -> None:
    def rel(value: float) -> str:
        return f"{(value - found.control) / found.control:+.1%}" if found.control else "n/a"

    print(
        f"{label:<22} {found.control:.4f}  "
        f"reorder-10 {found.reorder_ten:.4f} {rel(found.reorder_ten):>7}  "
        f"rerank-50 {found.rerank_pool:.4f} {rel(found.rerank_pool):>7}  "
        f"rerank-{PROBE} {found.rerank_deep:.4f} {rel(found.rerank_deep):>7}"
    )
    print(
        f"{'':<22} of the pool's ceiling, {found.inside_share:.1%} is reachable inside the "
        f"ten already served; a {PROBE}-deep pool adds {found.deeper_share:+.1%}"
    )


def _report_placement(
    label: str,
    overall: Placement,
    by_slice: dict[str, Placement],
    by_grade: dict[int, Placement],
    sizes: tuple[list[int], list[int]],
) -> None:
    print(f"\n{label}  {overall.total} judgment(s)")
    print(f"  all              {overall.row()}")
    missed = overall.missed
    if missed:
        print(
            f"  a judgment the ten missed but the probe found sits at median rank "
            f"{statistics.median(missed):.0f} (mean {statistics.fmean(missed):.0f}, "
            f"deepest {max(missed)})"
        )
    if overall.best_rank:
        median = statistics.median(overall.best_rank)
        at_one = sum(1 for rank in overall.best_rank if rank == 1) / len(overall.best_rank)
        print(
            f"  the best-graded judgment, when served, sits at median rank {median:.0f}; "
            f"it is first on {at_one:.1%} of the cases that serve it"
        )
    served_sizes, missed_sizes = sizes
    if served_sizes and missed_sizes:
        print(
            f"  the document holding a judgment has a median "
            f"{statistics.median(served_sizes):.0f} chunk(s) when the ten serve it and "
            f"{statistics.median(missed_sizes):.0f} when they do not"
        )
    for grade in sorted(by_grade, reverse=True):
        print(f"  grade {grade}          {by_grade[grade].row()}")
    for name in sorted(by_slice):
        print(f"  {name:<16} {by_slice[name].row()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, help="Measure one corpus only.")
    parser.add_argument(
        "--placement", action="store_true", help="Where the judged passages sit in the pool."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when re-ordering the served ten stops carrying the majority of the ceiling.",
    )
    args = parser.parse_args()

    corpora = (("corpus", args.root),) if args.root else CORPORA
    measured = 0
    stale: list[str] = []
    for label, root in corpora:
        if not (root / STORE_DIRNAME / STORE_FILENAME).exists():
            print(f"{label:<22} no store; skipped (build it to measure this corpus)")
            continue
        with SqliteStore.open(root, read_only=True) as store:
            for set_name in SETS:
                path = root / "eval" / f"{set_name}.jsonl"
                if not path.exists():
                    continue
                cases = load_cases(path)
                case_pools = pools(store, cases)
                if not case_pools:
                    continue
                measured += 1
                name = f"{label}/{set_name}"
                if args.placement:
                    _report_placement(
                        name, *placements(cases, case_pools), lengths(store, cases, case_pools)
                    )
                    continue
                found = decompose(cases, case_pools)
                _report(name, found)
                if set_name == "release" and found.inside_share < MAJORITY:
                    stale.append(f"{name} {found.inside_share:.1%}")

    if not measured:
        print("nothing measured: no corpus in this tree carries a store and a case set")
        return 1
    if args.check and stale:
        print(
            "\nthe recorded shape no longer describes the product: re-ordering the ten "
            f"already served carries under {MAJORITY:.0%} of the ceiling on {', '.join(stale)}.\n"
            "roadmap 6.37 and ADR-0152 concluded the loss is ordering rather than candidate "
            "generation; that conclusion, and anything filed on it, should be re-read."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
