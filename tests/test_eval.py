# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Evaluation harness (roadmap 2.11, spec 04 §7).

The metrics are checked against hand-computable examples — a harness whose arithmetic
nobody has verified produces numbers nobody should quote — and the committed judged set
is run against a real build of this repository's own documentation, including the
comparison D-010 insists on: Mycelium against the agent's grep loop.
"""

import json
import sys
from pathlib import Path

import pytest

from mycelium.build import build
from mycelium.eval import (
    EvaluationError,
    GrepRetriever,
    MyceliumRetriever,
    build_retriever,
    citation_coverage,
    load_cases,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
    run_evaluation,
    write_cases,
    write_run,
)
from mycelium.sdk.types import EvalCase, EvalSlice, RelevantAnchor
from mycelium.store import SqliteStore

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
from build_eval_cases import CORPUS_PATHS, stage_corpus  # noqa: E402

CASES = Path(__file__).parent.parent / "eval" / "cases.jsonl"


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A built copy of this repository's own docs — never the repository itself."""
    root = tmp_path_factory.mktemp("self-corpus")
    stage_corpus(root)
    build(root)
    return root


# ---------------------------------------------------------------------------
# Metrics: arithmetic anyone can check by hand
# ---------------------------------------------------------------------------


def test_ndcg_rewards_putting_the_best_result_first() -> None:
    judged = {"a": 3, "b": 1}
    assert ndcg_at_k(["a", "b"], judged, 10) == pytest.approx(1.0)
    assert ndcg_at_k(["b", "a"], judged, 10) < 1.0
    assert ndcg_at_k(["x", "y"], judged, 10) == 0.0
    # A case with no ground truth scores 0, not 1: it cannot be answered well.
    assert ndcg_at_k(["a"], {}, 10) == 0.0


def test_ndcg_uses_exponential_gain() -> None:
    """Grade 3 must be worth much more than grade 1, not three times more."""
    top_heavy = ndcg_at_k(["a", "b"], {"a": 3, "b": 1}, 10)
    inverted = ndcg_at_k(["b", "a"], {"a": 3, "b": 1}, 10)
    assert top_heavy - inverted > 0.15


def test_recall_and_reciprocal_rank() -> None:
    judged = {"a": 3, "b": 2, "c": 1}
    assert recall_at_k(["a", "b"], judged, 10) == pytest.approx(2 / 3)
    assert recall_at_k(["a", "b", "c"], judged, 2) == pytest.approx(2 / 3)
    assert recall_at_k([], judged, 10) == 0.0
    assert reciprocal_rank(["x", "a"], judged) == pytest.approx(0.5)
    assert reciprocal_rank(["x", "y"], judged) == 0.0


def test_citation_coverage_is_the_g1_measurement() -> None:
    assert citation_coverage(["a", "b"], {"a", "b"}) == 1.0
    assert citation_coverage(["a", "b"], {"a"}) == pytest.approx(0.5)
    assert citation_coverage([], set()) == 1.0  # abstention is measured separately


# ---------------------------------------------------------------------------
# Case sets
# ---------------------------------------------------------------------------


def test_the_committed_case_set_loads_and_covers_the_slices() -> None:
    cases = load_cases(CASES)
    assert len(cases) == 20  # the milestone's target
    assert len({case.case_id for case in cases}) == 20

    slices = {slice_ for case in cases for slice_ in case.slices}
    assert {
        EvalSlice.EXACT,
        EvalSlice.SYMBOL,
        EvalSlice.FACT,
        EvalSlice.CONCEPTUAL,
        EvalSlice.RELATIONSHIP,
        EvalSlice.UNANSWERABLE,
        EvalSlice.INJECTION,
    } <= slices
    assert any(not case.answerable for case in cases)
    assert all(case.note for case in cases)  # every judgment explains itself


def test_a_case_set_round_trips(tmp_path: Path) -> None:
    cases = load_cases(CASES)
    destination = tmp_path / "cases.jsonl"
    write_cases(destination, cases)
    assert load_cases(destination) == cases
    assert b"\r" not in destination.read_bytes()


def test_malformed_case_sets_are_rejected_by_line(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    path.write_text('{"case_id": "q-1"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"cases\.jsonl:1"):
        load_cases(path)

    duplicate = json.dumps(
        {"case_id": "q-1", "query": "x", "relevant": [{"anchor": "a.md#b/0", "grade": 3}]}
    )
    path.write_text(f"{duplicate}\n{duplicate}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate case_id"):
        load_cases(path)


def test_judgments_must_agree_with_answerability() -> None:
    with pytest.raises(ValueError, match="needs at least one relevant anchor"):
        EvalCase(case_id="q-1", query="x", answerable=True)
    with pytest.raises(ValueError, match="must have no relevant anchors"):
        EvalCase(
            case_id="q-1",
            query="x",
            answerable=False,
            relevant=(RelevantAnchor(anchor="a.md#b/0", grade=3),),
        )


# ---------------------------------------------------------------------------
# The harness against this repository's own documentation
# ---------------------------------------------------------------------------


def test_every_judged_anchor_exists_in_the_corpus(corpus: Path) -> None:
    """Judgments rot when headings move; this is the alarm.

    If it fails, a heading was renamed: re-judge the case and regenerate with
    `python tools/build_eval_cases.py`.
    """
    with SqliteStore.open(corpus, read_only=True) as store:
        missing = [
            (case.case_id, relevant.anchor)
            for case in load_cases(CASES)
            for relevant in case.relevant
            if store.get_chunk(relevant.anchor) is None
        ]
    assert missing == []


def test_a_run_reports_metrics_gates_and_a_manifest(corpus: Path) -> None:
    manifest = run_evaluation(corpus, load_cases(CASES))

    assert manifest.retriever == "mycelium"
    assert manifest.snapshot_id
    assert manifest.overall.cases == 20
    assert 0.0 <= manifest.overall.ndcg_at_10 <= 1.0
    assert len(manifest.results) == 20
    assert {gate.gate for gate in manifest.gates} == {"G1 Citations", "G4 Abstention"}
    assert all(gate.passed for gate in manifest.gates)
    # Reproducible from what it records (spec 04 §7.5).
    assert manifest.retriever_config["engine"] == "fts5-bm25"
    assert manifest.toolchain.python


def test_gate_g1_holds_every_returned_anchor_resolves(corpus: Path) -> None:
    """The one failure this product cannot tolerate."""
    manifest = run_evaluation(corpus, load_cases(CASES))
    assert manifest.overall.citation_coverage == 1.0
    coverage = next(gate for gate in manifest.gates if gate.gate.startswith("G1"))
    assert coverage.passed


def test_gate_g4_unanswerable_queries_return_nothing(corpus: Path) -> None:
    manifest = run_evaluation(corpus, load_cases(CASES))
    by_id = {case.case_id: case for case in load_cases(CASES)}
    for result in manifest.results:
        if not by_id[result.case_id].answerable:
            assert result.abstained, f"{result.case_id} invented {len(result.retrieved)} results"
    assert manifest.overall.false_answer_rate == 0.0


def test_metrics_are_reported_per_slice(corpus: Path) -> None:
    manifest = run_evaluation(corpus, load_cases(CASES))
    assert "conceptual" in manifest.per_slice
    assert "unanswerable" in manifest.per_slice
    assert sum(summary.cases for summary in manifest.per_slice.values()) >= 20
    # An overall win never excuses a protected-slice loss, so slices are visible.
    assert manifest.per_slice["exact"].ndcg_at_10 > 0.5


def test_mycelium_beats_the_grep_baseline(corpus: Path) -> None:
    """D-010: the incumbent is the agent's grep loop, and it must be beaten.

    Asserted as a *relative* claim, which is what the spec enforces pre-GA — no
    invented absolute threshold. If this ever fails, the answer is to fix the
    product, not to lower the bar.
    """
    cases = load_cases(CASES)
    mycelium = run_evaluation(corpus, cases, retriever_name="mycelium").overall
    grep = run_evaluation(corpus, cases, retriever_name="grep").overall

    assert mycelium.ndcg_at_10 > grep.ndcg_at_10
    assert mycelium.mrr > grep.mrr
    assert mycelium.latency_p95_ms <= grep.latency_p95_ms


def test_the_grep_baseline_is_fair(corpus: Path) -> None:
    """A baseline built to lose proves nothing, so this one is checked for competence."""
    grep = run_evaluation(corpus, load_cases(CASES), retriever_name="grep").overall
    assert grep.ndcg_at_10 > 0.3  # it finds real answers
    assert grep.citation_coverage == 1.0  # in the same anchor space
    assert grep.false_answer_rate == 0.0  # and abstains on the same cases


def test_both_retrievers_search_the_same_corpus(corpus: Path) -> None:
    with SqliteStore.open(corpus, read_only=True) as store:
        assert isinstance(build_retriever("mycelium", store), MyceliumRetriever)
        assert isinstance(build_retriever("grep", store), GrepRetriever)
        mycelium = set(build_retriever("mycelium", store).search("determinism gate", 50))
        grep = set(build_retriever("grep", store).search("determinism gate", 50))
    assert mycelium and grep
    assert mycelium & grep  # the same anchor space, not two different universes


def test_an_unknown_retriever_is_refused(corpus: Path) -> None:
    with SqliteStore.open(corpus, read_only=True) as store, pytest.raises(ValueError):
        build_retriever("magic", store)


def test_run_manifests_are_written_where_the_spec_says(corpus: Path) -> None:
    manifest = run_evaluation(corpus, load_cases(CASES))
    path = write_run(corpus, manifest)
    assert path.parent == corpus / ".mycelium" / "eval"
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded["run_id"] == manifest.run_id
    assert reloaded["schema_version"] == "mycelium/eval-run/v0"
    assert b"\r" not in path.read_bytes()


def test_evaluation_requires_a_snapshot_and_cases(tmp_path: Path) -> None:
    with pytest.raises(EvaluationError, match="no evaluation cases"):
        run_evaluation(tmp_path, [])
    with pytest.raises(EvaluationError, match="mycelium build"):
        run_evaluation(tmp_path, load_cases(CASES))


def test_the_corpus_definition_is_this_repository(corpus: Path) -> None:
    """The eval corpus is the project's own documentation, per the roadmap item."""
    assert "README.md" in CORPUS_PATHS
    assert "docs/adr" in CORPUS_PATHS
    assert "docs/journal" not in CORPUS_PATHS  # churns every session; excluded on purpose
    with SqliteStore.open(corpus, read_only=True) as store:
        assert store.counts()["documents"] > 15


def test_staging_never_touches_the_repository(tmp_path: Path) -> None:
    repository = Path(__file__).parent.parent
    before = (repository / "README.md").read_bytes()
    staged = tmp_path / "staged"
    stage_corpus(staged)
    build(staged)
    assert (repository / "README.md").read_bytes() == before
    assert (staged / "README.md").exists()  # the copy was built, not the original


def test_case_sets_can_be_regenerated(tmp_path: Path) -> None:
    """`tools/build_eval_cases.py` writes exactly what is committed."""
    cases = load_cases(CASES)
    regenerated = tmp_path / "cases.jsonl"
    write_cases(regenerated, cases)
    assert regenerated.read_text(encoding="utf-8") == CASES.read_text(encoding="utf-8")


def test_slices_do_not_dilute_ranking_metrics(corpus: Path) -> None:
    """Unanswerable cases must not drag the ranking averages down.

    They have no relevant anchor, so scoring them as nDCG 0 would punish the
    system for behaving correctly. Their correctness is the false-answer rate.
    """
    cases = load_cases(CASES)
    answerable = [case for case in cases if case.answerable]
    full = run_evaluation(corpus, cases).overall
    only_answerable = run_evaluation(corpus, answerable).overall
    assert full.ndcg_at_10 == pytest.approx(only_answerable.ndcg_at_10)
