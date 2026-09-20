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
from mycelium.eval.tasks import (
    MAX_SEARCH_K,
    AgentTask,
    load_tasks,
    run_task_suite,
    write_tasks,
)
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


def test_grep_pays_for_whole_documents_when_they_fit(corpus: Path) -> None:
    """The comparison's whole point: a grep hit is a line number, so the loop reads
    the file — and the file is what the model has to be handed. A small document is
    read whole, which is every document in this fixture and most of a real corpus."""
    task = AgentTask(task_id="t-z", prompt="retry backoff attempts parked")
    report = run_task_suite(corpus, [task])

    mycelium = report.by_strategy("mycelium")[0]
    grep = report.by_strategy("grep")[0]
    assert grep.tokens >= mycelium.tokens


def test_the_budget_is_respected(corpus: Path) -> None:
    task = AgentTask(task_id="t-b", prompt="retry backoff messages licence bus")
    outcome = run_task_suite(corpus, [task], budget_tokens=20).by_strategy("mycelium")[0]
    assert outcome.tokens <= 20


# ---------------------------------------------------------------------------
# What a grep loop does with a file larger than its budget (roadmap 6.22)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def lopsided(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One document far larger than any read, beside small ones that answer.

    The shape that broke the measurement on the real corpus: `ROADMAP.md` grew to
    88 000 tokens, matched every query, and was read whole — so the loop spent its
    whole budget on the wrong file and never opened a second (ADR-0131).
    """
    root = tmp_path_factory.mktemp("lopsided")
    (root / "knowledge").mkdir()
    filler = "\n\n".join(
        f"## Section {index}\n\nRetry backoff messages bus parked attempts. " + "word " * 200
        for index in range(40)
    )
    (root / "knowledge/huge.md").write_text(f"# Huge\n\n{filler}\n", encoding="utf-8", newline="\n")
    for name, text in CORPUS.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    build(root)
    return root


def test_a_document_larger_than_the_read_does_not_consume_the_whole_loop(
    lopsided: Path,
) -> None:
    """The defect 6.4 found and 6.22 fixed, in one assertion.

    Before: the first matching file was read whole whatever it cost, so one
    oversized document was the entire measurement and the other four reads the
    model promises never happened.
    """
    task = AgentTask(task_id="t-huge", prompt="retry backoff bus licence distributed")
    outcome = run_task_suite(lopsided, [task], budget_tokens=4_000).by_strategy("grep")[0]

    assert outcome.documents_read == 4  # every matching file, not just the biggest
    assert outcome.tokens <= 4 * 4_000  # bounded by the model of the loop


def test_the_evidence_in_a_small_file_survives_a_huge_one_ranking_above_it(
    lopsided: Path,
) -> None:
    """Why the bound is not a detail: the answer is in a file the loop only reaches
    because it is no longer spending everything on the first one."""
    task = AgentTask(
        task_id="t-reach",
        prompt="retry backoff bus licence distributed",
        requires=(anchor_for(lopsided, "knowledge/licence.md"),),
    )
    assert run_task_suite(lopsided, [task], budget_tokens=4_000).by_strategy("grep")[0].found


def test_one_read_costs_at_most_the_callers_budget(lopsided: Path) -> None:
    """A read is bounded by what one search may spend, so the incumbent's cost is a
    property of the loop rather than of whichever document happened to match."""
    task = AgentTask(task_id="t-window", prompt="retry backoff")
    for budget in (500, 1_000, 4_000):
        outcome = run_task_suite(lopsided, [task], budget_tokens=budget).by_strategy("grep")[0]
        assert outcome.tokens <= outcome.documents_read * budget


def test_a_section_larger_than_the_window_is_read_but_carries_no_evidence(
    tmp_path: Path,
) -> None:
    """The case that has to be named: the agent saw part of a passage, which is not
    being handed it. Scoring it as evidence would credit text nobody can point at."""
    root = tmp_path / "one-huge-section"
    (root / "knowledge").mkdir(parents=True)
    (root / "knowledge/wall.md").write_text(
        "# Wall\n\n## Only\n\n" + "backoff retry " * 4_000 + "\n", encoding="utf-8", newline="\n"
    )
    build(root)
    section = anchor_for(root, "knowledge/wall.md")

    task = AgentTask(task_id="t-wall", prompt="backoff retry", requires=(section,))
    outcome = run_task_suite(root, [task], budget_tokens=1_000).by_strategy("grep")[0]

    assert outcome.documents_read == 1
    assert outcome.tokens == 1_000  # the read happened, and was truncated
    assert not outcome.found  # and it is not evidence
    assert outcome.unresolved == ()  # the passage exists; the read did not cover it


def test_how_many_files_the_loop_opens_is_a_parameter_the_band_can_vary(
    lopsided: Path,
) -> None:
    """`tools/measure_agent_task_band.py` measures the constant instead of asserting
    it, which is only possible because the loop takes it rather than reads it."""
    task = AgentTask(task_id="t-band", prompt="retry backoff bus licence distributed")
    read = [
        run_task_suite(lopsided, [task], max_grep_files=count).by_strategy("grep")[0]
        for count in (1, 2, 4)
    ]

    assert [outcome.documents_read for outcome in read] == [1, 2, 4]
    assert read[0].tokens < read[1].tokens < read[2].tokens


def test_our_own_constant_is_the_one_the_tool_states() -> None:
    """`MAX_SEARCH_K` is declared here and must equal the cap `mycelium_search`
    enforces (roadmap 6.28, ADR-0143).

    Declared rather than imported, so the suite does not drag the serving surface
    into its import graph to read one integer — the shape roadmap 6.18 removed
    from the configuration path. Declaring it is only safe while something checks
    it, which is this.
    """
    from mycelium.mcp.tools import _MAX_K

    assert MAX_SEARCH_K == _MAX_K


def test_our_arm_can_spend_the_budget_it_is_given(lopsided: Path) -> None:
    """The defect 6.22 filed: `_mycelium_context` asked for ten results whatever
    the budget said, so the arm saturated and the comparison understated us while
    the incumbent went on scaling.

    What is asserted is the *shape* rather than a number: more budget must buy
    more context, up to what the corpus holds. The `lopsided` fixture is the one
    that can show it — the small corpus holds 41 tokens of matching text, so
    every budget above that is trivially saturated by the documents rather than
    by the arm.
    """
    task = AgentTask(task_id="t-budget", prompt="retry backoff bus licence distributed")
    spent = [
        run_task_suite(lopsided, [task], budget_tokens=budget).by_strategy("mycelium")[0].tokens
        for budget in (500, 2_000, 8_000)
    ]

    assert spent[0] <= 500, "the budget still bounds the answer"
    assert spent[0] < spent[1] < spent[2], f"the arm saturated at {spent}"


def test_a_caller_that_asks_for_less_gets_less(lopsided: Path) -> None:
    """`k` is a parameter the band varies, the way the incumbent's two already
    were. It binds before the budget does, which is why the published band shows
    both and why leaving it out let the saturation go unnoticed."""
    task = AgentTask(task_id="t-k", prompt="retry backoff bus licence distributed")
    small, large = (
        run_task_suite(lopsided, [task], budget_tokens=16_000, search_k=k)
        .by_strategy("mycelium")[0]
        .tokens
        for k in (1, MAX_SEARCH_K)
    )

    assert small < large, "asking for one result cannot cost what asking for fifty does"


def test_an_oversized_passage_is_skipped_rather_than_ending_the_packing(
    lopsided: Path,
) -> None:
    """The second correction, and it is fidelity to the tool: `handle_search` puts
    a result that would not fit into `omitted` and keeps filling from the rest of
    the ranking (spec 05 §3.1). This function used to **stop**, so one large
    passage early in the ranking cost the arm everything behind it.
    """
    task = AgentTask(task_id="t-skip", prompt="retry backoff bus licence distributed")
    outcome = run_task_suite(lopsided, [task], budget_tokens=400).by_strategy("mycelium")[0]

    assert outcome.tokens <= 400, "the budget is still the bound"
    assert outcome.documents_read >= 1, (
        "something fitted, which a `break` at the first oversized passage would have prevented"
    )


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


def test_the_committed_suite_on_the_corpus_we_did_not_write_meets_the_same_floor() -> None:
    """Spec 04 §7.4's floor, on the suite the 1.0 verdict is meant to be read on.

    The same assertions as the suite above, on the corpus ADR-0053 says a *gate*
    has to run on: twenty tasks, more than one shape, evidence behind every one
    (roadmap 6.23, ADR-0135).
    """
    tasks = load_tasks(Path("eval/corpora/uv-docs/eval/tasks.jsonl"))

    assert len(tasks) >= 20
    assert {task.kind for task in tasks} == {"answer", "locate", "relate"}
    assert all(task.requires for task in tasks)
    assert len({task.task_id for task in tasks}) == len(tasks)
    # Every anchor names a document of that corpus, which is the half of "we did
    # not write it" a file can assert on its own.
    assert all(anchor.startswith("docs/") for task in tasks for anchor in task.requires), (
        "a required anchor points outside the vendored corpus"
    )


def test_the_twins_suite_is_carried_rather_than_judged() -> None:
    """Nothing in the ingested twin's suite is a fresh judgement (ADR-0135).

    Every task id, prompt, kind and note is the source suite's; only the anchors
    differ, because only the anchors are computed. A prompt that diverged would
    mean somebody re-judged the twin, which answers a question about this agent
    rather than about retrieval (ADR-0027).
    """
    source = {
        task.task_id: task for task in load_tasks(Path("eval/corpora/uv-docs/eval/tasks.jsonl"))
    }
    carried = load_tasks(Path("eval/corpora/uv-docs-ingested/eval/tasks.jsonl"))

    assert carried, "the twin's suite is empty"
    for task in carried:
        origin = source[task.task_id]
        assert (task.prompt, task.kind, task.note) == (origin.prompt, origin.kind, origin.note)
        assert task.requires, "a carried task kept no evidence"
        assert len(task.requires) <= len(origin.requires)
        assert all(anchor.startswith("knowledge/evidence/") for anchor in task.requires)


def test_a_manifest_says_which_corpus_ran_and_never_a_local_path(tmp_path: Path) -> None:
    """What a published manifest claims about its own run (roadmap 6.23).

    Two things it must get right, because both end up committed: *which* corpus
    the comparison ran on — the verdict means different things on ours and on a
    vendored one (ADR-0053) — and a path a reader elsewhere can resolve. The
    self-hosted arm is measured in a clean checkout precisely because the working
    tree holds the report, and that checkout's temporary directory has no business
    in the record.
    """
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
    from measure_agent_task_band import ROOT, kind_of, recorded

    assert kind_of(ROOT / "eval" / "tasks.jsonl") == "this repository's own, compiled"
    assert "did not write" in kind_of(ROOT / "eval/corpora/uv-docs/eval/tasks.jsonl")
    # A checkout somewhere else is recorded relative to itself, not by its path.
    assert recorded(tmp_path, tmp_path) == "."
    assert recorded(tmp_path / "eval" / "tasks.jsonl", tmp_path) == "eval/tasks.jsonl"
    assert recorded(ROOT / "eval" / "corpora" / "uv-docs", ROOT) == "eval/corpora/uv-docs"
