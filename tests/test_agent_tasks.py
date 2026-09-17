# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The agent-task suite (roadmap 3.7, spec 04 §7.4, D-010, ADR-0022).

The comparison D-010 actually asks for is against the agent's own grep loop, and
the honest thing to measure without a model in the loop is what each strategy
puts in front of one: does the required evidence arrive, and what does it cost in
context? These tests pin that measurement's shape — not its numbers, which are a
property of the corpus and belong in the report, not in an assertion.
"""

import json
from pathlib import Path

import pytest

from mycelium.build import build
from mycelium.eval.tasks import AgentTask, load_tasks, run_task_suite, write_tasks
from mycelium.store import SqliteStore

CORPUS = {
    "knowledge/licence.md": "# Licence\n\nThe project is distributed under Apache-2.0.\n",
    "knowledge/retries.md": (
        "# Retries\n\nFailed deliveries retry with exponential backoff.\n\n"
        "## Limits\n\nAt most five attempts, then the message is parked.\n"
    ),
    "knowledge/bus.md": "# Event Bus\n\nThe bus routes messages between agents.\n",
}


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("task-corpus")
    for relative, text in CORPUS.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    build(root)
    return root


def anchor_for(root: Path, path: str) -> str:
    with SqliteStore.open(root, read_only=True) as store:
        document = store.get_document_by_path(path)
        assert document is not None
        return store.chunks_of(document.doc_id)[0].anchor


def test_a_task_that_can_be_answered_is_scored_found(corpus: Path) -> None:
    task = AgentTask(
        task_id="t-x",
        prompt="what licence is the project distributed under",
        requires=(anchor_for(corpus, "knowledge/licence.md"),),
    )
    report = run_task_suite(corpus, [task])

    outcome = report.by_strategy("mycelium")[0]
    assert outcome.found
    assert outcome.missing == ()
    assert outcome.tokens > 0  # context was actually spent


def test_missing_evidence_is_named_not_merely_counted(corpus: Path) -> None:
    """A real miss: the passage exists, and this query did not bring it back."""
    licence = anchor_for(corpus, "knowledge/licence.md")
    task = AgentTask(task_id="t-y", prompt="event bus routes messages", requires=(licence,))
    outcome = run_task_suite(corpus, [task]).by_strategy("mycelium")[0]

    assert not outcome.found
    assert outcome.missing == (licence,)
    assert outcome.unresolved == ()  # the evidence is there; retrieval did not find it
    assert outcome.scorable


def test_an_anchor_the_corpus_no_longer_holds_is_unresolved_not_a_miss(corpus: Path) -> None:
    """Roadmap 6.4: the distinction the suite could not make, and the one that
    silently capped its rate at 18/22 when the chunker moved four anchors."""
    task = AgentTask(
        task_id="t-y",
        prompt="what licence is the project distributed under",
        requires=("knowledge/nowhere.md#absent/0",),
    )
    report = run_task_suite(corpus, [task])
    outcome = report.by_strategy("mycelium")[0]

    assert outcome.unresolved == ("knowledge/nowhere.md#absent/0",)
    assert not outcome.scorable
    assert report.unresolved == {"t-y": ("knowledge/nowhere.md#absent/0",)}
    assert report.scorable == 0


def test_an_unresolved_task_is_excluded_from_the_rate_rather_than_failing_it(
    corpus: Path,
) -> None:
    """Neither strategy can hand a model a passage that does not exist, so counting
    it as a failure would report anchor rot as retrieval quality."""
    answerable = AgentTask(
        task_id="t-ok",
        prompt="what licence is the project distributed under",
        requires=(anchor_for(corpus, "knowledge/licence.md"),),
    )
    rotted = AgentTask(task_id="t-rot", prompt="anything", requires=("gone.md#nowhere/0",))
    report = run_task_suite(corpus, [answerable, rotted])

    assert report.tasks == 2
    assert report.scorable == 1
    # 1/1, not 1/2: the denominator is what the corpus can still answer for.
    assert report.summary("mycelium")["success_rate"] == 1.0
    payload = report.as_dict()
    assert payload["scorable"] == 1
    assert payload["unresolved"] == {"t-rot": ["gone.md#nowhere/0"]}


def test_both_strategies_run_on_every_task(corpus: Path) -> None:
    """A comparison with one side missing is not a comparison (D-010)."""
    tasks = [
        AgentTask(task_id="t-1", prompt="retry backoff"),
        AgentTask(task_id="t-2", prompt="event bus messages"),
    ]
    report = run_task_suite(corpus, tasks)

    assert report.tasks == 2
    assert len(report.outcomes) == 4
    assert {item.strategy for item in report.outcomes} == {"mycelium", "grep"}


def test_grep_pays_for_whole_documents(corpus: Path) -> None:
    """The comparison's whole point: a grep hit is a line number, so the loop reads
    the file — and the file is what the model has to be handed."""
    task = AgentTask(task_id="t-z", prompt="retry backoff attempts parked")
    report = run_task_suite(corpus, [task])

    mycelium = report.by_strategy("mycelium")[0]
    grep = report.by_strategy("grep")[0]
    assert grep.tokens >= mycelium.tokens
    assert grep.documents_read <= mycelium.documents_read  # fewer files, more text


def test_the_budget_is_respected(corpus: Path) -> None:
    task = AgentTask(task_id="t-b", prompt="retry backoff messages licence bus")
    outcome = run_task_suite(corpus, [task], budget_tokens=20).by_strategy("mycelium")[0]
    assert outcome.tokens <= 20


def test_a_suite_round_trips_through_jsonl(tmp_path: Path) -> None:
    tasks = (
        AgentTask(task_id="t-1", prompt="one", kind="locate", requires=("a.md#x/0",), note="n"),
        AgentTask(task_id="t-2", prompt="two", kind="relate"),
    )
    path = write_tasks(tmp_path / "tasks.jsonl", tasks)

    assert load_tasks(path) == tasks
    assert path.read_bytes().endswith(b"\n")
    assert b"\r\n" not in path.read_bytes()  # deterministic bytes, like every asset


def test_the_committed_suite_meets_the_spec_floor() -> None:
    """Spec 04 §7.4 asks for ≥ 20 realistic tasks, and for more than one shape."""
    tasks = load_tasks(Path("eval/tasks.jsonl"))

    assert len(tasks) >= 20
    assert {task.kind for task in tasks} == {"answer", "locate", "relate"}
    assert all(task.requires for task in tasks)  # a task with no evidence scores nothing
    assert len({task.task_id for task in tasks}) == len(tasks)


def test_the_report_serialises_for_a_run_manifest(corpus: Path) -> None:
    report = run_task_suite(corpus, [AgentTask(task_id="t-1", prompt="retry")])
    payload = json.loads(json.dumps(report.as_dict()))

    assert payload["tasks"] == 1
    assert payload["scorable"] == 1
    assert payload["unresolved"] == {}
    assert set(payload["strategies"]) == {"mycelium", "grep"}
    assert payload["outcomes"][0]["task_id"] == "t-1"


def test_the_suite_gate_refuses_a_corpus_that_lost_a_required_passage(
    corpus: Path, tmp_path: Path
) -> None:
    """`mycelium eval --tasks --gate` gates the *instrument*, not the product.

    Whether Mycelium beats grep is scored qualitatively until 1.0 (spec 04 §7.4);
    whether the suite still measures anything is decidable today, and CI now asks
    (ADR-0120).
    """
    from typer.testing import CliRunner

    from mycelium.cli.app import app

    suite = corpus / "eval"
    suite.mkdir(exist_ok=True)
    good = AgentTask(
        task_id="t-ok",
        prompt="what licence is the project distributed under",
        requires=(anchor_for(corpus, "knowledge/licence.md"),),
    )
    write_tasks(suite / "tasks.jsonl", [good])
    runner = CliRunner()
    assert runner.invoke(app, ["eval", str(corpus), "--tasks", "--gate"]).exit_code == 0

    write_tasks(
        suite / "tasks.jsonl",
        [good, AgentTask(task_id="t-rot", prompt="x", requires=("gone.md#nowhere/0",))],
    )
    failed = runner.invoke(app, ["eval", str(corpus), "--tasks", "--gate"])
    assert failed.exit_code == 1
    assert "t-rot" in failed.stdout
    # Without the gate it is a report, exactly as it was before.
    assert runner.invoke(app, ["eval", str(corpus), "--tasks"]).exit_code == 0
