# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""What a content-addressed blob write costs, and what the ceremony added to it.

Roadmap 6.19 put **~79 s of a 91.7 s** thousand-document cold build into 2 995
`cas_put` calls and attributed the cost to two things at once: a real-time
scanner in the write path, and the atomic ceremony doubling it. Roadmap 6.30
decomposed that (`tools/measure_cas_write.py`, ADR-0145) and found the split is
not where 6.19 guessed — on the machine of record the *second name* costs
~6.7 ms per blob and the fsync ~2.0 ms — so `cas_put` now writes straight to its
final name and the re-hash on read is the integrity story.

These three benchmarks are that decision's evidence, in the one place CI can
re-take it. `atomic_write_bytes` is measured beside `cas_put` deliberately: the
ceremony has not gone away, it has moved to the callers that need it (snapshot
publication, tier-1 custody, quarantine), and the ratio between the two lines is
what says whether keeping it there is still cheap.

**The ratio is the claim, not the milliseconds.** ADR-0132 measured this project
on a machine whose plain 4 KiB write costs about 500x an unencumbered SSD, and
this file exists partly so the same three numbers are taken on a CI runner that
has no filter driver at all. A reading where the ceremony is ~1x a plain write
says the Windows figure is one machine's; a reading where it is ~2x says the
shape is portable and only the constant is local.
"""

from pathlib import Path

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from mycelium.build.cas import cas_put
from mycelium.layout import atomic_write_bytes, write_bytes

BLOB = "x" * (12 * 1024)
"""This repository's own CAS holds a median blob of ~11.8 KiB."""


@pytest.fixture
def mycelium_dir(tmp_path: Path) -> Path:
    (tmp_path / "cas").mkdir()
    return tmp_path


def test_cas_put_of_a_median_blob(mycelium_dir: Path, benchmark: BenchmarkFixture) -> None:
    """The shipped path: hash, probe, write directly.

    Each round writes a *distinct* blob, because a `cas_put` of a digest already
    on disk returns without writing — benchmarking that would measure the
    `exists()` probe and report it as the cost of storing an artifact.
    """
    counter = iter(range(1_000_000))

    def store() -> None:
        cas_put(mycelium_dir, f"{BLOB}{next(counter)}")

    benchmark(store)


def test_a_plain_write_of_a_median_blob(tmp_path: Path, benchmark: BenchmarkFixture) -> None:
    """The primitive underneath, with no hashing and no probe."""
    data = BLOB.encode("utf-8")
    counter = iter(range(1_000_000))

    def store() -> None:
        write_bytes(tmp_path / f"blob-{next(counter)}", data)

    benchmark(store)


def test_an_atomic_write_of_a_median_blob(tmp_path: Path, benchmark: BenchmarkFixture) -> None:
    """The ceremony the CAS dropped and everybody else kept: tmp, fsync, rename.

    Its delta from the plain write above is the whole of roadmap 6.30's finding,
    and it is the number that decides whether the remaining callers — none of
    them disposable — are paying a little or a lot for their crash-safety.
    """
    data = BLOB.encode("utf-8")
    counter = iter(range(1_000_000))

    def store() -> None:
        atomic_write_bytes(tmp_path / f"atomic-{next(counter)}", data)

    benchmark(store)
