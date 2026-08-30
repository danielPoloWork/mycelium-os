# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Smoke test: the package imports and exposes a version (roadmap 1.2)."""

import re

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
