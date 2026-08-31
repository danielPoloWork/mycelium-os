#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Score candidate re-rankings of the lexical leg, on the **dev** sets (ADR-0031).

    python tools/measure_ranking.py [repository-root]

Roadmap 3.18 opened because the grep incumbent beats the product on the second
corpus. This is where a candidate fix is measured before it is proposed, and it
reads the dev sets on purpose: the release sets are what gate G3 judges the
outcome with, and a change developed against them cannot be told apart from a
change fitted to them (spec 04 §7.1).

Three candidates were measured with it and all three refused. The diagnosis they
share is in ADR-0031: BM25 normalises by length, our chunks are wildly
heterogeneous, and a three-token code fence containing the query term outranks the
paragraph that answers it.
"""

import re
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.eval.cases import load_cases  # noqa: E402
from mycelium.eval.metrics import (  # noqa: E402
    credit_judgments,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
    section_of,
)
from mycelium.eval.retrievers import build_retriever, terms_of  # noqa: E402
from mycelium.store import SearchHit, SqliteStore  # noqa: E402

DEPTH = 50
"""Candidate depth, matching the harness's retrieval limit."""
K = 10
OVERFETCH = 4
"""Candidates read per result when a strategy collapses several into one."""

Ranking = Callable[[SqliteStore, str], list[str]]


def _candidates(store: SqliteStore, query: str, depth: int) -> Sequence[SearchHit]:
    return store.search_chunks(" ".join(terms_of(query)), limit=depth)


def baseline(store: SqliteStore, query: str) -> list[str]:
    """What ships: field-weighted BM25 over chunks."""
    return [hit.chunk.anchor for hit in _candidates(store, query, DEPTH)]


def section_max(store: SqliteStore, query: str) -> list[str]:
    """One section competes once, represented by its best-scoring chunk."""
    best: dict[str, SearchHit] = {}
    for hit in _candidates(store, query, DEPTH * OVERFETCH):
        section = section_of(hit.chunk.anchor)
        if section not in best or hit.score > best[section].score:
            best[section] = hit
    ordered = sorted(best.values(), key=lambda hit: (-hit.score, hit.chunk.anchor))
    return [hit.chunk.anchor for hit in ordered[:DEPTH]]


def length_prior(floor: int) -> Ranking:
    """Damp chunks shorter than `floor` tokens, on the theory that a fragment
    cannot be an answer. It can: `## License` and one line is 24 tokens."""

    def rank(store: SqliteStore, query: str) -> list[str]:
        scored = [
            (hit.score * min(1.0, hit.chunk.tokens / floor), hit.chunk.anchor)
            for hit in _candidates(store, query, DEPTH * OVERFETCH)
        ]
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return [anchor for _, anchor in scored[:DEPTH]]

    return rank


def coverage_first(store: SqliteStore, query: str) -> list[str]:
    """Prefer passages containing more *distinct* query terms, then BM25 —
    coordination-level matching, and what the grep baseline ranks by."""
    terms = terms_of(query)
    patterns = [re.compile(rf"\b{re.escape(term)}", re.IGNORECASE) for term in terms]
    scored = []
    for hit in _candidates(store, query, DEPTH * OVERFETCH):
        haystack = f"{hit.title} {' '.join(hit.chunk.heading_path)} {hit.chunk.text}"
        covered = sum(1 for pattern in patterns if pattern.search(haystack))
        scored.append(((covered, hit.score), hit.chunk.anchor))
    scored.sort(key=lambda pair: (-pair[0][0], -pair[0][1], pair[1]))
    return [anchor for _, anchor in scored[:DEPTH]]


def grep(store: SqliteStore, query: str) -> list[str]:
    """The incumbent D-010 measures against."""
    return build_retriever("grep", store).search(query, DEPTH)


def score(root: Path, rank: Ranking) -> tuple[float, float, float]:
    cases = [case for case in load_cases(root / "eval" / "dev.jsonl") if case.answerable]
    totals = [0.0, 0.0, 0.0]
    with SqliteStore.open(root, read_only=True) as store:
        for case in cases:
            judged = {relevant.anchor: relevant.grade for relevant in case.relevant}
            credited = credit_judgments(rank(store, case.query), judged)
            totals[0] += ndcg_at_k(credited, judged, K)
            totals[1] += reciprocal_rank(credited, judged)
            totals[2] += recall_at_k(credited, judged, K)
    count = len(cases)
    return totals[0] / count, totals[1] / count, totals[2] / count


def main() -> int:
    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    ours = Path(args[0]) if args else ROOT
    corpora = [("ours/dev", ours), ("uv/dev", ROOT / "eval" / "corpora" / "uv-docs")]
    strategies: list[tuple[str, Ranking]] = [
        ("baseline (ships)", baseline),
        ("section:max", section_max),
        ("length>=60", length_prior(60)),
        ("length>=120", length_prior(120)),
        ("coverage-first", coverage_first),
        ("grep (incumbent)", grep),
    ]
    print(f"{'set':<10} {'strategy':<18} {'nDCG@10':>8} {'MRR':>7} {'R@10':>7}")
    for name, root in corpora:
        for label, rank in strategies:
            ndcg, mrr, recall = score(root, rank)
            print(f"{name:<10} {label:<18} {ndcg:8.3f} {mrr:7.3f} {recall:7.3f}")
    print("\nDev sets only. A candidate that wins here still has to clear gate G3 on the")
    print("release sets, and section:max did not - see ADR-0031.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
