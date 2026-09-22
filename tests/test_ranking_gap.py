# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The ranking-gap decomposition, and the credit rule it has to agree with (roadmap 6.37).

`tools/measure_ranking_gap.py` needs a built corpus to produce a verdict, so what
is tested here is the part that decides what the verdict *means*: that the oracle
awards a chunk the grade the **metric** would award it rather than the one a plain
dictionary lookup would, that a rank is read through the same *once* rule
`credit_judgments` applies, and that the three slices of the pool are ordered so
that the reported shares are shares of something.

Nothing here opens a store.
"""

import sys
from pathlib import Path

import pytest

from mycelium.eval.metrics import credit_judgments

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import measure_ranking_gap as gap  # noqa: E402

SECTION = "guide.md#install/"
"""A section judgment (ADR-0029): satisfied by any chunk under it."""


def test_a_chunk_judgment_is_graded_before_its_section() -> None:
    """A set that names both means what it wrote: the chunk, its section weaker."""
    judged = {"guide.md#install/0": 3, SECTION: 1}
    assert gap.credited_grade("guide.md#install/0", judged) == 3
    assert gap.credited_grade("guide.md#install/1", judged) == 1


def test_a_chunk_under_a_judged_section_is_not_worthless() -> None:
    """The correction this runner makes to ADR-0144's oracle.

    Sorting by `judged.get(anchor, 0)` scores every chunk under a judged *section*
    as zero and sinks it below unjudged candidates, which understates the ceiling
    it is measuring. The metric credits it, so the oracle has to as well.
    """
    judged = {SECTION: 3}
    assert judged.get("guide.md#install/2", 0) == 0
    assert gap.credited_grade("guide.md#install/2", judged) == 3


def test_an_unjudged_anchor_grades_zero() -> None:
    assert gap.credited_grade("other.md#topic/0", {SECTION: 3}) == 0


def test_a_section_judgment_is_satisfied_once_at_its_first_chunk() -> None:
    """*Once* is load-bearing, so a rank is the first chunk and not each of them."""
    anchors = ["other.md#a/0", "guide.md#install/4", "guide.md#install/5"]
    assert gap.first_ranks(anchors, {SECTION: 2}) == {SECTION: 2}


def test_ranks_agree_with_the_credit_rule() -> None:
    judged = {"guide.md#install/0": 3, "other.md#a/0": 2}
    anchors = ["x.md#y/0", "other.md#a/0", "guide.md#install/0"]
    ranks = gap.first_ranks(anchors, judged)
    credited = credit_judgments(anchors, judged)
    assert ranks == {"other.md#a/0": 2, "guide.md#install/0": 3}
    assert [credited[rank - 1] for rank in ranks.values()] == list(ranks)


def test_an_unfound_judgment_has_no_rank() -> None:
    assert gap.first_ranks(["x.md#y/0"], {SECTION: 3}) == {}


def test_re_ordering_can_never_score_below_the_order_it_was_given() -> None:
    """The property that makes `reorder-10` a ceiling rather than an arm."""
    judged = {"a.md#s/0": 3, "b.md#s/0": 2}
    anchors = ["c.md#s/0", "d.md#s/0", "b.md#s/0", "a.md#s/0"]
    assert gap.perfect(anchors, judged) >= gap.scored(anchors, judged)


def test_a_wider_slice_of_the_pool_is_never_a_worse_ceiling() -> None:
    """Why `inside_share` is a share: the three ceilings are monotone in width."""
    judged = {"a.md#s/0": 3, "z.md#s/0": 3}
    anchors = [f"f{index}.md#s/0" for index in range(gap.DEPTH)] + ["z.md#s/0"]
    anchors[0] = "a.md#s/0"
    served = gap.perfect(anchors[: gap.DEPTH], judged)
    whole = gap.perfect(anchors, judged)
    assert served <= whole
    assert whole > served, "the pool holds a judgment the served ten does not"


def test_the_shares_are_taken_against_the_shipped_pool() -> None:
    found = gap.Decomposition(control=0.5, reorder_ten=0.7, rerank_pool=0.9, rerank_deep=1.0)
    assert found.ceiling == pytest.approx(0.4)
    assert found.inside_share == pytest.approx(0.5)
    assert found.deeper_share == pytest.approx(0.25)


def test_a_set_with_no_headroom_reports_no_share_rather_than_dividing_by_zero() -> None:
    found = gap.Decomposition(control=1.0, reorder_ten=1.0, rerank_pool=1.0, rerank_deep=1.0)
    assert found.ceiling == 0.0
    assert found.inside_share == 0.0
    assert found.deeper_share == 0.0


def test_the_probe_reaches_past_the_shipped_pool() -> None:
    """Otherwise "past the pool" and "absent" could not be told apart at all."""
    assert gap.PROBE > gap.VECTOR_CANDIDATES > gap.DEPTH
