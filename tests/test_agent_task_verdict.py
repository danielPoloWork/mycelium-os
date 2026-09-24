# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Spec 04 §7.4's verdict: does Mycelium beat grep? (roadmap 7.3, D-031, ADR-0156).

The rule is a decision, so the numbers are pinned here: a lead of **more than two**
tasks (ADR-0120), a one-sided exact **sign test** below 0.05 over the tasks exactly one
strategy found (D-031), and a **median** context at most half grep's. It is read on the
corpora this project did not write, and armed there in CI and the ladder.
"""

from pathlib import Path

import pytest

from mycelium.eval.tasks import (
    VERDICT_CONTEXT_RATIO,
    VERDICT_LEAD_TASKS,
    VERDICT_SIGN_ALPHA,
    TaskOutcome,
    TaskSuiteReport,
    load_tasks,
    sign_test_p,
    task_verdict,
)


def _report(
    pairs: list[tuple[bool, bool]],
    *,
    ours_tokens: int = 1_000,
    grep_tokens: int = 5_000,
    unresolved: int = 0,
) -> TaskSuiteReport:
    """A suite whose i-th task Mycelium and grep found as `pairs[i]` says."""
    outcomes: list[TaskOutcome] = []
    for index, (ours, theirs) in enumerate(pairs):
        stale = ("gone.md#x/0",) if index < unresolved else ()
        for strategy, found, tokens in (
            ("mycelium", ours, ours_tokens),
            ("grep", theirs, grep_tokens),
        ):
            outcomes.append(
                TaskOutcome(
                    task_id=f"t-{index:04d}",
                    strategy=strategy,
                    found=found,
                    missing=(),
                    tokens=tokens,
                    documents_read=1,
                    latency_ms=1,
                    unresolved=stale,
                )
            )
    return TaskSuiteReport(tasks=len(pairs), outcomes=tuple(outcomes))


def _suite(wins: int, losses: int, both: int, neither: int, **kwargs: int) -> TaskSuiteReport:
    pairs = (
        [(True, False)] * wins
        + [(False, True)] * losses
        + [(True, True)] * both
        + [(False, False)] * neither
    )
    return _report(pairs, **kwargs)


def test_the_rule_is_the_one_decided() -> None:
    """If a number moves, it moves in a decision (D-031) and this is how the code learns."""
    assert VERDICT_LEAD_TASKS == 2
    assert VERDICT_SIGN_ALPHA == 0.05
    assert VERDICT_CONTEXT_RATIO == 0.5


@pytest.mark.parametrize(
    ("wins", "losses", "expected"),
    [(0, 0, 1.0), (3, 0, 0.125), (5, 0, 0.03125), (7, 1, 0.03515625), (6, 4, 0.376953125)],
)
def test_the_sign_test_is_exact(wins: int, losses: int, expected: float) -> None:
    assert sign_test_p(wins, losses) == pytest.approx(expected)


def test_a_clear_lead_at_a_quarter_of_the_context_holds() -> None:
    verdict = task_verdict(_suite(7, 1, 12, 2))
    assert (verdict.lead, verdict.only_mycelium, verdict.only_grep) == (6, 7, 1)
    assert verdict.holds, verdict.failures()


def test_a_lead_of_exactly_two_does_not_hold() -> None:
    """*More than* two: the lead 6.22 measured, 16 to 14, is the case the bar refuses."""
    verdict = task_verdict(_suite(2, 0, 14, 6))
    assert verdict.lead == 2
    assert not verdict.holds
    assert any("not more than 2" in reason for reason in verdict.failures())


def test_a_lead_the_suite_cannot_tell_from_chance_does_not_hold() -> None:
    """Three to nothing clears the lead and is a coin flipped three times (p = 0.125)."""
    verdict = task_verdict(_suite(3, 0, 15, 4))
    assert verdict.lead_holds
    assert not verdict.significant
    assert not verdict.holds


def test_a_lead_bought_among_many_disagreements_does_not_hold() -> None:
    """This repository today: +2 from six to four - the lead fails, and so would p."""
    verdict = task_verdict(_suite(6, 4, 10, 2))
    assert verdict.sign_p == pytest.approx(0.376953125)
    assert not verdict.holds


def test_the_context_bar_is_on_the_median() -> None:
    held = task_verdict(_suite(7, 1, 12, 2, ours_tokens=2_500, grep_tokens=5_000))
    assert held.context_holds
    missed = task_verdict(_suite(7, 1, 12, 2, ours_tokens=2_501, grep_tokens=5_000))
    assert not missed.context_holds
    assert not missed.holds


def test_an_unsound_suite_has_no_verdict() -> None:
    """An unresolved anchor voids the verdict whatever the rates say (ADR-0120)."""
    verdict = task_verdict(_suite(9, 0, 12, 1, unresolved=1))
    assert verdict.unresolved == 1
    assert not verdict.holds
    assert verdict.scorable == 21


@pytest.mark.parametrize("corpus", ["eval/corpora/uv-docs", "eval/corpora/uv-docs-ingested"])
def test_the_verdict_is_read_on_the_corpora_we_did_not_write(corpus: str) -> None:
    """The suites the gate is armed on are the vendored ones, and they are whole."""
    tasks = load_tasks(Path(corpus) / "eval" / "tasks.jsonl")
    assert len(tasks) >= 20


def test_the_cli_gate_fails_when_the_verdict_does_not_hold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    import mycelium.eval as evaluation
    from mycelium.cli.app import app

    (tmp_path / "eval").mkdir()
    (tmp_path / "eval" / "tasks.jsonl").write_text("", encoding="utf-8")
    runner = CliRunner()

    monkeypatch.setattr(evaluation, "run_task_suite", lambda _root, _tasks: _suite(2, 0, 14, 6))
    failed = runner.invoke(app, ["eval", str(tmp_path), "--tasks", "--gate", "--verdict"])
    assert failed.exit_code == 1
    # Without --verdict the same run is only the integrity gate, and passes.
    assert runner.invoke(app, ["eval", str(tmp_path), "--tasks", "--gate"]).exit_code == 0

    monkeypatch.setattr(evaluation, "run_task_suite", lambda _root, _tasks: _suite(7, 1, 12, 2))
    held = runner.invoke(app, ["eval", str(tmp_path), "--tasks", "--gate", "--verdict"])
    assert held.exit_code == 0, held.stdout


def test_verdict_without_tasks_is_a_usage_error(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from mycelium.cli.app import app

    result = CliRunner().invoke(app, ["eval", str(tmp_path), "--verdict"])
    assert result.exit_code == 2
