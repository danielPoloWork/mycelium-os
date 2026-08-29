#!/usr/bin/env python3
"""EADOS migrate sandbox (roadmap 5.3) — write containment for the brownfield `migrate` phase.

The migration's edits are the only place EADOS touches *real user code*, so every write goes
through here. Defense-in-depth, on the same principle as the renderer's write guard
([ADR-0007](../docs/adr/0007-renderer-write-guards-and-validation-independence.md)):

  * a write may only land **inside the target repo root** (path-traversal is refused via
    realpath + commonpath — symlinks are resolved, so a symlink that points outside is caught);
  * absolute / drive-qualified destinations are refused outright;
  * writes into a `.git/` at **any** depth are refused — a nested or submodule `.git/` is VCS
    metadata too (never corrupt it);
  * **additive by default** — refusing to overwrite an existing file unless `overwrite=True` is
    passed explicitly (a migration *adds* missing artifacts; clobbering user code is a human call).

Each migration step is still one reviewable, gated PR; this is the mechanical backstop underneath.
Dependency-free (Python standard library only).
"""

import os
import re
import sys


class SandboxError(Exception):
    """A write that would escape the sandbox, clobber a file, or touch VCS metadata."""


def _contained(root, dest):
    try:
        return os.path.commonpath([root, dest]) == root
    except ValueError:        # different drives on Windows -> definitely outside
        return False


def resolve(root, rel):
    """The absolute destination for `rel` within `root`, or raise SandboxError if `rel` is absolute,
    drive-qualified, escapes the root (after resolving symlinks), or targets `.git/`."""
    rel = str(rel)
    if os.path.isabs(rel) or re.match(r"[A-Za-z]:", rel):
        raise SandboxError(f"absolute/drive-qualified path not allowed: {rel!r}")
    root_real = os.path.realpath(root)
    dest = os.path.realpath(os.path.join(root_real, rel.replace("/", os.sep)))
    if not _contained(root_real, dest):
        raise SandboxError(f"path escapes the sandbox root: {rel!r}")
    # `.git` is off-limits at ANY depth, not just the top level: a nested or submodule `.git/`
    # (e.g. vendor/lib/.git/) is VCS metadata too, and corrupting it is just as harmful. An
    # exact segment match — a `.gitignore` file or a `foo.git/` directory is NOT rejected.
    parts = os.path.relpath(dest, root_real).replace(os.sep, "/").split("/")
    if ".git" in parts:
        raise SandboxError(f"refusing to write into .git: {rel!r}")
    return dest


def safe_write(root, rel, content, overwrite=False):
    """Write `content` to `root/rel` — only if contained, not VCS metadata, and (unless
    `overwrite`) not clobbering an existing file. Returns the absolute path written."""
    dest = resolve(root, rel)
    if os.path.exists(dest) and not overwrite:
        raise SandboxError(f"refusing to overwrite existing file (migration is additive): {rel!r}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    return dest


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    # This module is a library used by the migrate phase; there is no standalone action to run.
    print("sandbox.py is a write-containment library for the migrate phase (no CLI action).",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
