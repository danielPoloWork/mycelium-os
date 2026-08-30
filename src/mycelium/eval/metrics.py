# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Retrieval metrics (spec 04 §7.2).

Recall@10, Recall@50, nDCG@10, MRR, and citation coverage. Standard definitions,
written out rather than imported, because a metric whose implementation nobody can
read is a number nobody should trust — and because the graded-relevance detail
(gain ``2^grade - 1``) is exactly where evaluation harnesses quietly differ.
"""

import math
from collections.abc import Sequence

__all__ = [
    "citation_coverage",
    "dcg",
    "ndcg_at_k",
    "recall_at_k",
    "reciprocal_rank",
]


def dcg(gains: Sequence[float]) -> float:
    """Discounted cumulative gain of an ordered gain list."""
    return sum(gain / math.log2(rank + 2) for rank, gain in enumerate(gains))


def ndcg_at_k(retrieved: Sequence[str], judged: dict[str, int], k: int) -> float:
    """Normalised DCG at `k` with exponential gain, the IR default.

    Returns 0.0 when nothing is judged relevant: a case with no ground truth
    cannot be scored, and pretending otherwise (1.0 for "nothing to miss")
    would inflate every average that contains one.
    """
    if not judged:
        return 0.0
    gains = [(2 ** judged.get(anchor, 0)) - 1 for anchor in retrieved[:k]]
    ideal = sorted(judged.values(), reverse=True)[:k]
    best = dcg([(2**grade) - 1 for grade in ideal])
    return 0.0 if best == 0 else dcg(gains) / best


def recall_at_k(retrieved: Sequence[str], judged: dict[str, int], k: int) -> float:
    """Fraction of judged-relevant anchors present in the top `k`."""
    if not judged:
        return 0.0
    found = sum(1 for anchor in retrieved[:k] if anchor in judged)
    return found / len(judged)


def reciprocal_rank(retrieved: Sequence[str], judged: dict[str, int]) -> float:
    """1 / rank of the first relevant result, or 0.0 if none was returned."""
    for rank, anchor in enumerate(retrieved, start=1):
        if anchor in judged:
            return 1.0 / rank
    return 0.0


def citation_coverage(retrieved: Sequence[str], resolvable: set[str]) -> float:
    """Fraction of returned anchors that resolve in the snapshot (gate G1).

    Must be 1.00 every release, no exceptions: a citation that does not resolve is
    the one failure this product cannot tolerate. An empty result set is vacuously
    covered — abstention is measured separately.
    """
    if not retrieved:
        return 1.0
    return sum(1 for anchor in retrieved if anchor in resolvable) / len(retrieved)
