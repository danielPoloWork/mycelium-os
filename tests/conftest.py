# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Shared test fixtures, and the settings every property test runs under.

The one rule enforced here is that **a test's outcome must not depend on what
this machine happens to have downloaded**. The default embedding provider is
`local-onnx` (D-013), so a developer who has fetched the 133 MB model would
otherwise run a different suite from CI: builds would embed, counts would carry
vectors, and the determinism corpus would drift with the runtime's kernels.

So every test runs against an *empty* model cache by default and sees the
behaviour a fresh install sees — vectors unavailable, snapshot degraded, lexical
search intact. Tests that genuinely need the model ask for the `local_model`
fixture, which finds the real cache and skips when it is absent.

The same rule is why the hypothesis profile below exists: a property test's
timing budget was an *unversioned* input to this suite until roadmap 4.29, and
that is the same class of problem as an undeclared model cache — a threshold
nobody in this repository chose, able to move under a dependency bump.
"""

import os
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from hypothesis import Verbosity, settings

from fakes import FakeEmbedder
from mycelium.embedding.models import CACHE_ENV_VAR, DEFAULT_MODEL_ID, MODELS, cache_root

# ---------------------------------------------------------------------------
# Hypothesis profiles (roadmap 4.29, ADR-0060)
# ---------------------------------------------------------------------------

PROFILE_ENV_VAR = "HYPOTHESIS_PROFILE"
"""Which registered profile to load. Unset means :data:`DEFAULT_PROFILE`."""

DEFAULT_PROFILE = "mycelium"
DEADLINE_MS = 200
"""Per-example deadline, in milliseconds — deliberately the value hypothesis
6.165 already defaults to.

Restating a default looks like a no-op and is not. It was *unversioned*: nothing
in this repository named it, so `hypothesis>=6.112` was free to move the timing
budget of all twenty-three property tests in a patch release, and a suite with a
byte-identical-output gate (G6) should not have an input nobody declared. It is
also the seam roadmap 4.32 acts on — property tests whose deadline measures
SQLite store creation rather than the property they assert — and having one place
to act on is the point.

Changing the *number* is a separate decision from making it explicit, and it is
not taken here. Measured with `--hypothesis-show-statistics` on 2026-09-08 over
23 property tests: twenty-one run at 0-10 ms per example on every platform, which
is 20x headroom or better. Two do not:

- `test_any_mutation_sequence_stays_equal_to_clean` rebuilds a corpus
  (890-1784 ms) and has set `deadline=None` since roadmap 3.1.
- `test_any_query_text_is_safe` opens a SQLite store per example: 8-10 ms on
  `ubuntu-24.04`, 5-10 ms on `macos-14`, 40-62 ms on `windows-2022`, and
  **63-74 ms typical on a Windows development machine, where it exceeds the
  deadline outright** — 269 ms and 1075 ms observed, failing 5 of 6 runs from a
  cleared example database (BUG-0021). That is roadmap 4.32's test, and its fix
  is one `deadline=None` decorator there, not a change to this number.

So the number is left alone for a reason that survives the measurement rather
than resting on it: raising it would silently absorb 4.32, and lowering it to fit
the twenty-one would fail the store test everywhere instead of on one platform.
A global threshold cannot fix a test whose fixture cost is inside the measured
window — only a per-test `deadline=None` can, which is why the profile is a seam
and not a solution.
"""

settings.register_profile(
    DEFAULT_PROFILE,
    deadline=timedelta(milliseconds=DEADLINE_MS),
    print_blob=True,
)
"""The profile the suite runs under everywhere, locally and in CI.

`print_blob` is the diagnosability half: on a failure hypothesis prints a
`@reproduce_failure(...)` blob alongside the falsifying example, so the example
can be replayed from the *log* even when the example database that recorded it is
gone. Roadmap 4.29 exists because a property test failed once in a full-suite run
and left nothing behind to look at."""

settings.register_profile(
    "debug",
    deadline=None,
    print_blob=True,
    verbosity=Verbosity.verbose,
    max_examples=1000,
)
"""For chasing an intermittent property failure, and nothing else.

    HYPOTHESIS_PROFILE=debug pytest tests/test_markdown_adapter.py \\
        --hypothesis-show-statistics

No deadline (so a slow example is *reported* rather than converted into a
failure whose cause is its own timing), verbose (every example is printed), and
ten times the examples. Never the default: it makes a run slow and chatty, and a
suite that cannot fail on time is a suite that cannot notice a twenty-fold
slowdown in a parse-and-assert property."""

settings.load_profile(os.environ.get(PROFILE_ENV_VAR) or DEFAULT_PROFILE)


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture(autouse=True)
def _isolated_model_cache(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Point the model cache at an empty directory for the whole suite."""
    empty = tmp_path_factory.mktemp("empty-model-cache")
    previous = os.environ.get(CACHE_ENV_VAR)
    os.environ[CACHE_ENV_VAR] = str(empty)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(CACHE_ENV_VAR, None)
        else:
            os.environ[CACHE_ENV_VAR] = previous


@pytest.fixture
def local_model(request: pytest.FixtureRequest) -> Path:
    """The real model directory, or a skip.

    Restores the developer's cache location for this test only — the isolation
    above is a default, not a prohibition. CI has no model, so every test using
    this fixture skips there; the numbers they produce are reproduced by hand and
    recorded in ADR-0017 rather than asserted from a machine that cannot run them.
    """
    request.getfixturevalue("_isolated_model_cache")
    os.environ.pop(CACHE_ENV_VAR, None)
    directory = cache_root() / DEFAULT_MODEL_ID
    spec = MODELS[DEFAULT_MODEL_ID]
    missing = [item.name for item in spec.files if not (directory / item.name).is_file()]
    if missing:
        pytest.skip(f"{DEFAULT_MODEL_ID} not cached locally (missing {', '.join(missing)})")
    return directory
