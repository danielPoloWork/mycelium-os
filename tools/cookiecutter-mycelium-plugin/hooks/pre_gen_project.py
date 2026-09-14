#!/usr/bin/env python3
"""Refuse a plugin id spec 05 §4.4 (D-026) would refuse, before a line of code exists.

Cookiecutter renders every template placeholder in this file to a plain literal
before running it as Python, so everything below is ordinary string/regex work
against the value the operator typed.
"""

import re
import sys

PLUGIN_ID = "{{ cookiecutter.plugin_id }}"

RESERVED_WORDS = frozenset(
    {"search", "index", "graph", "build", "snapshot", "evidence", "verify"}
)
"""Core concepts a plugin id may not claim (spec 05 §4.4 rule 3)."""

TECH_SUFFIXES = ("-llm", "-ai", "-gpt")
"""Implementation-in-the-name suffixes rule 2 refuses: they rot or lie as the
implementation changes under a name that promised to be stable."""

_KEBAB = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)?$")
"""Lowercase kebab-case, one or two words (rule 1) — this pattern permits at
most one hyphen, which is what "one or two words" means as a shape."""


def main() -> int:
    if not _KEBAB.fullmatch(PLUGIN_ID):
        print(
            f"plugin id {PLUGIN_ID!r} must be lowercase kebab-case, one or two words "
            "(spec 05 §4.4 rule 1) — e.g. 'wiki', 'chats', 'pdf-tables'",
            file=sys.stderr,
        )
        return 1
    if PLUGIN_ID in RESERVED_WORDS:
        print(
            f"plugin id {PLUGIN_ID!r} is a reserved core concept "
            f"({', '.join(sorted(RESERVED_WORDS))}); a plugin cannot claim one "
            "(spec 05 §4.4 rule 3)",
            file=sys.stderr,
        )
        return 1
    if PLUGIN_ID.endswith(TECH_SUFFIXES):
        print(
            f"plugin id {PLUGIN_ID!r} carries a technology suffix "
            f"({', '.join(TECH_SUFFIXES)}); name the capability, not the implementation "
            "— put the technology in the description instead (spec 05 §4.4 rule 2)",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
