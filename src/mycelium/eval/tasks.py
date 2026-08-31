# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The agent-task suite: Mycelium against the incumbent it has to beat (D-010).

Spec 04 §7.4 is blunt about who the competitor is. It is not BM25 and it is not
another retriever — it is the agent's own `grep`/`glob`/`read` loop, and *"if
Mycelium OS does not visibly beat grep on these tasks, the correct response is to
fix the product, not the benchmark."*

**What this measures, and what it cannot.** Running a real agent needs a model,
a key, and a budget, and it answers differently every time — none of which
belongs in a gate that must run offline on three platforms (D-013, D-017). So
this suite measures the *substrate* both loops consume rather than the loop:
given a task and its required evidence, what does each strategy put in front of
the model, and what does that cost in tokens?

- **Mycelium** issues one search and returns budgeted, cited passages.
- **grep** does what an agent does without an index: scan for the task's terms,
  then *read the matching files whole*, because a grep hit is a line number and
  the model needs the surrounding document.

That second sentence is the whole comparison. Both strategies usually *find* the
evidence in a small corpus; what differs by an order of magnitude is how much
text the model has to be handed to see it. Task success here means "the required
evidence was present in what the agent received", which is necessary for the
agent to succeed and not sufficient — the model still has to read it. Spec 04
§7.4 calls for qualitative scoring pre-1.0 and a quantified gate at 1.0; this is
the qualitative half made reproducible, and ADR-0022 records what it leaves out.
"""

import json
import re
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from mycelium.chunking import estimate_tokens
from mycelium.eval.retrievers import terms_of
from mycelium.retrieval import search
from mycelium.store import SqliteStore

__all__ = [
    "DEFAULT_BUDGET_TOKENS",
    "AgentTask",
    "TaskOutcome",
    "TaskSuiteReport",
    "load_tasks",
    "run_task_suite",
]

DEFAULT_BUDGET_TOKENS: Final = 4_000
"""The packing budget spec 04 §4 gives a caller by default."""

MAX_GREP_FILES: Final = 5
"""How many matching documents a grep loop reads before it gives up.

An agent does not read forty files; it reads the first few and re-greps. Five is
generous to the baseline — the point is not to make grep look bad, it is to
count what a reasonable loop actually costs.
"""


class AgentTask(BaseModel):
    """One realistic task, and the evidence an answer to it must rest on.

    Deliberately *not* in :mod:`mycelium.sdk.types`. The SDK is the surface that
    freezes at 1.0 (roadmap 6.1), and this format will change the moment a model
    joins the loop and scoring becomes an answer rather than a retrieval check
    (spec 04 §7.4). A harness asset that is going to change does not belong in a
    contract that must not.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    prompt: str = Field(description="What the agent is asked to do, in a user's words.")
    kind: Literal["answer", "locate", "relate"] = "answer"
    """`answer` a question, `locate` a definition, `relate` two documents."""
    requires: tuple[str, ...] = Field(
        default=(), description="Anchors whose text the agent must have been given."
    )
    note: str | None = None


@dataclass(frozen=True, slots=True)
class TaskOutcome:
    """What one strategy produced for one task."""

    task_id: str
    strategy: str
    found: bool
    """Whether every required anchor's text reached the agent."""
    missing: tuple[str, ...]
    tokens: int
    """Tokens of context the agent would have had to read."""
    documents_read: int
    latency_ms: int

    def as_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "strategy": self.strategy,
            "found": self.found,
            "missing": list(self.missing),
            "tokens": self.tokens,
            "documents_read": self.documents_read,
            "latency_ms": self.latency_ms,
        }


@dataclass(frozen=True, slots=True)
class TaskSuiteReport:
    """The comparison, per strategy and overall."""

    tasks: int
    outcomes: tuple[TaskOutcome, ...]

    def by_strategy(self, strategy: str) -> tuple[TaskOutcome, ...]:
        return tuple(item for item in self.outcomes if item.strategy == strategy)

    def summary(self, strategy: str) -> dict[str, float]:
        rows = self.by_strategy(strategy)
        if not rows:
            return {}
        return {
            "success_rate": sum(1 for row in rows if row.found) / len(rows),
            "mean_tokens": sum(row.tokens for row in rows) / len(rows),
            "total_tokens": float(sum(row.tokens for row in rows)),
            "mean_documents_read": sum(row.documents_read for row in rows) / len(rows),
            "p95_latency_ms": float(
                sorted(row.latency_ms for row in rows)[max(0, int(0.95 * (len(rows) - 1)))]
            ),
        }

    def as_dict(self) -> dict[str, object]:
        strategies = sorted({item.strategy for item in self.outcomes})
        return {
            "tasks": self.tasks,
            "strategies": {name: self.summary(name) for name in strategies},
            "outcomes": [item.as_dict() for item in self.outcomes],
        }


def load_tasks(path: Path) -> tuple[AgentTask, ...]:
    """Read a task suite (JSONL, one task per line)."""
    text = path.read_text(encoding="utf-8")
    return tuple(AgentTask.model_validate_json(line) for line in text.splitlines() if line.strip())


def _mycelium_context(
    store: SqliteStore, task: AgentTask, budget: int
) -> tuple[set[str], int, int]:
    """What `mycelium_search` would hand the agent: budgeted, cited passages."""
    outcome = search(store, task.prompt, limit=10)
    anchors: set[str] = set()
    tokens = 0
    documents: set[str] = set()
    for hit in outcome.hits:
        cost = estimate_tokens(hit.hit.chunk.text)
        if tokens + cost > budget:
            break
        tokens += cost
        anchors.add(hit.hit.chunk.anchor)
        documents.add(hit.hit.path)
    return anchors, tokens, len(documents)


def _grep_context(
    store: SqliteStore, root: Path, task: AgentTask, budget: int
) -> tuple[set[str], int, int]:
    """What a grep loop would hand the agent: whole files that matched a term.

    The read is the expensive half and the honest one. `grep` returns a line
    number, and a line number is not context — an agent that greps then reads is
    the loop this product exists to replace, so the loop is what gets measured.
    """
    terms = terms_of(task.prompt)
    if not terms:
        return set(), 0, 0
    patterns = [re.compile(rf"\b{re.escape(term)}", re.IGNORECASE) for term in terms]

    scored: list[tuple[int, str]] = []
    corpus = {
        document.path: store.chunks_of(doc_id)
        for doc_id in store.document_ids()
        if (document := store.get_document(doc_id)) is not None
    }
    for path, chunks in corpus.items():
        text = "\n".join(chunk.text for chunk in chunks)
        matched = sum(1 for pattern in patterns if pattern.search(text))
        if matched:
            scored.append((matched, path))
    scored.sort(key=lambda row: (-row[0], row[1]))

    anchors: set[str] = set()
    tokens = 0
    read = 0
    for _, path in scored[:MAX_GREP_FILES]:
        chunks = corpus[path]
        cost = sum(estimate_tokens(chunk.text) for chunk in chunks)
        if tokens + cost > budget and read:
            break
        tokens += cost
        read += 1
        anchors.update(chunk.anchor for chunk in chunks)
    return anchors, tokens, read


def run_task_suite(
    root: Path, tasks: Sequence[AgentTask], *, budget_tokens: int = DEFAULT_BUDGET_TOKENS
) -> TaskSuiteReport:
    """Run every task through both strategies against the published snapshot."""
    outcomes: list[TaskOutcome] = []
    with SqliteStore.open(root, read_only=True) as store:
        for task in tasks:
            for strategy in ("mycelium", "grep"):
                started = time.perf_counter()
                anchors, tokens, documents = (
                    _mycelium_context(store, task, budget_tokens)
                    if strategy == "mycelium"
                    else _grep_context(store, root, task, budget_tokens)
                )
                elapsed = int((time.perf_counter() - started) * 1000)
                missing = tuple(sorted(set(task.requires) - anchors))
                outcomes.append(
                    TaskOutcome(
                        task_id=task.task_id,
                        strategy=strategy,
                        found=not missing,
                        missing=missing,
                        tokens=tokens,
                        documents_read=documents,
                        latency_ms=elapsed,
                    )
                )
    return TaskSuiteReport(tasks=len(tasks), outcomes=tuple(outcomes))


def write_tasks(path: Path, tasks: Iterable[AgentTask]) -> Path:
    """Write a task suite as JSONL — one task per line, deterministic bytes."""
    lines = [
        json.dumps(task.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        for task in tasks
    ]
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8", newline="\n")
    return path
