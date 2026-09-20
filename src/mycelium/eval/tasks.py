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
  then *read* the files that matched, because a grep hit is a line number and the
  model needs the surrounding document.

That second sentence is the whole comparison. Both strategies usually *find* the
evidence in a small corpus; what differs is how much text the model has to be
handed to see it. Task success here means "the required evidence was present in
what the agent received", which is necessary for the agent to succeed and not
sufficient — the model still has to read it. Spec 04 §7.4 calls for qualitative
scoring pre-1.0 and a quantified gate at 1.0; this is the qualitative half made
reproducible, and ADR-0022 records what it leaves out.

**A read is bounded, and that changed the measurement** (roadmap 6.22, ADR-0131).
The loop used to read the first matching file *whole, whatever it cost*, and then
stop because the budget was gone. On a corpus whose largest document had grown to
88 000 tokens that produced a degenerate incumbent: one file on 22 of 22 tasks,
93 % of its measured cost in that one file, and five-sixths of the loop its own
constant describes never running. An agent does not read a file larger than its
context — it reads a window around the hit, or it re-greps. So one read costs at
most what one search may, the loop opens :data:`MAX_GREP_FILES` files, and the
incumbent's cost is bounded by the model of the loop rather than by whichever
document happened to match.

**A required anchor that no longer exists is reported, never scored** (roadmap
6.4, ADR-0120). A task's `requires` list is a judgement about the corpus, and the
corpus moves underneath it: at 6.4 four of the twenty-two tasks pointed at anchors
the store no longer held, because the packed chunker (ADR-0047) had merged three
chunks of one ADR into one and shifted every ordinal after it. Nothing noticed,
because a missing anchor scored exactly like a retrieval miss — so the suite's
headline rate had silently become *retrieval quality plus anchor rot*, with no way
to tell them apart, and its ceiling was 18/22 rather than 22/22. Such a task is now
counted as **unresolved** and excluded from the rate, which is the only honest
reading: neither strategy can put in front of a model a passage that does not
exist, so it measures nothing about either.
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
from mycelium.sdk.types import Chunk
from mycelium.store import SqliteStore

__all__ = [
    "DEFAULT_BUDGET_TOKENS",
    "MAX_SEARCH_K",
    "AgentTask",
    "TaskKind",
    "TaskOutcome",
    "TaskSuiteReport",
    "encode_tasks",
    "load_tasks",
    "run_task_suite",
]

type TaskKind = Literal["answer", "locate", "relate"]
"""What a task asks for: `answer` a question, `locate` a definition, `relate` two
documents.

Named rather than inlined because `tools/build_agent_tasks.py` declares the same
three strings when it writes the suite, and a vocabulary spelled twice is a
vocabulary that can disagree with itself — a typo there produced a `str` that only
failed at construction, and only once someone type-checked the generator
(roadmap 4.43)."""

DEFAULT_BUDGET_TOKENS: Final = 4_000
"""The packing budget spec 04 §4 gives a caller by default."""

MAX_SEARCH_K: Final = 50
"""How many results the Mycelium arm asks `search` for.

The mirror of :data:`MAX_GREP_FILES`: the incumbent's model has two constants and
ours has one, and until roadmap 6.28 ours was **not this number**. It was a
literal `limit=10` inside `_mycelium_context`, which models no caller at all —
`mycelium_search` defaults `k` to **8** and caps it at **50**, so ten is neither.

50 is the cap the contract states, and the reason to ask for it is that
`budget_tokens` is what actually bounds the answer: a caller that declares a
budget and wants it spent asks for the most the tool allows and lets the budget
truncate. With `limit=10` the *count* bound first, so the arm saturated at about
3 100 tokens and stopped improving from a 4 000-token budget upward while the
incumbent went on scaling — the comparison understated us, which D-010 holds to
a higher standard than the reverse and is why roadmap 6.22 filed it instead of
fixing it in passing (ADR-0143).

Asking for more cannot cost more than the budget: the packing loop below spends
at most `budget`, whatever `k` says. What it changes is whether the budget can
be spent at all.

A *default* caller saturates too, and the band report says so: at `k = 8` the
arm holds at 17/22 on this repository however large the budget, because `k`
rather than the budget is what binds. `tools/measure_agent_task_band.py` sweeps
this constant beside the incumbent's two, so the choice is auditable rather than
asserted (ADR-0131's rule, applied to our own side).

Pinned against `mycelium.mcp.tools._MAX_K` by `tests/test_agent_tasks.py` rather
than imported from it: the suite must not drag the serving surface into its
import graph to read one integer, and a declaration that can drift silently is
the defect roadmap 6.18 fixed in the configuration path.
"""

MAX_GREP_FILES: Final = 5
"""How many matching documents a grep loop reads before it gives up.

An agent does not read forty files; it reads the first few and re-greps. Five is
generous to the baseline — the point is not to make grep look bad, it is to
count what a reasonable loop actually costs.

Until roadmap 6.22 this number was aspirational: the loop read the *first*
matching file whole whatever it cost, which on this corpus meant one document on
22 of 22 tasks and never a second (ADR-0131).
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
    kind: TaskKind = "answer"
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
    unresolved: tuple[str, ...] = ()
    """Required anchors this snapshot does not contain at all.

    Not a retrieval failure and not scored as one: the passage a judgement names
    is gone, so the task asks for evidence no strategy could return."""

    @property
    def scorable(self) -> bool:
        """Whether this outcome says anything about retrieval."""
        return not self.unresolved

    def as_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "strategy": self.strategy,
            "found": self.found,
            "missing": list(self.missing),
            "unresolved": list(self.unresolved),
            "scorable": self.scorable,
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

    @property
    def unresolved(self) -> dict[str, tuple[str, ...]]:
        """Task id → the required anchors this snapshot does not hold, sorted.

        The suite's own health, and the first thing a reader needs: a rate over
        eighteen tasks and a rate over twenty-two are not the same measurement,
        and only this says which one is being quoted.
        """
        return {
            item.task_id: item.unresolved
            for item in sorted(self.outcomes, key=lambda row: row.task_id)
            if item.unresolved
        }

    @property
    def scorable(self) -> int:
        """Tasks whose required evidence still exists — the rate's denominator."""
        return self.tasks - len(self.unresolved)

    def summary(self, strategy: str) -> dict[str, float]:
        rows = tuple(item for item in self.by_strategy(strategy) if item.scorable)
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
            "scorable": self.scorable,
            "unresolved": {key: list(value) for key, value in self.unresolved.items()},
            "strategies": {name: self.summary(name) for name in strategies},
            "outcomes": [item.as_dict() for item in self.outcomes],
        }


def load_tasks(path: Path) -> tuple[AgentTask, ...]:
    """Read a task suite (JSONL, one task per line)."""
    text = path.read_text(encoding="utf-8")
    return tuple(AgentTask.model_validate_json(line) for line in text.splitlines() if line.strip())


def _mycelium_context(
    store: SqliteStore, task: AgentTask, budget: int, search_k: int = MAX_SEARCH_K
) -> tuple[set[str], int, int]:
    """What `mycelium_search` would hand the agent: budgeted, cited passages.

    **Two corrections at roadmap 6.28, and both are fidelity to the tool rather
    than favour** (ADR-0143). The comparison is only worth something if this
    function models `handle_search`, and it differed from it twice:

    - it asked for a hard-coded ten results whatever the caller's budget, so the
      arm saturated at about 3 100 tokens and stopped improving from a
      4 000-token budget upward. Ten is neither the tool's default `k` (8) nor
      its maximum (50): it modelled no caller. :data:`MAX_SEARCH_K` is now the
      cap, and the budget below is what bounds the answer;
    - it **stopped** at the first result that would not fit, where the tool
      *skips* it and goes on packing (`omitted`, spec 05 §3.1). A single large
      passage early in the ranking therefore cost the arm everything behind it.

    Both moved the number in our favour, which is exactly why 6.22 filed them
    rather than folding them into a pull request about something else, and why
    the band is re-published with the change.
    """
    outcome = search(store, task.prompt, limit=search_k)
    anchors: set[str] = set()
    tokens = 0
    documents: set[str] = set()
    for hit in outcome.hits:
        cost = estimate_tokens(hit.hit.chunk.text)
        if tokens + cost > budget:
            # Skipped, not stopped: `handle_search` puts an over-budget result in
            # `omitted` and keeps filling from the rest of the ranking.
            continue
        tokens += cost
        anchors.add(hit.hit.chunk.anchor)
        documents.add(hit.hit.path)
    return anchors, tokens, len(documents)


def _read_window(
    chunks: Sequence[Chunk], patterns: Sequence[re.Pattern[str]], window: int
) -> tuple[tuple[Chunk, ...], int]:
    """One read of one document: what an agent gets back, and what it costs.

    A small document is read whole, because an agent that has decided to open a
    file does not page through four kilobytes. A document larger than the window
    is read *around the hit* — grep handed over a line number, and the read tool
    takes an offset — so the loop takes the best-matching section and grows
    outward, preferring what follows the hit, until the next section would not
    fit (roadmap 6.22, ADR-0131).

    Sections rather than lines, and the rounding is stated rather than hidden:
    the whole harness works in the store's rendered view of the corpus, so this
    measures grep's cost in the same tokens as Mycelium's instead of charging it
    for markup a model never sees. What it costs is fidelity at the window's
    edge — a real read stops mid-section.

    A section larger than the window is the case worth naming. The read is
    truncated at the window and returns **no** section: the agent saw part of a
    passage, which is not the same as being handed it, and scoring it as evidence
    would credit grep for text nobody can point at. This corpus has five such
    sections and four of them are in `ROADMAP.md`.
    """
    costs = [estimate_tokens(chunk.text) for chunk in chunks]
    whole = sum(costs)
    if whole <= window:
        return tuple(chunks), whole

    ranked = sorted(
        range(len(chunks)),
        key=lambda index: (
            -sum(1 for pattern in patterns if pattern.search(chunks[index].text)),
            index,
        ),
    )
    centre = ranked[0]
    if costs[centre] > window:
        return (), window

    taken = {centre}
    spent = costs[centre]
    after, before = centre + 1, centre - 1
    while True:
        # Forward first: a section's answer usually follows the term that found it.
        nxt = next(
            (
                index
                for index in (after, before)
                if 0 <= index < len(chunks) and spent + costs[index] <= window
            ),
            None,
        )
        if nxt is None:
            break
        taken.add(nxt)
        spent += costs[nxt]
        if nxt == after:
            after += 1
        else:
            before -= 1
    return tuple(chunks[index] for index in sorted(taken)), spent


def _grep_context(
    store: SqliteStore, task: AgentTask, budget: int, max_files: int
) -> tuple[set[str], int, int]:
    """What a grep loop would hand the agent: a read of each file that matched.

    The read is the expensive half and the honest one. `grep` returns a line
    number, and a line number is not context — an agent that greps then reads is
    the loop this product exists to replace, so the loop is what gets measured.

    **What one read costs is the caller's own budget** (roadmap 6.22). Mycelium
    spends `budget_tokens` once, on passages it ranked; a grep loop spends it per
    file it opens, because there is no packing and no ranking across files — and
    it opens `max_files` of them. So the incumbent's ceiling is five reads, set by
    the model of the loop, where before it was the size of the largest document
    that happened to match.

    `max_files` is a parameter rather than a constant read from module scope
    because it is a *modelling choice*, and one this project measured instead of
    asserting: `tools/measure_agent_task_band.py` runs the comparison across the
    band, so a reader can see how much of the verdict the choice is worth.
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
    for _, path in scored[:max_files]:
        taken, cost = _read_window(corpus[path], patterns, budget)
        tokens += cost
        read += 1
        anchors.update(chunk.anchor for chunk in taken)
    return anchors, tokens, read


def run_task_suite(
    root: Path,
    tasks: Sequence[AgentTask],
    *,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    max_grep_files: int = MAX_GREP_FILES,
    search_k: int = MAX_SEARCH_K,
) -> TaskSuiteReport:
    """Run every task through both strategies against the published snapshot.

    Both constants of the incumbent's model are parameters — how much one read
    costs, and how many files the loop opens — because the verdict depends on
    them and a number nobody can vary is a number nobody can check (roadmap 6.22).

    **And now ours is too.** `search_k` is the one constant on our side of the
    comparison, and it was a literal inside `_mycelium_context` while the
    incumbent's two were swept and published — an asymmetry that let our arm
    saturate unnoticed for five milestones (roadmap 6.28, ADR-0143).
    """
    outcomes: list[TaskOutcome] = []
    with SqliteStore.open(root, read_only=True) as store:
        for task in tasks:
            # Asked of the snapshot before anything is timed: a judgement that
            # names a passage the corpus no longer holds is stale, and scoring it
            # as a miss would blame retrieval for the chunker having moved
            # (roadmap 6.4).
            unresolved = tuple(
                sorted(anchor for anchor in task.requires if store.get_chunk(anchor) is None)
            )
            for strategy in ("mycelium", "grep"):
                started = time.perf_counter()
                anchors, tokens, documents = (
                    _mycelium_context(store, task, budget_tokens, search_k)
                    if strategy == "mycelium"
                    else _grep_context(store, task, budget_tokens, max_grep_files)
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
                        unresolved=unresolved,
                    )
                )
    return TaskSuiteReport(tasks=len(tasks), outcomes=tuple(outcomes))


def encode_tasks(tasks: Iterable[AgentTask]) -> str:
    """The bytes :func:`write_tasks` would write, without writing them.

    Split out for the reason :func:`mycelium.eval.cases.encode_cases` was: a
    generator's `--check` compares what it would write against what is committed,
    and a second rendering of the same records is a second thing that can quietly
    disagree with the writer. There is one canonical form and one function that
    produces it (roadmap 5.38, 6.23).
    """
    lines = [
        json.dumps(task.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        for task in tasks
    ]
    return "".join(f"{line}\n" for line in lines)


def write_tasks(path: Path, tasks: Iterable[AgentTask]) -> Path:
    """Write a task suite as JSONL — one task per line, deterministic bytes."""
    path.write_text(encode_tasks(tasks), encoding="utf-8", newline="\n")
    return path
