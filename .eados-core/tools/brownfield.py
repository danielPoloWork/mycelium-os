#!/usr/bin/env python3
"""EADOS brownfield reader (roadmap 5.1) — READ-ONLY.

Ingests an existing repository and maps it against the EADOS standard, reporting the **gaps** a
migration would close (the agent contract, the docs system, CI, the source tree, …). It **never
writes**: ingestion and analysis are safe; the migration *planner* (5.2) and its **write-contained
sandbox** (5.3) are separate, later slices — this tool only reads. Dependency-free.

    python .eados-core/tools/brownfield.py <repo-path>
"""

import os
import sys

# The EADOS-standard artifacts a governed repo carries: (label, [candidate paths]). An artifact is
# "present" if ANY candidate exists (file or directory) — tolerant of common naming variants.
STANDARD = [
    ("agent contract", ["AGENTS.md"]),
    ("readme", ["README.md", "README.rst", "README"]),
    ("changelog", ["CHANGELOG.md", "CHANGELOG"]),
    ("license", ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"]),
    ("security policy", ["SECURITY.md", ".github/SECURITY.md"]),
    ("ADRs", ["docs/adr", "docs/adrs", "doc/adr"]),
    ("spec", ["docs/specs", "docs/spec"]),
    ("CI", [".github/workflows", ".gitlab-ci.yml", ".circleci"]),
    ("source tree", ["src", "lib", "source"]),
]


def _present(repo, candidates):
    return any(os.path.exists(os.path.join(repo, c.replace("/", os.sep))) for c in candidates)


def scan(repo):
    """Return [(label, candidates, present)] for each standard artifact. READ-ONLY."""
    return [(label, cands, _present(repo, cands)) for label, cands in STANDARD]


def gaps(repo):
    """The labels of standard artifacts missing from `repo` — the migration backlog."""
    return [label for label, _cands, present in scan(repo) if not present]


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    argv = sys.argv[1:] if argv is None else argv
    # `--help` answers (#373). This is reachable as `eados adopt --help`, and on a host with no
    # slash commands the CLI is the whole command surface — a tool there that treats `--help` as a
    # path and reports "not a directory: --help" teaches the user the surface is broken.
    if any(a in ("-h", "--help") for a in argv):
        print("usage: brownfield.py <repo-path>\n\n"
              "Read-only brownfield gap map: which standard EADOS artifacts an existing\n"
              "repository already has. Reports; writes nothing. The `/eados adopt` intake\n"
              "(orchestrator/commands/adopt.md) turns the map into a manifest.")
        return 0
    if len(argv) != 1:
        print("usage: brownfield.py <repo-path>", file=sys.stderr)
        return 2
    repo = argv[0]
    if not os.path.isdir(repo):
        print(f"brownfield: ERROR — not a directory: {repo}", file=sys.stderr)
        return 2
    rows = scan(repo)
    present = sum(1 for _l, _c, p in rows if p)
    print(f"brownfield map of {repo}  ({present}/{len(rows)} standard artifacts present):")
    for label, cands, p in rows:
        mark = "[x]" if p else "[ ]"
        print(f"  {mark} {label}  ({cands[0]})")
    missing = gaps(repo)
    if missing:
        print(f"\ngaps to migrate ({len(missing)}): {', '.join(missing)}")
    else:
        print("\nno gaps — the repo already meets the EADOS standard.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
