# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Snapshot lifecycle benchmarks (roadmap 3.2, ADR-0016).

The claim these back is comparative, not absolute: restoring a published
snapshot is cheaper than recompiling the corpus that produced it, which is what
makes `mycelium rollback` worth having on a single mutable store. Rollback is
*not* the O(1) pointer swap spec 02 §4.3 sketches — it rewrites the catalog and
the lexical index — so the number belongs beside the clean-build number in
`test_build_bench.py` rather than in a budget of its own.
"""

from pathlib import Path

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from mycelium.build import build, collect_garbage, list_snapshots, rollback

SECTIONS = "\n\n".join(
    f"## Section {index}\n\nProse for section {index}, mentioning [[doc-{index}]] "
    "and enough words to resemble documentation."
    for index in range(8)
)


@pytest.fixture(scope="module")
def published(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    """A repository with two published snapshots; the older one is the target."""
    root = tmp_path_factory.mktemp("bench-snapshots")
    for index in range(30):
        target = root / "knowledge" / "verified" / f"doc-{index}.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# Document {index}\n\n{SECTIONS}\n", encoding="utf-8")
    first = build(root).manifest  # pins identities and publishes the target

    edited = root / "knowledge" / "verified" / "doc-0.md"
    edited.write_text(edited.read_text(encoding="utf-8") + "\nDrift.\n", encoding="utf-8")
    build(root)
    return root, first.snapshot_id


def test_rollback_of_30_documents(published: tuple[Path, str], benchmark: BenchmarkFixture) -> None:
    root, snapshot_id = published
    benchmark(rollback, root, snapshot_id)


def test_listing_snapshots(published: tuple[Path, str], benchmark: BenchmarkFixture) -> None:
    root, _ = published
    benchmark(list_snapshots, root)


def test_gc_over_a_retained_history(
    published: tuple[Path, str], benchmark: BenchmarkFixture
) -> None:
    """The steady-state cost: nothing to collect, so this measures the sweep
    itself — what a scheduled `mycelium gc` pays when it finds a tidy store."""
    root, _ = published
    benchmark(collect_garbage, root)
