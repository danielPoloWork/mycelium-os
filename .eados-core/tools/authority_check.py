#!/usr/bin/env python3
"""EADOS authority check — the path→role gate (RFC-0001 §5 / roadmap 2.4).

Given the **acting role** and the paths a change touches, verify every path is within that role's
**writable surface** (`owns` ∪ `may_draft`) per `orchestrator/os/authority/authority.yaml`. The
agent invokes it *before* drafting a change; a path the role may not write is rejected. This is
how the ownership map stops an agent from editing artifacts it has no authority over — the CI
cannot know the acting role of a PR, so the check is role-aware and agent-invoked. Dependency-free
(stdlib + the sibling renderer's YAML loader).

    python .eados-core/tools/authority_check.py <role> <path> [<path> ...]
    git diff --cached --name-only | xargs python .eados-core/tools/authority_check.py tech-lead
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # .eados-core/
sys.path.insert(0, HERE)
import render  # noqa: E402  — the hand-rolled, dependency-free YAML loader

AUTHORITY = os.path.join(ROOT, "orchestrator", "os", "authority", "authority.yaml")


def load_authority(path=AUTHORITY):
    with open(path, encoding="utf-8") as handle:
        return render.load_yaml(handle.read())


def role_globs(authority, role):
    """The globs a role may WRITE (owns ∪ may_draft), or None if the role is not declared."""
    for r in authority.get("roles") or []:
        if isinstance(r, dict) and r.get("name") == role:
            return list(r.get("owns") or []) + list(r.get("may_draft") or [])
    return None


def _glob_re(glob):
    """Compile an ownership glob to a regex. `**` matches across directories; `*` matches within a
    path segment; everything else is literal."""
    out, i = [], 0
    while i < len(glob):
        if glob[i:i + 2] == "**":
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def in_authority(path, globs):
    return any(_glob_re(g).match(path) for g in globs)


def denied_paths(authority, role, paths):
    """The subset of `paths` the role may not write. Raises ValueError for an unknown role."""
    globs = role_globs(authority, role)
    if globs is None:
        raise ValueError(f"unknown role '{role}'")
    return [p.replace("\\", "/") for p in paths
            if not in_authority(p.replace("\\", "/"), globs)]


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        print("usage: authority_check.py <role> <path> [<path> ...]", file=sys.stderr)
        return 2
    role, paths = argv[0], argv[1:]
    try:
        denied = denied_paths(load_authority(), role, paths)
    except ValueError as exc:
        print(f"authority-check: ERROR — {exc}", file=sys.stderr)
        return 2
    if denied:
        print(f"authority-check: DENIED — role '{role}' may not write:")
        for p in denied:
            print(f"  {p}")
        return 1
    print(f"authority-check: OK — all {len(paths)} path(s) are within '{role}'s authority.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
