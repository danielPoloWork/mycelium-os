#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""What spec 04 §4 asks the result set to do, and what the corpora can earn (roadmap 6.38)

    python tools/measure_result_rules.py               # the boost family, every set
    python tools/measure_result_rules.py --fields      # what a boost would have to read
    python tools/measure_result_rules.py --redundancy  # what dedupe and stitching would collapse
    python tools/measure_result_rules.py --check       # the shipped result set is the one
                                                       # this measurement supports

Spec 04 §4 describes five behaviours for the result set. One — diversity — was measured
across its whole family and **refused** (roadmap 6.29, ADR-0144), and the spec records the
refusal. Three others are described as though they ship and do not exist anywhere under
`src/`: boosts, near-duplicate collapse, and stitching. The fifth, packing, does exist.
Roadmap 6.35 found the gap while mapping §1's stage budgets onto the labels the query path
already times, and reported it rather than gating it. This runner is what decides each one,
because the alternative to measuring is deleting a sentence, and the spec is the record of
what was intended as much as of what shipped.

## A boost can only reorder a field that varies

Spec 04 §4 makes boosts **multiplicative on the fused rank score**. A multiplicative factor
applied to every candidate alike is order-preserving *exactly* — `b · s` sorts as `s` does
for any `b > 0` — so a boost over a field with one value in the corpus is not a weak effect
to be measured, it is no effect at all, by arithmetic. `--fields` reports the distinct
values of each field a §4 boost would read, and that is the whole decision for the ones
that turn out to be constant.

## Where the usable range is, before any arm is run

With one leg a candidate at pool rank `r` scores `1 / (RRF_K + r)`, so neighbours differ by
`(RRF_K + r + 1) / (RRF_K + r)` — about 1.6 % at the top of the pool. A boost `b` therefore
moves a candidate roughly `(b - 1) · (RRF_K + r)` ranks: at `r = 10`, **1.05 is ~3 ranks,
0.9 is ~8, 0.7 is ~30, and 0.5 clears the pool**. That is a real operating range, and it is
worth saying why it differs from ADR-0144's finding that RRF *"leaves no room in the
middle"*. There the discount applied to a document's second and third chunk — competing
against its own neighbours at nearly equal score — so it was inert or total. A boost over a
**class** of candidates moves that class against the whole 1.80x spread of the pool, which
is a band wide enough to tune in. Whether anything in it wins is a different question, and
the reason this file sweeps rather than picks.

## The bar

The one this project applies to every ranking change (ADR-0070, ADR-0080, ADR-0144): an arm
earns the default only with a gain on a **release** set — the judgements it was not
developed against — **no overall regression on any set**, and no slice worse than gate G3's
−2 % anywhere. A gain confined to the dev sets is *proposable* and ships as nothing.

Roadmap 6.37 priced this window: **58.4 %–72.1 % of the whole depth-10 ceiling is reachable
by re-ordering the ten already served** (ADR-0152), and a boost is exactly such a
re-ordering. So an arm here is measured against a real denominator rather than against
zero — the headroom it is competing for is known.

## Dedupe and stitching are one measurement

Both collapse result slots that carry content the caller already has: dedupe when two
chunks are near-identical, stitching when two are adjacent pieces of one section. Neither
can be scored by nDCG — collapsing a slot *removes* a judged anchor's chance to be credited,
so the metric punishes both on principle — so what `--redundancy` reports is the
**opportunity**: how often the shipped ten actually contains something either rule would
collapse. A rule with no occasions is decided by that alone.

**`--check` fails when a boost arm earns the default and nothing ships it** — never on an
arm losing, which is a recorded outcome. Its job is to notice the day a corpus or a ranking
change makes one of these decisions worth re-opening.
"""

import argparse
import random
import statistics
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
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

SLICE_FLOOR: Final = -0.02
"""Gate G3's condition, applied to an arm rather than to a release (spec 04 §7.3)."""


OVERLAP: Final = 0.8
"""What spec 04 §4's *"high lexical overlap"* is taken to mean: token-set Jaccard.

Deliberately generous. Refusing dedupe on exact-digest equality alone would be refusing a
narrower rule than the spec describes, so the looser half of its own test is measured too.
"""


def _jaccard(first: frozenset[str], second: frozenset[str]) -> float:
    union = first | second
    return len(first & second) / len(union) if union else 0.0


def ranks_moved(weight: float, rank: int = DEPTH) -> float:
    """Roughly how many ranks a multiplicative boost `weight` moves a candidate at `rank`.

    Neighbours in a one-leg pool differ by `(RRF_K + r + 1) / (RRF_K + r)`, so a factor
    `w` crosses about `|w - 1| * (RRF_K + r)` of them. Stated by the runner rather than
    only in this docstring, because it is what makes the swept range the range it is.
    """
    return abs(weight - 1.0) * (RRF_K + rank)


DEPTH_WEIGHTS: Final = (0.5, 0.7, 0.8, 0.9, 0.95, 1.05, 1.1, 1.25)
"""The heading-proximity family, swept **in both directions** (ADR-0080's discipline).

Below 1.0 the spec's stated intent: a chunk `d` headings deep is scored `w ** (d - 1)`, so
H1/H2 sections outrank deep fragments. Above 1.0 the opposite prior — deep fragments are
more specific and may answer better. 1.0 is the shipped ranking and is not swept.
"""


CONTROL_WEIGHT: Final = 0.9
"""The weight the permutation control is run at: mid-range, ~8 ranks of movement."""


@dataclass(frozen=True, slots=True)
class Candidate:
    """One fused candidate, with the fields a §4 boost would read."""

    anchor: str
    score: float
    depth: int
    digest: str
    tokens: frozenset[str]

    @property
    def section(self) -> str:
        """Document and heading path — the unit stitching would return whole."""
        document, _, path = self.anchor.partition("#")
        return f"{document}#{path.rsplit('/', 1)[0]}"

    @property
    def position(self) -> int:
        """The chunk's index within its section, or -1 when the anchor has none."""
        tail = self.anchor.rsplit("/", 1)[-1]
        return int(tail) if tail.isdigit() else -1


Pool = list[Candidate]


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
    """Every case's fused pool, once; the arms are arithmetic on it."""
    found: dict[str, Pool] = {}
    for case in cases:
        if not case.answerable or not case.relevant:
            continue
        outcome = search(store, case.query, limit=VECTOR_CANDIDATES)
        found[case.case_id] = [
            Candidate(
                anchor=hit.hit.chunk.anchor,
                score=hit.score,
                depth=len(hit.hit.chunk.heading_path),
                digest=hit.hit.chunk.chunk_digest,
                tokens=frozenset(hit.hit.chunk.text.lower().split()),
            )
            for hit in outcome.hits
        ]
    return found


def shipped_arm(pool: Pool) -> list[str]:
    return [candidate.anchor for candidate in pool[:DEPTH]]


def depth_arm(pool: Pool, weight: float, *, within: bool = False) -> list[str]:
    """Spec 04 §4's heading-proximity boost: `score * weight ** (depth - 1)`.

    A chunk with no heading path is its own section and is not penalised, which is why
    the exponent floors at zero rather than going negative.

    `within` confines the boost to the ten already served, so it may re-order them but
    never promote a candidate from below the fold. Spec 04 §4's boost is pool-wide and the
    default here is what the spec describes; the narrow variant is measured beside it
    because ADR-0152 established that 58-72 % of the reachable headroom lives in exactly
    that window, which makes "did the promotion or the re-ordering cost it?" a real
    question rather than a quibble.
    """
    window = pool[:DEPTH] if within else pool
    boosted = sorted(window, key=lambda c: -(c.score * weight ** max(c.depth - 1, 0)))
    return [candidate.anchor for candidate in boosted[:DEPTH]]


def shuffled_arm(pool: Pool, weight: float, seed: str) -> list[str]:
    """The permutation control: the same multipliers, dealt to the wrong candidates.

    Without it, "every heading arm loses" has two readings that want opposite follow-ups -
    heading depth is the wrong signal, or RRF's order is near-optimal and *any* perturbation
    of this size costs about this much. Shuffling the depths within a pool keeps the
    multiplier distribution exactly and destroys only the association with the candidate, so
    the difference between the two arms is what the signal is worth. Seeded by case id, so a
    re-run reproduces.
    """
    depths = [candidate.depth for candidate in pool]
    random.Random(seed).shuffle(depths)
    boosted = sorted(
        zip(pool, depths, strict=True),
        key=lambda pair: -(pair[0].score * weight ** max(pair[1] - 1, 0)),
    )
    return [candidate.anchor for candidate, _ in boosted[:DEPTH]]


def score(
    cases: Sequence[EvalCase],
    case_pools: dict[str, Pool],
    weight: float,
    *,
    shuffle: bool = False,
    within: bool = False,
) -> Scores:
    per_case: dict[str, float] = {}
    for case in cases:
        pool = case_pools.get(case.case_id)
        if pool is None:
            continue
        judged = {anchor.anchor: anchor.grade for anchor in case.relevant}
        if shuffle:
            served = shuffled_arm(pool, weight, case.case_id)
        elif weight == 1.0:
            served = shipped_arm(pool)
        else:
            served = depth_arm(pool, weight, within=within)
        per_case[case.case_id] = ndcg_at_k(credit_judgments(served, judged), judged, DEPTH)
    return _fold(cases, per_case)


def _relative(after: float, before: float) -> float:
    if before == 0:
        return 0.0 if after == 0 else 1.0
    return (after - before) / before


def _worst_slice(base: Scores, arm: Scores) -> tuple[str, float]:
    worst, delta = "", 0.0
    for name, before in base.per_slice.items():
        moved = _relative(arm.per_slice.get(name, 0.0), before)
        if moved < delta:
            worst, delta = name, moved
    return worst, delta


def _report_arm(label: str, base: Scores, arm: Scores) -> tuple[float, float]:
    """One line per arm; returns its overall move and its worst slice's move."""
    overall = _relative(arm.overall, base.overall)
    moved = sum(
        1
        for case_id, value in base.per_case.items()
        if abs(arm.per_case.get(case_id, value) - value) > 1e-9
    )
    name, delta = _worst_slice(base, arm)
    worst = f"worst slice {name} {delta:+.1%}" if name else "no slice moved"
    print(f"  {label:<16} {arm.overall:.4f}  {overall:+.2%}  {moved:>3} case(s) moved   {worst}")
    return overall, delta


@dataclass(frozen=True)
class Reading:
    """One arm on one set: its overall move and its worst slice's move."""

    set_name: str
    overall: float
    worst_slice: float

    @property
    def is_release(self) -> bool:
        return self.set_name.endswith("/release")


def earning_arms(readings: dict[str, list[Reading]]) -> list[str]:
    """The arms that clear the bar, read across **every** set together.

    The bar is the module docstring's, and it is a statement about an arm, not about a
    set: a gain on some release set, **no overall regression on any set**, and no slice
    worse than `SLICE_FLOOR` anywhere. Until roadmap 7.10 the check read each release set
    alone, so an arm gaining +0.23 % on this repository's own corpus while losing 19 % on
    each vendored one was reported as earning the default (BUG-0037).
    """
    earned: list[str] = []
    for arm, rows in readings.items():
        gains = [row for row in rows if row.is_release and row.overall > 0]
        if not gains:
            continue
        if any(row.overall < 0 for row in rows):
            continue
        if any(row.worst_slice < SLICE_FLOOR for row in rows):
            continue
        earned.append(arm + " " + ", ".join(f"{row.set_name} {row.overall:+.2%}" for row in gains))
    return earned


def fields(store: SqliteStore) -> dict[str, Counter[str]]:
    """The distinct values of every field a spec 04 §4 boost would read."""
    seen: dict[str, Counter[str]] = {
        "trust_class": Counter(),
        "verification_status": Counter(),
        "curated": Counter(),
    }
    for doc_id in store.document_ids():
        document = store.get_document(doc_id)
        if document is None:
            continue
        seen["trust_class"][str(document.trust_class)] += 1
        seen["verification_status"][str(document.verification_status)] += 1
        seen["curated"][str(document.curated)] += 1
    return seen


def _report_fields(label: str, seen: dict[str, Counter[str]]) -> None:
    print(f"\n{label}")
    for name, counts in seen.items():
        shape = ", ".join(f"{value} x{count}" for value, count in counts.most_common())
        verdict = (
            "INERT - one value, so the boost is order-preserving" if len(counts) < 2 else "varies"
        )
        print(f"  {name:<20} {shape:<34} {verdict}")


@dataclass
class Redundancy:
    """What dedupe and stitching would find in the shipped ten."""

    cases: int = 0
    with_duplicate: int = 0
    with_adjacent: int = 0
    duplicate_slots: int = 0
    adjacent_slots: int = 0
    overlapping_pairs: int = 0
    with_overlap: int = 0

    def record(self, pool: Pool) -> None:
        served = pool[:DEPTH]
        self.cases += 1
        digests = Counter(candidate.digest for candidate in served)
        duplicates = sum(count - 1 for count in digests.values() if count > 1)
        overlapping = sum(
            1
            for index, first in enumerate(served)
            for second in served[index + 1 :]
            if first.digest != second.digest and _jaccard(first.tokens, second.tokens) >= OVERLAP
        )
        self.overlapping_pairs += overlapping
        self.with_overlap += 1 if overlapping else 0
        sections: dict[str, list[int]] = {}
        for candidate in served:
            if candidate.position >= 0:
                sections.setdefault(candidate.section, []).append(candidate.position)
        adjacent = 0
        for positions in sections.values():
            ordered = sorted(positions)
            adjacent += sum(
                1
                for before, after in zip(ordered, ordered[1:], strict=False)
                if after == before + 1
            )
        self.duplicate_slots += duplicates
        self.adjacent_slots += adjacent
        self.with_duplicate += 1 if duplicates else 0
        self.with_adjacent += 1 if adjacent else 0

    def row(self) -> str:
        total = self.cases or 1
        return (
            f"same-digest {self.duplicate_slots:>4} ({self.with_duplicate / total:5.1%})  "
            f"overlap>={OVERLAP:.0%} {self.overlapping_pairs:>4} "
            f"({self.with_overlap / total:5.1%})  "
            f"adjacent {self.adjacent_slots:>4} ({self.with_adjacent / total:5.1%})"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, help="Measure one corpus only.")
    parser.add_argument(
        "--fields", action="store_true", help="What a spec 04 §4 boost would have to read."
    )
    parser.add_argument(
        "--redundancy", action="store_true", help="What dedupe and stitching would collapse."
    )
    parser.add_argument(
        "--check", action="store_true", help="Fail when an arm earns a default nothing carries."
    )
    args = parser.parse_args()

    corpora = (("corpus", args.root),) if args.root else CORPORA
    measured = 0
    readings: dict[str, list[Reading]] = {}
    for label, root in corpora:
        if not (root / STORE_DIRNAME / STORE_FILENAME).exists():
            print(f"{label:<22} no store; skipped (build it to measure this corpus)")
            continue
        with SqliteStore.open(root, read_only=True) as store:
            if args.fields:
                _report_fields(label, fields(store))
                measured += 1
                continue
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
                if args.redundancy:
                    found = Redundancy()
                    for pool in case_pools.values():
                        found.record(pool)
                    print(f"{name:<22} {found.row()}")
                    continue
                base = score(cases, case_pools, 1.0)
                print(f"{name:<22} shipped {base.overall:.4f}")
                for weight in DEPTH_WEIGHTS:
                    arm = score(cases, case_pools, weight)
                    label_arm = f"depth^{weight} (~{ranks_moved(weight):.0f}r)"
                    overall, delta = _report_arm(label_arm, base, arm)
                    readings.setdefault(f"depth^{weight}", []).append(Reading(name, overall, delta))
                    narrow = score(cases, case_pools, weight, within=True)
                    inside, inside_delta = _report_arm(f"  ^{weight} within ten", base, narrow)
                    readings.setdefault(f"depth^{weight} within-ten", []).append(
                        Reading(name, inside, inside_delta)
                    )
                control = score(cases, case_pools, CONTROL_WEIGHT, shuffle=True)
                _report_arm(f"shuffled^{CONTROL_WEIGHT}", base, control)

    if not measured:
        print("nothing measured: no corpus in this tree carries a store and a case set")
        return 1
    earned = earning_arms(readings)
    if args.check and earned:
        print(
            "\na heading-proximity arm now earns a default this product does not carry: "
            f"{', '.join(earned)}.\nroadmap 6.38 and ADR-0153 recorded that none did; that "
            "refusal should be re-opened rather than rediscovered."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
