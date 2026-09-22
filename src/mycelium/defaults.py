# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The handful of literals the command line shows as option defaults.

Every value here is a plain `int` or `str` with no dependencies, and each is
defined in this module for one measured reason (roadmap 6.36). Typer evaluates a
command's default values while building its command tree, so a default imported
from `mycelium.build.snapshots` makes ``mycelium --version`` import the whole
build subsystem to learn that a number is ten. Measured before the split, these
five literals cost the command line **1 229 ms and 253 modules** — more than the
rest of the CLI's import graph put together.

This module holds the *definitions*; the modules that own the behaviour each
re-export their own, so `from mycelium.build.snapshots import DEFAULT_KEEP`
keeps working and stays the documented import. Nothing here may grow an import:
a dependency in this file puts that dependency back on the path of every
invocation, which is the defect it exists to prevent
(`tests/test_cli_import_cost.py` holds that line).
"""

from typing import Final

__all__ = [
    "DEFAULT_CACHE_MAX_AGE_DAYS",
    "DEFAULT_EXPORT_DIRNAME",
    "DEFAULT_KEEP",
    "MAX_DEPTH",
    "STORE_DIRNAME",
    "STORE_FILENAME",
]

DEFAULT_KEEP: Final = 10
"""Snapshots retained by `mycelium gc`, newest first. `CURRENT` is always kept."""

DEFAULT_CACHE_MAX_AGE_DAYS: Final = 30
"""How long an unreferenced cached artifact survives before it is collectable."""

MAX_DEPTH: Final = 3
"""Traversal ceiling. Spec 04 §5 budgets graph *expansion* at one hop; the tool
takes a depth because a human debugging a vault wants two or three, and an
unbounded walk over a dense corpus is a denial of service with a friendly name."""

DEFAULT_EXPORT_DIRNAME: Final = "export"
"""Where bundles land under the repository root, per spec 03 §9's own tree.

``mycelium init`` gitignores it: D-006 says bundles are not committed by default,
and a directory the tool writes into the repository *is* committed by default
unless something says otherwise.
"""

STORE_DIRNAME: Final = ".mycelium"
STORE_FILENAME: Final = "store.db"
