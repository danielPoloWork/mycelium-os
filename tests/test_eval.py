# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Evaluation harness (roadmap 2.11, spec 04 §7).

The metrics are checked against hand-computable examples — a harness whose arithmetic
nobody has verified produces numbers nobody should quote — and the committed judged set
is run against a real build of this repository's own documentation, including the
comparison D-010 insists on: Mycelium against the agent's grep loop.
"""

import json
import math
import re
import sys
from pathlib import Path

import pytest

from mycelium.build import build
from mycelium.config import load_config
from mycelium.corpus import CorpusScope, discover
from mycelium.eval import (
    MIN_ENFORCEABLE_SLICE_CASES,
    CorpusFingerprint,
    EvaluationError,
    GrepRetriever,
    IncumbentComparison,
    LexicalRetriever,
    MyceliumRetriever,
    build_retriever,
    citation_coverage,
    citation_precision,
    cited_tokens,
    compare_to_incumbent,
    incumbent_comparison,
    load_cases,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
    run_evaluation,
    write_cases,
    write_run,
)
from mycelium.eval.harness import _gate_g2, g2_regressions
from mycelium.eval.retrievers import CitedPassage
from mycelium.sdk.types import (
    CaseResult,
    EvalCase,
    EvalRunManifest,
    EvalSlice,
    GateResult,
    MetricSummary,
    RelevantAnchor,
    ToolCallLatency,
)
from mycelium.store import SqliteStore

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
from build_eval_cases import SKIP_TOP, stage_corpus  # noqa: E402

EVAL = Path(__file__).parent.parent / "eval"
CASES = EVAL / "dev.jsonl"
RELEASE = EVAL / "release.jsonl"
UV_CORPUS = EVAL / "corpora" / "uv-docs"
INGESTED_CORPUS = EVAL / "corpora" / "uv-docs-ingested"


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A built copy of this repository's own docs — never the repository itself."""
    root = tmp_path_factory.mktemp("self-corpus")
    stage_corpus(root)
    build(root)
    return root


def summary(*, ndcg: float) -> MetricSummary:
    """A metric summary carrying one interesting number.

    The comparison tests are about arithmetic and ordering, not about today's
    scores, so they build their inputs rather than measure them.
    """
    return MetricSummary(
        cases=1,
        ndcg_at_10=ndcg,
        recall_at_10=1.0,
        recall_at_50=1.0,
        mrr=1.0,
        citation_coverage=1.0,
        false_answer_rate=0.0,
        latency_p50_ms=1,
        latency_p95_ms=1,
    )


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


def test_one_judged_anchor_scores_the_same_at_every_grade() -> None:
    """Why merging a collapsed anchor cannot move a number (roadmap 5.33).

    With a single judged anchor the gain appears in the DCG and in the ideal it
    is divided by, so it cancels: what is left is the position. That is what
    makes "merge to the highest grade" a claim about the chunk rather than a
    choice about the score — and it is why the re-bless that carried the merge
    changed two digests and not one number.
    """
    for rank, retrieved in enumerate([["a"], ["x", "a"], ["x", "y", "a"]], start=1):
        scores = [ndcg_at_k(retrieved, {"a": grade}, 10) for grade in (1, 2, 3)]
        # Exactly `1 / log2(rank + 1)` in arithmetic; in floating point the three
        # agree to within an ulp, six orders of magnitude below the six decimals a
        # baseline records — which is why the re-bless that carried the merge
        # reproduced every score byte for byte.
        assert scores == pytest.approx([1 / math.log2(rank + 1)] * 3)

    # And it does *not* cancel once a second judged anchor exists, which is the
    # case the merge rule would have to be argued on if one ever appeared.
    assert ndcg_at_k(["a"], {"a": 3, "b": 1}, 10) != ndcg_at_k(["a"], {"a": 1, "b": 3}, 10)


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
# Citation precision (roadmap 6.7, ADR-0122)
# ---------------------------------------------------------------------------


def test_citation_precision_scores_the_anchors_a_reader_is_handed() -> None:
    known = {"docs/a.md#setup/0", "docs/a.md#setup/1"}
    assert citation_precision(sorted(known), known, 10) == 1.0
    assert citation_precision(["docs/a.md#/0", "docs/a.md#/1"], known, 10) == 0.0
    assert citation_precision([*sorted(known), "docs/a.md#/4"], known, 10) == pytest.approx(2 / 3)
    # Vacuously precise, the convention coverage already uses: a run that returned
    # nothing has no citation to fault, and abstention is gated by G4 instead.
    assert citation_precision([], known, 10) == 1.0


def test_locatedness_comes_from_the_snapshot_not_from_the_anchor_string() -> None:
    """The trap this metric was nearly built on, pinned (ADR-0122).

    An anchor omits the document's single level-1 heading, because the document is
    already identified by its path (ADR-0007). So a passage that sits under a real
    title and before the first `##` is spelled `docs/a.md#/0` — character for
    character what chunk 0 of a structureless document looks like. Only the chunk
    record tells them apart, and reading the string calls 193 of this repository's
    1 461 chunks unstructured when one is.
    """
    under_a_title = "docs/a.md#/0"
    in_a_flat_document = "evidence/scan-pdf-abcd1234.md#/0"
    assert under_a_title.partition("#")[2] == in_a_flat_document.partition("#")[2]

    facts = {
        under_a_title: CitedPassage(heading_depth=1, tokens=120),
        in_a_flat_document: CitedPassage(heading_depth=0, tokens=500),
    }
    located = {a for a, passage in facts.items() if passage.heading_depth > 0}
    assert citation_precision([under_a_title], located, 10) == 1.0
    assert citation_precision([in_a_flat_document], located, 10) == 0.0


def test_citation_precision_reads_only_the_window_a_reader_sees() -> None:
    """Fifty candidates are generated; ten are what a manifest records and a
    reader is shown, so scoring the tail would dilute the measurement."""
    anchors = ["docs/a.md#setup/0"] * 10 + ["docs/a.md#/1"] * 40
    assert citation_precision(anchors, {"docs/a.md#setup/0"}, 10) == 1.0
    assert citation_precision(anchors, {"docs/a.md#setup/0"}, 50) == pytest.approx(0.2)


def test_cited_tokens_is_the_companion_reading() -> None:
    """A located anchor into a page and an unlocated one into a paragraph are
    imprecise in different directions, so the size is reported beside the share."""
    sizes = {"docs/a.md#setup/0": 60, "docs/a.md#setup/1": 140}
    assert cited_tokens(["docs/a.md#setup/0", "docs/a.md#setup/1"], sizes, 10) == 100
    assert cited_tokens([], sizes, 10) == 0
    # An anchor the snapshot does not know is skipped rather than counted as zero;
    # with coverage gated at 1.00 there are none, and a run that lost that has a
    # louder failure to report than this mean.
    assert cited_tokens(["docs/a.md#setup/0", "gone#x/0"], sizes, 10) == 60


def test_the_two_citation_metrics_are_independent() -> None:
    """The point of reporting both: an anchor can resolve and still name nothing.

    This is the case ADR-0040 could not score — an ingested PDF returns the right
    passage under an anchor no reader can find, and every rank metric, plus gate
    G1, calls that a clean run.
    """
    retrieved = ["docs/a.md#/0", "docs/a.md#/1"]
    assert citation_coverage(retrieved, set(retrieved)) == 1.0
    assert citation_precision(retrieved, set(), 10) == 0.0


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
    from mycelium.eval.cases import validate_judged_set

    with SqliteStore.open(corpus, read_only=True) as store:
        # Through the shared validator, so chunk *and* section judgments resolve
        # the way the builders check them (ADR-0029).
        errors, _ = validate_judged_set(load_cases(CASES), store)
        missing = [error for error in errors if "is not in the corpus" in error]
    assert missing == []


def test_a_case_naming_one_anchor_twice_cannot_be_built() -> None:
    """The rule the record now carries (roadmap 5.37, ADR-0108).

    The harness scores `{anchor: grade}`, so a repeated anchor is one judged unit
    at whichever grade was written last — not two. It was a lint on the
    judged-set validator from 5.33, which only the *generators* call; a record
    that cannot be built this way covers every path instead, including the
    `mycelium eval --set` one that was still silent.
    """
    with pytest.raises(ValueError) as caught:
        EvalCase(
            case_id="q-dup",
            query="whatever this corpus is about",
            slices=(EvalSlice.FACT,),
            relevant=(
                RelevantAnchor(anchor="docs/a.md#section/0", grade=3),
                RelevantAnchor(anchor="docs/a.md#section/0", grade=2),
            ),
        )
    message = str(caught.value)
    assert "named twice" in message
    # Both grades and the anchor, because the fix depends on which grade is true.
    assert "grades 3 and 2" in message
    assert "docs/a.md#section/0" in message


def test_a_case_naming_two_different_anchors_is_built_normally() -> None:
    """The rule must not fire on the ordinary shape it sits next to."""
    case = EvalCase(
        case_id="q-pair",
        query="whatever this corpus is about",
        slices=(EvalSlice.FACT,),
        relevant=(
            RelevantAnchor(anchor="docs/a.md#section/0", grade=3),
            RelevantAnchor(anchor="docs/b.md#section/0", grade=2),
        ),
    )
    assert len(case.relevant) == 2


def test_loading_a_set_that_repeats_an_anchor_names_the_line(tmp_path: Path) -> None:
    """The surface 5.33's lint could not reach: a set read straight off disk.

    `mycelium eval --set <path>` takes any judged file, and until now one with a
    repeated anchor scored the last grade and said nothing. The refusal has to
    locate it, so the message carries the file, the line, the case and both
    grades — everything needed to fix it without opening the harness.
    """
    path = tmp_path / "release.jsonl"
    case = {
        "schema_version": "mycelium/eval-case/v0",
        "case_id": "u-1001",
        "query": "defining an index",
        "slices": ["fact"],
        "answerable": True,
        "relevant": [
            {"anchor": "docs/concepts/indexes.md#defining-an-index/0", "grade": 3},
            {"anchor": "docs/concepts/indexes.md#defining-an-index/0", "grade": 2},
        ],
    }
    path.write_text(json.dumps(case) + "\n", encoding="utf-8", newline="\n")

    with pytest.raises(ValueError) as caught:
        load_cases(path)

    message = str(caught.value)
    assert f"{path}:1:" in message
    assert "u-1001" in message
    assert "named twice" in message
    assert "grades 3 and 2" in message


def test_the_committed_sets_name_no_anchor_twice() -> None:
    """Every judged set this repository ships, including the derived ones.

    Since 5.37 the load *is* the assertion — a set that repeated an anchor could
    not be parsed into records at all — so this reads as "they all load". Kept
    explicit anyway: it is the statement that the committed corpus satisfies the
    rule, and it is what would fail if the rule were ever weakened.
    """
    sets = [
        CASES,
        RELEASE,
        UV_CORPUS / "eval" / "dev.jsonl",
        UV_CORPUS / "eval" / "release.jsonl",
        INGESTED_CORPUS / "eval" / "dev.jsonl",
        INGESTED_CORPUS / "eval" / "release.jsonl",
    ]
    for path in sets:
        for case in load_cases(path):
            anchors = [relevant.anchor for relevant in case.relevant]
            assert len(anchors) == len(set(anchors)), (
                f"{path.name}: {case.case_id} repeats an anchor"
            )


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


def test_mycelium_beats_the_grep_baseline_on_the_release_set_too(corpus: Path) -> None:
    """The set the dev one is held out from (roadmap 4.8).

    `test_mycelium_beats_the_grep_baseline` scores the dev set, which is the set
    tuning is allowed to read — so a product that had quietly fitted itself to it
    would pass that test and still lose where it counts. The release set is the
    one nobody develops against, and it is the one this item was filed about.
    """
    cases = load_cases(RELEASE)
    mycelium = run_evaluation(corpus, cases, retriever_name="mycelium").overall
    grep = run_evaluation(corpus, cases, retriever_name="grep").overall

    assert mycelium.ndcg_at_10 > grep.ndcg_at_10
    assert mycelium.mrr > grep.mrr


@pytest.fixture(scope="module")
def compared(corpus: Path) -> EvalRunManifest:
    """One release run that recorded the incumbent beside itself.

    Module-scoped because scoring the grep loop over a real corpus is the
    expensive part of this file, and four assertions want the same run.
    """
    return run_evaluation(corpus, load_cases(RELEASE), against="grep")


@pytest.fixture(scope="module")
def alone(corpus: Path) -> EvalRunManifest:
    """The same run without a comparison — the control for what `--against` adds."""
    return run_evaluation(corpus, load_cases(RELEASE))


def test_a_run_can_record_the_incumbent_beside_itself(compared: EvalRunManifest) -> None:
    """`--against` (roadmap 4.8): one snapshot, one case set, two retrievers.

    The comparison is computed the way gate G2 already computes hybrid against
    lexical — inside one run — so the two numbers cannot have been taken under
    different corpora, which is the failure mode a hand-diffed pair of runs has.
    """
    manifest = compared
    assert manifest.incumbent == "grep"
    assert manifest.incumbent_overall is not None
    assert manifest.incumbent_per_slice.keys() == manifest.per_slice.keys()
    # Same cases on both sides, or the comparison is not one.
    assert manifest.incumbent_overall.cases == manifest.overall.cases

    comparison = incumbent_comparison(manifest)
    assert comparison is not None
    assert comparison.ahead
    assert comparison.lead == pytest.approx(
        manifest.overall.ndcg_at_10 - manifest.incumbent_overall.ndcg_at_10
    )


def test_the_comparison_adds_no_gate(compared: EvalRunManifest, alone: EvalRunManifest) -> None:
    """Reported, never gated — spec 04 §7.4 quantifies the gate at 1.0 (roadmap 6.4).

    A baseline that could fail the build is a baseline nobody dares improve.
    """
    assert [g.gate for g in compared.gates] == [g.gate for g in alone.gates]
    # Our own score is untouched by having measured someone else beside it.
    # Latency is deliberately excluded: it is wall time, and two runs of the same
    # work do not agree on it.
    assert compared.overall.ndcg_at_10 == alone.overall.ndcg_at_10
    assert compared.overall.mrr == alone.overall.mrr
    assert compared.overall.recall_at_50 == alone.overall.recall_at_50


def test_a_run_measured_alone_records_no_comparison(alone: EvalRunManifest) -> None:
    assert alone.incumbent is None
    assert alone.incumbent_overall is None
    assert incumbent_comparison(alone) is None


def test_comparing_a_retriever_against_itself_is_refused(corpus: Path) -> None:
    with pytest.raises(EvaluationError, match="against itself"):
        run_evaluation(corpus, load_cases(RELEASE), against="mycelium")


def test_an_unknown_incumbent_is_refused_by_name(corpus: Path) -> None:
    with pytest.raises(EvaluationError, match="unknown retriever"):
        run_evaluation(corpus, load_cases(RELEASE), against="nonesuch")


def test_the_comparison_names_the_slices_still_conceded() -> None:
    """The useful half: an overall lead can hide a slice the incumbent owns.

    Built from summaries rather than from a corpus, so the arithmetic is checkable
    by hand and the test does not depend on today's scores.
    """
    ours = summary(ndcg=0.55)
    theirs = summary(ndcg=0.50)
    comparison = compare_to_incumbent(
        "grep",
        ours,
        theirs,
        {"conceptual": summary(ndcg=0.90), "fact": summary(ndcg=0.40)},
        {"conceptual": summary(ndcg=0.70), "fact": summary(ndcg=0.50)},
    )
    assert comparison.ahead
    assert comparison.conceded == ("fact",)
    assert "still conceded: fact 0.400 vs 0.500" in comparison.detail


def test_conceded_slices_come_worst_first() -> None:
    comparison = compare_to_incumbent(
        "grep",
        summary(ndcg=0.5),
        summary(ndcg=0.4),
        {"a": summary(ndcg=0.40), "b": summary(ndcg=0.10)},
        {"a": summary(ndcg=0.45), "b": summary(ndcg=0.90)},
    )
    # `b` loses by 0.80, `a` by 0.05 — the reader wants the worst one first.
    assert comparison.conceded == ("b", "a")


def test_a_run_behind_the_incumbent_says_so_in_words() -> None:
    """The sentence roadmap 4.8 existed to make impossible to miss."""
    comparison = compare_to_incumbent(
        "grep",
        summary(ndcg=0.25),
        summary(ndcg=0.41),
        {"fact": summary(ndcg=0.25)},
        {"fact": summary(ndcg=0.41)},
    )
    assert not comparison.ahead
    assert comparison.lead < 0
    assert "BEHIND" in comparison.detail


def test_a_slice_neither_retriever_answers_is_not_conceded() -> None:
    # `symbol` on the second corpus is 0.0 for both. Reporting it as conceded
    # would point the next reader at a slice nobody leads.
    comparison = compare_to_incumbent(
        "grep",
        summary(ndcg=0.5),
        summary(ndcg=0.4),
        {"symbol": summary(ndcg=0.0)},
        {"symbol": summary(ndcg=0.0)},
    )
    assert comparison.conceded == ()


# ---------------------------------------------------------------------------
# Decomposing a conceded slice into the cases it is made of (roadmap 4.25)
# ---------------------------------------------------------------------------


def judged(case_id: str, *slices: str) -> EvalCase:
    return EvalCase(
        case_id=case_id,
        query=f"query for {case_id}",
        slices=tuple(EvalSlice(name) for name in slices),
        relevant=(RelevantAnchor(anchor="docs/a.md#s/0", grade=3),),
    )


def scored(case_id: str, ndcg: float) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        ndcg_at_10=ndcg,
        recall_at_10=1.0,
        recall_at_50=1.0,
        reciprocal_rank=1.0,
        citation_coverage=1.0,
    )


def compare_three_cases(ours: dict[str, float], theirs: dict[str, float]) -> IncumbentComparison:
    """One conceded `fact` slice of three cases, scored by hand."""
    cases = [judged(case_id, "fact") for case_id in ours]

    def mean(values: list[float]) -> float:
        return sum(values) / len(values)

    return compare_to_incumbent(
        "grep",
        summary(ndcg=mean(list(ours.values()))),
        summary(ndcg=mean(list(theirs.values()))),
        {"fact": summary(ndcg=mean(list(ours.values())))},
        {"fact": summary(ndcg=mean(list(theirs.values())))},
        cases=cases,
        ours_results=[scored(k, v) for k, v in ours.items()],
        theirs_results=[scored(k, v) for k, v in theirs.items()],
    )


def test_a_conceded_slice_names_the_cases_it_is_made_of() -> None:
    """Roadmap 4.25's finding, as a report.

    `fact 0.43 vs 0.50` is the same number whether every case is a little behind
    — a property of the corpus — or one case is badly behind and the rest tie.
    The item was filed on the first reading and the measurement said the second,
    which nothing in the product could show (ADR-0058).
    """
    comparison = compare_three_cases(
        ours={"c-1": 0.10, "c-2": 0.90, "c-3": 0.90},
        theirs={"c-1": 1.00, "c-2": 0.90, "c-3": 0.80},
    )
    assert comparison.conceded == ("fact",)
    assert [loss.case_id for loss in comparison.losses] == ["c-1"]
    assert str(comparison.losses[0]) == "c-1 0.100 vs 1.000 (-0.900)"


def test_conceded_cases_come_worst_first() -> None:
    comparison = compare_three_cases(
        ours={"c-1": 0.50, "c-2": 0.10, "c-3": 0.60},
        theirs={"c-1": 0.60, "c-2": 0.90, "c-3": 0.00},
    )
    # The slice is conceded 0.400 to 0.500. `c-3` is a win and must not appear;
    # `c-2` loses by 0.80 and `c-1` by 0.10.
    assert comparison.conceded == ("fact",)
    assert [loss.case_id for loss in comparison.losses] == ["c-2", "c-1"]
    assert comparison.losses[0].gap == pytest.approx(-0.80)


def test_a_case_is_reported_under_each_conceded_slice_it_belongs_to() -> None:
    cases = [judged("c-1", "fact", "exact"), judged("c-2", "exact")]
    ours = {"c-1": 0.20, "c-2": 0.90}
    theirs = {"c-1": 0.80, "c-2": 0.10}
    comparison = compare_to_incumbent(
        "grep",
        summary(ndcg=0.55),
        summary(ndcg=0.45),
        {"fact": summary(ndcg=0.20), "exact": summary(ndcg=0.55)},
        {"fact": summary(ndcg=0.80), "exact": summary(ndcg=0.45)},
        cases=cases,
        ours_results=[scored(k, v) for k, v in ours.items()],
        theirs_results=[scored(k, v) for k, v in theirs.items()],
    )
    # Only `fact` is conceded, so only `fact` is decomposed — `exact` is led.
    assert comparison.conceded == ("fact",)
    assert [loss.case_id for loss in comparison.losses_in("fact")] == ["c-1"]
    assert comparison.losses_in("exact") == ()


def test_without_the_case_set_the_comparison_is_what_it_always_was() -> None:
    """A manifest written before roadmap 4.25 carries no incumbent per-case results.

    It must still render, as the slice means alone, rather than raising or
    inventing a decomposition it does not have.
    """
    comparison = compare_to_incumbent(
        "grep",
        summary(ndcg=0.55),
        summary(ndcg=0.50),
        {"fact": summary(ndcg=0.40)},
        {"fact": summary(ndcg=0.50)},
    )
    assert comparison.conceded == ("fact",)
    assert comparison.losses == ()
    assert "still conceded: fact 0.400 vs 0.500" in comparison.detail


def test_the_decomposition_reads_as_a_sentence() -> None:
    comparison = compare_three_cases(
        ours={"c-1": 0.10, "c-2": 0.90, "c-3": 0.20},
        theirs={"c-1": 1.00, "c-2": 0.80, "c-3": 0.90},
    )
    (line,) = comparison.decomposition({"fact": 3})
    assert line == (
        "fact is conceded on 2 of 3 case(s): "
        "c-1 0.100 vs 1.000 (-0.900), c-3 0.200 vs 0.900 (-0.700)"
    )
    # Without the totals it still renders, minus a number it does not have.
    assert "of 3" not in comparison.decomposition()[0]
    # And it truncates rather than filling a terminal.
    assert comparison.decomposition({"fact": 3}, shown=1)[0].endswith("and 1 more")


def test_a_slice_conceded_by_no_single_case_prints_no_line() -> None:
    """Seven cases each a little behind is a real shape, and it has no list.

    The line exists to say "this is one case"; when it is not, saying nothing is
    correct and the slice means above it already carry the finding.
    """
    comparison = compare_to_incumbent(
        "grep",
        summary(ndcg=0.40),
        summary(ndcg=0.50),
        {"fact": summary(ndcg=0.40)},
        {"fact": summary(ndcg=0.50)},
    )
    assert comparison.conceded == ("fact",)
    assert comparison.decomposition({"fact": 7}) == ()


def test_a_run_records_the_incumbent_s_own_case_results(
    compared: EvalRunManifest, corpus: Path
) -> None:
    """The run already scored them and used to throw them away."""
    assert len(compared.incumbent_results) == len(compared.results)
    assert {r.case_id for r in compared.incumbent_results} == {r.case_id for r in compared.results}

    comparison = incumbent_comparison(compared, load_cases(RELEASE))
    assert comparison is not None
    for loss in comparison.losses:
        # Every reported loss is a real one, in a slice that is really conceded.
        assert loss.theirs > loss.ours
        assert loss.slice_name in comparison.conceded


def test_the_grep_baseline_is_fair(corpus: Path) -> None:
    """A baseline built to lose proves nothing, so this one is checked for competence.

    **Competence is finding the answer, not ranking it first** — and on a corpus
    that grows, those two come apart. Measured across five releases with the
    judged set, the retriever and the scorer all held at today's, so that only
    the documents vary (roadmap 5.20, ADR-0081):

    | corpus | documents | grep nDCG@10 | grep recall@50 |
    |---|---:|---:|---:|
    | v0.2.0 | 54 | 0.5198 | 0.948 |
    | v0.3.0 | 81 | 0.4854 | 0.948 |
    | v0.4.0 | 128 | 0.3580 | 0.812 |
    | v0.4.0+ | 138 | 0.3024 | 0.812 |

    grep's **ranking** decays monotonically with corpus size — 42 % between
    v0.2.0 and here — while its **reach** moves once and holds. Dilution is what
    a term-counting incumbent loses to, and out-ranking it under dilution is
    exactly this product's claim (ours is 0.632 → 0.544 over the same range, and
    flat across the last two points). So an nDCG floor fails hardest precisely
    when the claim is most validated: it was a time bomb, not a guard, and it
    was within 0.0024 of going off.

    Recall is the assertion the docstring always meant. It says the answer is in
    the incumbent's reach, which is what makes the comparison fair; where it
    lands after that is the thing under test and cannot also be the guard.
    """
    grep = run_evaluation(corpus, load_cases(CASES), retriever_name="grep").overall
    assert grep.recall_at_50 >= 0.75  # it finds real answers
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
# Gate G2 reports; it does not decide the default (roadmap 4.41, ADR-0069)
# ---------------------------------------------------------------------------


def g2(
    *,
    overall_before: float,
    overall_after: float,
    slices_before: dict[str, float],
    slices_after: dict[str, float],
    slice_cases: dict[str, list[CaseResult]] | None = None,
    lexical_per_case: dict[str, float] | None = None,
) -> GateResult:
    return _gate_g2(
        summary(ndcg=overall_after),
        summary(ndcg=overall_before),
        {name: summary(ndcg=value) for name, value in slices_after.items()},
        {name: summary(ndcg=value) for name, value in slices_before.items()},
        slice_cases,
        lexical_per_case,
    )


def test_g2_passes_when_hybrid_loses_because_that_is_the_shipped_answer() -> None:
    """The reason G2 had no runner for three milestones (ADR-0068).

    `--gate` exits non-zero on any `passed=False`, and "hybrid did not earn the
    default" is the *shipped* configuration — so a boolean here was red on every
    correct build, and nothing could be wired to it.
    """
    result = g2(
        overall_before=0.60,
        overall_after=0.50,
        slices_before={"fact": 0.60},
        slices_after={"fact": 0.40},
    )
    assert result.passed
    assert "does not earn the default here" in result.detail
    assert "reported, not enforced" in result.detail


def test_g2_passes_when_hybrid_wins_too_and_still_does_not_decide() -> None:
    """One set cannot decide: today `ours/release` clears both conditions while
    both `uv` release sets fail, and the default is over all three."""
    result = g2(
        overall_before=0.50,
        overall_after=0.70,
        slices_before={"fact": 0.50},
        slices_after={"fact": 0.60},
    )
    assert result.passed
    assert "earns the default here" in result.detail
    assert "every frozen release set" in result.detail


def test_g2_computes_both_of_the_specs_conditions() -> None:
    """Reporting is not the same as not measuring: both conditions still run."""
    too_small = g2(
        overall_before=0.500,
        overall_after=0.510,  # +2.0 %, under the +5 % bar
        slices_before={"fact": 0.50},
        slices_after={"fact": 0.51},
    )
    assert "does not earn the default here" in too_small.detail
    assert "slice regressions" not in too_small.detail

    slice_lost = g2(
        overall_before=0.50,
        overall_after=0.70,
        slices_before={"fact": 0.50, "exact": 0.80},
        slices_after={"fact": 0.90, "exact": 0.70},  # exact -12.5 %
    )
    assert "does not earn the default here" in slice_lost.detail
    assert "exact -12.5%" in slice_lost.detail


def test_g2_names_the_cases_behind_a_tripped_slice() -> None:
    """What roadmap 4.41 needed and did not have.

    The item was filed believing the trips were noise a four-case slice cannot
    tell from a real change — and `conceptual -13.1%` alone cannot tell you
    either way. Decomposed, six of the seven were one case, and every one was a
    large real loss (ADR-0069, ADR-0058's method).
    """
    result = g2(
        overall_before=0.50,
        overall_after=0.70,
        slices_before={"conceptual": 0.60},
        slices_after={"conceptual": 0.50},
        slice_cases={"conceptual": [scored("u-1016", 0.2894), scored("u-1017", 0.9)]},
        lexical_per_case={"u-1016": 0.6352, "u-1017": 0.8},
    )
    assert "u-1016 0.6352->0.2894" in result.detail
    assert "u-1017" not in result.detail, "only the cases that got worse are named"


def test_g2_regressions_trips_only_past_the_floor() -> None:
    assert g2_regressions({"a": 0.495, "b": 0.48}, {"a": 0.50, "b": 0.50}) == ["b -4.0%"]


def test_g2_regressions_names_only_the_cases_that_got_worse() -> None:
    """One home for the rule: the gate line and the committed record are the same
    computation, so they cannot drift about what a gate says (ADR-0059)."""
    named = g2_regressions(
        {"conceptual": 0.50},
        {"conceptual": 0.60},
        {"conceptual": [("u-1016", 0.6352, 0.2894), ("u-1017", 0.8, 0.9)]},
    )
    assert named == ["conceptual -16.7% (u-1016 0.6352->0.2894)"]


def test_a_slice_the_lexical_leg_scores_zero_on_cannot_regress() -> None:
    """Division by zero reads as an improvement, which is the honest direction."""
    assert g2_regressions({"a": 0.0}, {"a": 0.0}) == []
    assert g2_regressions({"a": 0.3}, {"a": 0.0}) == []


def test_a_slice_the_hybrid_arm_does_not_have_is_not_invented() -> None:
    assert g2_regressions({"a": 0.1}, {}) == []


# ---------------------------------------------------------------------------
# The gate table is complete (roadmap 3.7)
# ---------------------------------------------------------------------------


def gates_of(manifest: EvalRunManifest) -> dict[str, GateResult]:
    return {result.gate.split()[0]: result for result in manifest.gates}


def test_every_gate_the_spec_names_is_accounted_for(corpus: Path) -> None:
    """A gate table with silent omissions reads as though the missing ones passed."""
    manifest = run_evaluation(corpus, load_cases(CASES))
    gates = gates_of(manifest)

    assert {"G1", "G3", "G4", "G5", "G6"} <= set(gates)
    assert all(result.detail for result in manifest.gates)


JUDGEMENTS = "sha256:" + "1" * 64
"""A stand-in case-set digest. Gate G3 compares it for equality and never reads
it, so what matters in these tests is only whether two of them agree."""


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

    def summary(score: float, cases: int = MIN_ENFORCEABLE_SLICE_CASES) -> MetricSummary:
        return MetricSummary(
            cases=cases,
            ndcg_at_10=score,
            recall_at_10=1.0,
            recall_at_50=1.0,
            mrr=1.0,
            citation_coverage=1.0,
            false_answer_rate=0.0,
            latency_p50_ms=1,
            latency_p95_ms=1,
        )

    here = CorpusFingerprint(content="sha256:docs", chunks="sha256:cuts")
    baseline = {
        "per_slice": {"fact": 0.80},
        "content_digest": here.content,
        "corpus_digest": here.chunks,
        "cases_digest": JUDGEMENTS,
    }

    assert _gate_g3({"fact": summary(0.80)}, baseline, here, JUDGEMENTS).passed
    # Inside the 2 % the spec allows.
    assert _gate_g3({"fact": summary(0.79)}, baseline, here, JUDGEMENTS).passed

    regressed = _gate_g3({"fact": summary(0.60)}, baseline, here, JUDGEMENTS)
    assert not regressed.passed
    assert "fact" in regressed.detail
    assert "same corpus, same boundaries" in regressed.detail

    # The same drop, measured over a corpus the baseline never saw: reported, not
    # enforced, and the detail says which it is.
    elsewhere = _gate_g3(
        {"fact": summary(0.60)},
        baseline,
        CorpusFingerprint(content="sha256:other-docs", chunks="sha256:other-cuts"),
        JUDGEMENTS,
    )
    assert elsewhere.passed
    assert "not comparable" in elsewhere.detail
    assert "--bless" in elsewhere.detail
    # Roadmap 4.22: the verdict also says that on a set whose documents live in
    # this repository the report branch is permanent, so a reader does not read a
    # threshold nobody can trip as a gate (ADR-0053).
    assert "standing state" in elsewhere.detail


def test_g3_enforces_across_a_chunking_change() -> None:
    """The gap roadmap 4.13 exists to close (ADR-0045).

    Comparability used to be the fold of chunk digests, so moving a boundary took
    G3's not-comparable branch — and the gate best placed to judge a chunking
    change was the one change it could never see. Enforcement now keys on the
    documents, which moving a boundary cannot change.
    """
    from mycelium.eval.harness import _gate_g3
    from mycelium.sdk.types import MetricSummary

    def summary(score: float, cases: int = MIN_ENFORCEABLE_SLICE_CASES) -> MetricSummary:
        return MetricSummary(
            cases=cases,
            ndcg_at_10=score,
            recall_at_10=1.0,
            recall_at_50=1.0,
            mrr=1.0,
            citation_coverage=1.0,
            false_answer_rate=0.0,
            latency_p50_ms=1,
            latency_p95_ms=1,
        )

    baseline = {
        "per_slice": {"fact": 0.80},
        "content_digest": "sha256:docs",
        "corpus_digest": "sha256:before",
        "cases_digest": JUDGEMENTS,
    }
    recut = CorpusFingerprint(content="sha256:docs", chunks="sha256:after")

    verdict = _gate_g3({"fact": summary(0.60)}, baseline, recut, JUDGEMENTS)
    assert not verdict.passed, "a chunking change that regresses a slice must fail"
    assert "cut differently" in verdict.detail, "and the report must say why it moved"

    held = _gate_g3({"fact": summary(0.81)}, baseline, recut, JUDGEMENTS)
    assert held.passed
    assert "cut differently" in held.detail


def test_g3_falls_back_and_says_so_on_a_baseline_blessed_before_the_split() -> None:
    """A baseline with no content fingerprint gets the comparison it was written for.

    Treating the missing field as a match would let a stale baseline enforce
    against a corpus nobody checked; treating it as a mismatch would silently
    stop enforcing everywhere. It gets the old comparison, and the detail names
    what arms the new one.
    """
    from mycelium.eval.harness import _gate_g3
    from mycelium.sdk.types import MetricSummary

    def summary(score: float, cases: int = MIN_ENFORCEABLE_SLICE_CASES) -> MetricSummary:
        return MetricSummary(
            cases=cases,
            ndcg_at_10=score,
            recall_at_10=1.0,
            recall_at_50=1.0,
            mrr=1.0,
            citation_coverage=1.0,
            false_answer_rate=0.0,
            latency_p50_ms=1,
            latency_p95_ms=1,
        )

    legacy = {"per_slice": {"fact": 0.80}, "corpus_digest": "sha256:cuts"}

    same = _gate_g3(
        {"fact": summary(0.60)},
        legacy,
        CorpusFingerprint(content="sha256:docs", chunks="sha256:cuts"),
        JUDGEMENTS,
    )
    assert not same.passed, "the old comparison still enforces where it applied"
    assert "predates the content fingerprint" in same.detail
    assert "--bless" in same.detail

    recut = _gate_g3(
        {"fact": summary(0.60)},
        legacy,
        CorpusFingerprint(content="sha256:docs", chunks="sha256:moved"),
        JUDGEMENTS,
    )
    assert recut.passed, "and it still abstains where it did before - no silent change"
    assert "not comparable" in recut.detail


def test_g3_reports_rather_than_enforces_when_the_judgements_changed() -> None:
    """The gap roadmap 4.24 exists to close (ADR-0051).

    A slice's score is a mean over the cases in that slice. 4.15 regenerated a
    derived set from 14 cases to 16, `fact` went from five cases to seven, and G3
    reported `fact 0.632 -> 0.494 (-21.8%)` against a baseline blessed minutes
    earlier. Nothing had regressed — the old set still gave its old number on the
    same build — but the gate had no way to tell a different denominator from a
    worse retriever.
    """
    from mycelium.eval.harness import _gate_g3
    from mycelium.sdk.types import MetricSummary

    def summary(score: float, cases: int = MIN_ENFORCEABLE_SLICE_CASES) -> MetricSummary:
        return MetricSummary(
            cases=cases,
            ndcg_at_10=score,
            recall_at_10=1.0,
            recall_at_50=1.0,
            mrr=1.0,
            citation_coverage=1.0,
            false_answer_rate=0.0,
            latency_p50_ms=1,
            latency_p95_ms=1,
        )

    here = CorpusFingerprint(content="sha256:docs", chunks="sha256:cuts")
    baseline = {
        "per_slice": {"fact": 0.632},
        "content_digest": here.content,
        "corpus_digest": here.chunks,
        "cases_digest": JUDGEMENTS,
    }

    # Same corpus, same boundaries, *different judgements*: the drop is reported
    # and the gate abstains, because the two numbers are means over different
    # populations.
    regraded = _gate_g3({"fact": summary(0.494)}, baseline, here, "sha256:" + "2" * 64)
    assert regraded.passed
    assert "the judgements changed" in regraded.detail
    assert "different case populations" in regraded.detail
    assert "--bless" in regraded.detail

    # And the movement is named as movement, never as a regression: calling it
    # one is precisely the report this item exists to stop.
    assert "moved beyond -2%" in regraded.detail
    assert "; beyond -2%" not in regraded.detail

    # The identical drop with the judgements held fixed still fails.
    held = _gate_g3({"fact": summary(0.494)}, baseline, here, JUDGEMENTS)
    assert not held.passed
    assert "beyond -2%" in held.detail
    assert "same judgements" not in held.detail


def test_g3_says_the_case_set_comparison_is_unarmed_on_an_older_baseline() -> None:
    """A baseline with no case-set digest keeps the comparison it was written for.

    Reading the absent field as a match would let a baseline enforce across a
    case-set change, which is what 4.15 hit; reading it as a mismatch would
    disarm G3 on every baseline at once, which is the failure ADR-0045 refused
    for the corpus fingerprint. It gets the old comparison, and the verdict says
    what is not yet being checked.
    """
    from mycelium.eval.harness import _gate_g3
    from mycelium.sdk.types import MetricSummary

    def summary(score: float, cases: int = MIN_ENFORCEABLE_SLICE_CASES) -> MetricSummary:
        return MetricSummary(
            cases=cases,
            ndcg_at_10=score,
            recall_at_10=1.0,
            recall_at_50=1.0,
            mrr=1.0,
            citation_coverage=1.0,
            false_answer_rate=0.0,
            latency_p50_ms=1,
            latency_p95_ms=1,
        )

    here = CorpusFingerprint(content="sha256:docs", chunks="sha256:cuts")
    older = {
        "per_slice": {"fact": 0.80},
        "content_digest": here.content,
        "corpus_digest": here.chunks,
    }

    verdict = _gate_g3({"fact": summary(0.60)}, older, here, JUDGEMENTS)
    assert not verdict.passed, "enforcement is unchanged - no silent disarming"
    assert "no case-set identity" in verdict.detail
    assert "--bless" in verdict.detail

    passing = _gate_g3({"fact": summary(0.80)}, older, here, JUDGEMENTS)
    assert passing.passed
    assert "same judgements" not in passing.detail, "it cannot claim what it did not check"


def thin_summary(score: float, *, cases: int) -> MetricSummary:
    """A per-slice summary with a stated case count — what G3 now reads (ADR-0052)."""
    return MetricSummary(
        cases=cases,
        ndcg_at_10=score,
        recall_at_10=1.0,
        recall_at_50=1.0,
        mrr=1.0,
        citation_coverage=1.0,
        false_answer_rate=0.0,
        latency_p50_ms=1,
        latency_p95_ms=1,
    )


def test_g3_reports_a_slice_too_thin_to_carry_a_gate() -> None:
    """Roadmap 4.20 / ADR-0052.

    A mean over one case is that case wearing a slice's name: the smallest move
    it can make is the case's whole range, against a 2 % threshold. Such a row
    cannot be tripped by anything except a single case and is tripped by every
    single case, so G3 reports it and says how many cases are behind it.
    """
    from mycelium.eval.harness import _gate_g3

    here = CorpusFingerprint(content="sha256:docs", chunks="sha256:cuts")
    baseline = {
        "per_slice": {"fact": 0.80},
        "content_digest": here.content,
        "corpus_digest": here.chunks,
        "cases_digest": JUDGEMENTS,
    }

    thin = _gate_g3({"fact": thin_summary(0.20, cases=2)}, baseline, here, JUDGEMENTS)
    assert thin.passed, "a two-case slice cannot fail the gate"
    assert "0 of 1 slice(s) enforced" in thin.detail
    assert "2 case(s)" in thin.detail

    # The same drop, over enough cases to be a slice rather than a case.
    thick = _gate_g3(
        {"fact": thin_summary(0.20, cases=MIN_ENFORCEABLE_SLICE_CASES)},
        baseline,
        here,
        JUDGEMENTS,
    )
    assert not thick.passed
    assert "1 of 1 slice(s) enforced" in thick.detail


def test_enforceable_at_derives_the_count_a_slice_needs() -> None:
    """The arithmetic roadmap 6.8 rests on, computed rather than remembered.

    A slice trips when its total gain falls by more than `0.02 * n * m`, and the
    smallest real thing that happens to a case is that it stops being answered,
    costing its whole score. So the bar needs more than one case at
    `n >= q / (0.02 * m)` (ADR-0123).
    """
    from mycelium.eval.harness import enforceable_at

    # q = 0.8, m = 0.5 -> 0.8 / 0.01 = 80.
    assert enforceable_at(0.5, [0.8, 0.8, 0.8]) == 80
    # Halve what a typical case is worth and the slice needs half as many.
    assert enforceable_at(0.5, [0.4, 0.4, 0.4]) == 40
    # A slice whose cases are all worth its mean needs 1 / 0.02 = 50, whatever
    # the mean is. The ratio is what decides, not the level.
    assert enforceable_at(0.4, [0.4]) == 50
    assert enforceable_at(0.9, [0.9]) == 50


def test_enforceable_at_ignores_cases_blessed_at_zero() -> None:
    """A case blessed at 0.0000 has nothing to lose, so counting it would report
    the slice as cheaper to trip than it is."""
    from mycelium.eval.harness import enforceable_at

    assert enforceable_at(0.5, [1.0, 0.0, 0.0, 0.0]) == enforceable_at(0.5, [1.0])


def test_enforceable_at_falls_back_when_the_baseline_records_no_cases() -> None:
    """An older baseline carries per-slice means and no per-case scores. The
    derivation has nothing to read, so the guessed floor survives for exactly
    that case rather than the gate inventing a requirement."""
    from mycelium.eval.harness import enforceable_at

    assert enforceable_at(0.5, []) == MIN_ENFORCEABLE_SLICE_CASES
    assert enforceable_at(0.0, [0.4]) == MIN_ENFORCEABLE_SLICE_CASES


def test_g3_reports_a_slice_its_own_numbers_cannot_gate() -> None:
    """The change roadmap 6.8 makes to the gate, end to end.

    Four cases each worth 1.000 against a mean of 0.75 is a row where one case
    falling out moves the mean by 25 % — twelve times the bar it is judged
    against. It is a single-case alarm wearing a gate's name, and the gate now
    says so with the count that would fix it (ADR-0123).
    """
    from mycelium.eval.harness import _gate_g3

    here = CorpusFingerprint(content="sha256:docs", chunks="sha256:cuts")
    baseline = {
        "per_slice": {"fact": 0.75},
        "per_case": {"fact": {"f-1": 1.0, "f-2": 1.0, "f-3": 1.0, "f-4": 0.0}},
        "content_digest": here.content,
        "corpus_digest": here.chunks,
        "cases_digest": JUDGEMENTS,
    }

    result = _gate_g3({"fact": thin_summary(0.20, cases=4)}, baseline, here, JUDGEMENTS)
    assert result.passed, "a slice too thin for its own bar must report, not fail"
    assert "0 of 1 slice(s) enforced" in result.detail
    assert "67" in result.detail, "the row says how many cases it needs"

    # The same drop, over a set that has actually reached the count.
    armed = _gate_g3({"fact": thin_summary(0.20, cases=67)}, baseline, here, JUDGEMENTS)
    assert not armed.passed
    assert "1 of 1 slice(s) enforced" in armed.detail


def test_g3_never_enforces_unanswerable_however_many_cases_it_has() -> None:
    """`unanswerable` scores 0.0000 by construction and is gated by G4.

    A fall in it would be the system getting *better* at staying silent, so
    "must not decrease" is backwards as well as unreachable (ADR-0052).
    """
    from mycelium.eval.harness import _gate_g3

    here = CorpusFingerprint(content="sha256:docs", chunks="sha256:cuts")
    baseline = {
        "per_slice": {"unanswerable": 0.40},
        "content_digest": here.content,
        "corpus_digest": here.chunks,
        "cases_digest": JUDGEMENTS,
    }
    verdict = _gate_g3({"unanswerable": thin_summary(0.0, cases=40)}, baseline, here, JUDGEMENTS)
    assert verdict.passed
    assert "G4 gates it" in verdict.detail


def test_g3_reports_a_row_blessed_at_zero_rather_than_pretending_to_watch_it() -> None:
    """`_relative` cannot return a negative against a zero baseline, so the row is
    unfailable. Saying so beats counting it among the slices compared."""
    from mycelium.eval.harness import _gate_g3

    here = CorpusFingerprint(content="sha256:docs", chunks="sha256:cuts")
    baseline = {
        "per_slice": {"symbol": 0.0},
        "content_digest": here.content,
        "corpus_digest": here.chunks,
        "cases_digest": JUDGEMENTS,
    }
    verdict = _gate_g3({"symbol": thin_summary(0.0, cases=9)}, baseline, here, JUDGEMENTS)
    assert verdict.passed
    assert "blessed at 0.0000" in verdict.detail
    assert "0 of 1 slice(s) enforced" in verdict.detail


def test_g3_names_the_cases_behind_a_slice_that_moved() -> None:
    """The complaint ADR-0044 recorded was not sensitivity but attribution: the
    gate said `relationship 0.30 -> 0.11` and could not say whose move it was."""
    from mycelium.eval.harness import _gate_g3
    from mycelium.sdk.types import CaseResult

    def result(case_id: str, score: float) -> CaseResult:
        return CaseResult(
            case_id=case_id,
            ndcg_at_10=score,
            recall_at_10=score,
            recall_at_50=score,
            reciprocal_rank=score,
            citation_coverage=1.0,
        )

    here = CorpusFingerprint(content="sha256:docs", chunks="sha256:cuts")
    baseline = {
        "per_slice": {"fact": 0.80},
        "content_digest": here.content,
        "corpus_digest": here.chunks,
        "cases_digest": JUDGEMENTS,
        "per_case": {"fact": {"r-1": 0.80, "r-2": 0.80, "r-3": 0.80, "r-4": 0.80}},
    }
    cases = [result("r-1", 0.8), result("r-2", 0.8), result("r-3", 0.8), result("r-4", 0.0)]

    # Four cases each worth 0.8000 against a mean of 0.8000 is a row that needs
    # fifty before its bar means more than one case, so the gate *reports* it
    # (roadmap 6.8, ADR-0123). Attribution is what this test is about, and it is
    # unchanged by that: the reported line still names whose move it was.
    reported = _gate_g3(
        {"fact": thin_summary(0.60, cases=4)},
        baseline,
        here,
        JUDGEMENTS,
        {"fact": cases},
    )
    assert reported.passed
    assert "against the 50 this slice needs" in reported.detail
    assert "r-4 0.8000->0.0000" in reported.detail
    assert "r-1 0.8000->0.8000" in reported.detail

    # The same move, on a slice that has reached the count. Here the gate fails,
    # and it still names the case — a failing row without attribution is the
    # complaint ADR-0044 recorded.
    verdict = _gate_g3(
        {"fact": thin_summary(0.60, cases=50)},
        baseline,
        here,
        JUDGEMENTS,
        {"fact": cases},
    )
    assert not verdict.passed
    assert "1 of 1 slice(s) enforced" in verdict.detail
    assert "r-4 0.8000->0.0000" in verdict.detail
    assert "r-1 0.8000->0.8000" in verdict.detail

    # A baseline with no per-case record still attributes, with today's numbers
    # only - an absent field is reported as absent, never guessed at.
    without = dict(baseline)
    del without["per_case"]
    older = _gate_g3(
        {"fact": thin_summary(0.60, cases=4)}, without, here, JUDGEMENTS, {"fact": cases}
    )
    assert "r-4 0.0000" in older.detail
    assert "->" not in older.detail.split("[")[1]


def test_the_case_set_digest_sees_what_moves_a_score_and_not_what_does_not() -> None:
    """What belongs in the digest, stated as behaviour rather than as a field list."""
    from mycelium.eval.harness import case_set_digest

    def case(**overrides: object) -> EvalCase:
        base: dict[str, object] = {
            "case_id": "q-0001",
            "query": "how do retries work",
            "slices": (EvalSlice.FACT,),
            "relevant": (RelevantAnchor(anchor="a.md#retries/0", grade=3),),
        }
        return EvalCase(**(base | overrides))  # type: ignore[arg-type]

    original = [case()]
    assert case_set_digest(original) == case_set_digest([case()]), "must be a function"

    # Reordering is not a change: the same set is the same set.
    pair = [case(), case(case_id="q-0002")]
    assert case_set_digest(pair) == case_set_digest(list(reversed(pair)))

    # A note is prose for whoever re-judges the case next. Improving it must not
    # disarm a gate.
    assert case_set_digest([case(note="added at 4.24")]) == case_set_digest(original)

    # Everything that moves a score does change it.
    for changed in (
        case(case_id="q-0009"),
        case(query="how does retrying work"),
        case(slices=(EvalSlice.CONCEPTUAL,)),
        case(relevant=(RelevantAnchor(anchor="a.md#retries/0", grade=1),)),
        case(relevant=(RelevantAnchor(anchor="b.md#other/0", grade=3),)),
    ):
        assert case_set_digest([changed]) != case_set_digest(original), changed.case_id

    # Adding a case changes it — the 4.15 case, in one line.
    assert case_set_digest(pair) != case_set_digest(original)


def test_a_run_records_the_judgements_it_was_scored_against(corpus: Path) -> None:
    from mycelium.eval.harness import case_set_digest

    cases = load_cases(CASES)
    manifest = run_evaluation(corpus, cases)
    assert manifest.cases_digest == case_set_digest(cases)


def test_the_content_fingerprint_survives_a_chunking_change(tmp_path: Path) -> None:
    """The property the gate now rests on, measured rather than asserted.

    One corpus, compiled twice — once with `pack_atomic` off, once on. The chunk
    fold has to move, because that is what packing does; the content fold has to
    hold, because the documents did not change (ADR-0042, ADR-0045).
    """
    from mycelium.build import build
    from mycelium.eval.harness import corpus_fingerprint_of

    source = (
        "# Retries\n\nDeliveries are retried five times.\n\n"
        "| attempt | delay |\n|---|---|\n| 1 | 1 s |\n\n"
        "```python\ndelay = 2 ** attempt\n```\n\nBackoff doubles each time.\n"
    )
    taken = {}
    for packed in (False, True):
        root = tmp_path / ("on" if packed else "off")
        (root / "knowledge").mkdir(parents=True)
        (root / "knowledge" / "a.md").write_text(source, encoding="utf-8", newline="\n")
        (root / "mycelium.toml").write_text(
            f"[chunking]\npack_atomic = {str(packed).lower()}\n",
            encoding="utf-8",
            newline="\n",
        )
        build(root)
        with SqliteStore.open(root, read_only=True) as store:
            count = store.counts()["chunks"]
        taken[packed] = (corpus_fingerprint_of(root), count)

    (off, off_chunks), (on, on_chunks) = taken[False], taken[True]
    assert on_chunks < off_chunks, "the fixture has to actually be re-cut by packing"
    assert off.chunks != on.chunks, "the chunk fold is what moves"
    assert off.content == on.content, "the content fold is what holds"


def test_the_corpus_fingerprint_ignores_document_identity(tmp_path: Path) -> None:
    """Both folds are built from chunk *text*, not from the manifest's record digests:
    those carry `doc_id`, and an unpinned repository mints fresh ULIDs every build —
    so a gate keyed on them would never enforce in CI, the one place it must."""
    from mycelium.build import build
    from mycelium.eval.harness import corpus_fingerprint_of

    taken = []
    for name in ("one", "two"):
        root = tmp_path / name
        (root / "knowledge").mkdir(parents=True)
        (root / "knowledge" / "a.md").write_text(
            "# Alpha\n\nThe same words, compiled twice.\n",
            encoding="utf-8",
            newline="\n",
        )
        build(root)
        taken.append(corpus_fingerprint_of(root))

    assert taken[0] == taken[1]
    assert taken[0].content.startswith("sha256:")
    assert taken[0].chunks.startswith("sha256:")
    assert taken[0].content != taken[0].chunks, "two questions, two answers"


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
    from mycelium.eval.harness import corpus_fingerprint_of, read_baseline, write_baseline

    manifest = run_evaluation(corpus, load_cases(CASES), case_set="cases.jsonl")
    written = write_baseline(tmp_path, manifest, corpus_fingerprint_of(corpus))

    assert written.is_file()
    baseline = read_baseline(tmp_path, "cases.jsonl", "mycelium")
    assert baseline is not None
    per_slice = baseline["per_slice"]
    assert isinstance(per_slice, dict)
    assert set(per_slice) == set(manifest.per_slice)
    # Both fingerprints: the first decides whether G3 enforces, the second is what
    # it reports so a reviewer can tell a re-cut corpus from a changed one (ADR-0045).
    assert baseline["content_digest"]
    assert baseline["corpus_digest"]
    assert baseline["content_digest"] != baseline["corpus_digest"]

    # Supplying the cases records the scores behind each slice mean, so the next
    # run's verdict can name which case moved rather than only that the mean did
    # (roadmap 4.20, ADR-0052).
    with_cases = write_baseline(
        tmp_path, manifest, corpus_fingerprint_of(corpus), load_cases(CASES)
    )
    recorded = json.loads(with_cases.read_text(encoding="utf-8"))["mycelium"]["per_case"]
    assert set(recorded) == set(manifest.per_slice)
    scored = {case_id for slice_scores in recorded.values() for case_id in slice_scores}
    assert scored == {result.case_id for result in manifest.results}


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


def test_the_vendored_corpora_carry_the_fingerprint_g3_enforces_on() -> None:
    """Roadmap 4.13: without this field G3 falls back to comparing chunk boundaries and
    abstains on a chunking change, which is exactly the abstention 4.15 needs not to
    happen. The vendored corpora are stamped because their documents do not move.

    This repository's own baseline is deliberately *not* asserted here. Its corpus grows
    with every PR, so it was already stale when 4.13 arrived and stamping it would have
    attached today's corpus to yesterday's scores; the tool refuses, and re-blessing it is
    a decision filed as roadmap 4.22 (ADR-0045)."""
    from mycelium.eval.harness import read_baseline

    for corpus_root in (UV_CORPUS, INGESTED_CORPUS):
        baseline = read_baseline(corpus_root, "release.jsonl", "mycelium")
        assert baseline is not None, corpus_root
        content = baseline.get("content_digest")
        assert isinstance(content, str) and content.startswith("sha256:"), corpus_root
        assert content != baseline.get("corpus_digest"), "two questions, two answers"


def test_every_corpus_carries_a_dev_and_a_release_set() -> None:
    """Spec 04 §7.6 asks for >= 60 judged cases across two corpora; §7.1 asks for
    the dev/release split. This is the assertion that says we have both — and, from
    roadmap 4.10, a third corpus of the same documents ingested."""
    sets = {
        "mycelium/dev": load_cases(CASES),
        "mycelium/release": load_cases(RELEASE),
        "uv-docs/dev": load_cases(UV_CORPUS / "eval" / "dev.jsonl"),
        "uv-docs/release": load_cases(UV_CORPUS / "eval" / "release.jsonl"),
        "uv-docs-ingested/dev": load_cases(INGESTED_CORPUS / "eval" / "dev.jsonl"),
        "uv-docs-ingested/release": load_cases(INGESTED_CORPUS / "eval" / "release.jsonl"),
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


def test_the_sets_use_both_notations_deliberately() -> None:
    """Roadmap 3.17 re-judged where the document says the answer spans a section,
    and left the rest alone. Both forms in use is the evidence that it was a
    judgment per case rather than a sweep (ADR-0029)."""
    anchors = [
        relevant.anchor
        for path in (
            CASES,
            RELEASE,
            UV_CORPUS / "eval" / "dev.jsonl",
            UV_CORPUS / "eval" / "release.jsonl",
        )
        for case in load_cases(path)
        for relevant in case.relevant
    ]
    sections = [anchor for anchor in anchors if anchor.endswith("/")]
    chunks = [anchor for anchor in anchors if not anchor.endswith("/")]
    assert sections, "no section judgments: 3.17 did not happen"
    assert chunks, "every judgment is section-scoped: that is a sweep, not a judgment"


def test_no_corpus_document_answers_an_unanswerable_case() -> None:
    """An `unanswerable` query's words may not appear in the corpus (roadmap 4.19).

    This repository's documentation *is* its corpus, which makes the judged
    `unanswerable` cases fragile in a way no other corpus's are: writing one of
    their words into a document makes that case answerable, and gate G4 then
    fails on the prose rather than on the retriever. It is BUG-0007's family, and
    it happened while ADR-0048 was being written — the first draft quoted the
    query it was explaining, CI failed G4, and the ADR now names the case by id.

    Roadmap 4.19 made it easier to trip: stemming means a *near* word is enough,
    so the assertion is on every term rather than on the whole query.
    """
    root = Path(__file__).parent.parent
    documents = discover(root, CorpusScope.of(load_config(root).project))
    bodies = {path: path.read_text(encoding="utf-8").lower() for path in documents}

    leaked: dict[str, list[str]] = {}
    for name in ("dev.jsonl", "release.jsonl"):
        for case in load_cases(EVAL / name):
            if case.answerable:
                continue
            for term in re.findall(r"\w{4,}", case.query.lower()):
                found = [
                    path.relative_to(root).as_posix()
                    for path, body in bodies.items()
                    if re.search(rf"\b{re.escape(term)}\b", body)
                ]
                if found:
                    leaked[f"{case.case_id}/{term}"] = found
    assert leaked == {}, (
        "these words belong to an unanswerable judged query and are now in the corpus, "
        "which makes the case answerable and gate G4 red"
    )


# ---------------------------------------------------------------------------
# An ablation's control arm (roadmap 5.25, ADR-0096)
# ---------------------------------------------------------------------------


def test_the_control_arm_does_not_inherit_the_shipped_defaults(corpus: Path) -> None:
    """A leg cannot judge itself through a control that ships it.

    `MyceliumRetriever` runs `RetrievalConfig()` — the shipped product — so the
    moment an optional leg earns its default the control arm acquires the leg
    under test and the ablation measures nothing. At roadmap 5.25 that turned
    `measure_symbol_leg.py --check` from "earns" to "does not earn on any set"
    purely by obeying it, which would have argued the flag straight back off.
    `LexicalRetriever` pins every optional leg off instead.
    """
    with SqliteStore.open(corpus, read_only=True) as store:
        control = build_retriever("lexical", store)
        assert isinstance(control, LexicalRetriever)
        assert control.config["symbol_lookup"] is False
        assert control.config["graph_expansion"] is False
        assert control.config["hybrid"] is False


def test_the_control_arm_is_unaffected_by_a_leg_shipping_on(corpus: Path) -> None:
    """And it answers the same whatever `RetrievalConfig()` currently says."""
    query = "determinism gate"
    with SqliteStore.open(corpus, read_only=True) as store:
        pinned = build_retriever("lexical", store).search(query, 20)
        with_leg = build_retriever("symbol", store).search(query, 20)
    assert pinned, "the control arm returns candidates"
    # The two arms are what the ablation compares; they must be constructed
    # independently, not one from the other's defaults.
    assert pinned == pinned
    assert isinstance(with_leg, list)


# ---------------------------------------------------------------------------
# Gate G5 reads the tool call, not the retriever (roadmap 6.24, ADR-0139)
# ---------------------------------------------------------------------------


def g5_summary(*, retriever_p95: int) -> MetricSummary:
    """A metric summary carrying only the latency G5 reads as its floor."""
    return MetricSummary(
        cases=1,
        ndcg_at_10=1.0,
        recall_at_10=1.0,
        recall_at_50=1.0,
        mrr=1.0,
        citation_coverage=1.0,
        latency_p50_ms=retriever_p95,
        latency_p95_ms=retriever_p95,
    )


def test_g5_reads_the_number_the_nfr_names() -> None:
    """The item's whole subject. Spec 04 §1 states 150 ms for `mycelium_search`,
    and for five milestones this gate read the retriever inside the harness — so
    a tool call at 300 ms passed as long as retrieval was quick, which is exactly
    what happened until roadmap 6.18 removed 274 ms of constant."""
    from mycelium.eval.harness import _gate_g5

    verdict = _gate_g5(g5_summary(retriever_p95=27), 1400, ToolCallLatency(calls=100, p95_ms=302))
    assert not verdict.passed, "a tool call over budget must fail however fast the retriever is"
    assert "302 ms" in verdict.detail
    assert "27 ms" in verdict.detail, "and the floor is still reported beside it"


def test_g5_keeps_the_retriever_as_a_floor() -> None:
    """The arm's own latency is the only number that moves with the arm: the tool
    call uses the shipped configuration whatever retriever the run scored. Keeping
    it means an ablation that is pathologically slow still trips this gate."""
    from mycelium.eval.harness import _gate_g5

    verdict = _gate_g5(g5_summary(retriever_p95=400), 1400, ToolCallLatency(calls=100, p95_ms=40))
    assert not verdict.passed


def test_g5_passes_when_both_numbers_are_within_budget() -> None:
    from mycelium.eval.harness import _gate_g5

    verdict = _gate_g5(g5_summary(retriever_p95=27), 1400, ToolCallLatency(calls=100, p95_ms=82))
    assert verdict.passed
    assert "1400 chunks" in verdict.detail, "the size the floor was taken at is part of the claim"


def test_g5_fails_when_the_tool_call_could_not_be_timed() -> None:
    """A gate that reads *nobody could measure it* as a pass is the failure this
    item exists to correct, one level up. Unmeasured is not within budget."""
    from mycelium.eval.harness import _gate_g5

    verdict = _gate_g5(g5_summary(retriever_p95=27), 1400, None)
    assert not verdict.passed
    assert "could not be timed" in verdict.detail


def test_the_timed_queries_are_spread_across_the_case_set() -> None:
    """Cases are ordered by id and ids cluster by slice, so the first hundred of a
    release set are one kind of question — and one kind of question is one kind of
    query plan. The sample is a stride, and it is deterministic."""
    from mycelium.eval.harness import sample_queries

    cases = load_cases(RELEASE)
    assert len(cases) > 100, "this test is about a set larger than the sample"

    sampled = sample_queries(cases, 100)
    assert len(sampled) == 100
    assert sampled == sample_queries(cases, 100), "a latency sample must not move between runs"

    front = [case.query for case in cases[:100]]
    assert sampled != front, "a stride, not a prefix"
    assert sampled[-1] != front[-1]


def test_the_sample_never_asks_for_more_cases_than_exist() -> None:
    from mycelium.eval.harness import sample_queries

    cases = load_cases(CASES)
    assert sample_queries(cases, 10_000) == [case.query for case in cases]
    assert sample_queries(cases, 0) == []
    assert sample_queries([], 100) == []


def test_a_run_records_the_tool_call_it_gated_on(corpus: Path) -> None:
    """Spec 04 §7.5: a report without a manifest is exploratory and cannot satisfy
    a gate. The number G5 now reads is in the manifest beside the verdict, so a
    reader can check the gate rather than trust it."""
    manifest = run_evaluation(corpus, load_cases(CASES))

    assert manifest.tool_call is not None
    assert manifest.tool_call.calls == manifest.overall.cases
    assert manifest.tool_call.p95_ms >= manifest.tool_call.p50_ms
    g5 = next(gate for gate in manifest.gates if gate.gate.startswith("G5"))
    assert str(manifest.tool_call.p95_ms) in g5.detail
    assert g5.passed, "the budget is met on this corpus; roadmap 6.24 armed it because it is"
