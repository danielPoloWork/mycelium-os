#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Re-run gate G2, and see which leg reaches a case nothing serves.

    python tools/measure_hybrid_gate.py                  # every corpus, both sets
    python tools/measure_hybrid_gate.py --cases u-1023 u-1024
    python tools/measure_hybrid_gate.py <corpus-root>

Two questions, and the file exists because both had gone three milestones without
being asked.

**Does hybrid earn the default yet?** Gate G2 is a *comparison* — hybrid against
lexical on the same cases, ≥ +5 % nDCG@10 with no slice worse than −2 % (spec 04
§7.3) — and it only runs when someone passes `--retriever hybrid`. CI never does,
because CI has no embedding model (D-013: nothing is downloaded unless
configured). So G2's verdict has been carried as prose since ADR-0017 while the
lexical leg it is measured against moved four times underneath it: packing
(roadmap 4.15), stemming (4.19), function-word stripping (4.28), and the heading
split (4.36). A gate whose two arms move independently and are never re-compared
is a claim, not a gate.

**Which leg can reach this case at all?** When a judged case scores 0.0000, the
useful question is not "why is the ranking bad" but *where the judged anchor sits
in each candidate list*: the lexical list, the vector list, and the fused one.
Those three numbers separate a reach failure from a ranking failure from a
fusion-depth failure, and they are what roadmap 4.33 turned out to need — the two
cases it was filed for have different answers on all three.

**What this file cannot see** is the same blind spot `measure_ranking.py` has: it
scores answerable cases only, so gate G4 is outside its view.

**And it deliberately does not print latency.** It did, for one revision, and the
numbers moved by 10× between two runs of the same tree on the same machine
(lexical p95 15 ms then 141 ms) while every nDCG stayed identical to four
decimals. A figure that unstable printed beside "budget 150 ms" invites a
conclusion it cannot support, so gate G5 is left to the harness, which measures it
where the product actually runs. The scores here are deterministic; that is the
difference.

Needs the embedding model. Without it every hybrid column is unavailable and the
file says so rather than printing a lexical-only table that looks like a result.
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

from mycelium.embedding import Embedder, EmbeddingError, build_embedder  # noqa: E402
from mycelium.eval.cases import load_cases  # noqa: E402
from mycelium.eval.metrics import credit_judgments, ndcg_at_k  # noqa: E402
from mycelium.eval.retrievers import build_retriever  # noqa: E402
from mycelium.retrieval import VECTOR_CANDIDATES  # noqa: E402
from mycelium.sdk.types import EvalCase  # noqa: E402
from mycelium.store import SqliteStore  # noqa: E402

CORPORA: Final = (
    ("ours", ROOT),
    ("uv", ROOT / "eval" / "corpora" / "uv-docs"),
    ("uv-ingested", ROOT / "eval" / "corpora" / "uv-docs-ingested"),
)

DEPTH: Final = 10
"""The k every judged metric in this project is taken at."""

_G2_OVERALL: Final = 0.05
_G2_SLICE: Final = -0.02
"""Spec 04 §7.3's two conditions, restated so this file can print the verdict
without importing the gate's private helpers."""


@dataclass(frozen=True, slots=True)
class Scored:
    """One retriever's scores over one judged set."""

    overall: float
    per_slice: dict[str, float]
    per_case: dict[str, float]


def _score(cases: Sequence[EvalCase], retriever: object) -> Scored:
    per_case: dict[str, float] = {}
    slices: dict[str, list[float]] = {}
    for case in cases:
        judged = {anchor.anchor: anchor.grade for anchor in case.relevant}
        ranked = retriever.search(case.query, DEPTH)  # type: ignore[attr-defined]
        score = ndcg_at_k(credit_judgments(ranked, judged), judged, DEPTH)
        per_case[case.case_id] = score
        for name in case.slices:
            slices.setdefault(name, []).append(score)
    overall = statistics.fmean(per_case.values()) if per_case else 0.0
    return Scored(
        overall=overall,
        per_slice={name: statistics.fmean(values) for name, values in slices.items()},
        per_case=per_case,
    )


def _relative(after: float, before: float) -> float:
    """The gate's own convention: a zero baseline cannot regress (harness `_relative`)."""
    if before == 0.0:
        return 1.0 if after > 0.0 else 0.0
    return (after - before) / before


def _verdict(hybrid: Scored, lexical: Scored) -> tuple[bool, str]:
    overall = _relative(hybrid.overall, lexical.overall)
    regressions = [
        f"{name} {_relative(score, lexical.per_slice[name]):+.1%}"
        for name, score in sorted(hybrid.per_slice.items())
        if name in lexical.per_slice and _relative(score, lexical.per_slice[name]) < _G2_SLICE
    ]
    passed = overall >= _G2_OVERALL and not regressions
    detail = f"{overall:+.1%} overall (needs {_G2_OVERALL:+.0%})"
    if regressions:
        detail += f"; regressions past {_G2_SLICE:.0%}: {', '.join(regressions)}"
    return passed, detail


def _legs(
    store: SqliteStore, embedder: Embedder, case: EvalCase
) -> list[tuple[str, int, str, str, str]]:
    """Where each judged anchor sits in the lexical, vector and fused lists.

    The whole point of the row: a case scoring 0.0000 is a *reach* failure if the
    anchor is absent from both candidate lists, a *ranking* failure if it is deep
    in one of them, and a *fusion-depth* failure if it is shallow in the vector
    list and still misses the top ten.
    """
    lexical = store.search_chunks(case.query, limit=100_000)
    lexical_rank = {hit.chunk.anchor: index for index, hit in enumerate(lexical, 1)}
    vectors = store.search_vectors(
        embedder.embed_query(case.query), model_id=embedder.model_id, limit=100_000
    )
    vector_rank = {hit.chunk.anchor: index for index, hit in enumerate(vectors, 1)}
    fused = build_retriever("hybrid", store, embedder).search(case.query, DEPTH)
    fused_rank = {anchor: index for index, anchor in enumerate(fused, 1)}

    def place(rank: int | None, population: int) -> str:
        return "-" if rank is None else f"{rank}/{population}"

    return [
        (
            anchor.anchor,
            anchor.grade,
            place(lexical_rank.get(anchor.anchor), len(lexical)),
            place(vector_rank.get(anchor.anchor), len(vectors)),
            "-" if anchor.anchor not in fused_rank else str(fused_rank[anchor.anchor]),
        )
        for anchor in case.relevant
    ]


def _report_set(label: str, root: Path, set_name: str, embedder: Embedder) -> None:
    path = root / "eval" / f"{set_name}.jsonl"
    if not path.is_file():
        print(f"{label}/{set_name:<8} no such case set")
        return
    cases = [case for case in load_cases(path) if case.answerable]
    store = SqliteStore.open(root, read_only=True)
    try:
        lexical = _score(cases, build_retriever("mycelium", store))
        hybrid = _score(cases, build_retriever("hybrid", store, embedder))
    finally:
        store.close()

    passed, detail = _verdict(hybrid, lexical)
    print(
        f"{label}/{set_name:<8} lexical {lexical.overall:.4f}  hybrid {hybrid.overall:.4f}  "
        f"G2 {'pass' if passed else 'FAIL'}  {detail}"
    )
    for name in sorted(set(lexical.per_slice) | set(hybrid.per_slice)):
        before, after = lexical.per_slice.get(name, 0.0), hybrid.per_slice.get(name, 0.0)
        cases_in = sum(1 for case in cases if name in case.slices)
        print(
            f"    {name:<14} {before:.4f} -> {after:.4f}  "
            f"({_relative(after, before):+.1%})  {cases_in} case(s)"
        )


def _report_cases(names: Sequence[str], embedder: Embedder) -> None:
    print(f"\n=== which leg reaches it (vector leg fuses its top {VECTOR_CANDIDATES}) ===\n")
    header = f"{'set':<20} {'case':<8} {'judged anchor':<58} {'gr':>2}"
    print(f"{header} {'lex':>10} {'vec':>10} {'fused':>5}")
    for label, root in CORPORA:
        for set_name in ("dev", "release"):
            path = root / "eval" / f"{set_name}.jsonl"
            if not path.is_file():
                continue
            wanted = [case for case in load_cases(path) if case.case_id in set(names)]
            if not wanted:
                continue
            store = SqliteStore.open(root, read_only=True)
            try:
                for case in wanted:
                    for anchor, grade, lex, vec, fused in _legs(store, embedder, case):
                        where = f"{label + '/' + set_name:<20} {case.case_id:<8}"
                        print(
                            f"{where} {anchor[:58]:<58} {grade:>2} {lex:>10} {vec:>10} {fused:>5}"
                        )
            finally:
                store.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, help="one corpus root, or all three")
    parser.add_argument("--cases", nargs="*", default=[], help="per-leg view for these case ids")
    args = parser.parse_args()

    try:
        embedder = build_embedder(provider="local-onnx", model_id="bge-small-en-v1.5")
    except EmbeddingError as error:
        print(f"the hybrid arm needs the embedding model, and it is unavailable: {error}")
        print("nothing is printed rather than a lexical-only table that looks like a result.")
        return 1
    if embedder is None:  # pragma: no cover - only when the provider is "none"
        print("no embedder configured")
        return 1

    corpora = [("corpus", args.root)] if args.root else list(CORPORA)
    print(f"{'set':<20} {'gate G2 — hybrid must earn the default (spec 04 §7.3)'}")
    for label, root in corpora:
        for set_name in ("dev", "release"):
            _report_set(label, root, set_name, embedder)

    if args.cases:
        _report_cases(args.cases, embedder)

    print("\nDev sets are what tuning may read. G2's verdict is the release rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
