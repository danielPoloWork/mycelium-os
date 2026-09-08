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

from datetime import timedelta

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

    `test_build_incremental.py` sets `deadline=None` on a property that rebuilds a
    corpus, and roadmap 4.32 will do the same for the tests whose deadline
    measures store creation. That has to keep working, or the profile would be a
    regression rather than a seam.

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
