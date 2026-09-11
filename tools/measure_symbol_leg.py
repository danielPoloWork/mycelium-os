#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Run spec 04 §3's symbol leg against its slice: does it earn the default? (roadmap 5.9)

    python tools/measure_symbol_leg.py                 # every corpus, both sets
    python tools/measure_symbol_leg.py --coverage      # what can the leg even fire on?
    python tools/measure_symbol_leg.py --promote       # the other reading of §2
    python tools/measure_symbol_leg.py --check         # the shipped default is the
                                                       # one this measurement supports

**The bar, and where it comes from.** Spec 04 §3 prescribes the leg — *"exact
lookup in `symbols` for identifier-like tokens"* — and spec 04 §2 routes
identifier queries to it first, but neither states a gate the way §5 does for
graph expansion. So this adopts §5's shape on the slice this leg exists for:
**≥ +3 % nDCG@10 on the `symbol` slice with no overall regression**, which is
also the shape gate G2 uses for hybrid (+5 % overall, no slice past −2 %). The
bar is stated here rather than in the spec, and ADR-0080 says so plainly instead
of implying the spec asked for it.

**Two arms, and two readings of the same sentence.** `mycelium` is the shipped
lexical ranking; `symbol` is that ranking with the leg on. The leg itself has two
readings, because spec 04 §2's *"symbol lookup **first**"* and ADR-0075's *"a leg
adds, it never promotes"* cannot both be obeyed:

- **add** (the default, `SYMBOL_PROMOTE = False`): the leg carries only
  definition sites no other leg returned;
- **promote** (`--promote`): a definition site is offered whether or not the
  ranking already found it.

Both are measured, because choosing between them by argument rather than by
measurement is what this project does not do.

**`--coverage` is the measurement that explains the other one.** It reports what
each corpus defines, which judged queries hold an identifier-like token naming
one of those symbols, and where the lexical leg already ranks that symbol's
definition sites. A leg that cannot fire is not a leg with a bad constant, and
the difference matters when someone later proposes tuning one.

**`--check` fails on a disagreement between the code and the measurement, never
on the ablation's outcome**, for the reason ADR-0068 gives and ADR-0075 repeats:
"stays opt-in" is a legitimate result, and a runner that exited non-zero on it
would be red on every correct build.
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
from mycelium.eval.retrievers import build_retriever  # noqa: E402
from mycelium.retrieval import (  # noqa: E402
    SYMBOL_CANDIDATES,
    SYMBOL_DISCOUNT,
    VECTOR_CANDIDATES,
    search,
    symbol_lookup_ids,
)
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

SLICE: Final = "symbol"
"""The slice the bar is stated on: the queries this leg exists to serve."""

SLICE_MIN: Final = 0.03
"""+3 %, spec 04 §5's bar for the leg it does gate, adopted for this one."""


@dataclass(frozen=True, slots=True)
class Scores:
    """One retriever on one case set."""

    overall: float
    per_slice: dict[str, float]
    per_case: dict[str, float]


def _score(cases: Sequence[EvalCase], retriever: object) -> Scores:
    per_case: dict[str, float] = {}
    by_slice: dict[str, list[float]] = {}
    scored: list[float] = []
    for case in cases:
        if not case.answerable:
            # Gate G4 owns the unanswerable slice; nDCG cannot speak about a case
            # with no judgments to rank (the blind spot every runner here declares).
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


def _verdict(base: Scores, with_leg: Scores) -> tuple[bool, str]:
    slice_delta = _relative(with_leg.per_slice.get(SLICE, 0.0), base.per_slice.get(SLICE, 0.0))
    overall_delta = _relative(with_leg.overall, base.overall)
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
    name: str, set_name: str, base: Scores, with_leg: Scores, cases: Sequence[EvalCase]
) -> bool:
    earns, why = _verdict(base, with_leg)
    label = f"{name}/{set_name}"
    identical = all(
        abs(with_leg.per_case[case_id] - value) < 1e-9 for case_id, value in base.per_case.items()
    )
    print(
        f"{label:<20} lexical {base.overall:.4f}  symbol {with_leg.overall:.4f}  "
        f"{'EARNS' if earns else 'no  '}  {why}"
        f"{'   (every case identical)' if identical else ''}"
    )
    for slice_name in sorted(set(base.per_slice) | set(with_leg.per_slice)):
        before = base.per_slice.get(slice_name, 0.0)
        after = with_leg.per_slice.get(slice_name, 0.0)
        if abs(after - before) < 1e-9:
            continue
        moved = [
            f"{case_id} {base.per_case[case_id]:.4f}->{with_leg.per_case[case_id]:.4f}"
            for case in cases
            if (case_id := case.case_id) in with_leg.per_case
            and slice_name in [str(s) for s in case.slices]
            and abs(with_leg.per_case[case_id] - base.per_case[case_id]) > 1e-9
        ]
        print(
            f"    {slice_name:<14} {before:.4f} -> {after:.4f}  "
            f"{_relative(after, before):+.1%}   {', '.join(moved)}"
        )
    return earns


def _coverage(name: str, root: Path, store: SqliteStore) -> None:
    """What the leg can fire on at all, before asking what it does when it does.

    Three numbers per corpus and one line per firing, because the ablation's
    result is uninterpretable without them: a leg scoring 0.0 % because it never
    ran and a leg scoring 0.0 % because it ran and changed nothing are different
    findings with different follow-ups (ADR-0080).
    """
    symbols = store.all_symbols()
    print(f"\n{name}: {len(symbols)} symbol(s) defined")
    for symbol in symbols:
        print(f"    {symbol.symbol:<44} defined_in {symbol.defined_in}")

    for set_name in SETS:
        path = root / "eval" / f"{set_name}.jsonl"
        if not path.exists():
            continue
        cases = load_cases(path)
        in_slice = [case for case in cases if SLICE in [str(s) for s in case.slices]]
        fired = []
        for case in cases:
            ids = symbol_lookup_ids(case.query)
            found = store.symbols_by_id(ids) if ids else ()
            if not found:
                continue
            fired.append(case)
            slices = ",".join(str(s) for s in case.slices)
            print(f"  {set_name}: {case.case_id} [{slices}] {case.query!r}")
            outcome = search(store, case.query, limit=VECTOR_CANDIDATES)
            ranked = [hit.hit.chunk.anchor for hit in outcome.hits]
            judged = {anchor.anchor for anchor in case.relevant}
            for symbol in found:
                for ref in symbol.doc_refs:
                    position = ranked.index(ref) + 1 if ref in ranked else None
                    print(
                        f"      {symbol.symbol} defines {ref}\n"
                        f"        lexical rank {position} of {len(ranked)}; "
                        f"judged relevant: {ref in judged}"
                    )
        print(
            f"  {set_name}: the leg can fire on {len(fired)} of {len(cases)} case(s); "
            f"{len(in_slice)} case(s) are in the '{SLICE}' slice, "
            f"{len([c for c in fired if c in in_slice])} of which it can fire on"
        )


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
        "--coverage",
        action="store_true",
        help="Report what the leg can fire on, and where the lexical leg already ranks it.",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help=(
            "Score the other reading of spec 04 §2 — the leg may re-rank a passage "
            "another leg already returned. Reported by ADR-0080, never shipped."
        ),
    )
    args = parser.parse_args()

    corpora = [("corpus", args.root)] if args.root else list(CORPORA)
    if args.promote:
        retrieval.SYMBOL_PROMOTE = True  # type: ignore[misc]
    print(
        f"symbol leg ablation: candidates {SYMBOL_CANDIDATES}, discount {SYMBOL_DISCOUNT}, "
        f"promote {args.promote} (spec 04 §§2-3; ADR-0080)\n"
    )

    any_earns = False
    measured = 0
    for name, root in corpora:
        if not (root / STORE_DIRNAME / STORE_FILENAME).exists():
            print(f"{name}: not built; run `mycelium build {root}`")
            continue
        with SqliteStore.open(root, read_only=True) as store:
            if args.coverage:
                _coverage(name, root, store)
                measured += 1
                continue
            base_retriever = build_retriever("mycelium", store)
            leg_retriever = build_retriever("symbol", store)
            for set_name in SETS:
                path = root / "eval" / f"{set_name}.jsonl"
                if not path.exists():
                    continue
                cases = [
                    case
                    for case in load_cases(path)
                    if not args.cases or case.case_id in args.cases
                ]
                if not cases:
                    continue
                base = _score(cases, base_retriever)
                with_leg = _score(cases, leg_retriever)
                measured += 1
                any_earns |= _report(name, set_name, base, with_leg, cases)

    if not measured:
        print("nothing measured")
        return 1
    if args.coverage:
        return 0

    shipped = RetrievalConfig().symbol_lookup
    print(
        f"\nverdict: the symbol leg {'earns' if any_earns else 'does not earn'} the default on "
        f"{'at least one' if any_earns else 'any'} set; "
        f"[retrieval] symbol_lookup ships {'on' if shipped else 'off'}"
    )
    if args.check and shipped != any_earns:
        print(
            "\nThe shipped default and this measurement disagree. The default follows the "
            "ablation, so one of them is wrong: re-read the table above, and change either "
            "the flag in `RetrievalConfig` or the reason in ADR-0080."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
