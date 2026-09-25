# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The spec 04 §4 arms, and the arithmetic that bounds them (roadmap 6.38).

`tools/measure_result_rules.py` needs a built corpus to produce a verdict, so what is
tested here is the part that decides what the verdict *means*: that a multiplicative boost
over a field with one value cannot reorder anything (the whole argument against three of
§4's four boosts), that the heading arm is the policy it claims to be in both directions,
that the within-ten variant never reaches below the fold, and that the permutation control
perturbs by the same amount while carrying no signal.

Nothing here opens a store.
"""

import sys
from pathlib import Path

import pytest

from mycelium.retrieval import RRF_K

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import measure_result_rules as rules  # noqa: E402


def candidate(
    anchor: str, score: float, depth: int, digest: str = "d", text: str = "a b"
) -> rules.Candidate:
    return rules.Candidate(
        anchor=anchor, score=score, depth=depth, digest=digest, tokens=frozenset(text.split())
    )


def pool(*depths: int) -> rules.Pool:
    """A pool with this project's own RRF scores: pool rank r scores 1/(k+r)."""
    return [
        candidate(f"doc.md#s/{index}", 1.0 / (RRF_K + index + 1), depth)
        for index, depth in enumerate(depths)
    ]


def test_a_boost_over_one_value_cannot_reorder_anything() -> None:
    """The whole argument against the trust_class, verification and curated boosts.

    Every corpus in this repository is single-valued in all three, so the boost multiplies
    every candidate by the same factor — and `b * s` sorts as `s` does for any `b > 0`.
    """
    constant = pool(2, 2, 2, 2, 2)
    before = [c.anchor for c in constant]
    for weight in (0.5, 0.9, 1.1, 2.0):
        assert rules.depth_arm(constant, weight) == before[: rules.DEPTH]


def test_a_weight_of_one_is_the_shipped_ranking() -> None:
    mixed = pool(1, 3, 2, 4, 1)
    assert rules.depth_arm(mixed, 1.0) == rules.shipped_arm(mixed)


def test_a_weight_below_one_demotes_the_deeper_chunk() -> None:
    """Spec 04 §4's stated intent: H1/H2 sections over deep fragments."""
    shallow, deep = pool(4, 1)
    assert rules.shipped_arm([shallow, deep]) == [shallow.anchor, deep.anchor]
    assert rules.depth_arm([shallow, deep], 0.5) == [deep.anchor, shallow.anchor]


def test_a_weight_above_one_promotes_it_instead() -> None:
    """The other direction, which ADR-0080's discipline requires measuring too."""
    deep, shallow = pool(1, 4)
    assert rules.depth_arm([deep, shallow], 1.5) == [shallow.anchor, deep.anchor]


def test_a_chunk_with_no_heading_path_is_not_penalised() -> None:
    """It is its own section, so the exponent floors at zero rather than going negative."""
    none, one = pool(0, 1)
    assert rules.depth_arm([none, one], 0.5) == [none.anchor, one.anchor]


def test_the_within_ten_arm_never_reaches_below_the_fold() -> None:
    """Otherwise it would not be the window ADR-0152 priced."""
    deep_then_shallow = pool(*([3] * rules.DEPTH + [1] * 5))
    served = rules.depth_arm(deep_then_shallow, 0.5, within=True)
    assert set(served) <= {c.anchor for c in deep_then_shallow[: rules.DEPTH]}
    promoted = rules.depth_arm(deep_then_shallow, 0.5)
    assert set(promoted) - {c.anchor for c in deep_then_shallow[: rules.DEPTH]}


def test_the_control_keeps_the_multipliers_and_loses_the_association() -> None:
    mixed = pool(1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4)
    served = rules.shuffled_arm(mixed, 0.9, "q-0001")
    assert len(served) == rules.DEPTH
    assert set(served) <= {c.anchor for c in mixed}


def test_the_control_is_deterministic_for_a_case() -> None:
    mixed = pool(1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4)
    assert rules.shuffled_arm(mixed, 0.9, "q-0001") == rules.shuffled_arm(mixed, 0.9, "q-0001")


def test_ranks_moved_is_the_arithmetic_the_record_quotes() -> None:
    """A factor `w` crosses about `|w - 1| * (RRF_K + r)` neighbours."""
    assert rules.ranks_moved(1.05) == pytest.approx(0.05 * (RRF_K + rules.DEPTH))
    assert rules.ranks_moved(0.95) == pytest.approx(rules.ranks_moved(1.05))
    assert rules.ranks_moved(0.5) > rules.DEPTH, "clears the served ten"


def test_an_anchor_names_its_section_and_its_place_in_it() -> None:
    one = candidate("guide.md#install/3", 1.0, 2)
    assert one.section == "guide.md#install"
    assert one.position == 3
    assert candidate("guide.md#install/", 1.0, 2).position == -1


def test_overlap_is_a_token_set_jaccard() -> None:
    assert rules._jaccard(frozenset("ab"), frozenset("ab")) == pytest.approx(1.0)
    assert rules._jaccard(frozenset("ab"), frozenset("cd")) == pytest.approx(0.0)
    assert rules._jaccard(frozenset(), frozenset()) == pytest.approx(0.0)


def test_redundancy_counts_adjacent_chunks_of_one_section() -> None:
    found = rules.Redundancy()
    found.record(
        [
            candidate("a.md#s/0", 0.9, 1),
            candidate("a.md#s/1", 0.8, 1),
            candidate("b.md#t/5", 0.7, 1),
        ]
    )
    assert found.adjacent_slots == 1
    assert found.with_adjacent == 1


def test_redundancy_does_not_call_distant_chunks_adjacent() -> None:
    found = rules.Redundancy()
    found.record([candidate("a.md#s/0", 0.9, 1), candidate("a.md#s/7", 0.8, 1)])
    assert found.adjacent_slots == 0


def test_redundancy_counts_a_repeated_digest_once_per_extra_slot() -> None:
    found = rules.Redundancy()
    found.record(
        [
            candidate("a.md#s/0", 0.9, 1, digest="same"),
            candidate("b.md#t/0", 0.8, 1, digest="same"),
            candidate("c.md#u/0", 0.7, 1, digest="other"),
        ]
    )
    assert found.duplicate_slots == 1


# ---------------------------------------------------------------------------
# The bar --check applies (roadmap 7.10, BUG-0037)
# ---------------------------------------------------------------------------


def reading(set_name: str, overall: float, worst: float = 0.0) -> rules.Reading:
    return rules.Reading(set_name, overall, worst)


def test_a_release_gain_with_no_loss_anywhere_earns_the_default() -> None:
    readings = {
        "depth^1.05": [
            reading("ours/release", 0.01),
            reading("ours/dev", 0.0),
            reading("uv/release", 0.002),
        ]
    }
    assert rules.earning_arms(readings) == ["depth^1.05 ours/release +1.00%, uv/release +0.20%"]


def test_a_gain_on_one_set_does_not_earn_against_a_loss_on_another() -> None:
    """BUG-0037: +0.23 % on this repository's corpus against -19 % on each vendored one
    was reported as earning the default. The bar is about the arm, across every set."""
    readings = {
        "depth^1.05": [
            reading("ours/release", 0.0023),
            reading("uv/release", -0.1895),
            reading("uv-ingested/release", -0.2071),
        ]
    }
    assert rules.earning_arms(readings) == []


def test_a_dev_regression_also_refuses_the_arm() -> None:
    readings = {"depth^0.9": [reading("ours/release", 0.01), reading("ours/dev", -0.001)]}
    assert rules.earning_arms(readings) == []


def test_a_slice_past_the_floor_refuses_the_arm_anywhere() -> None:
    readings = {"depth^0.9": [reading("ours/release", 0.02), reading("uv/dev", 0.01, -0.03)]}
    assert rules.earning_arms(readings) == []


def test_a_gain_confined_to_dev_is_proposable_and_earns_nothing() -> None:
    readings = {"depth^0.9": [reading("ours/dev", 0.05), reading("ours/release", 0.0)]}
    assert rules.earning_arms(readings) == []
