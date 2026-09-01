# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Where things live under `.mycelium/`, and how they get written durably.

A leaf module: it imports nothing from `mycelium`, and that is its whole job.
Three subsystems need these five names — the build cache writes blobs, snapshot
publication swaps pointers, tier-1 custody stores acquired originals — and while
they lived inside `mycelium.build` the third one could not have them without
importing the compiler, which imports the configuration, which asks the plugin
registry which parsers exist, which reaches custody. That circle closed the first
time the build needed to read a custody record (roadmap 4.3).

Layout and durable-write primitives are not "build" concepts. They are what a
content-addressed store on a filesystem is made of, and they belong somewhere
nothing has to reach *through* to get at them.
"""

import os
from pathlib import Path
from typing import Final

__all__ = [
    "CAS_DIRNAME",
    "CUSTODY_DIRNAME",
    "atomic_write_bytes",
    "atomic_write_text",
]

CAS_DIRNAME: Final = "cas"
"""Content-addressed storage under `.mycelium/`: `cas/<xx>/<sha256>` (spec 02 §3)."""

CUSTODY_DIRNAME: Final = "originals"
"""The one subtree of the CAS that is **not** disposable (ADR-0033).

Tier-1 custody — acquired originals, the KIR compiled from them, and the fidelity
reports that account for them — lives at `cas/originals/` per architecture §4. It
is named here, beside the sweepable layout it sits inside, because the garbage
collector has to know which of the two it is looking at, and a lifecycle rule that
lived only in the module writing the blobs would be invisible to the module
deleting them. :mod:`mycelium.ingest.custody` owns what goes in it.
"""


def atomic_write_text(path: Path, text: str) -> None:
    """Write `text` to `path` through a same-directory temp file and rename."""
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write `data` to `path` through a same-directory temp file and rename.

    The temp file lives beside the target (rename is only atomic within one
    filesystem), is fsynced before the rename (so the *content* is durable before
    the *name* appears), and is removed on failure.

    Bytes rather than text is the primitive because tier-1 custody stores acquired
    originals — a DOCX, a PDF — and those must land byte-for-byte (ADR-0033).
    """
    tmp = path.with_name(path.name + ".tmp")
    # O_BINARY matters: without it, Windows' CRT opens in text mode and rewrites
    # LF as CRLF — which would make manifest bytes platform-dependent (G6), and
    # would corrupt every acquired original that happens to contain 0x0A.
    flags = os.O_CREAT | os.O_WRONLY | os.O_TRUNC | getattr(os, "O_BINARY", 0)
    descriptor = os.open(tmp, flags)
    try:
        try:
            os.write(descriptor, data)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    _fsync_dir(path.parent)


def _fsync_dir(directory: Path) -> None:
    """Make a rename durable on POSIX; a no-op where directories can't be opened."""
    if os.name != "posix":  # pragma: no cover - exercised on the POSIX CI cells
        return
    descriptor = os.open(directory, os.O_RDONLY)  # pragma: no cover
    try:  # pragma: no cover
        os.fsync(descriptor)
    finally:  # pragma: no cover
        os.close(descriptor)
