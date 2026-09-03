# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The evaluation harness (spec 04 §7).

Runs a judged case set against a retriever, reports per-slice and overall metrics,
evaluates the gates that are meaningful at this stage, and writes a run manifest —
because "a report without a manifest is exploratory and cannot satisfy a gate"
(§7.5).

Every gate spec 04 §7.3 names is accounted for here — enforced, delegated, or
explained. A gate table with silent omissions reads as though the missing ones
were satisfied:

======  ==========================================================================
G1      **Enforced.** Citation coverage must be 1.00 — every returned anchor
        resolves in the snapshot. It is the failure this product cannot tolerate.
G2      **Enforced when the hybrid retriever runs** (roadmap 3.3). Hybrid must
        beat the lexical baseline by ≥ 5 % nDCG@10 with no slice worse than
        −2 %, on the same cases and the same snapshot; otherwise the shipped
        default is lexical-only and says so.
G3      **Enforced against a committed baseline** (roadmap 3.7). No slice may
        regress more than 2 % against `eval/baselines/<set>.json`. Without one
        the gate says so rather than passing silently; `--bless` writes it.
        Comparability is judged on the *documents*, not on where their chunk
        boundaries fall, so a chunking change is gated rather than excused —
        the blindness roadmap 4.13 removed (ADR-0045).
G4      **Enforced.** False-answer rate on `unanswerable` cases ≤ 5 %: a query
        whose vocabulary the corpus does not contain must return nothing rather
        than confident noise.
G5      **Enforced, with its limit stated.** Query p95 ≤ 150 ms (spec 04 §1),
        measured on the corpus at hand and reported with its chunk count — the
        budget is defined at the 10⁵-chunk reference profile, so passing here is
        a floor rather than the measurement the spec asks for.
G6      **Delegated.** Determinism is a compiler gate with its own CI job and
        its own golden (ADR-0012); reported so the table is complete.
G7      Not applicable: grounding gates a *synthesized document's* promotion, and
        the synthesis lane arrives at roadmap 4.4.
======  ==========================================================================

Absolute quality targets are deliberately absent. Pre-GA the spec enforces
*relative* discipline (§7.3), so this harness reports numbers and compares
retrievers; it does not assert that nDCG must exceed some invented threshold.
"""

import json
import platform
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from mycelium.__about__ import __version__
from mycelium.build.publish import read_current
from mycelium.config import load_config
from mycelium.embedding import Embedder, EmbeddingError, build_embedder
from mycelium.eval.metrics import (
    citation_coverage,
    credit_judgments,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)
from mycelium.eval.retrievers import Retriever, build_retriever, resolvable_anchors
from mycelium.sdk.identity import digest_json, digest_text, new_ulid
from mycelium.sdk.types import (
    CaseResult,
    EvalCase,
    EvalRunManifest,
    GateResult,
    MetricSummary,
    Toolchain,
)
from mycelium.store import STORE_DIRNAME, SqliteStore

__all__ = [
    "BASELINES_DIRNAME",
    "EVAL_DIRNAME",
    "QUERY_BUDGET_P95_MS",
    "CorpusFingerprint",
    "baseline_path",
    "corpus_fingerprint_of",
    "read_baseline",
    "write_baseline",
    "write_run",
    "MAX_FALSE_ANSWER_RATE",
    "RETRIEVAL_LIMIT",
    "EvaluationError",
    "IncumbentComparison",
    "compare_to_incumbent",
    "incumbent_comparison",
    "run_evaluation",
]

EVAL_DIRNAME: Final = "eval"
RETRIEVAL_LIMIT: Final = 50
"""Deep enough for Recall@50, which is the widest metric the spec asks for."""

MAX_FALSE_ANSWER_RATE: Final = 0.05
"""Gate G4 for v1; tightens at 1.0."""

QUERY_BUDGET_P95_MS: Final = 150
"""Gate G5: the end-to-end query budget spec 04 §1 sets."""

BASELINES_DIRNAME: Final = "baselines"
"""Committed per-slice scores a release is measured against (gate G3)."""


class EvaluationError(RuntimeError):
    """The run could not be performed at all."""


def _percentile(values: Sequence[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def _summarise(cases: Sequence[EvalCase], results: Sequence[CaseResult]) -> MetricSummary:
    """Average a set of case results, keeping answerable and unanswerable apart.

    Ranking metrics are averaged over *answerable* cases only: an unanswerable
    case has no relevant anchor, so scoring it as nDCG 0 would drag the mean down
    for behaving correctly. Its correctness is the false-answer rate instead.
    """
    by_id = {case.case_id: case for case in cases}
    answerable = [r for r in results if by_id[r.case_id].answerable]
    unanswerable = [r for r in results if not by_id[r.case_id].answerable]
    latencies = [r.latency_ms for r in results]

    def mean(values: Sequence[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    false_answers = [r for r in unanswerable if not r.abstained]
    return MetricSummary(
        cases=len(results),
        ndcg_at_10=mean([r.ndcg_at_10 for r in answerable]),
        recall_at_10=mean([r.recall_at_10 for r in answerable]),
        recall_at_50=mean([r.recall_at_50 for r in answerable]),
        mrr=mean([r.reciprocal_rank for r in answerable]),
        citation_coverage=mean([r.citation_coverage for r in results]),
        false_answer_rate=(len(false_answers) / len(unanswerable)) if unanswerable else 0.0,
        latency_p50_ms=_percentile(latencies, 0.50),
        latency_p95_ms=_percentile(latencies, 0.95),
    )


def _evaluate_case(case: EvalCase, retriever: Retriever, resolvable: set[str]) -> CaseResult:
    judged = {relevant.anchor: relevant.grade for relevant in case.relevant}
    started = time.perf_counter()
    retrieved = retriever.search(case.query, RETRIEVAL_LIMIT)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    # Scored against the judgments the ranking satisfies, not the raw anchors: a
    # judgment may name a section, and a section is credited once however many of
    # its chunks come back (ADR-0029). `retrieved` is what the manifest records,
    # because a reader checking a case wants the anchors, not their resolution.
    credited = credit_judgments(retrieved, judged)

    return CaseResult(
        case_id=case.case_id,
        retrieved=tuple(retrieved[:10]),  # the manifest records what a reader would see
        ndcg_at_10=ndcg_at_k(credited, judged, 10),
        recall_at_10=recall_at_k(credited, judged, 10),
        recall_at_50=recall_at_k(credited, judged, 50),
        reciprocal_rank=reciprocal_rank(credited, judged),
        citation_coverage=citation_coverage(retrieved, resolvable),
        abstained=not retrieved,
        latency_ms=elapsed_ms,
    )


def _gate_g2(
    hybrid: MetricSummary,
    baseline: MetricSummary,
    hybrid_slices: dict[str, MetricSummary],
    baseline_slices: dict[str, MetricSummary],
) -> GateResult:
    """Gate G2 — hybrid must *earn* the default (spec 04 §7.3).

    Two conditions, both relative to the lexical baseline on the same cases:
    ≥ +5 % nDCG@10 overall, and no slice worse than −2 %. A slice the baseline
    scores 0 on cannot regress, so it is reported as an improvement rather than a
    division by zero.
    """
    overall_delta = _relative(hybrid.ndcg_at_10, baseline.ndcg_at_10)
    regressions = []
    for name, summary in sorted(hybrid_slices.items()):
        before = baseline_slices.get(name)
        if before is None:
            continue
        delta = _relative(summary.ndcg_at_10, before.ndcg_at_10)
        if delta < -0.02:
            regressions.append(f"{name} {delta:+.1%}")

    passed = overall_delta >= 0.05 and not regressions
    verdict = "earns the default" if passed else "does not earn the default; ship lexical-only"
    detail = (
        f"hybrid nDCG@10 {hybrid.ndcg_at_10:.4f} vs lexical {baseline.ndcg_at_10:.4f} "
        f"({overall_delta:+.1%}; needs +5.0%)"
    )
    if regressions:
        detail += f"; slice regressions beyond -2%: {', '.join(regressions)}"
    return GateResult(gate="G2 Earn hybrid", passed=passed, detail=f"{detail} - {verdict}")


def _relative(after: float, before: float) -> float:
    if before == 0.0:
        return 1.0 if after > 0.0 else 0.0
    return (after - before) / before


@dataclass(frozen=True, slots=True)
class CorpusFingerprint:
    """Two questions about a published corpus, deliberately kept apart.

    Gate G3 needs a controlled variable, and until roadmap 4.13 it had only one
    fingerprint to ask about — the fold of chunk digests — which conflated *what
    the corpus says* with *where its boundaries fall*. That made the gate meant
    to catch a bad chunking change blind to chunking changes by construction: any
    change to boundaries moved the digest, so the gate took its
    "not comparable, reported not enforced" branch and said nothing about the one
    class of change it was best placed to judge (ADR-0045).

    ``content``
        What the corpus says: per document, a digest of its text as the published
        chunks carry it, with whitespace collapsed so the *placement* of the
        boundaries cannot reach it. Two builds of the same documents agree
        whether or not the chunker moved between them. This is what decides
        whether G3 enforces.

    ``chunks``
        How the corpus was cut: the fold of the chunks' own content digests —
        exactly the fingerprint BUG-0014 introduced, unchanged in meaning so a
        baseline blessed before this split still means what it said. Now it is
        *reported* rather than gated on, which is how a reviewer learns that
        boundaries moved and that G3 enforced across the move on purpose.

    Neither carries identity. Chunk digests are digests of text, and the content
    fold is built from those same texts, so a repository whose documents are not
    yet pinned — minting a fresh ULID per document on every build — produces the
    same fingerprints twice. A fold over anything identity-bearing would never
    match in CI, where every run starts from an empty store (ADR-0021).
    """

    content: str
    chunks: str

    def __bool__(self) -> bool:
        """Whether a fingerprint was taken at all — an unreadable store gives none."""
        return bool(self.content or self.chunks)


def corpus_fingerprint_of(root: Path, snapshot_id: str = "") -> CorpusFingerprint:
    """Fingerprint the published corpus at `root` — see :class:`CorpusFingerprint`.

    Both folds come from one pass over the published chunks, deliberately *not*
    from the manifest's `artifact_digests`: those fold chunk *records*, which
    carry `doc_id` (ADR-0021, BUG-0014).

    Chunks are folded per document **in document order**, taken from each chunk's
    line span rather than from its anchor. Anchors sort lexicographically, so
    `…/10` precedes `…/2`, and the order in which a document's chunks concatenate
    would then depend on how many there are — which is the very thing the content
    fold must not be able to see.
    """
    try:
        with SqliteStore.open(root, read_only=True) as store:
            chunk_digests: list[str] = []
            documents: list[list[str]] = []
            for doc_id in store.document_ids():
                chunks = sorted(store.chunks_of(doc_id), key=lambda chunk: chunk.lines)
                chunk_digests.extend(chunk.chunk_digest for chunk in chunks)
                record = store.get_document(doc_id)
                body = " ".join(" ".join(chunk.text.split()) for chunk in chunks)
                documents.append([record.path if record else doc_id, digest_text(body)])
    except Exception:  # noqa: BLE001 - a fingerprint is never worth failing a run for
        return CorpusFingerprint(content="", chunks="")
    return CorpusFingerprint(
        content=digest_json(sorted(documents)),
        chunks=digest_json(sorted(chunk_digests)),
    )


def _gate_g3(
    per_slice: dict[str, MetricSummary],
    baseline: dict[str, object] | None,
    fingerprint: CorpusFingerprint,
) -> GateResult:
    """Gate G3 — no release may regress a protected slice by more than 2 % (spec 04 §7.3).

    A regression check needs a controlled variable, and on a self-hosting corpus
    the corpus is not one: this project's documentation grows with every change,
    and adding documents moves per-slice scores without anything about retrieval
    having changed. The gate therefore **enforces when the corpus is the same one
    the baseline was taken on, and reports when it is not** — naming the change
    rather than failing on it. Anything else makes G3 fire on documentation and
    trains everyone to re-bless, which is how a gate becomes decoration.

    "The same corpus" means *the same documents*, and it stopped meaning that
    when it was defined as the fold of chunk digests: a chunking change moves
    every boundary, so the gate best placed to judge one took its
    not-comparable branch and abstained (roadmap 4.13, ADR-0045). Enforcement now
    keys on :attr:`CorpusFingerprint.content`, which the placement of the
    boundaries cannot reach, and the chunk fold is *reported* — so a chunking
    change is gated and visibly named, rather than silently excused.

    A baseline blessed before that split carries no content fingerprint. Rather
    than guess, the gate falls back to the comparison that baseline was written
    for and says so, naming `--bless` as what arms the stronger one. Silently
    treating a missing field as a match would let a stale baseline enforce
    against a corpus nobody checked.

    The baseline is a committed file, not the previous run in `.mycelium/`: a
    gate comparing against whatever happens to be on this machine compares
    against nothing in CI, where every run starts empty. Establishing it is a
    deliberate act (`mycelium eval --bless`), so a regression can never be
    absorbed by quietly moving the line.
    """
    if not baseline:
        return GateResult(
            gate="G3 No regression",
            passed=True,
            detail=(
                "no committed baseline for this set; run `mycelium eval --bless` to "
                "establish one - until then there is nothing to regress against"
            ),
        )
    slices = baseline.get("per_slice")
    if not isinstance(slices, dict):
        return GateResult(
            gate="G3 No regression",
            passed=True,
            detail="the committed baseline records no per-slice scores; re-bless it",
        )

    regressions = []
    for name, summary in sorted(per_slice.items()):
        before = slices.get(name)
        if not isinstance(before, int | float):
            continue
        delta = _relative(summary.ndcg_at_10, float(before))
        if delta < -0.02:
            regressions.append(f"{name} {before:.4f} -> {summary.ndcg_at_10:.4f} ({delta:+.1%})")

    baseline_content = baseline.get("content_digest")
    baseline_chunks = baseline.get("corpus_digest")
    recut = baseline_chunks != fingerprint.chunks

    if isinstance(baseline_content, str) and baseline_content:
        same_corpus = baseline_content == fingerprint.content
        legacy = False
    else:
        # Blessed before the content fingerprint existed: compare on what that
        # baseline actually recorded, and say which comparison ran.
        same_corpus = not recut
        legacy = True

    fresh = sorted(set(per_slice) - set(slices))

    detail = f"{len(slices)} slice(s) compared"
    if fresh:
        detail += f"; new since the baseline: {', '.join(fresh)}"
    if regressions:
        detail += f"; beyond -2%: {'; '.join(regressions)}"
    if not same_corpus:
        detail += (
            "; the corpus has changed since the baseline was taken, so these numbers are "
            "not comparable - reported, not enforced. Re-bless deliberately with "
            "`mycelium eval --bless` once the corpus is the one you mean to measure"
        )
        return GateResult(gate="G3 No regression", passed=True, detail=detail)
    if legacy:
        detail += (
            "; this baseline predates the content fingerprint, so comparability was "
            "judged on chunk boundaries - re-bless with `mycelium eval --bless` to "
            "enforce across a chunking change (roadmap 4.13)"
        )
    elif recut:
        # The case roadmap 4.13 exists for: same documents, different boundaries.
        detail += (
            "; the same documents cut differently - a chunking change, enforced rather "
            "than excused (ADR-0045)"
        )
    else:
        detail += "; same corpus, same boundaries"
    if not regressions and not legacy:
        detail += ", no slice regressed"
    return GateResult(gate="G3 No regression", passed=not regressions, detail=detail)


def _gate_g5(overall: MetricSummary, chunks: int) -> GateResult:
    """Gate G5 — the query budget from spec 04 §1: p95 ≤ 150 ms end to end.

    Enforced on whatever corpus was run, and *reported with its size*, because
    the budget is defined against the 10⁵-chunk reference profile. Passing here
    is necessary and not sufficient: a small corpus that misses the budget is
    certainly broken, while one that meets it has proved only that it meets it
    at this size (ADR-0022).
    """
    within = overall.latency_p95_ms <= QUERY_BUDGET_P95_MS
    return GateResult(
        gate="G5 Performance",
        passed=within,
        detail=(
            f"query p95 {overall.latency_p95_ms} ms against a {QUERY_BUDGET_P95_MS} ms budget, "
            f"on {chunks} chunks (the budget is stated for the 10^5-chunk reference profile, "
            f"so this is a floor, not the measurement spec 04 §1 asks for)"
        ),
    )


def _gate_g6() -> GateResult:
    """Gate G6 — determinism, which is a *compiler* gate with its own CI job.

    Reported here rather than re-run: spec 04 §7.3 lists it among the gates and
    says it "runs with eval in CI", so a gate table that silently omitted it
    would read as though determinism were unguarded.
    """
    return GateResult(
        gate="G6 Determinism",
        passed=True,
        detail=(
            "enforced elsewhere: byte-identical rebuild against the committed golden "
            "(`pytest -m determinism`, its own CI job, ADR-0012)"
        ),
    )


def _gates(overall: MetricSummary, unanswerable_cases: int) -> tuple[GateResult, ...]:
    coverage_ok = overall.citation_coverage == 1.0
    gates = [
        GateResult(
            gate="G1 Citations",
            passed=coverage_ok,
            detail=(
                f"citation coverage {overall.citation_coverage:.4f} "
                f"({'= 1.00 as required' if coverage_ok else 'MUST be 1.00'})"
            ),
        )
    ]
    if unanswerable_cases:
        abstention_ok = overall.false_answer_rate <= MAX_FALSE_ANSWER_RATE
        gates.append(
            GateResult(
                gate="G4 Abstention",
                passed=abstention_ok,
                detail=(
                    f"false-answer rate {overall.false_answer_rate:.2%} on "
                    f"{unanswerable_cases} unanswerable case(s); "
                    f"limit {MAX_FALSE_ANSWER_RATE:.0%}"
                ),
            )
        )
    else:
        gates.append(
            GateResult(
                gate="G4 Abstention",
                passed=True,
                detail="no unanswerable cases in this set; nothing to abstain from",
            )
        )
    return tuple(gates)


def _score(
    cases: Sequence[EvalCase], retriever: Retriever, resolvable: set[str]
) -> tuple[list[CaseResult], MetricSummary, dict[str, MetricSummary]]:
    """Run one retriever over the case set and summarise it overall and per slice."""
    results = [_evaluate_case(case, retriever, resolvable) for case in cases]
    by_id = {case.case_id: case for case in cases}
    per_slice: dict[str, MetricSummary] = {}
    for slice_name in sorted({s.value for case in cases for s in case.slices}):
        sliced = [
            result
            for result in results
            if slice_name in {s.value for s in by_id[result.case_id].slices}
        ]
        per_slice[slice_name] = _summarise([by_id[result.case_id] for result in sliced], sliced)
    return results, _summarise(cases, results), per_slice


@dataclass(frozen=True, slots=True)
class IncumbentComparison:
    """What a run says about the incumbent it was measured against (D-010).

    Spec 04 §7.4 names the real incumbent — the agent's own `grep`/`glob`/`read`
    loop — and states the doctrine in one line: *if Mycelium OS does not visibly
    beat grep, the correct response is to fix the product, not the benchmark.*
    Roadmap 4.8 was that finding, and it stayed open for three milestones. What
    kept it open was not the difficulty of the fix; it was that the comparison
    lived in an ADR table and in one CI step on one corpus, so nobody could see
    the gap close, and nobody would see it reopen.

    This is the comparison as a *record*: computed on the run's own snapshot,
    over the same cases and the same anchor space, and written into the manifest
    that spec 04 §7.5 already requires. It is **reported, never gated** — spec
    04 §7.4 quantifies the gate at 1.0 (roadmap 6.4), and a baseline that could
    fail the build is a baseline nobody dares improve.

    :attr:`conceded` is the part worth reading. An overall lead can hide a slice
    the incumbent still owns, and that slice is where the next hypothesis comes
    from.
    """

    retriever: str
    lead: float
    """`ours - theirs` on nDCG@10 overall. Negative means the incumbent leads."""
    conceded: tuple[str, ...]
    """Slices where the incumbent scores strictly higher, worst first."""
    detail: str

    @property
    def ahead(self) -> bool:
        """Whether the product leads overall. Slices may still be conceded."""
        return self.lead > 0.0


def compare_to_incumbent(
    retriever: str,
    ours: MetricSummary,
    theirs: MetricSummary,
    ours_slices: Mapping[str, MetricSummary],
    theirs_slices: Mapping[str, MetricSummary],
) -> IncumbentComparison:
    """Summarise one run against its incumbent, and name what it still concedes."""
    lead = ours.ndcg_at_10 - theirs.ndcg_at_10
    conceded = sorted(
        (
            name
            for name, summary in theirs_slices.items()
            if summary.ndcg_at_10 > ours_slices.get(name, summary).ndcg_at_10
        ),
        key=lambda name: ours_slices[name].ndcg_at_10 - theirs_slices[name].ndcg_at_10,
    )
    verdict = "ahead of" if lead > 0 else ("level with" if lead == 0 else "BEHIND")
    detail = (
        f"nDCG@10 {ours.ndcg_at_10:.3f} against {retriever}'s {theirs.ndcg_at_10:.3f} "
        f"({lead:+.3f}) - {verdict} the incumbent"
    )
    if conceded:
        losses = ", ".join(
            f"{name} {ours_slices[name].ndcg_at_10:.3f} vs {theirs_slices[name].ndcg_at_10:.3f}"
            for name in conceded
        )
        detail += f"; still conceded: {losses}"
    return IncumbentComparison(
        retriever=retriever, lead=lead, conceded=tuple(conceded), detail=detail
    )


def incumbent_comparison(manifest: EvalRunManifest) -> IncumbentComparison | None:
    """The comparison a run recorded, or ``None`` when it was measured alone."""
    if manifest.incumbent is None or manifest.incumbent_overall is None:
        return None
    return compare_to_incumbent(
        manifest.incumbent,
        manifest.overall,
        manifest.incumbent_overall,
        manifest.per_slice,
        manifest.incumbent_per_slice,
    )


def baseline_path(root: Path, case_set: str) -> Path:
    """Where a set's committed baseline lives: `eval/baselines/<set>.json`."""
    return root / EVAL_DIRNAME / BASELINES_DIRNAME / f"{Path(case_set).stem}.json"


def read_baseline(root: Path, case_set: str, retriever: str) -> dict[str, object] | None:
    """The committed baseline for one retriever on one case set, if there is one."""
    path = baseline_path(root, case_set)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    entry = data.get(retriever)
    return entry if isinstance(entry, dict) else None


def write_baseline(
    root: Path,
    manifest: EvalRunManifest,
    fingerprint: CorpusFingerprint | None = None,
) -> Path:
    """Freeze this run's per-slice scores as the baseline gate G3 compares against.

    Committed to the repository rather than left in `.mycelium/`, because a
    baseline nobody can see is a baseline nobody can challenge — and because CI
    starts from an empty derived store every time (spec 04 §7.5).

    Both fingerprints are recorded. `content_digest` is what G3 keys enforcement
    on; `corpus_digest` keeps the name and the meaning it has had since
    BUG-0014 — the fold of chunk boundaries — so a reviewer reading two baselines
    side by side can tell a re-cut corpus from a changed one.
    """
    path = baseline_path(root, manifest.case_set)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {}
    if path.is_file():
        with suppress(OSError, ValueError):
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
    # Explicit `is None` rather than truthiness: an unreadable store yields a
    # falsy fingerprint, and "we looked and found nothing" must be recorded as
    # such rather than silently replaced by a default that says the same thing.
    taken = CorpusFingerprint(content="", chunks="") if fingerprint is None else fingerprint
    data[manifest.retriever] = {
        "blessed_from_snapshot": manifest.snapshot_id,
        # What makes the comparison apples-to-apples: two runs over the same
        # documents share this digest, whatever their chunk counts or their
        # assigned identities happen to be (ADR-0021, ADR-0045).
        "content_digest": taken.content,
        # How those documents were cut. Reported by G3, never gated on — the
        # distinction roadmap 4.13 exists to draw.
        "corpus_digest": taken.chunks,
        "toolchain": manifest.toolchain.model_dump(mode="json"),
        "overall_ndcg_at_10": round(manifest.overall.ndcg_at_10, 6),
        "per_slice": {
            name: round(summary.ndcg_at_10, 6)
            for name, summary in sorted(manifest.per_slice.items())
        },
    }
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def run_evaluation(
    root: Path,
    cases: Sequence[EvalCase],
    *,
    retriever_name: str = "mycelium",
    case_set: str = "cases.jsonl",
    companion: Sequence[EvalCase] | None = None,
    companion_set: str | None = None,
    against: str | None = None,
) -> EvalRunManifest:
    """Score `cases` against the published snapshot at `root`.

    Running the `hybrid` retriever also runs the lexical one, because gate G2 is
    a *comparison*: "hybrid ≥ +5 % nDCG@10 vs BM25-only" cannot be evaluated from
    one number, and taking the baseline from a previous run would compare across
    snapshots. Both retrievers see the same cases, the same snapshot, and the
    same anchor space.

    `companion` is scored beside `cases` and reported, never gated. It is how the
    dev/release split earns its keep: G3 asks "did this change make the release
    set worse", and the *gap* between the two sets asks the question G3 cannot —
    "did this change make the set we tuned against better than the one we did
    not" (spec 04 §7.1, ADR-0027). No threshold ships, because nobody has the
    evidence to set one; the number is put where a reviewer sees it.

    `against` names a second retriever — in practice `grep`, spec 04 §7.4's real
    incumbent — and scores it the same way G2 already scores the lexical leg
    beside the hybrid one: same store, same cases, same anchor space, so the two
    numbers are a comparison rather than two runs a reader has to trust were
    taken alike. Reported, never gated (ADR-0049).
    """
    if not cases:
        msg = "no evaluation cases to run"
        raise EvaluationError(msg)

    snapshot = read_current(root / STORE_DIRNAME)
    if snapshot is None:
        msg = f"no published snapshot at {root}; run `mycelium build` first"
        raise EvaluationError(msg)

    embedder = _embedder_for(root, retriever_name)
    with SqliteStore.open(root, read_only=True) as store:
        try:
            retriever = build_retriever(retriever_name, store, embedder)
        except ValueError as error:
            raise EvaluationError(str(error)) from error
        resolvable = resolvable_anchors(store)
        results, overall, per_slice = _score(cases, retriever, resolvable)
        retriever_config = dict(retriever.config)

        chunks = store.counts()["chunks"]
        fingerprint = corpus_fingerprint_of(root, snapshot)
        gates = list(_gates(overall, sum(1 for case in cases if not case.answerable)))
        gates.append(
            _gate_g3(per_slice, read_baseline(root, case_set, retriever_name), fingerprint)
        )
        gates.append(_gate_g5(overall, chunks))
        gates.append(_gate_g6())
        if retriever_name == "hybrid":
            _, lexical, lexical_slices = _score(
                cases, build_retriever("mycelium", store), resolvable
            )
            gates.append(_gate_g2(overall, lexical, per_slice, lexical_slices))

        incumbent_overall = None
        incumbent_slices: dict[str, MetricSummary] = {}
        if against is not None:
            if against == retriever_name:
                msg = f"cannot compare {retriever_name!r} against itself"
                raise EvaluationError(msg)
            try:
                incumbent = build_retriever(against, store, _embedder_for(root, against))
            except ValueError as error:
                raise EvaluationError(str(error)) from error
            _, incumbent_overall, incumbent_slices = _score(cases, incumbent, resolvable)

        companion_overall = None
        if companion:
            _, companion_overall, _ = _score(companion, retriever, resolvable)

    return EvalRunManifest(
        run_id=new_ulid(),
        snapshot_id=snapshot,
        created_at=datetime.now(tz=UTC),
        config_digest=digest_json(
            {"retriever": retriever_name, "config": retriever_config, "limit": RETRIEVAL_LIMIT}
        ),
        case_set=case_set,
        retriever=retriever_name,
        retriever_config=dict(retriever_config),
        toolchain=Toolchain(mycelium=__version__, python=platform.python_version()),
        overall=overall,
        per_slice=per_slice,
        results=tuple(results),
        gates=tuple(gates),
        companion_set=companion_set if companion_overall is not None else None,
        companion_overall=companion_overall,
        incumbent=against if incumbent_overall is not None else None,
        incumbent_overall=incumbent_overall,
        incumbent_per_slice=incumbent_slices,
    )


def _embedder_for(root: Path, retriever_name: str) -> Embedder | None:
    """Load the configured embedder when the run needs one, with a usable error."""
    if retriever_name != "hybrid":
        return None
    settings = load_config(root)
    try:
        return build_embedder(
            provider=settings.embedding.provider,
            model_id=settings.embedding.model_id,
            model_path=Path(settings.embedding.model_path)
            if settings.embedding.model_path
            else None,
            allow_download=settings.embedding.allow_download,
        )
    except EmbeddingError as error:
        msg = f"cannot evaluate the hybrid retriever: {error}"
        raise EvaluationError(msg) from error


def write_run(root: Path, manifest: EvalRunManifest) -> Path:
    """Persist a run under ``.mycelium/eval/`` (spec 04 §7.5).

    Runs live with the derived store because they are reproducible from it; only
    released benchmark reports are committed to the repository.
    """
    directory = root / STORE_DIRNAME / EVAL_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{manifest.run_id}.json"
    text = json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")
    return path
