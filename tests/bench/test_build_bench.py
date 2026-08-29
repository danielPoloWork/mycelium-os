# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Full-build benchmark (roadmap 2.7).

Measures the steady-state full rebuild of a 30-document repository — discover,
parse, chunk, store, manifest, publish. v0 rebuilds everything every time; the
incremental DAG (roadmap 3.1) is what must beat this number on single-document
edits (< 2 s p95, RFC-0001). Baseline only.
"""

from pathlib import Path

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from mycelium.build import build

SECTIONS = "\n\n".join(
    f"## Section {index}\n\nProse for section {index}, mentioning [[doc-{index}]] "
    "and enough words to resemble documentation."
    for index in range(8)
)


@pytest.fixture(scope="module")
def small_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("bench-build")
    for index in range(30):
        target = root / "knowledge" / "verified" / f"doc-{index}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# Document {index}\n\n{SECTIONS}\n", encoding="utf-8")
    build(root)  # pin identities once so the measured builds are steady-state
    return root


def test_full_rebuild_of_30_documents(small_repo: Path, benchmark: BenchmarkFixture) -> None:
    benchmark(build, small_repo)
