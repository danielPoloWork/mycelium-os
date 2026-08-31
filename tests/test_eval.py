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
from build_eval_cases import SKIP_TOP, stage_corpus  # noqa: E402

EVAL = Path(__file__).parent.parent / "eval"
CASES = EVAL / "dev.jsonl"
RELEASE = EVAL / "release.jsonl"
UV_CORPUS = EVAL / "corpora" / "uv-docs"


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
    assert {gate.gate for gate in manifest.gates} == {
        "G1 Citations",
        "G3 No regression",
        "G4 Abstention",
        "G5 Performance",
        "G6 Determinism",
    }  # G2 only when hybrid runs; G7 needs the synthesis lane (4.4)
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


def test_the_judged_corpus_is_the_one_the_gates_run_on(corpus: Path) -> None:
    """Staging copies the repository and lets `mycelium.toml` decide the corpus.

    It used to stage a hand-written list of paths, which meant judgments were
    validated against a *smaller* corpus than the gates score them on — an
    `unanswerable` case could pass the builder and be answerable in CI (ADR-0027).
    """
    assert ".git" in SKIP_TOP  # version control is not corpus
    assert "export" in SKIP_TOP  # nor is anything the compiler wrote
    with SqliteStore.open(corpus, read_only=True) as store:
        documents = {
            chunk.anchor.split("#")[0]
            for doc in store.document_ids()
            for chunk in store.chunks_of(doc)
        }
    assert "README.md" in documents
    assert any(path.startswith("docs/adr/") for path in documents)
    # `mycelium.toml` excludes it, so staging the whole tree still leaves it out.
    assert not any(path.startswith("docs/journal/") for path in documents)
    assert not any(path.startswith("eval/corpora/") for path in documents)


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


# ---------------------------------------------------------------------------
# The gate table is complete (roadmap 3.7)
# ---------------------------------------------------------------------------


def gates_of(manifest) -> dict:  # type: ignore[no-untyped-def]
    return {result.gate.split()[0]: result for result in manifest.gates}


def test_every_gate_the_spec_names_is_accounted_for(corpus: Path) -> None:
    """A gate table with silent omissions reads as though the missing ones passed."""
    manifest = run_evaluation(corpus, load_cases(CASES))
    gates = gates_of(manifest)

    assert {"G1", "G3", "G4", "G5", "G6"} <= set(gates)
    assert all(result.detail for result in manifest.gates)


def test_g3_says_so_when_no_baseline_is_committed(tmp_path: Path, corpus: Path) -> None:
    """An absent baseline must not read as a pass; it must read as an absence."""
    manifest = run_evaluation(corpus, load_cases(CASES))
    g3 = gates_of(manifest)["G3"]
    assert "--bless" in g3.detail


def test_g3_enforces_only_on_a_comparable_corpus(corpus: Path) -> None:
    """A regression check needs a controlled variable, and on a self-hosting corpus
    the corpus is not one: adding documentation moves slices without a line of
    retrieval code changing. CI caught exactly that on this gate's first run."""
    from mycelium.eval.harness import _gate_g3
    from mycelium.sdk.types import MetricSummary

    def summary(score: float) -> MetricSummary:
        return MetricSummary(
            cases=1,
            ndcg_at_10=score,
            recall_at_10=1.0,
            recall_at_50=1.0,
            mrr=1.0,
            citation_coverage=1.0,
            false_answer_rate=0.0,
            latency_p50_ms=1,
            latency_p95_ms=1,
        )

    here = "sha256:same"
    baseline = {"per_slice": {"fact": 0.80}, "corpus_digest": here}

    assert _gate_g3({"fact": summary(0.80)}, baseline, here).passed
    # Inside the 2 % the spec allows.
    assert _gate_g3({"fact": summary(0.79)}, baseline, here).passed

    regressed = _gate_g3({"fact": summary(0.60)}, baseline, here)
    assert not regressed.passed
    assert "fact" in regressed.detail

    # The same drop, measured over a corpus the baseline never saw: reported, not
    # enforced, and the detail says which it is.
    elsewhere = _gate_g3({"fact": summary(0.60)}, baseline, "sha256:different")
    assert elsewhere.passed
    assert "not comparable" in elsewhere.detail
    assert "--bless" in elsewhere.detail


def test_the_corpus_fingerprint_ignores_document_identity(tmp_path: Path) -> None:
    """It is folded from chunk *content* digests, not the manifest's record digests:
    those carry `doc_id`, and an unpinned repository mints fresh ULIDs every build —
    so a gate keyed on them would never enforce in CI, the one place it must."""
    from mycelium.build import build
    from mycelium.eval.harness import corpus_digest_of

    digests = []
    for name in ("one", "two"):
        root = tmp_path / name
        (root / "knowledge").mkdir(parents=True)
        (root / "knowledge" / "a.md").write_text(
            "# Alpha\n\nThe same words, compiled twice.\n",
            encoding="utf-8",
            newline="\n",
        )
        build(root)
        digests.append(corpus_digest_of(root))

    assert digests[0] == digests[1]
    assert digests[0].startswith("sha256:")


def test_g5_reports_the_corpus_it_measured(corpus: Path) -> None:
    """Passing on a small corpus is a floor, and the detail has to say so."""
    g5 = gates_of(run_evaluation(corpus, load_cases(CASES)))["G5"]
    assert g5.passed
    assert "150 ms budget" in g5.detail
    assert "reference profile" in g5.detail


def test_g6_is_delegated_not_silently_dropped(corpus: Path) -> None:
    g6 = gates_of(run_evaluation(corpus, load_cases(CASES)))["G6"]
    assert "determinism" in g6.detail.lower() or "golden" in g6.detail


def test_blessing_writes_a_baseline_that_g3_then_reads(tmp_path: Path, corpus: Path) -> None:
    from mycelium.eval.harness import read_baseline, write_baseline

    manifest = run_evaluation(corpus, load_cases(CASES), case_set="cases.jsonl")
    written = write_baseline(tmp_path, manifest)

    assert written.is_file()
    baseline = read_baseline(tmp_path, "cases.jsonl", "mycelium")
    assert baseline is not None
    assert set(baseline["per_slice"]) == set(manifest.per_slice)  # type: ignore[index]
    assert "corpus_digest" in baseline  # what makes the comparison comparable


def test_the_committed_baseline_covers_the_gated_case_set() -> None:
    """A gate whose baseline is missing from the repository gates nothing in CI.

    The *release* set is what CI gates, so it is the one that must be blessed —
    the dev set is scored beside it and reported, never gated (ADR-0027).
    """
    from mycelium.eval.harness import read_baseline

    baseline = read_baseline(Path("."), "release.jsonl", "mycelium")
    assert baseline is not None
    per_slice = baseline["per_slice"]
    assert isinstance(per_slice, dict)
    slices = {slice_.value for case in load_cases(RELEASE) for slice_ in case.slices}
    assert set(per_slice) >= slices - {"unanswerable"}
    assert baseline["corpus_digest"]  # blessed against a named corpus, not a mood


def test_both_corpora_carry_a_dev_and_a_release_set() -> None:
    """Spec 04 §7.6 asks for >= 60 judged cases across two corpora; §7.1 asks for
    the dev/release split. This is the assertion that says we have both."""
    sets = {
        "mycelium/dev": load_cases(CASES),
        "mycelium/release": load_cases(RELEASE),
        "uv-docs/dev": load_cases(UV_CORPUS / "eval" / "dev.jsonl"),
        "uv-docs/release": load_cases(UV_CORPUS / "eval" / "release.jsonl"),
    }
    assert sum(len(cases) for cases in sets.values()) >= 60
    # Disjoint by construction: a case that sits in both sets makes the split a
    # label rather than a separation.
    dev_ids = {case.case_id for name, cases in sets.items() if "/dev" in name for case in cases}
    release_ids = {
        case.case_id for name, cases in sets.items() if "/release" in name for case in cases
    }
    assert not dev_ids & release_ids
    for name, cases in sets.items():
        assert any(not case.answerable for case in cases), f"{name} has no unanswerable case"


# ---------------------------------------------------------------------------
# Judged-anchor granularity (roadmap 3.15, ADR-0029)
# ---------------------------------------------------------------------------


def test_a_section_judgment_is_satisfied_by_any_chunk_under_it() -> None:
    from mycelium.eval.metrics import credit_judgments

    judged = {"a.md#setup/": 3}
    credited = credit_judgments(["a.md#setup/7"], judged)
    assert credited == ["a.md#setup/"]
    assert ndcg_at_k(credited, judged, 10) == 1.0


def test_a_section_is_credited_once_however_many_of_its_chunks_come_back() -> None:
    """Without this a retriever fills the top ten with one section and scores a
    perfect run for finding a single thing (ADR-0029)."""
    from mycelium.eval.metrics import credit_judgments

    judged = {"a.md#setup/": 3, "b.md#other/": 3}
    credited = credit_judgments(
        ["a.md#setup/0", "a.md#setup/1", "a.md#setup/2", "b.md#other/4"], judged
    )
    assert credited == ["a.md#setup/", "a.md#setup/1", "a.md#setup/2", "b.md#other/"]
    assert recall_at_k(credited, judged, 10) == 1.0
    assert (
        recall_at_k(credit_judgments(["a.md#setup/0", "a.md#setup/1"], judged), judged, 10) == 0.5
    )


def test_a_chunk_judgment_still_means_that_chunk() -> None:
    from mycelium.eval.metrics import credit_judgments

    judged = {"a.md#setup/3": 3}
    assert credit_judgments(["a.md#setup/7"], judged) == ["a.md#setup/7"]
    assert ndcg_at_k(credit_judgments(["a.md#setup/7"], judged), judged, 10) == 0.0
    assert ndcg_at_k(credit_judgments(["a.md#setup/3"], judged), judged, 10) == 1.0


def test_an_exact_judgment_wins_over_a_section_one_for_the_same_chunk() -> None:
    """A set naming both means what it wrote: the chunk, and the section as a
    weaker fallback."""
    from mycelium.eval.metrics import credit_judgments

    judged = {"a.md#setup/3": 3, "a.md#setup/": 1}
    assert credit_judgments(["a.md#setup/3", "a.md#setup/9"], judged) == [
        "a.md#setup/3",
        "a.md#setup/",
    ]


def test_a_judged_anchor_may_not_be_ambiguous() -> None:
    """A heading can slug to digits, so a bare `doc#2024` cannot be told apart
    from ordinal 2024 of the lead section. The trailing slash removes the guess."""
    from pydantic import ValidationError

    from mycelium.sdk.types import RelevantAnchor

    RelevantAnchor(anchor="a.md#2024/", grade=3)
    RelevantAnchor(anchor="a.md#2024/0", grade=3)
    with pytest.raises(ValidationError):
        RelevantAnchor(anchor="a.md#2024", grade=3)


def test_the_committed_sets_still_judge_chunks() -> None:
    """This item shipped the *notation*; re-judging the sets under it is a
    separate, deliberate act (roadmap 3.17), so nothing here has moved yet."""
    for path in (CASES, RELEASE):
        for case in load_cases(path):
            for relevant in case.relevant:
                assert not relevant.anchor.endswith("/"), f"{case.case_id} already section-scoped"
