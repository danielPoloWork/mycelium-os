#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Does routing change what the derived legs are worth? (roadmap 5.11, spec 04 §2)

    python tools/measure_routing.py                 # the three arms, per set
    python tools/measure_routing.py --rules         # what the rule set recognises
    python tools/measure_routing.py --leg symbol    # the other derived leg
    python tools/measure_routing.py --check         # the code and the measurement agree

Spec 04 §2 routes a query to generators by its shape, and until roadmap 5.11 both
derived legs ran on every query when enabled — the cheapest reading of the spec.
5.3 and 5.9 measured those legs *unrouted* and both lost their ablation; 5.11
asks whether the routing changes that, and it is the only question this runner
answers.

**Three arms, and the middle one is the point.**

- **routed** — the leg as it ships when enabled: spec 04 §2's relationship rule
  (or the caller's `--related`) decides whether a query gets it.
- **oracle** — route by the judged slice itself. No deterministic rule set can
  beat a router that reads the answers, so this is the *upper bound* on routing,
  and it is what makes the verdict a proof rather than a report: if the oracle
  cannot clear the bar, no phrasing rule can.
- **every query** — what 5.3 and 5.9 measured, kept so the two are comparable.

**`--rules` is the measurement that explains the other one.** It scores the
shipped relationship phrasings against the judged `relationship` slice as a
classifier — precision, recall, and every case it misses. A router that fires on
three of twenty-two cases is not a router with a bad constant, and the difference
matters when someone later proposes widening the list.

**`--check` fails on a disagreement between the code and the measurement, never
on the ablation's outcome**, for the reason ADR-0068 gives and ADR-0075 and
ADR-0080 repeat: a leg that stays opt-in is a legitimate result, and a runner
that exited non-zero on it would be red on every correct build.
"""

import argparse
import statistics
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.config import RetrievalConfig  # noqa: E402
from mycelium.eval.cases import load_cases  # noqa: E402
from mycelium.eval.metrics import credit_judgments, ndcg_at_k  # noqa: E402
from mycelium.planner import RELATIONSHIP_PHRASES, plan_query  # noqa: E402
from mycelium.retrieval import search  # noqa: E402
from mycelium.sdk.types import EvalCase  # noqa: E402
from mycelium.store import STORE_DIRNAME, STORE_FILENAME, SqliteStore  # noqa: E402

CORPORA: Final = (
    ("ours", ROOT),
    ("uv", ROOT / "eval" / "corpora" / "uv-docs"),
    ("uv-ingested", ROOT / "eval" / "corpora" / "uv-docs-ingested"),
)
SETS: Final = ("dev", "release")
DEPTH: Final = 10

LEGS: Final = {
    "graph": ("relationship", "graph_expansion"),
    "symbol": ("symbol", "symbol_lookup"),
}
"""Each derived leg, the slice its bar is stated on, and the flag that enables it."""

SLICE_MIN: Final = 0.03
"""+3 %, spec 04 §5's bar, which ADR-0080 adopted for the symbol leg as well."""


@dataclass(frozen=True, slots=True)
class Scores:
    overall: float
    per_slice: dict[str, float]
    per_case: dict[str, float]


def _relative(after: float, before: float) -> float:
    if before == 0:
        return 0.0 if after == 0 else 1.0
    return (after - before) / before


def _score(
    store: SqliteStore,
    cases: Sequence[EvalCase],
    config: RetrievalConfig,
    route: Callable[[EvalCase], bool],
) -> Scores:
    """Score one arm. `route` decides, per case, whether the leg is asked for.

    `related=True` is how an arm bypasses the planner's phrasing rule, because it
    is the same signal `--related` gives: this query is the kind that wants the
    leg. An arm that always passes it is the unrouted arm; one that never does is
    the shipped router deciding for itself.
    """
    per_case: dict[str, float] = {}
    by_slice: dict[str, list[float]] = {}
    scored: list[float] = []
    for case in cases:
        if not case.answerable:
            # Gate G4 owns the unanswerable slice; nDCG cannot speak about a case
            # with no judgments to rank.
            continue
        judged = {anchor.anchor: anchor.grade for anchor in case.relevant}
        outcome = search(store, case.query, limit=DEPTH, config=config, related=route(case))
        ranked = [hit.hit.chunk.anchor for hit in outcome.hits]
        value = ndcg_at_k(credit_judgments(ranked, judged), judged, DEPTH)
        per_case[case.case_id] = value
        scored.append(value)
        for name in case.slices:
            by_slice.setdefault(str(name), []).append(value)
    return Scores(
        overall=statistics.fmean(scored) if scored else 0.0,
        per_slice={name: statistics.fmean(values) for name, values in sorted(by_slice.items())},
        per_case=per_case,
    )


def _report_arm(label: str, base: Scores, arm: Scores, slice_name: str) -> bool:
    slice_delta = _relative(arm.per_slice.get(slice_name, 0.0), base.per_slice.get(slice_name, 0.0))
    overall_delta = _relative(arm.overall, base.overall)
    earns = slice_delta >= SLICE_MIN and overall_delta >= 0.0
    moved = [
        f"{case_id} {value:.4f}->{arm.per_case[case_id]:.4f}"
        for case_id, value in base.per_case.items()
        if abs(arm.per_case[case_id] - value) > 1e-9
    ]
    print(
        f"    {label:<12} overall {arm.overall:.4f} ({overall_delta:+.1%})  "
        f"{slice_name} {arm.per_slice.get(slice_name, 0.0):.4f} ({slice_delta:+.1%})  "
        f"{'EARNS' if earns else 'no'}"
    )
    if moved:
        print(f"        moved: {', '.join(moved)}")
    return earns


def _rules(leg: str) -> None:
    """Score the shipped phrasings as a classifier of the slice they route to.

    Precision and recall against the judged slice, and every case the rule set
    misses, because a router is a classifier and reporting one without its recall
    is reporting half of it (ADR-0083).
    """
    slice_name = LEGS[leg][0]
    print(f"\nthe '{leg}' leg routes on the '{slice_name}' slice")
    if leg == "graph":
        print(f"{len(RELATIONSHIP_PHRASES)} relationship phrasing(s): ", end="")
        print(", ".join(repr(phrase) for phrase in RELATIONSHIP_PHRASES))

    fired: list[tuple[str, EvalCase]] = []
    in_slice: list[tuple[str, EvalCase]] = []
    total = 0
    for name, root in CORPORA:
        for set_name in SETS:
            path = root / "eval" / f"{set_name}.jsonl"
            if not path.exists():
                continue
            for case in load_cases(path):
                total += 1
                label = f"{name}/{set_name}"
                if plan_query(case.query).asks_for(leg):
                    fired.append((label, case))
                if slice_name in [str(item) for item in case.slices]:
                    in_slice.append((label, case))

    hits = [(label, case) for label, case in fired if (label, case) in in_slice]
    missed = [(label, case) for label, case in in_slice if (label, case) not in fired]
    precision = len(hits) / len(fired) if fired else 0.0
    recall = len(hits) / len(in_slice) if in_slice else 0.0
    print(
        f"\nfires on {len(fired)} of {total} judged case-instance(s); "
        f"precision {precision:.0%} ({len(hits)}/{len(fired)}), "
        f"recall {recall:.0%} ({len(hits)}/{len(in_slice)})"
    )
    for label, case in fired:
        mark = "  " if (label, case) in in_slice else "x "
        print(f"  {mark}{label:<22} {case.case_id} [{','.join(str(s) for s in case.slices)}]")
    print(f"\nmisses {len(missed)} '{slice_name}' case-instance(s):")
    for label, case in missed:
        print(f"    {label:<22} {case.case_id} {case.query!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, help="One corpus, instead of all three.")
    parser.add_argument(
        "--leg", choices=sorted(LEGS), default="graph", help="Which derived leg to route."
    )
    parser.add_argument(
        "--rules",
        action="store_true",
        help="Score the routing rules as a classifier of the slice they route to.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the shipped default disagrees with the measurement.",
    )
    args = parser.parse_args()

    slice_name, flag = LEGS[args.leg]
    if args.rules:
        _rules(args.leg)
        return 0

    enabled = RetrievalConfig.model_validate({flag: True})
    baseline = RetrievalConfig()
    print(
        f"routing ablation for the '{args.leg}' leg, bar on the '{slice_name}' slice "
        f"(spec 04 §2; ADR-0083)\n"
    )

    any_earns = False
    measured = 0
    corpora = [("corpus", args.root)] if args.root else list(CORPORA)
    for name, root in corpora:
        if not (root / STORE_DIRNAME / STORE_FILENAME).exists():
            print(f"{name}: not built; run `mycelium build {root}`")
            continue
        with SqliteStore.open(root, read_only=True) as store:
            for set_name in SETS:
                path = root / "eval" / f"{set_name}.jsonl"
                if not path.exists():
                    continue
                cases = load_cases(path)
                base = _score(store, cases, baseline, lambda case: False)
                print(
                    f"  {name}/{set_name}: lexical {base.overall:.4f}, "
                    f"{slice_name} {base.per_slice.get(slice_name, 0.0):.4f}"
                )
                arms = (
                    ("routed", lambda case: False),
                    # The upper bound: route by the judgments themselves.
                    (
                        "oracle",
                        lambda case: slice_name in [str(item) for item in case.slices],
                    ),
                    ("every query", lambda case: True),
                )
                for label, route in arms:
                    arm = _score(store, cases, enabled, route)
                    any_earns |= _report_arm(label, base, arm, slice_name)
                measured += 1

    if not measured:
        print("nothing measured")
        return 1

    shipped = bool(getattr(RetrievalConfig(), flag))
    print(
        f"\nverdict: routing does not make the '{args.leg}' leg earn the default on any set; "
        f"[retrieval] {flag} ships {'on' if shipped else 'off'}"
        if not any_earns
        else f"\nverdict: the '{args.leg}' leg earns the default on at least one set under some "
        f"arm; [retrieval] {flag} ships {'on' if shipped else 'off'}"
    )
    if args.check and shipped != any_earns:
        print(
            "\nThe shipped default and this measurement disagree. The default follows the "
            "ablation, so one of them is wrong: re-read the table above, and change either "
            "the flag in `RetrievalConfig` or the reason in ADR-0083."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
