# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The evaluation harness (spec 04 §7).

Runs a judged case set against a retriever, reports per-slice and overall metrics,
evaluates the gates that are meaningful at this stage, and writes a run manifest —
because "a report without a manifest is exploratory and cannot satisfy a gate"
(§7.5).

Which gates v0 can honestly evaluate:

======  ==========================================================================
G1      **Enforced.** Citation coverage must be 1.00 — every returned anchor
        resolves in the snapshot. Nothing else about the corpus is needed to
        check it, and it is the failure this product cannot tolerate.
G4      **Enforced.** False-answer rate on `unanswerable` cases ≤ 5 %: a query
        whose vocabulary the corpus does not contain must return nothing rather
        than confident noise.
G2      Not applicable: hybrid retrieval does not exist yet (roadmap 3.3), so
        there is nothing to earn its keep against.
G3      Not applicable: no previous release on a frozen set to regress against.
        It becomes meaningful once a release set is frozen (3.7).
G5      Measured, not gated: latency percentiles are recorded, but the budget is
        defined against the 10⁵-chunk reference profile (3.7), not this corpus.
G6      Elsewhere: the determinism gate is a compiler gate (roadmap 2.10).
======  ==========================================================================

Absolute quality targets are deliberately absent. Pre-GA the spec enforces
*relative* discipline (§7.3), so this harness reports numbers and compares
retrievers; it does not assert that nDCG must exceed some invented threshold.
"""

import json
import platform
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from mycelium.__about__ import __version__
from mycelium.build.publish import read_current
from mycelium.eval.metrics import (
    citation_coverage,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)
from mycelium.eval.retrievers import Retriever, build_retriever, resolvable_anchors
from mycelium.sdk.identity import digest_json, new_ulid
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
    "EVAL_DIRNAME",
    "write_run",
    "MAX_FALSE_ANSWER_RATE",
    "RETRIEVAL_LIMIT",
    "EvaluationError",
    "run_evaluation",
]

EVAL_DIRNAME: Final = "eval"
RETRIEVAL_LIMIT: Final = 50
"""Deep enough for Recall@50, which is the widest metric the spec asks for."""

MAX_FALSE_ANSWER_RATE: Final = 0.05
"""Gate G4 for v1; tightens at 1.0."""


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

    return CaseResult(
        case_id=case.case_id,
        retrieved=tuple(retrieved[:10]),  # the manifest records what a reader would see
        ndcg_at_10=ndcg_at_k(retrieved, judged, 10),
        recall_at_10=recall_at_k(retrieved, judged, 10),
        recall_at_50=recall_at_k(retrieved, judged, 50),
        reciprocal_rank=reciprocal_rank(retrieved, judged),
        citation_coverage=citation_coverage(retrieved, resolvable),
        abstained=not retrieved,
        latency_ms=elapsed_ms,
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


def run_evaluation(
    root: Path,
    cases: Sequence[EvalCase],
    *,
    retriever_name: str = "mycelium",
    case_set: str = "cases.jsonl",
) -> EvalRunManifest:
    """Score `cases` against the published snapshot at `root`."""
    if not cases:
        msg = "no evaluation cases to run"
        raise EvaluationError(msg)

    snapshot = read_current(root / STORE_DIRNAME)
    if snapshot is None:
        msg = f"no published snapshot at {root}; run `mycelium build` first"
        raise EvaluationError(msg)

    with SqliteStore.open(root, read_only=True) as store:
        retriever = build_retriever(retriever_name, store)
        resolvable = resolvable_anchors(store)
        results = [_evaluate_case(case, retriever, resolvable) for case in cases]
        retriever_config = dict(retriever.config)

    overall = _summarise(cases, results)
    by_id = {case.case_id: case for case in cases}
    per_slice: dict[str, MetricSummary] = {}
    for slice_name in sorted({s.value for case in cases for s in case.slices}):
        sliced = [
            result
            for result in results
            if slice_name in {s.value for s in by_id[result.case_id].slices}
        ]
        per_slice[slice_name] = _summarise([by_id[result.case_id] for result in sliced], sliced)

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
        gates=_gates(overall, sum(1 for case in cases if not case.answerable)),
    )


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
