# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The reference profile's query-stage reporting (roadmap 6.35, ADR-0150).

Spec 04 §1 states five latency budgets and roadmap 6.24 armed a gate on the last
of them. The other four are *reported* here rather than gated, and this pins the
parts of that decision a future edit could quietly undo: which timed label belongs
to which spec stage, that `terms` is not one of them, that a stage which did not
run is reported rather than omitted, and that a stage with no label to read is
named along with the reason it has none.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import benchmark_reference_profile as profile  # noqa: E402 - the tool is not a package


def test_every_timed_label_names_a_spec_stage_and_its_budget() -> None:
    budgets = {
        "plan + candidates": profile.CANDIDATE_BUDGET_MS,
        "fusion + boosts + dedupe": profile.FUSION_BUDGET_MS,
        "graph expansion": profile.GRAPH_BUDGET_MS,
    }
    for label, (stage, budget) in profile.SPEC_STAGES.items():
        assert stage in budgets, f"{label} names a stage spec 04 §1 does not state"
        assert budget == budgets[stage]


def test_terms_is_not_a_pipeline_stage() -> None:
    """`terms` is `explain`'s per-term report (ADR-0050), not a stage of spec 04 §1.

    Pricing it against a stage budget would charge a budget for work the spec's
    pipeline does not contain — and it is timed into `timings_ms` beside the
    stages, so leaving it out has to be deliberate and stay deliberate.
    """
    assert "terms" not in profile.SPEC_STAGES
    assert "total" not in profile.SPEC_STAGES


def test_a_stage_that_ran_is_reported_against_its_budget() -> None:
    samples = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    notes = profile._query_stage_notes([{"lexical": value, "fusion": 0} for value in samples])
    lexical = notes["query_stages"]["lexical"]
    assert lexical["spec_stage"] == "plan + candidates"
    assert lexical["budget_ms"] == profile.CANDIDATE_BUDGET_MS
    assert lexical["samples"] == len(samples)
    # The same percentile every other measurement in this file reports, rather
    # than a second definition living beside the first.
    reference = profile.Measurement(name="reference", unit="ms", budget=None)
    reference.samples = [float(value) for value in samples]
    assert lexical["p95"] == reference.p95
    assert lexical["p50"] == reference.p50


def test_a_stage_that_did_not_run_is_reported_not_omitted() -> None:
    """A stage absent from a report reads as a stage that cost nothing.

    The graph leg ships off by default (ADR-0075) rather than free, so it is
    reported with no samples and a note saying why.
    """
    notes = profile._query_stage_notes([{"lexical": 40, "fusion": 0}])
    graph = notes["query_stages"]["graph"]
    assert graph["samples"] == 0
    assert "p95" not in graph
    assert "did not run" in graph["note"]
    assert graph["budget_ms"] == profile.GRAPH_BUDGET_MS


def test_a_stage_with_no_label_is_named_with_its_reason() -> None:
    notes = profile._query_stage_notes([{"lexical": 40}])
    untimed = notes["query_stages_untimed"]
    assert [entry["spec_stage"] for entry in untimed] == ["stitch + pack"]
    assert untimed[0]["budget_ms"] == profile.STITCH_PACK_BUDGET_MS
    assert "unimplemented" in untimed[0]["why"]


def test_the_report_says_the_stages_are_not_gated() -> None:
    # The decision itself, carried in the manifest rather than only in an ADR:
    # a reader of the numbers should not have to guess whether CI enforces them.
    notes = profile._query_stage_notes([{"lexical": 40}])
    assert "gates the end-to-end total only" in notes["query_stages_are_reported_not_gated"]


def test_terms_is_ignored_even_when_the_path_times_it() -> None:
    notes = profile._query_stage_notes([{"lexical": 40, "terms": 90, "total": 130}])
    assert set(notes["query_stages"]) == set(profile.SPEC_STAGES)
    assert notes["query_stages_timed"] == ["lexical"]
