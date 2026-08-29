# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The ``mycelium`` command line — one of v1's two public surfaces (D-011).

- :mod:`mycelium.cli.app` — the typer application and its commands.
- :mod:`mycelium.cli.doctor` — the diagnostics behind ``mycelium doctor``.
- :mod:`mycelium.cli.output` — exit codes, JSON emission, and colour policy.
"""

from mycelium.cli.app import app, main

__all__ = ["app", "main"]
