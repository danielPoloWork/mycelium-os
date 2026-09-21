#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""What does one content-addressed blob write actually cost? (roadmap 6.30)

    python tools/measure_cas_write.py                  # this machine, both disks
    python tools/measure_cas_write.py --dir <path>      # one directory, e.g. another volume
    python tools/measure_cas_write.py --json            # for a manifest

Roadmap 6.19 measured a 1 000-document cold build at **91.7 s** against a 60 s
budget and found **~79 s of it in 2 995 `cas_put` calls** - three artifacts per
document, 26.4 ms each on the machine of record. It attributed the cost to two
things: a real-time scanner in the write path, and the atomic ceremony
(`tmp -> fsync -> rename`) doubling it by making the scanner charge for two
names instead of one.

That attribution was a reading of one aggregate number. This decomposes it, so
the question 6.30 asks - *what durability does a derived store owe, and what
would dropping it buy* - is answered per operation rather than per build:

- **plain write** - `open`/`write`/`close` straight to the final name;
- **write + fsync** - what durability costs once the name already exists;
- **tmp + rename** - what a second name costs, with no fsync at all;
- **tmp + fsync + rename** - `layout.atomic_write_bytes`, which is what ships.

The arms are nested, so each line's delta from the one above is the price of
exactly one thing.

## Read the sizes, not just the 4 KiB

6.19's constant was quoted at 4 KiB. This repository's own CAS holds a median
blob of ~11.8 KiB and a mean of ~66 KiB, so the sweep covers the range. If cost
tracks *size* the bottleneck is bandwidth; if it tracks *operations* it is a
filter driver, and the remedy is fewer file operations rather than smaller ones.
That is the distinction this tool exists to make, and it is the one a reader on
another machine needs before believing any of the numbers here.

**Nothing here writes into `.mycelium/`.** Every arm works in a scratch
directory it creates and removes, so running this against a repository cannot
disturb a build cache.
"""

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

BLOBS_PER_BUILD: Final = 2995
"""What a 1 000-document cold build writes: a parse, a chunks and a document
artifact each, less the handful already present (roadmap 6.19, ADR-0132)."""

SIZES: Final = (4 * 1024, 12 * 1024, 64 * 1024)
"""4 KiB is 6.19's quoted constant; 12 KiB is this repository's median blob and
64 KiB its mean. A cost flat across these three is a per-operation cost."""

REPETITIONS: Final = 40


@dataclass(frozen=True, slots=True)
class Arm:
    """One write strategy, and what it adds to the one before it."""

    name: str
    fsync: bool
    via_tmp: bool


@dataclass(frozen=True, slots=True)
class Row:
    """One arm, at one size, on one volume."""

    directory: str
    size: int
    arm: str
    median_ms: float

    @property
    def per_build_s(self) -> float:
        return self.median_ms * BLOBS_PER_BUILD / 1000

    def as_dict(self) -> dict[str, object]:
        return {
            "directory": self.directory,
            "bytes": self.size,
            "arm": self.arm,
            "median_ms": round(self.median_ms, 4),
            "per_build_s": round(self.per_build_s, 2),
        }


ARMS: Final = (
    Arm("plain write", fsync=False, via_tmp=False),
    Arm("write + fsync", fsync=True, via_tmp=False),
    Arm("tmp + rename", fsync=False, via_tmp=True),
    Arm("tmp + fsync + rename", fsync=True, via_tmp=True),
)


def write_once(path: Path, data: bytes, arm: Arm) -> None:
    """One blob, by one strategy. Mirrors `layout.atomic_write_bytes` exactly."""
    target = path.with_name(path.name + ".tmp") if arm.via_tmp else path
    flags = os.O_CREAT | os.O_WRONLY | os.O_TRUNC | getattr(os, "O_BINARY", 0)
    descriptor = os.open(target, flags)
    try:
        os.write(descriptor, data)
        if arm.fsync:
            os.fsync(descriptor)
    finally:
        os.close(descriptor)
    if arm.via_tmp:
        os.replace(target, path)


def sample(directory: Path, data: bytes, arm: Arm, index: int) -> float:
    """Milliseconds for one write of `data` into a fresh name, by one strategy."""
    path = directory / f"blob-{arm.name.replace(' ', '-').replace('+', '')}-{index}"
    started = time.perf_counter()
    write_once(path, data, arm)
    elapsed = (time.perf_counter() - started) * 1000
    path.unlink(missing_ok=True)
    return elapsed


def measure(directory: Path, repetitions: int, label: str) -> list[Row]:
    """Every arm at every size, **interleaved**.

    Round-robin rather than arm-by-arm blocks, and it is not a detail: this
    machine has minute-scale slow periods, and a blocked run charges whichever
    arm happened to be running through one. Interleaving spreads any such period
    across all four arms, so the *differences* - which are the whole point, since
    each arm adds exactly one operation to the one above - survive a machine that
    is not perfectly idle.

    Medians, for the same reason a mean would not do: a scanner's occasional
    multi-hundred-millisecond excursion is real and is not what a build pays per
    blob.

    Each sample writes a *fresh* name, because the cost under test is a blob
    appearing - overwriting one already on disk is an operation the CAS never
    performs.
    """
    samples: dict[tuple[int, str], list[float]] = {
        (size, arm.name): [] for size in SIZES for arm in ARMS
    }
    payloads = {size: os.urandom(size) for size in SIZES}
    for index in range(repetitions):
        for size in SIZES:
            for arm in ARMS:
                samples[(size, arm.name)].append(sample(directory, payloads[size], arm, index))
    return [
        Row(label, size, arm.name, statistics.median(samples[(size, arm.name)]))
        for size in SIZES
        for arm in ARMS
    ]


def render(rows: Sequence[Row]) -> None:
    for directory in dict.fromkeys(row.directory for row in rows):
        print(f"\n{directory}")
        for size in SIZES:
            print(f"  {size // 1024} KiB:")
            baseline = 0.0
            for arm in ARMS:
                row = next(
                    item
                    for item in rows
                    if item.directory == directory and item.size == size and item.arm == arm.name
                )
                delta = f"{row.median_ms - baseline:+7.3f}" if baseline else "       "
                baseline = baseline or row.median_ms
                print(
                    f"    {arm.name:<21} {row.median_ms:7.3f} ms  {delta}   "
                    f"{row.per_build_s:6.1f} s per {BLOBS_PER_BUILD} blobs"
                )
    print(
        "\nEach line's delta is the price of one thing: fsync on an existing name, a "
        "second name, then both. A cost flat across the three sizes is charged per "
        "operation, not per byte - which is a filter driver in the path, and means the "
        "remedy is fewer operations rather than smaller writes (roadmap 6.30)."
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir",
        type=Path,
        action="append",
        dest="directories",
        help=(
            "A volume to measure on; repeatable. The default measures beside this "
            "repository and in the system temp directory, which are often different disks."
        ),
    )
    parser.add_argument(
        "--repetitions", type=int, default=REPETITIONS, help="Samples per arm (default 40)."
    )
    parser.add_argument("--json", action="store_true", help="Emit the rows as JSON.")
    arguments = parser.parse_args(argv)

    targets = arguments.directories or [ROOT, Path(tempfile.gettempdir())]
    rows: list[Row] = []
    for target in targets:
        # A scratch directory of our own, removed afterwards: measuring must never
        # leave debris in a build cache or in somebody's working tree.
        with tempfile.TemporaryDirectory(dir=target, prefix=".cas-write-probe-") as scratch:
            rows.extend(measure(Path(scratch), arguments.repetitions, str(target)))

    if arguments.json:
        print(
            json.dumps(
                {"blobs_per_build": BLOBS_PER_BUILD, "rows": [row.as_dict() for row in rows]},
                indent=2,
            )
        )
    else:
        render(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
