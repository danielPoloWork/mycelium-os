# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Configuration-read benchmarks (roadmap 6.18, ADR-0128).

The claim these back is the one that made NFR-2 reachable at all. `handle_search`
reads `mycelium.toml` per call — correctly, because an operator may edit it under
a running server — and `load_config` asked `mycelium.modules` whether a section
names an installed module (ADR-0077). That question called
:func:`importlib.metadata.entry_points`, which re-reads the metadata of **every**
installed distribution on every call: **259 ms** on the machine of record,
against the 150 ms budget spec 04 §1 sets for an entire `mycelium_search`. The
6.4 reference profile found the consequence — no corpus of any size had ever met
that budget, including one a hundred times smaller than the condition the budget
is stated for — and the cost was a constant that had nothing to do with
retrieval.

Measured on this repository's own corpus, before and after the scan was cached:

| | before | after |
|---|---:|---:|
| `modules.installed_ids()` | 264 ms | **0.00 ms** |
| `load_config()` | 262 ms | **2.4 ms** |
| `handle_search` end to end | 302 ms | **41 ms** |

So what `load_config` costs now is what reading and validating the file costs,
which is the thing it is supposed to cost. This file guards that: the budget
below is deliberately loose against the measured 2.4 ms, because it is here to
catch a **reintroduced environment scan** — a 100x regression — rather than to
police a millisecond on a shared runner.

Why there is no second cache here: the item that filed this predicted two, one
per lifetime — an entry-point scan belongs to the environment and a
`mycelium.toml` to the repository. The measurement refused the second one. At
2.4 ms it would buy less than the store open beside it (8.7 ms) against a 150 ms
budget, and it would cost an invalidation question — a build may rewrite the
file — for a saving nothing can perceive (ADR-0128).
"""

import time

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from mycelium import modules
from mycelium.config import CONFIG_FILENAME, load_config

CONFIG_BUDGET_MS = 25
"""A guard on the *mechanism*, not on the machine.

Two orders of magnitude above the measured read and an order of magnitude below
the 259 ms scan it exists to keep out, so it fires on a reintroduced scan and
stays quiet on a slow morning."""

FILE = """
[project]
name = "bench-docs"
exclude = ["tests", "docs/journal"]

[ingest]
parsers = ["markdown"]
connectors = ["file"]

[retrieval]
profile = "lexical"

[chunking]
max_tokens = 512
"""


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory) -> object:
    root = tmp_path_factory.mktemp("bench-config")
    (root / CONFIG_FILENAME).write_text(FILE, encoding="utf-8")
    return root


def test_load_config(repo: object, benchmark: BenchmarkFixture) -> None:
    load_config(repo)  # type: ignore[arg-type]  # the first call scans, once per process
    benchmark(load_config, repo)


def test_reading_the_configuration_stays_off_the_environment(repo: object) -> None:
    """Not a benchmark: the assertion the table above turns into a guard.

    A `load_config` that scans the environment again costs ~259 ms, so this
    fires long before anyone reads a benchmark report.
    """
    load_config(repo)  # type: ignore[arg-type]
    started = time.perf_counter()
    load_config(repo)  # type: ignore[arg-type]
    assert (time.perf_counter() - started) * 1000 < CONFIG_BUDGET_MS


def test_the_scan_is_what_was_expensive(repo: object) -> None:
    """Not a benchmark: it names the cost, so a future reader of the table above
    can tell whether the number moved because of the file or the environment."""
    modules.forget_installed()
    started = time.perf_counter()
    modules.installed_ids()
    cold = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    modules.installed_ids()
    warm = (time.perf_counter() - started) * 1000

    # The scan is not asserted to be *slow* — it is whatever the environment
    # makes it — only that the cache is what stands between it and every call.
    assert warm < cold or cold < 1.0
    assert warm < 1.0
