#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Replay every input known to have faulted a native dependency, each in a fresh interpreter.

    python tools/check_known_faults.py [--python PATH] [--reads N]

A fault inside a C extension is not an exception. When tree-sitter 0.26.0 hit an
access violation on one projected fence, no `except` ran, no quarantine record
was written and the build process died ([BUG-0022]). A defect like that can only
be observed from outside the process that suffers it, so each input here is read
by a child interpreter and judged by how the child exits.

The inputs are committed, not left inside a corpus. BUG-0022 named the ingested
corpus as its regression guard; the corpus stopped carrying the trigger on
2026-09-12, when its PDFs were re-rendered (BUG-0025), and the next day a bot
widened the pin the guard protected with nothing left to notice (roadmap 8.2,
ADR-0162).

`--python` is the interpreter to replay in. The suite replays in the locked
development environment (`tests/test_symbols.py`); `tools/check_distribution.py`
replays in a clean environment holding the built wheel's extras at the newest
versions their ranges allow, which is what a consumer installing them gets. That
second replay is how a defect pin is lifted: widen the range, run that check.

Each input is read `--reads` times in one child, because the fault is heap
corruption and its timing moves: on Windows one read per fresh process faulted 4
times in 10, five reads 10 times in 10. A child that reads every time, and reads
the same thing every time, passes.

Exit 0 when every input reads; 1 when one faults, hangs, reads two different ways
or is no longer the bytes its record names; 2 when one cannot be read here at all
because its grammar is not installed, which each caller judges for itself.
"""

import argparse
import hashlib
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "symbols"


@dataclass(frozen=True, slots=True)
class KnownFault:
    """One input that faulted a native dependency, and what the record says of it."""

    bug: str
    distribution: str
    """The distribution whose native code faulted, as the ranges in `pyproject.toml` name it."""
    faulting: tuple[str, ...]
    """The releases observed to fault on this input. A declared range must admit none."""
    grammar: str
    fixture: Path
    size: int
    sha256: str


KNOWN_FAULTS: Final[tuple[KnownFault, ...]] = (
    KnownFault(
        bug="BUG-0022",
        distribution="tree-sitter",
        faulting=("0.26.0",),
        grammar="python",
        fixture=FIXTURES / "bug-0022-fence.txt",
        size=20_644,
        sha256="e4b47df88f4ffdeaf5a82d4105934cdb60c993ebdafa1fe80c6703359fffb69b",
    ),
)
"""Every input this repository knows to have killed a process in native code.

One row per bug record. Today every row is a code fence and the reader is the
grammar binding, so the child below reads fences; a fault in another native
dependency adds a row and, if it needs one, a reader."""

READS: Final = 5
TIMEOUT_S: Final = 300

UNAVAILABLE: Final = 2
DIVERGED: Final = 3

ACCESS_VIOLATION: Final = 0xC0000005
"""The NTSTATUS a Windows process exits with when it faults, as `subprocess` reports it."""

CHILD = f"""
import importlib.metadata
import sys
from pathlib import Path

from mycelium.symbols import load_grammar, read_fence

grammar, path, reads = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])
loaded = load_grammar(grammar)
if loaded is None:
    print(f"the {{grammar}} grammar does not load in this interpreter")
    raise SystemExit({UNAVAILABLE})
source = path.read_bytes()
first = read_fence(loaded, source)
for _ in range(reads - 1):
    if read_fence(loaded, source) != first:
        print("two reads of the same bytes differed")
        raise SystemExit({DIVERGED})
binding = importlib.metadata.version("tree-sitter")
print(
    f"{{len(first.definitions)}} definitions, {{len(first.references)}} references, "
    f"binding {{binding}}, {{grammar}} grammar {{loaded.version}}"
)
"""
"""What the child runs. Imports `mycelium` from whatever environment the
interpreter belongs to — never from this checkout's `src/`, so a clean
environment is judged on the wheel installed in it."""

type Status = Literal["read", "unavailable", "diverged", "faulted", "hung", "altered"]


@dataclass(frozen=True, slots=True)
class Replay:
    """How one input fared in one interpreter."""

    fault: KnownFault
    status: Status
    detail: str

    @property
    def passed(self) -> bool:
        return self.status == "read"


def altered(fault: KnownFault) -> str | None:
    """Why the committed input is not the one its record names, or ``None`` if it is."""
    if not fault.fixture.is_file():
        return f"{fault.fixture.relative_to(ROOT).as_posix()} is missing"
    data = fault.fixture.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != fault.size or digest != fault.sha256:
        return (
            f"{fault.fixture.relative_to(ROOT).as_posix()} is {len(data)} bytes with sha256 "
            f"{digest}, not the {fault.size} bytes {fault.bug} names ({fault.sha256}); a "
            "rewritten input reproduces nothing, so restore it rather than re-record it"
        )
    return None


def describe_exit(code: int) -> str:
    """A child's exit status in the words its platform uses for a fault."""
    if code < 0:
        try:
            return f"killed by {signal.Signals(-code).name}"
        except ValueError:
            return f"killed by signal {-code}"
    if code == ACCESS_VIOLATION:
        return "an access violation (0xC0000005)"
    if code > 0xFFFF:
        return f"status 0x{code:08X}"
    return f"exit status {code}"


def replay(python: str, fault: KnownFault, *, reads: int = READS) -> Replay:
    """Read `fault`'s input `reads` times in a fresh `python`, and judge the exit."""
    reason = altered(fault)
    if reason is not None:
        return Replay(fault, "altered", reason)
    command = [
        python,
        # Isolated, so neither the caller's PYTHONPATH nor its working directory can
        # put this checkout's `src/` ahead of the environment being judged; the fault
        # handler, so a fault prints where it happened before the process dies.
        "-I",
        "-X",
        "faulthandler",
        "-c",
        CHILD,
        fault.grammar,
        str(fault.fixture),
        str(reads),
    ]
    try:
        result = subprocess.run(  # noqa: S603 - a fixed argument vector, never a shell string
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return Replay(fault, "hung", f"no exit after {TIMEOUT_S} s ({reads} reads)")
    said = (result.stdout or "").strip()
    if result.returncode == 0:
        return Replay(fault, "read", f"read {reads} times: {said}")
    if result.returncode == UNAVAILABLE:
        return Replay(fault, "unavailable", said)
    if result.returncode == DIVERGED:
        return Replay(fault, "diverged", said)
    trace = (result.stderr or "").strip().splitlines()
    where = f"; the fault handler said: {trace[0]}" if trace else ""
    return Replay(
        fault,
        "faulted",
        f"the child died with {describe_exit(result.returncode)} within {reads} reads{where}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay every input known to have faulted a native dependency."
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="the interpreter to replay in (default: this one)",
    )
    parser.add_argument(
        "--reads", type=int, default=READS, help=f"reads per input (default: {READS})"
    )
    arguments = parser.parse_args()

    unavailable = failed = 0
    for fault in KNOWN_FAULTS:
        outcome = replay(arguments.python, fault, reads=arguments.reads)
        print(f"{fault.bug} [{outcome.status}] {outcome.detail}")
        if outcome.status == "unavailable":
            unavailable += 1
        elif not outcome.passed:
            failed += 1
    if failed:
        return 1
    return UNAVAILABLE if unavailable else 0


if __name__ == "__main__":
    raise SystemExit(main())
