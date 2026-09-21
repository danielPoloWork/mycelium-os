#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Should one document be allowed half the slots a search returns? (roadmap 6.29)

    python tools/measure_document_diversity.py                 # every arm, every set
    python tools/measure_document_diversity.py --concentration  # the statistic itself
    python tools/measure_document_diversity.py --oracle          # the ceilings, and the headroom
    python tools/measure_document_diversity.py --check           # the shipped ranking is the
                                                                 # one this measurement supports

Roadmap 6.22 measured the agent-task suite and found that across twenty-two tasks
the top ten spans a mean of **5.8 distinct documents**, and that on ten of them a
single document takes half the slots or more. That is not a defect on its face -
returning six chunks of the ADR that answers the question is precisely what
should happen - but nobody had ever measured the alternative, so the behaviour
was an accident of RRF rather than a decision. This runner is the measurement
that turns it into one, on the judged sets, where a ranking change belongs.

## The two families, and why they are the only two

A search returns `DEPTH` chunks out of a fused pool `VECTOR_CANDIDATES` deep.
Anything that spends fewer slots on one document must either **refuse** slots or
**discount** them:

- **cap `n`** - a document contributes at most `n` chunks; freed slots are filled
  by the next candidates from other documents. A hard refusal.
- **decay `lambda`** - greedy re-ranking in which a document's j-th selected
  chunk is scored `rrf * lambda ** j`. A soft discount, and the shape spec 04 §5
  already uses for the graph leg.

`cap 1` and `lambda -> 0` are the same policy (round robin over documents); `cap
>= DEPTH` and `lambda = 1` are both the shipped ranking. Every other diversity
rule worth the name interpolates between those ends, so measuring both families
across their range measures the family of policies, not two guesses.

## RRF leaves no room in the middle, and the arithmetic says so before the data

With one leg, a candidate at pool rank `r` scores `1 / (RRF_K + r)`. Across a
pool `VECTOR_CANDIDATES` deep that is a total spread of

    (RRF_K + VECTOR_CANDIDATES) / (RRF_K + 1) = 110 / 61 = 1.80x

between the best and the worst candidate in the whole pool. So a multiplicative
discount is either **inert** or **total**: below `61/110 = 0.55` it pushes a
document's second chunk beneath *every* other candidate, which is round robin;
near 1.0 it changes nothing. There is no operating point in between waiting to be
tuned - which is ADR-0075's finding about the graph discount, reached again by a
different mechanism, and the reason this file reports a *curve* rather than
searching for a constant.

## The bar

The one this project applies to every ranking change (ADR-0070, ADR-0080): an
arm earns the default only with a gain on a **release** set - the judgements it
was not developed against - **no overall regression on any set**, and no slice
worse than gate G3's -2 % anywhere. A gain confined to the dev sets is reported
as *proposable* and ships as nothing.

## The ceilings are measured before any heuristic is tuned

`--oracle` reports three upper bounds no policy can pass:

- **best cap per case** and **best decay per case** - the arm chosen with
  hindsight, per query. No fixed policy can reach it, so it is the ceiling of
  its whole family;
- **the pool re-ranked perfectly** - the 50 candidates ordered by their judged
  grade. It is the headroom that exists at depth 10 *at all*, and it is the
  number that says whether document concentration is where the loss is.

Reading the ceiling first is the discipline ADR-0094 set: a heuristic tuned
before its ceiling is known is tuned against an unknown denominator.

**`--check` fails when an arm earns the default and nothing ships it** - never on
an arm losing, which is the recorded outcome. Its job is to notice the day a
change elsewhere in the ranking makes this decision worth re-opening.
"""

import argparse
import statistics
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Final

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.eval.cases import load_cases  # noqa: E402
from mycelium.eval.metrics import credit_judgments, ndcg_at_k  # noqa: E402
from mycelium.retrieval import RRF_K, VECTOR_CANDIDATES, search  # noqa: E402
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

CAPS: Final = (1, 2, 3, 4, 5)
"""The whole usable range: `cap >= DEPTH` is the shipped ranking by definition."""

DECAYS: Final = (0.5, 0.7, 0.8, 0.9, 0.95)
"""Spanning the band the RRF spread leaves: below ~0.55 every decay is round
robin, and at 1.0 every decay is the shipped ranking."""

SLICE_FLOOR: Final = -0.02
"""Gate G3's condition, applied to an arm rather than to a release (spec 04 §7.3)."""

#: The spread between the best and the worst candidate in a one-leg pool. Stated
#: here because it is what makes the decay family's range what it is.
RRF_SPREAD: Final = (RRF_K + VECTOR_CANDIDATES) / (RRF_K + 1)

Pool = list[tuple[str, float]]
"""One case's fused candidates, best first, with their RRF scores."""

Rerank = Callable[[Pool], list[str]]
"""An arm: a pool in, the `DEPTH` anchors it would serve out."""


def document_of(anchor: str) -> str:
    """The document an anchor names. `path#heading/index` -> `path`."""
    return anchor.split("#")[0]


def cap_arm(pool: Pool, cap: int, depth: int = DEPTH) -> list[str]:
    """At most `cap` chunks per document; freed slots fall to the next document."""
    taken: Counter[str] = Counter()
    kept: list[str] = []
    for anchor, _ in pool:
        document = document_of(anchor)
        if taken[document] >= cap:
            continue
        taken[document] += 1
        kept.append(anchor)
        if len(kept) == depth:
            break
    return kept


def decay_arm(pool: Pool, decay: float, depth: int = DEPTH) -> list[str]:
    """Greedy: the best remaining after discounting by what its document already took.

    Greedy rather than "multiply then sort", because the discount depends on what
    has been *selected*, not on where a chunk sat in the undiscounted order -
    sorting once would apply a penalty that the sort itself then invalidates.
    """
    remaining = list(pool)
    taken: Counter[str] = Counter()
    kept: list[str] = []
    while remaining and len(kept) < depth:
        best, best_value = 0, -1.0
        for index, (anchor, score) in enumerate(remaining):
            value = score * (decay ** taken[document_of(anchor)])
            if value > best_value:
                best, best_value = index, value
        anchor, _ = remaining.pop(best)
        taken[document_of(anchor)] += 1
        kept.append(anchor)
    return kept


def shipped_arm(pool: Pool, depth: int = DEPTH) -> list[str]:
    """The control: the fused order, untouched."""
    return [anchor for anchor, _ in pool[:depth]]


@dataclass(frozen=True, slots=True)
class Scores:
    """One arm on one case set."""

    overall: float
    per_slice: dict[str, float]
    per_case: dict[str, float]


def _fold(cases: Sequence[EvalCase], per_case: dict[str, float]) -> Scores:
    by_slice: dict[str, list[float]] = {}
    for case in cases:
        if case.case_id not in per_case:
            continue
        for name in case.slices:
            by_slice.setdefault(str(name), []).append(per_case[case.case_id])
    return Scores(
        overall=statistics.fmean(per_case.values()) if per_case else 0.0,
        per_slice={name: statistics.fmean(values) for name, values in sorted(by_slice.items())},
        per_case=per_case,
    )


def pools(store: SqliteStore, cases: Sequence[EvalCase]) -> dict[str, Pool]:
    """Every case's fused pool, once.

    The pool is the same for every arm - they differ only in which of it they
    serve - so the searches happen here and the arms are arithmetic on the
    result. Doing it per arm would multiply the only expensive step by eleven.
    """
    found: dict[str, Pool] = {}
    for case in cases:
        if not case.answerable:
            # Gate G4 owns the unanswerable slice; nDCG cannot speak about a case
            # with no judgments to rank (the blind spot every runner here declares).
            continue
        outcome = search(store, case.query, limit=VECTOR_CANDIDATES)
        found[case.case_id] = [(hit.hit.chunk.anchor, hit.score) for hit in outcome.hits]
    return found


def score(cases: Sequence[EvalCase], case_pools: dict[str, Pool], rerank: Rerank) -> Scores:
    per_case: dict[str, float] = {}
    for case in cases:
        pool = case_pools.get(case.case_id)
        if pool is None:
            continue
        judged = {anchor.anchor: anchor.grade for anchor in case.relevant}
        per_case[case.case_id] = ndcg_at_k(credit_judgments(rerank(pool), judged), judged, DEPTH)
    return _fold(cases, per_case)


def _relative(after: float, before: float) -> float:
    if before == 0:
        return 0.0 if after == 0 else 1.0
    return (after - before) / before


def _worst_slice(base: Scores, arm: Scores) -> tuple[str, float]:
    """The slice this arm treats worst, and by how much."""
    worst, delta = "", 0.0
    for name, before in base.per_slice.items():
        moved = _relative(arm.per_slice.get(name, 0.0), before)
        if moved < delta:
            worst, delta = name, moved
    return worst, delta


def _report(label: str, arm_name: str, base: Scores, arm: Scores) -> tuple[bool, float]:
    """One line per arm; returns whether it gained overall, and by how much."""
    overall = _relative(arm.overall, base.overall)
    moved = sum(
        1
        for case_id, value in base.per_case.items()
        if abs(arm.per_case.get(case_id, value) - value) > 1e-9
    )
    slice_name, slice_delta = _worst_slice(base, arm)
    worst = f"worst slice {slice_name} {slice_delta:+.1%}" if slice_name else "no slice moved"
    print(f"  {arm_name:<16} {arm.overall:.4f}  {overall:+.2%}  {moved:>3} case(s) moved   {worst}")
    return overall > 0.0, overall


def _concentration(label: str, cases: Sequence[EvalCase], case_pools: dict[str, Pool]) -> None:
    """The statistic 6.22 found on the agent tasks, taken on the judged sets.

    Reported before any arm, because an intervention's size is uninterpretable
    without the size of the thing it intervenes on - and because if the judged
    sets were *not* concentrated, the ablation below would be measuring nothing
    and saying so would be the finding.
    """
    distinct: list[int] = []
    largest: list[int] = []
    half = 0
    for case in cases:
        pool = case_pools.get(case.case_id)
        if not pool:
            continue
        top = shipped_arm(pool)
        counts = Counter(document_of(anchor) for anchor in top)
        distinct.append(len(counts))
        biggest = counts.most_common(1)[0][1]
        largest.append(biggest)
        if biggest >= len(top) / 2:
            half += 1
    if not distinct:
        return
    print(
        f"{label:<22} {len(distinct)} case(s): mean {statistics.fmean(distinct):.2f} distinct "
        f"document(s) in the top {DEPTH}, largest share mean "
        f"{statistics.fmean(largest):.2f} / max {max(largest)}, "
        f"{half} case(s) ({half / len(distinct):.0%}) where one document takes half the slots"
    )


def _oracle(label: str, cases: Sequence[EvalCase], case_pools: dict[str, Pool]) -> None:
    """The three ceilings, none of them reachable by a shipped policy."""
    base = score(cases, case_pools, shipped_arm)
    best_cap: list[float] = []
    best_decay: list[float] = []
    perfect: list[float] = []
    for case in cases:
        pool = case_pools.get(case.case_id)
        if pool is None:
            continue
        judged = {anchor.anchor: anchor.grade for anchor in case.relevant}

        def at(anchors: list[str], judged: dict[str, int] = judged) -> float:
            return ndcg_at_k(credit_judgments(anchors, judged), judged, DEPTH)

        control = at(shipped_arm(pool))
        best_cap.append(max([control, *(at(cap_arm(pool, cap)) for cap in CAPS)]))
        best_decay.append(max([control, *(at(decay_arm(pool, decay)) for decay in DECAYS)]))
        ordered = sorted((anchor for anchor, _ in pool), key=lambda a: -judged.get(a, 0))
        perfect.append(at(ordered[:DEPTH]))
    if not perfect:
        return
    mean = statistics.fmean
    print(f"{label:<22} control {base.overall:.4f}")
    for name, values, note in (
        ("best cap per case", best_cap, "ceiling of every fixed cap"),
        ("best decay per case", best_decay, "ceiling of every fixed decay"),
        ("pool re-ranked", perfect, f"all the headroom there is at depth {DEPTH}"),
    ):
        print(
            f"  {name:<22} {mean(values):.4f}  "
            f"{_relative(mean(values), base.overall):+.2%}   <- {note}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, help="One corpus, instead of all three.")
    parser.add_argument("--cases", nargs="*", help="Only these case ids.")
    parser.add_argument(
        "--concentration",
        action="store_true",
        help="Report how concentrated the top ten already is, and measure nothing else.",
    )
    parser.add_argument(
        "--oracle",
        action="store_true",
        help=(
            "Report the ceiling of each family - the arm chosen per case with hindsight - "
            "and the headroom a perfect re-ranking of the pool would reach."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when an arm earns the default and the shipped ranking does not carry it.",
    )
    args = parser.parse_args()

    corpora = [("corpus", args.root)] if args.root else list(CORPORA)
    if not (args.concentration or args.oracle):
        print(
            f"document diversity ablation: depth {DEPTH}, pool {VECTOR_CANDIDATES}, "
            f"RRF k={RRF_K} (spread {RRF_SPREAD:.2f}x, so a decay below "
            f"{1 / RRF_SPREAD:.2f} is round robin); caps {list(CAPS)}, decays {list(DECAYS)}"
            "\n(roadmap 6.29; spec 04 section section 3-4; ADR-0075, ADR-0094)\n"
        )

    arms: list[tuple[str, Rerank]] = [
        *((f"cap {cap}", partial(cap_arm, cap=cap)) for cap in CAPS),
        *((f"decay {decay}", partial(decay_arm, decay=decay)) for decay in DECAYS),
    ]

    gained_on_release: list[str] = []
    regressed: list[str] = []
    slice_failed: list[str] = []
    measured = 0
    for name, root in corpora:
        if not (root / STORE_DIRNAME / STORE_FILENAME).exists():
            print(f"{name}: not built; run `mycelium build {root}`")
            continue
        with SqliteStore.open(root, read_only=True) as store:
            for set_name in SETS:
                path = root / "eval" / f"{set_name}.jsonl"
                if not path.exists():
                    continue
                cases = [
                    case
                    for case in load_cases(path)
                    if case.answerable and (not args.cases or case.case_id in args.cases)
                ]
                if not cases:
                    continue
                label = f"{name}/{set_name}"
                case_pools = pools(store, cases)
                measured += 1

                if args.concentration:
                    _concentration(label, cases, case_pools)
                    continue
                if args.oracle:
                    _oracle(label, cases, case_pools)
                    continue

                # The control is the shipped fused order over the same pool - not
                # a second retriever, because every arm here differs from it only
                # in which of the pool it serves (ADR-0096's rule, one layer up).
                base = score(cases, case_pools, shipped_arm)
                print(f"{label:<22} control {base.overall:.4f}")
                for arm_name, rerank in arms:
                    arm = score(cases, case_pools, rerank)
                    gained, overall = _report(label, arm_name, base, arm)
                    key = f"{label} {arm_name}"
                    if gained and set_name == "release":
                        gained_on_release.append(key)
                    if overall < 0.0:
                        regressed.append(key)
                    if _worst_slice(base, arm)[1] < SLICE_FLOOR:
                        slice_failed.append(key)
                print()

    if not measured:
        print("nothing measured")
        return 1
    if args.concentration or args.oracle:
        return 0

    # An arm earns only if it gained on a release set and cost nothing anywhere:
    # the arms are named per set above, so the test is on the arm, across sets.
    earned = sorted(
        {
            key.split(" ", 1)[1]
            for key in gained_on_release
            if not any(
                other.endswith(key.split(" ", 1)[1]) for other in (*regressed, *slice_failed)
            )
        }
    )
    if earned:
        verdict = (
            f"{len(earned)} arm(s) earn the default: {', '.join(earned)} - a release-set "
            "gain with no set regressing and no slice past -2 %"
        )
    else:
        verdict = (
            "no arm earns the default: every cap and every decay either changes nothing "
            "or costs a release set, which is what the RRF spread above predicts"
        )
    print(f"verdict: {verdict}; the shipped ranking caps nothing (ADR-0144)")
    if args.check and earned:
        print(
            "\nAn arm now earns a default the shipped ranking does not carry. That is not a "
            "failure of this run - it is the signal that ADR-0144's refusal was measured "
            "under a ranking that has since changed. Re-read the table, then either ship the "
            "arm or record why the measurement no longer means what it says."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
