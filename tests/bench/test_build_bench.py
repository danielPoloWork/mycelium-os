# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Build benchmarks (roadmap 2.7 baseline; roadmap 3.1 incremental claims).

Three numbers on the same 30-document repository, because the incremental
claim (RFC-0001: single-document edit rebuild < 2 s p95, byte-equal to clean)
is a *relationship* between them:

- **clean** — recompile everything, no cache: the 2.7 baseline, still what a
  cold start costs;
- **no-op incremental** — nothing changed: the floor (plan + publish overhead);
- **single-edit incremental** — one document changed: what an editing loop
  actually pays, and the number the < 2 s budget governs.
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


def _make_repo(tmp_path_factory: pytest.TempPathFactory, name: str) -> Path:
    root = tmp_path_factory.mktemp(name)
    for index in range(30):
        target = root / "knowledge" / "verified" / f"doc-{index}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# Document {index}\n\n{SECTIONS}\n", encoding="utf-8")
    build(root)  # pin identities once so the measured builds are steady-state
    return root


@pytest.fixture(scope="module")
def steady_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _make_repo(tmp_path_factory, "bench-build")


@pytest.fixture(scope="module")
def edited_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _make_repo(tmp_path_factory, "bench-build-edit")


def test_clean_rebuild_of_30_documents(steady_repo: Path, benchmark: BenchmarkFixture) -> None:
    benchmark(build, steady_repo, clean=True)


def test_noop_incremental_build(steady_repo: Path, benchmark: BenchmarkFixture) -> None:
    benchmark(build, steady_repo)


def test_single_edit_incremental_build(edited_repo: Path, benchmark: BenchmarkFixture) -> None:
    target = edited_repo / "knowledge" / "verified" / "doc-0.md"
    pinned = target.read_text(encoding="utf-8")  # keeps the identity frontmatter
    counter = iter(range(1_000_000))

    def edit_one() -> None:
        target.write_text(f"{pinned}\nEdit {next(counter)}.\n", encoding="utf-8")

    benchmark.pedantic(build, args=(edited_repo,), setup=edit_one, rounds=10)
