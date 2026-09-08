# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The settings every property test runs under (roadmap 4.29, ADR-0060).

Twenty-three property tests inherit their timing budget and their failure output
from one `register_profile` call in `conftest.py`. Nothing else in the suite would
notice if that call were deleted, reordered after `load_profile`, or shadowed —
the tests would simply go back to running on whatever the installed hypothesis
defaults to, which is the state roadmap 4.29 was filed to end. So the profile is
asserted like any other contract.
"""

import ast
import pathlib
from datetime import timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import conftest


def test_the_registered_profile_is_the_one_in_effect() -> None:
    """`register_profile` without `load_profile` is a no-op nobody would notice."""
    assert settings.default.deadline == timedelta(milliseconds=conftest.DEADLINE_MS)


def test_the_deadline_is_declared_rather_than_inherited() -> None:
    """The point of 4.29's first half.

    `hypothesis>=6.112` is the pin, and its default deadline is not part of that
    contract: a patch release may move the timing budget of every property test
    in this suite. Asserting the number here makes such a change arrive as a
    failing test in *this* file rather than as an intermittent failure somewhere
    else.
    """
    assert conftest.DEADLINE_MS == 200
    assert settings.get_profile(conftest.DEFAULT_PROFILE).deadline == timedelta(
        milliseconds=conftest.DEADLINE_MS
    )


def test_a_failure_prints_a_blob_that_survives_the_lost_database() -> None:
    """The other half: a failure has to be reproducible from the log alone.

    4.29 exists because a property test failed once in a full-suite run and left
    nothing behind — no persisted falsifying example, and a tail truncated before
    the traceback. `print_blob` puts a `@reproduce_failure(...)` in the failure
    output itself, which no truncation of the *database* can take away.
    """
    assert settings.default.print_blob is True


def test_the_debug_profile_exists_and_removes_the_deadline() -> None:
    """The documented route when an intermittent property failure recurs.

    Its deadline is `None` on purpose: while chasing a flake, a slow example
    must be *reported* by the statistics rather than converted into a failure
    whose cause is its own timing.
    """
    debug = settings.get_profile("debug")
    assert debug.deadline is None
    assert debug.print_blob is True
    assert debug.max_examples > settings.default.max_examples


def test_the_profile_env_var_selects_a_profile() -> None:
    """`HYPOTHESIS_PROFILE=debug` has to reach `load_profile`, not just exist."""
    assert conftest.PROFILE_ENV_VAR == "HYPOTHESIS_PROFILE"
    # Loading is global, so it is restored before this test returns.
    previous = settings.default
    try:
        settings.load_profile("debug")
        assert settings.default.deadline is None
    finally:
        settings.load_profile(conftest.DEFAULT_PROFILE)
        assert settings.default.deadline == previous.deadline


_EXAMPLES_SEEN: list[int] = []


@settings(max_examples=5)
@given(value=st.integers())
def _property_with_its_own_settings(value: int) -> None:
    _EXAMPLES_SEEN.append(value)


def test_a_per_test_setting_still_overrides_the_profile() -> None:
    """The profile is a floor, not a ceiling.

    Two property tests set `deadline=None` because their example body builds a
    corpus or a store (roadmap 3.1 and 4.29). That has to keep working, or the
    profile would be a regression rather than a seam.

    Asserted by counting examples rather than by reading hypothesis's private
    resolved-settings attribute: the profile does not set `max_examples`, so the
    library default of 100 applies, and `max_examples=5` here is only observable
    if the per-test decorator wins. An upper bound rather than equality, because
    the reuse phase may replay a remembered example on top of the five.
    """
    _EXAMPLES_SEEN.clear()
    _property_with_its_own_settings()
    assert 0 < len(_EXAMPLES_SEEN) <= 5 + 1, (
        f"{len(_EXAMPLES_SEEN)} examples ran; the profile's default of "
        f"{settings.default.max_examples} was not overridden"
    )


# ---------------------------------------------------------------------------
# The exemption, and the guard that keeps it honest (roadmap 4.32, ADR-0061)
# ---------------------------------------------------------------------------

TESTS_DIR = pathlib.Path(__file__).parent

FIXTURE_SIGNALS = frozenset({"tmp_path", "tmp_path_factory"})
"""Requesting a temp path from a *property* test means filesystem work per example."""

BODY_SIGNALS = (
    "SqliteStore",
    "TemporaryDirectory",
    "mktemp(",
    "write_text(",
    "write_bytes(",
    ".mkdir(",
    "shutil.",
)
"""Constructors whose cost lands inside hypothesis's measured window.

Deliberately short and literal. A wider list is not safer: an early draft
included `replace(` for `os.replace` and flagged
`test_digest_text_ignores_line_endings_and_composition`, whose `replace` is
`str.replace` on a line ending. A guard that cries wolf gets deleted, so this
list names only what has actually appeared in an example body, and the docstring
below states what it therefore cannot see."""


def _property_tests() -> list[tuple[str, ast.FunctionDef, dict[str, str]]]:
    """Every `@given` function under `tests/`, with its file's helper bodies."""
    found: list[tuple[str, ast.FunctionDef, dict[str, str]]] = []
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        helpers = {
            node.name: ast.unparse(node) for node in tree.body if isinstance(node, ast.FunctionDef)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and any(
                "given" in ast.unparse(d) for d in node.decorator_list
            ):
                found.append((path.name, node, helpers))
    return found


def _touches_io(node: ast.FunctionDef, helpers: dict[str, str]) -> list[str]:
    """Why this example body is I/O-bound, or an empty list if it is not."""
    reasons = [f"requests {a.arg}" for a in node.args.args if a.arg in FIXTURE_SIGNALS]
    sources = {node.name: ast.unparse(node)}
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
            body = helpers.get(sub.func.id)
            if body is not None:
                sources[sub.func.id] = body
    for where, source in sources.items():
        for signal in BODY_SIGNALS:
            if signal in source:
                site = "its body" if where == node.name else f"the helper {where}()"
                reasons.append(f"{signal.rstrip('(')} in {site}")
    return sorted(set(reasons))


def _exempt(node: ast.FunctionDef) -> bool:
    return any("deadline=None" in ast.unparse(d) for d in node.decorator_list)


def test_the_walker_sees_the_property_tests_it_is_supposed_to_guard() -> None:
    """A guard whose scan finds nothing passes vacuously — BUG-0020's lesson."""
    names = {name for _, node, _ in _property_tests() for name in [node.name]}
    assert len(names) > 20, f"only found {len(names)} property tests; the walker is broken"
    assert "test_any_query_text_is_safe" in names
    assert "test_any_mutation_sequence_stays_equal_to_clean" in names


def test_a_property_test_that_builds_a_store_exempts_itself_from_the_deadline() -> None:
    """Roadmap 4.32, stated as a rule instead of a list of four names.

    hypothesis's deadline covers the whole example body, fixtures included, so a
    property test that opens a store or writes a corpus per example is timing its
    filesystem and calling the result a property failure. That is BUG-0021, and it
    reached CI: 501 ms on `ubuntu-24.04` against an 8-10 ms typical.

    Two tests are in that shape today and both are exempt. The point of asserting
    it is the third one, whenever someone writes it: without this, it inherits a
    200 ms filesystem benchmark and fails on a busy machine months later, which is
    exactly how 4.29 started.

    Limit, stated rather than implied: the scan reads each test file and the
    helpers defined *in it*. A helper imported from another module that does the
    I/O would slip through, and no static rule closes that — which is why the
    exemption also carries a comment at each site.
    """
    gaps = []
    for filename, node, helpers in _property_tests():
        reasons = _touches_io(node, helpers)
        if reasons and not _exempt(node):
            gaps.append(f"{filename}::{node.name} — {', '.join(reasons)}")
    assert not gaps, (
        "these property tests do I/O per example and would be timed on it:\n  "
        + "\n  ".join(gaps)
        + "\n\nAdd @settings(deadline=None) with a comment saying what the deadline "
        "was measuring (see tests/test_store.py), or move the setup into a "
        "module-scoped fixture so it is not inside the measured window."
    )


@pytest.mark.parametrize(
    ("filename", "test_name"),
    [
        ("test_store.py", "test_any_query_text_is_safe"),
        ("test_build_incremental.py", "test_any_mutation_sequence_stays_equal_to_clean"),
    ],
)
def test_the_two_known_io_properties_are_the_ones_that_are_exempt(
    filename: str, test_name: str
) -> None:
    """Names the population, so a future reader does not have to re-derive it.

    Roadmap 4.32 was filed saying "four property tests"; the number came from a
    `pytest-xdist --dist load` run, where per-test distribution destroys this
    suite's fixture reuse and every worker rebuilds what a module-scoped fixture
    made once (ADR-0055). In the configuration this project actually ships, the
    population is these two.
    """
    match = [
        (node, helpers)
        for name, node, helpers in _property_tests()
        if name == filename and node.name == test_name
    ]
    assert match, f"{filename}::{test_name} is gone; 4.32's population has moved"
    node, helpers = match[0]
    assert _touches_io(node, helpers), f"{test_name} no longer does I/O per example"
    assert _exempt(node), f"{test_name} lost its deadline=None"
