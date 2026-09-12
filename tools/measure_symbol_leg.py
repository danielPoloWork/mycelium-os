#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Run spec 04 §3's symbol leg against its slice: does it earn the default? (roadmap 5.9, 5.23)

    python tools/measure_symbol_leg.py                        # every corpus, both sets
    python tools/measure_symbol_leg.py --coverage             # what can the leg even fire on?
    python tools/measure_symbol_leg.py --promote              # the other reading of §2
    python tools/measure_symbol_leg.py --promote-languages cli   # promotion for one language
    python tools/measure_symbol_leg.py --oracle               # the ceiling: a perfect table
    python tools/measure_symbol_leg.py --check                # the shipped default is the
                                                              # one this measurement supports

**The bar, and where it comes from.** Spec 04 §3 prescribes the leg — *"exact
lookup in `symbols` for identifier-like tokens"* — and spec 04 §2 routes
identifier queries to it first, but neither states a gate the way §5 does for
graph expansion. So this adopts §5's shape on the slice this leg exists for:
**≥ +3 % nDCG@10 on the `symbol` slice with no overall regression**, which is
also the shape gate G2 uses for hybrid (+5 % overall, no slice past −2 %). The
bar is stated here rather than in the spec, and ADR-0080 says so plainly instead
of implying the spec asked for it.

**Four arms, and two readings of the same sentence.** `mycelium` is the shipped
lexical ranking; `symbol` is that ranking with the leg on. The leg itself has two
readings, because spec 04 §2's *"symbol lookup **first**"* and ADR-0075's *"a leg
adds, it never promotes"* cannot both be obeyed:

- **add** (the default, `SYMBOL_PROMOTE = False`): the leg carries only
  definition sites no other leg returned;
- **promote** (`--promote`): a definition site is offered whether or not the
  ranking already found it;
- **promote by language** (`--promote-languages cli`): promotion for the sites
  of one language and add-only for the rest — the arm roadmap 5.23 asked for,
  because a command's sites are the sections that run or name it, and a
  filename's sites are headings that spell it (ADR-0091);
- **oracle** (`--oracle`): a *perfect* symbol table — one whose sites are the
  judged anchors themselves — under both readings. No source can beat it, so it
  is the upper bound on what any extractor could do, and it separates two
  findings that look alike: a leg whose *source* is weak and a leg whose
  *mechanism* cannot carry what the source found (ADR-0083's oracle, applied to
  a source rather than a router; ADR-0094).

All are measured, because choosing between them by argument rather than by
measurement is what this project does not do.

**`--coverage` is the measurement that explains the other ones.** It reports what
each corpus defines, which judged queries name one of those symbols, and where
the lexical leg already ranks that symbol's sites. A leg that cannot fire is not
a leg with a bad constant, and the difference matters when someone later
proposes tuning one.

**What earns the default.** The bar is applied per set, and a default flip needs
it on a *release* set — the held-out judgments — with no overall regression on
any set. A gain confined to the dev sets is reported as **proposable** and ships
as nothing: the dev sets are where rules are developed against, and ADR-0070 set
the precedent that a ranking change earns its default on the sets it was not
developed against. Roadmap 5.23 is the first arm of this leg to clear the bar
anywhere, and it clears it on dev sets only (ADR-0094).

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
    RRF_K,
    SYMBOL_CANDIDATES,
    SYMBOL_DISCOUNT,
    VECTOR_CANDIDATES,
    reciprocal_rank_fusion,
    search,
    symbol_lookup_ids,
)
from mycelium.sdk.types import EvalCase  # noqa: E402
from mycelium.store import STORE_DIRNAME, STORE_FILENAME, SearchHit, SqliteStore  # noqa: E402

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


def _score(cases: Sequence[EvalCase], retriever: object) -> Scores:
    per_case: dict[str, float] = {}
    for case in cases:
        if not case.answerable:
            # Gate G4 owns the unanswerable slice; nDCG cannot speak about a case
            # with no judgments to rank (the blind spot every runner here declares).
            continue
        judged = {anchor.anchor: anchor.grade for anchor in case.relevant}
        retrieved = retriever.search(case.query, DEPTH)  # type: ignore[attr-defined]
        per_case[case.case_id] = ndcg_at_k(credit_judgments(retrieved, judged), judged, DEPTH)
    return _fold(cases, per_case)


def _judged_chunks(store: SqliteStore, case: EvalCase) -> list[str]:
    """The chunk anchors a case's judgments name, sections expanded to their chunks."""
    anchors: list[str] = []
    for judgment in sorted(case.relevant, key=lambda item: -item.grade):
        anchor = judgment.anchor
        if not anchor.endswith("/"):
            anchors.append(anchor)
            continue
        document = store.get_document_by_path(anchor.split("#")[0])
        if document is None:
            continue
        prefix = anchor.rstrip("/") + "/"
        anchors.extend(
            c.anchor for c in store.chunks_of(document.doc_id) if c.anchor.startswith(prefix)
        )
    return list(dict.fromkeys(anchors))


def _score_oracle(store: SqliteStore, cases: Sequence[EvalCase], *, promote: bool) -> Scores:
    """A perfect table's leg: the judged anchors themselves, ranked by BM25 like any site.

    Add-only offers the judged chunks the lexical leg did not reach; promote
    offers them all. Neither is achievable by an extractor — a judgment is not a
    syntax — which is what makes each the ceiling of its reading.
    """
    per_case: dict[str, float] = {}
    for case in cases:
        if not case.answerable:
            continue
        judged = {anchor.anchor: anchor.grade for anchor in case.relevant}
        outcome = search(store, case.query, limit=VECTOR_CANDIDATES)
        lexical: list[SearchHit] = [fused.hit for fused in outcome.hits]
        reached = {hit.chunk.anchor for hit in lexical}
        wanted = _judged_chunks(store, case)
        if not promote:
            wanted = [anchor for anchor in wanted if anchor not in reached]
        leg = list(store.rank_anchors(case.query, wanted, limit=len(wanted))) if wanted else []
        lists = [("lexical", lexical)]
        if leg:
            lists.append(("symbol", leg[:SYMBOL_CANDIDATES]))
        fused = reciprocal_rank_fusion(
            lists, k=RRF_K, limit=DEPTH, weights={"symbol": SYMBOL_DISCOUNT}
        )
        retrieved = [hit.hit.chunk.anchor for hit in fused]
        per_case[case.case_id] = ndcg_at_k(credit_judgments(retrieved, judged), judged, DEPTH)
    return _fold(cases, per_case)


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
    name: str,
    set_name: str,
    base: Scores,
    with_leg: Scores,
    cases: Sequence[EvalCase],
    *,
    arm: str = "symbol",
) -> bool:
    earns, why = _verdict(base, with_leg)
    label = f"{name}/{set_name}"
    identical = all(
        abs(with_leg.per_case[case_id] - value) < 1e-9 for case_id, value in base.per_case.items()
    )
    print(
        f"{label:<20} lexical {base.overall:.4f}  {arm} {with_leg.overall:.4f}  "
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
        print(
            f"    {symbol.symbol:<44} defined_in {symbol.defined_in}  "
            f"({len(symbol.doc_refs)} site(s))"
        )

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
            judged_sections = {anchor for anchor in judged if anchor.endswith("/")}
            for symbol in found:
                sites = symbol.doc_refs
                shown = sites if len(sites) <= 6 else sites[:6]
                print(f"      {symbol.symbol}: {len(sites)} site(s)")
                for ref in shown:
                    position = ranked.index(ref) + 1 if ref in ranked else None
                    relevant = ref in judged or any(
                        ref.startswith(section.rstrip("/") + "/") for section in judged_sections
                    )
                    print(
                        f"        {ref}  lexical rank {position} of {len(ranked)}; "
                        f"judged relevant: {relevant}"
                    )
                if len(sites) > len(shown):
                    print(f"        … and {len(sites) - len(shown)} more")
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
    parser.add_argument(
        "--promote-languages",
        nargs="*",
        default=None,
        metavar="LANGUAGE",
        help=(
            "Score promotion for these symbol languages only (`cli`), add-only for the "
            "rest — the arm roadmap 5.23 asked for (ADR-0094)."
        ),
    )
    parser.add_argument(
        "--oracle",
        action="store_true",
        help=(
            "Score a perfect symbol table — sites equal to the judged anchors — under both "
            "readings: the ceiling no extractor can pass."
        ),
    )
    args = parser.parse_args()

    corpora = [("corpus", args.root)] if args.root else list(CORPORA)
    if args.promote:
        retrieval.SYMBOL_PROMOTE = True  # type: ignore[misc]
    if args.promote_languages is not None:
        retrieval.SYMBOL_PROMOTE_LANGUAGES = tuple(args.promote_languages)  # type: ignore[misc]
    arm = "symbol"
    if args.promote:
        arm = "promote"
    elif args.promote_languages:
        arm = "promote:" + ",".join(args.promote_languages)
    print(
        f"symbol leg ablation: candidates {SYMBOL_CANDIDATES}, discount {SYMBOL_DISCOUNT}, "
        f"promote {args.promote}, promote languages {list(args.promote_languages or ())} "
        f"(spec 04 §§2-3; ADR-0080, ADR-0094)\n"
    )

    earned: dict[str, bool] = {}
    regressed: list[str] = []
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
                measured += 1
                if args.oracle:
                    for promote in (False, True):
                        label = "oracle:promote" if promote else "oracle:add"
                        _report(
                            name,
                            set_name,
                            base,
                            _score_oracle(store, cases, promote=promote),
                            cases,
                            arm=label,
                        )
                    continue
                with_leg = _score(cases, leg_retriever)
                earned[f"{name}/{set_name}"] = _report(
                    name, set_name, base, with_leg, cases, arm=arm
                )
                if _relative(with_leg.overall, base.overall) < 0.0:
                    regressed.append(f"{name}/{set_name}")

    if not measured:
        print("nothing measured")
        return 1
    if args.coverage or args.oracle:
        return 0

    shipped = RetrievalConfig().symbol_lookup
    on_dev = sorted(label for label, earns in earned.items() if earns and label.endswith("/dev"))
    on_release = sorted(
        label for label, earns in earned.items() if earns and label.endswith("/release")
    )
    any_earns = bool(on_release) and not regressed
    if any_earns:
        verdict = f"earns the default: the bar on {', '.join(on_release)} and no set regressed"
    elif on_dev and not regressed:
        verdict = (
            f"is proposable, not earned: the bar on {', '.join(on_dev)} only - a default "
            "needs a held-out (release) gain"
        )
    elif regressed:
        verdict = f"does not earn the default: overall regression on {', '.join(regressed)}"
    else:
        verdict = "does not earn the default on any set"
    print(
        f"\nverdict: the symbol leg ({arm}) {verdict}; "
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
