# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Smoke test: the package imports, exposes a version, and advertises its types."""

import re
from pathlib import Path

import mycelium
from mycelium.__about__ import __version__


def test_package_exposes_version() -> None:
    """The package re-exports a single, well-formed SemVer string.

    The literal value is deliberately not asserted here: `tools/consistency_lint.py`
    already enforces version lockstep across the version constant, the README badge,
    the released changelog, and the release notes — which is a stronger check than a
    hardcoded copy, and one that does not need editing at every release.
    """
    assert mycelium.__version__ is __version__
    assert re.fullmatch(r"\d+\.\d+\.\d+", mycelium.__version__)


def test_the_package_advertises_its_types() -> None:
    """PEP 561: a typed package says so with a marker, or consumers get `Any`.

    Roadmap 4.43. Without this file every `from mycelium…` outside `src/` is
    `import-untyped` and everything downstream of it is `Any` — 73 of the 184
    errors `mypy --strict tools` reported, and silence for a package whose pitch is
    typed record contracts (ADR-0004).

    Asserted here rather than left to the packaging default, because that is what
    it was: hatchling ships package data automatically, so the marker's absence
    produced no build error and no test failure — only a flood of unrelated errors
    in whoever type-checked a consumer. Deleting it should fail *this*, by name.
    """
    marker = Path(mycelium.__file__).parent / "py.typed"
    assert marker.is_file(), "src/mycelium/py.typed is missing; consumers see no types"
    assert marker.read_bytes() == b"", "the marker is a presence, not a payload"
