# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The derived verification mode (roadmap 4.31, ADR-0055).

`tools/verify.py` decides which gates a change runs. That makes it the control on threat-model
boundary **B13**: if the scope could be narrowed, choosing a mode would be a way to land
unverified code. So what is asserted here is not that the classifier is clever — it is that
every way of getting it wrong fails *wide*.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import verify  # noqa: E402 - the tool is not an installed package

# ---------------------------------------------------------------------------
# Derivation: the widest thing the diff touches decides
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        (["README.md", "docs/adr/0001-x.md"], "docs"),
        (["docs/assets/brand/logo.png"], "docs"),
        (["src/mycelium/markdown/adapter.py"], "code"),
        (["tests/test_store.py"], "code"),
        (["tools/measure_ranking.py"], "code"),
        (["pyproject.toml"], "code"),
        (["src/mycelium/retrieval.py"], "retrieval"),
        (["src/mycelium/store/sqlite.py"], "retrieval"),
        (["src/mycelium/config.py"], "retrieval"),
        # `harness.py` drives the retriever over the cases, averages the results
        # and decides every gate. It was outside the tuning paths, so a change to
        # it ran no gate at all — PR #81, where CI reported `eval / gates G1-G6`
        # as *skipping* (roadmap 4.35, ADR-0059).
        (["src/mycelium/eval/harness.py"], "retrieval"),
        (["eval/release.jsonl"], "retrieval"),
        (["eval/baselines/release.json"], "retrieval"),
        # A vendored corpus used to be wider than `retrieval`, because only `full`
        # built and gated one. `retrieval` gates them all now, so the exception
        # retired and one rule covers the sets, the baselines and the corpora
        # alike (roadmap 4.35, ADR-0059).
        (["eval/corpora/uv-docs/eval/release.jsonl"], "retrieval"),
        (["eval/corpora/uv-docs-ingested/provenance.json"], "retrieval"),
        ([".github/workflows/ci.yml"], "full"),
    ],
)
def test_a_path_derives_its_mode(paths: list[str], expected: str) -> None:
    mode, reason = verify.derive(paths)
    assert mode == expected
    assert paths[0] in reason or "changed" in reason


def test_a_corpus_change_gates_the_corpus_that_changed() -> None:
    """The narrowing roadmap 4.26 walked into, closed at the other end.

    4.26 fixed it by raising a corpus change to `full`, because `retrieval` built
    and gated *our* corpus and not the one that changed — so growing the set G3
    enforces on would have left that set's own gate unrun. 4.35 made `retrieval`
    gate every corpus, which removes the reason for the exception rather than the
    protection it gave: what matters is that the changed corpus is gated, not
    which rung does it (ADR-0059).
    """
    mode, _ = verify.derive(["eval/corpora/uv-docs/eval/release.jsonl"])
    assert mode == "retrieval"
    gated = " ".join(" ".join(command) for _, command in verify.plan(mode))
    assert "eval/corpora/uv-docs" in gated


def test_the_widest_path_decides_however_many_others_there_are() -> None:
    # One ranker file among a hundred documents is a retrieval change.
    paths = [f"docs/journal/2026/09/{n}.md" for n in range(100)]
    assert verify.derive(paths)[0] == "docs"
    assert verify.derive([*paths, "src/mycelium/retrieval.py"])[0] == "retrieval"
    assert verify.derive([*paths, ".github/workflows/ci.yml"])[0] == "full"


def test_an_unclassifiable_file_fails_wide() -> None:
    """The safe direction for a list nobody remembers to update."""
    mode, reason = verify.derive(["Dockerfile"])
    assert mode == "full"
    assert "classify" in reason


def test_an_empty_diff_runs_everything_rather_than_nothing() -> None:
    # "Nothing changed" is far more often a broken base ref than a no-op change.
    mode, reason = verify.derive([])
    assert mode == "full"
    assert "nothing changed" in reason


def test_a_tuning_path_outranks_an_eval_path() -> None:
    # Both derive `retrieval`, but the reason should name the one that can change
    # what a query returns rather than what the gates measure.
    _, reason = verify.derive(["eval/release.jsonl", "src/mycelium/retrieval.py"])
    assert "retrieval.py" in reason


# ---------------------------------------------------------------------------
# Resolution: widening is a request, narrowing is refused
# ---------------------------------------------------------------------------


def test_no_request_keeps_the_derived_mode() -> None:
    assert verify.resolve("code", None) == "code"


@pytest.mark.parametrize(("derived", "asked"), [("docs", "full"), ("code", "retrieval")])
def test_a_wider_mode_is_honoured(derived: str, asked: str) -> None:
    assert verify.resolve(derived, asked) == asked


def test_the_same_mode_is_honoured() -> None:
    assert verify.resolve("retrieval", "retrieval") == "retrieval"


@pytest.mark.parametrize(("derived", "asked"), [("retrieval", "docs"), ("full", "code")])
def test_a_narrower_mode_is_refused(
    derived: str, asked: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """B13's control. A mode that could be narrowed is a way to skip gates."""
    with pytest.raises(SystemExit) as caught:
        verify.resolve(derived, asked)
    assert caught.value.code == 2
    printed = capsys.readouterr().out
    assert f"refusing --mode {asked}" in printed
    assert derived in printed
    assert "B13" in printed, "the refusal names the boundary it protects"


# ---------------------------------------------------------------------------
# The plan: each mode is a superset of the narrower one
# ---------------------------------------------------------------------------


def test_every_mode_runs_everything_the_narrower_one_runs() -> None:
    """The property that makes "widen" mean what it says.

    Without it, `--mode full` could run *different* gates rather than more of
    them, and a widened run could skip something the derived mode covered.
    """
    plans = [[name for name, _ in verify.plan(mode)] for mode in verify.MODES]
    for narrower, wider in zip(plans, plans[1:], strict=False):
        assert wider[: len(narrower)] == narrower, "a wider mode reordered or dropped a gate"
        assert len(wider) > len(narrower), "a wider mode must actually add something"


def test_retrieval_gates_every_vendored_corpus() -> None:
    """Roadmap 4.35's decision, as the assertion that would have caught its absence.

    These are the sets gate G3 enforces on (ADR-0053). A retrieval change that
    does not gate them is a retrieval change nobody measured where it counts —
    and CI has gated them at this mode all along, which is the drift ADR-0059
    closed.
    """
    gated = " ".join(" ".join(command) for _, command in verify.plan("retrieval"))
    for corpus in verify.CORPORA:
        assert f"eval {corpus}" in gated, f"`retrieval` does not gate {corpus}"


def test_full_adds_the_benchmarks_rather_than_a_wider_name() -> None:
    """Moving the corpora down into `retrieval` left `full` needing content of its own.

    A mode that adds nothing promises a gate it does not run. The suite executes
    the benchmarks beside four hundred other tests on a loaded machine; a
    performance claim needs them alone (AGENTS.md §10), and it is the one job CI
    gates on `full`.
    """
    added = [name for name, _ in verify.plan("full")][len(verify.plan("retrieval")) :]
    assert added == ["benchmarks"]


def test_the_congruence_lint_runs_in_every_mode() -> None:
    # Including `docs`, which is the mode most changes to this repository take.
    for mode in verify.MODES:
        assert verify.plan(mode)[0][0] == "congruence"


def test_the_cheapest_gates_come_first() -> None:
    # A failing run should cost seconds, not the whole suite.
    names = [name for name, _ in verify.plan("full")]
    assert names.index("format") < names.index("tests")
    assert names.index("tests") < names.index("gates")


def test_every_command_invokes_this_interpreter() -> None:
    """Never a bare `python` or a console script: a virtualenv's `Scripts/` is not
    on PATH on every runner, and the gate that silently ran the wrong interpreter
    would be the one nobody could reproduce."""
    for _, command in verify.plan("full"):
        assert command[0] == sys.executable
