# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Smoke test: the package imports and exposes a version (roadmap 1.2)."""

import mycelium


def test_package_exposes_version() -> None:
    assert mycelium.__version__ == "0.0.0"
