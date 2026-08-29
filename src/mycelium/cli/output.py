# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""CLI output conventions (spec 05 §1).

Three rules, applied by every command:

- **Exit codes are a contract**: ``0`` ok, ``1`` the operation failed, ``2`` the
  invocation was wrong. Click supplies ``2`` for usage errors on its own; ``1``
  is ours to raise deliberately.
- **stdout carries the answer, stderr carries the commentary.** Under ``--json``
  stdout holds exactly one JSON document and nothing else, so
  ``mycelium search --json … | jq`` never has to filter out a progress line.
- **Colour is opt-out and never assumed**: disabled when ``NO_COLOR`` is set
  (any value, per no-color.org), when the stream is not a TTY, and always under
  ``--json``.
"""

import json
import os
import sys
from contextlib import suppress
from enum import IntEnum
from typing import Any, Final

import typer

__all__ = [
    "ExitCode",
    "configure_streams",
    "detail",
    "emit_json",
    "fail",
    "style",
    "success",
    "use_color",
    "warn",
]


def configure_streams() -> None:
    """Make stdout/stderr able to carry the corpus.

    A Windows console still defaults to a legacy code page, where printing a
    Japanese heading or an em dash raises ``UnicodeEncodeError`` and takes the
    whole command down — unacceptable for a tool whose corpus is explicitly
    multilingual (D-028). UTF-8 with ``errors="replace"`` degrades an
    unrepresentable glyph instead of the process. The CLI's own chrome stays
    ASCII regardless, so the fallback only ever applies to content.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        with suppress(ValueError, OSError):  # a detached stream keeps its encoding
            reconfigure(encoding="utf-8", errors="replace")


class ExitCode(IntEnum):
    """The CLI's exit-code contract (spec 05 §1)."""

    OK = 0
    FAILED = 1
    USAGE = 2


_GREEN: Final = "green"
_YELLOW: Final = "yellow"
_RED: Final = "red"
_DIM: Final = "bright_black"


def use_color(stream: Any = None) -> bool:
    """Whether to style output on `stream` (default stdout)."""
    if os.environ.get("NO_COLOR") is not None:
        return False
    target = stream or sys.stdout
    return bool(getattr(target, "isatty", lambda: False)())


def style(text: str, colour: str, *, stream: Any = None) -> str:
    return typer.style(text, fg=colour) if use_color(stream) else text


def emit_json(payload: object) -> None:
    """Write the single JSON document that is this command's entire stdout."""
    typer.echo(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


def success(message: str) -> None:
    typer.echo(style(message, _GREEN))


def detail(message: str) -> None:
    typer.echo(style(message, _DIM))


def warn(message: str) -> None:
    """A caveat that does not change the exit code — always to stderr."""
    typer.echo(style(f"warning: {message}", _YELLOW, stream=sys.stderr), err=True)


def fail(message: str, *, code: ExitCode = ExitCode.FAILED) -> typer.Exit:
    """Report a failure on stderr and return the exception to raise."""
    typer.echo(style(f"error: {message}", _RED, stream=sys.stderr), err=True)
    return typer.Exit(int(code))
