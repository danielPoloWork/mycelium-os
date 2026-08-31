# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Retrieval metrics (spec 04 §7.2).

Recall@10, Recall@50, nDCG@10, MRR, and citation coverage. Standard definitions,
written out rather than imported, because a metric whose implementation nobody can
read is a number nobody should trust — and because the graded-relevance detail
(gain ``2^grade - 1``) is exactly where evaluation harnesses quietly differ.
"""

import math
from collections.abc import Mapping, Sequence
from typing import Final

__all__ = [
    "SECTION_MARKER",
    "citation_coverage",
    "credit_judgments",
    "dcg",
    "ndcg_at_k",
    "recall_at_k",
    "reciprocal_rank",
]


SECTION_MARKER: Final = "/"
"""A judged anchor ending here names a section, not a chunk (ADR-0029)."""


def section_of(anchor: str) -> str:
    """The section a chunk anchor belongs to, in judged-anchor form."""
    document, _, path = anchor.partition("#")
    return f"{document}#{path.rsplit('/', 1)[0]}/"


def credit_judgments(retrieved: Sequence[str], judged: Mapping[str, int]) -> list[str]:
    """Rewrite a retrieved list into the judgments it satisfies, each **once**.

    A judgment may name a chunk or a section (:data:`mycelium.sdk.types.JudgedAnchor`).
    A chunk judgment is satisfied by that chunk; a section judgment by any chunk
    under it. Everything else is passed through unchanged, so it scores zero the
    way an unjudged anchor always has.

    **Once** is the load-bearing word. A section split into twelve chunks would
    otherwise let a retriever fill the top ten with that one section and score a
    perfect run for finding a single thing. After the first match the rest of the
    section is neither rewarded nor punished — it lands in the ranking as any
    unjudged passage does, which is what it is.

    Chunk judgments are matched before section judgments, so a set that names both
    means what it wrote: the exact chunk, and its section as a weaker fallback.
    """
    seen: set[str] = set()
    credited: list[str] = []
    for anchor in retrieved:
        if anchor in judged and anchor not in seen:
            seen.add(anchor)
            credited.append(anchor)
            continue
        section = section_of(anchor)
        if section in judged and section not in seen:
            seen.add(section)
            credited.append(section)
            continue
        credited.append(anchor)
    return credited


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
