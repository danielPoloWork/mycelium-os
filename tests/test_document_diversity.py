# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The diversity ablation's arms, and the arithmetic that bounds them (roadmap 6.29).

`tools/measure_document_diversity.py` needs a built corpus to produce a verdict,
so what is tested here is the part that decides what the verdict *means*: that
each arm is the policy it claims to be, that the two ends of both families are
the shipped ranking and round robin, and that the RRF spread which makes the
middle uninhabitable is the number ADR-0144 says it is.

Nothing here opens a store.
"""

import sys
from pathlib import Path

import pytest

from mycelium.retrieval import RRF_K, VECTOR_CANDIDATES

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import measure_document_diversity as ablation  # noqa: E402


def pool(*documents: str) -> ablation.Pool:
    """A fused pool with this project's own RRF scores: rank r scores 1/(k+r)."""
    return [
        (f"{document}#section/{index}", 1.0 / (RRF_K + rank))
        for rank, (document, index) in enumerate(
            ((document, position) for position, document in enumerate(documents)), start=1
        )
    ]


def documents(anchors: list[str]) -> list[str]:
    return [ablation.document_of(anchor) for anchor in anchors]


# ---------------------------------------------------------------------------
# What an anchor's document is
# ---------------------------------------------------------------------------


def test_the_document_is_the_part_before_the_fragment() -> None:
    assert ablation.document_of("docs/adr/0075-x.md#context/2") == "docs/adr/0075-x.md"
    assert ablation.document_of("README.md#/0") == "README.md"


# ---------------------------------------------------------------------------
# The cap family
# ---------------------------------------------------------------------------


def test_a_cap_refuses_the_next_chunk_of_a_document_and_backfills() -> None:
    """The freed slot goes to the next candidate from another document - a cap
    that simply dropped the chunk would return a shorter list, which is a
    different (and worse) policy than the one under measurement."""
    candidates = pool("a.md", "a.md", "a.md", "b.md", "c.md")
    assert documents(ablation.cap_arm(candidates, 2, depth=4)) == ["a.md", "a.md", "b.md", "c.md"]


def test_cap_one_is_round_robin_over_documents() -> None:
    candidates = pool("a.md", "a.md", "b.md", "a.md", "c.md")
    assert documents(ablation.cap_arm(candidates, 1, depth=3)) == ["a.md", "b.md", "c.md"]


def test_a_cap_at_or_above_the_depth_is_the_shipped_ranking() -> None:
    """One end of the family, and the reason the sweep stops at 5: a cap of ten
    cannot refuse anything inside a top ten."""
    candidates = pool(*["a.md"] * 12)
    assert ablation.cap_arm(candidates, ablation.DEPTH) == ablation.shipped_arm(candidates)


# ---------------------------------------------------------------------------
# The decay family
# ---------------------------------------------------------------------------


def test_a_decay_of_one_is_the_shipped_ranking() -> None:
    """The other family's inert end. A discount of 1.0 discounts nothing, so the
    greedy pass must reproduce the fused order exactly."""
    candidates = pool("a.md", "b.md", "a.md", "a.md", "c.md", "b.md")
    assert ablation.decay_arm(candidates, 1.0) == ablation.shipped_arm(candidates)


def test_a_decay_below_the_rrf_spread_is_round_robin() -> None:
    """The family's other end, and it is arithmetic rather than tuning.

    A candidate at pool rank `r` scores `1/(60+r)`, so the whole pool spans
    `110/61 = 1.80x`. Below `61/110` a document's second chunk is discounted
    beneath *every* other candidate in the pool - so the pass takes one chunk
    from each document before any document gets a second. There is nothing to
    tune in that region: every value in it is the same policy.
    """
    saturating = 1.0 / ablation.RRF_SPREAD
    candidates = pool("a.md", "a.md", "a.md", "b.md", "b.md", "c.md")
    served = documents(ablation.decay_arm(candidates, saturating * 0.99, depth=6))
    assert served[:3] == ["a.md", "b.md", "c.md"]


def test_the_rrf_spread_is_the_number_the_record_quotes() -> None:
    """ADR-0144 argues from this constant, so a change to `RRF_K` or to the pool
    depth has to come past this test and re-open the argument.

    The two inputs are read from `mycelium.retrieval`, where they live, rather
    than through the runner that imports them: a test that reads a constant
    second-hand cannot notice the day the runner stops tracking it.
    """
    assert RRF_K == 60
    assert VECTOR_CANDIDATES == 50
    assert pytest.approx(110 / 61) == ablation.RRF_SPREAD
    assert pytest.approx(1.803, abs=0.001) == ablation.RRF_SPREAD


# ---------------------------------------------------------------------------
# The sweep itself
# ---------------------------------------------------------------------------


def test_the_sweep_spans_both_families_end_to_end() -> None:
    """The arms are a decision about *coverage*: a sweep that omitted the
    saturating end or stopped short of inert would be a search for a constant
    rather than a measurement of a family."""
    assert min(ablation.CAPS) == 1
    assert max(ablation.CAPS) < ablation.DEPTH
    assert min(ablation.DECAYS) < 1.0 / ablation.RRF_SPREAD
    assert max(ablation.DECAYS) < 1.0
    assert ablation.SLICE_FLOOR == -0.02
