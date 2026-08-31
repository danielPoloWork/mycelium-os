# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Evaluation: the harness, the metrics, and the baseline that keeps them honest.

- :mod:`mycelium.eval.cases` — judged case sets as versioned JSONL (spec 04 §7.1).
- :mod:`mycelium.eval.metrics` — Recall@k, nDCG@10, MRR, citation coverage (§7.2).
- :mod:`mycelium.eval.retrievers` — the product, and the grep incumbent (§7.4, D-010).
- :mod:`mycelium.eval.harness` — runs a set, gates the result, writes a manifest (§7.5).

D-010 makes evaluation a permanent release gate rather than a launch exercise, and
names the standard to beat: not another retriever, but the agent's own grep loop.
That comparison is built in from the first run, because a benchmark you only run
against yourself measures nothing.
"""

from mycelium.eval.cases import load_cases, write_cases
from mycelium.eval.harness import (
    BASELINES_DIRNAME,
    EVAL_DIRNAME,
    MAX_FALSE_ANSWER_RATE,
    QUERY_BUDGET_P95_MS,
    RETRIEVAL_LIMIT,
    EvaluationError,
    run_evaluation,
    write_baseline,
    write_run,
)
from mycelium.eval.metrics import (
    citation_coverage,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)
from mycelium.eval.retrievers import (
    GrepRetriever,
    MyceliumRetriever,
    Retriever,
    build_retriever,
)
from mycelium.eval.tasks import AgentTask, TaskSuiteReport, load_tasks, run_task_suite

__all__ = [
    "BASELINES_DIRNAME",
    "EVAL_DIRNAME",
    "QUERY_BUDGET_P95_MS",
    "AgentTask",
    "TaskSuiteReport",
    "load_tasks",
    "run_task_suite",
    "write_baseline",
    "MAX_FALSE_ANSWER_RATE",
    "RETRIEVAL_LIMIT",
    "EvaluationError",
    "GrepRetriever",
    "MyceliumRetriever",
    "Retriever",
    "build_retriever",
    "citation_coverage",
    "load_cases",
    "ndcg_at_k",
    "recall_at_k",
    "reciprocal_rank",
    "run_evaluation",
    "write_cases",
    "write_run",
]
