#!/usr/bin/env python3
"""The `/eados` command registry, parsed once (#373).

`orchestrator/commands/README.md` is the canonical surface registry (ADR-0019 class 4): its table
declares every command, its class, its procedure and what it does. Two things already read it — the
`command-adapters` gate and, now, the host-independent CLI — and a second parser for the same table
is a second list to drift, which is the defect #365 and #366 each spent a gate closing.

So it is parsed **here**, once, and imported by both. Line-oriented like the `action-pins`
precedent: the table is markdown, and a row that wraps is exactly the shape a looser matcher gets
wrong.

Not a schema: the registry stays prose a human maintains. This only reads it.
"""

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # .eados-core/
REGISTRY = os.path.join(ROOT, "orchestrator", "commands", "README.md")

# `| `/eados <name>` | <phase> | **available** (ref) | [`proc.md`](proc.md) | <what it does> |`
#
# The description cell is OPTIONAL. The contract this parser owes its oldest caller — the
# `command-adapters` gate — is name + procedure; requiring a fifth column would make that gate
# stricter than it was and reject a table shape it used to accept. Widening a shared parser must
# never narrow an existing consumer.
# Every cell excludes newlines. `[^|]` alone crosses the line break and swallows the *next* row's
# leading `|`, so the row after each match silently disappears — the table parsed as half its size
# and nothing said so. Rows are lines; the pattern has to say that.
_ROW = re.compile(
    r"^\|\s*`/eados (\w+)`\s*\|([^|\n]*)\|[^|\n]*\*\*available\*\*[^|\n]*\|"
    r"\s*\[[^\]\n]+\]\(([^)\n]+)\)[^|\n]*\|(?:([^|\n]*)\|)?",
    re.MULTILINE)


def canonical_procedure(link):
    """A Procedure-cell link (relative to `orchestrator/commands/`) as a repo-relative path:
    `init.md` -> `.eados-core/orchestrator/commands/init.md`; `../generate.md` ->
    `.eados-core/orchestrator/generate.md`."""
    rel = os.path.normpath(os.path.join("orchestrator", "commands", link.split("#", 1)[0]))
    return os.path.join(".eados-core", rel).replace(os.sep, "/")


def parse(text):
    """`[{name, phase, procedure, summary}]` for every **available** command, in table order.

    `phase` is the table's own second column — `init`, `design`, … for the state machine, `— (any)`
    for a cross-cutting command. Callers classify from it rather than from a hardcoded list, so a
    command that changes class needs no code change."""
    out = []
    for name, phase, link, summary in _ROW.findall(text):
        out.append({"name": name,
                    "phase": phase.strip(),
                    "procedure": canonical_procedure(link.strip()),
                    "summary": re.sub(r"\s+", " ", summary).strip()})
    return out


def load(path=REGISTRY):
    """`parse()` over the registry file; `[]` when it is absent (a partial checkout)."""
    try:
        with open(path, encoding="utf-8") as handle:
            return parse(handle.read())
    except OSError:
        return []


def names(path=REGISTRY):
    """Just the command names, in registry order."""
    return [c["name"] for c in load(path)]


def is_phase(entry):
    """True when the row names a workflow phase rather than a cross-cutting command. The
    cross-cutting rows carry `— (any)` in the phase column; a phase row names its state."""
    phase = str((entry or {}).get("phase") or "")
    return bool(phase) and "any" not in phase and not phase.startswith("—")
