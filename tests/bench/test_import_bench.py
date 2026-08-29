# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""One real benchmark so `pytest tests/bench --benchmark-only` has something to collect
(roadmap 1.3; BUG-0003 guard note — an empty tests/bench/ exits 5, which CI reads as a
failure rather than "no benchmarks yet")."""

import importlib

from pytest_benchmark.fixture import BenchmarkFixture


def test_package_import(benchmark: BenchmarkFixture) -> None:
    benchmark(importlib.import_module, "mycelium")
