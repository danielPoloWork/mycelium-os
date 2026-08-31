# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""What counts as a document — one rule, shared (spec 02 §3, ADR-0021).

Discovery and watch mode both have to answer "is this file part of the corpus",
and they must answer identically: a watcher that fires for a file the compiler
ignores rebuilds nothing forever, and a compiler that indexes a file the watcher
ignores publishes changes nobody triggered. They agreed by having the same rule
written twice, which is agreement by coincidence. This module is the rule.

Four tests, in order:

1. **Nothing dot-prefixed.** Excludes `.mycelium/`, `.git/`, and editor litter in
   one line, and is the rule the derived store relies on.
2. **Nothing the tool itself writes.** `export/` holds bundles this repository
   produced (roadmap 3.6), and `--with-markdown` puts *copies of the corpus*
   there. Indexing your own output is never what anyone means: it duplicates
   every document, and because the copies carry the same pinned `mycelium_id`,
   the identity guard quarantines them and every later build reports a warning
   for a file the operator never wrote ([BUG-0010]).
3. **The authored tree, when there is one.** `knowledge/` if it exists, else the
   whole repository, so a plain docs repository needs no layout ceremony.
4. **Whatever `[project] exclude` names.** The escape hatch for a repository
   whose tree carries Markdown that is not documentation — test fixtures, vendored
   samples, generated reports. This project needs it for its own corpus, which is
   how the gap was found (BUG-0007).
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Final, Self

__all__ = ["DERIVED_DIRNAMES", "CorpusScope", "discover"]

DERIVED_DIRNAMES: Final = frozenset({"export"})
"""Top-level directories this tool writes into and must therefore never read.

`.mycelium/` is already covered by the dot-prefix rule; `export/` is not, because
spec 03 §9 puts bundles in plain sight where a human can find them.
"""


@lru_cache(maxsize=256)
def _matcher(pattern: str) -> re.Pattern[str]:
    """Compile one exclude pattern.

    Deliberately not `fnmatch`, where ``*`` crosses ``/`` and ``docs/*.md``
    therefore matches ``docs/a/b.md`` — a surprise in the direction of excluding
    too much. Here ``*`` stays within one segment, ``**`` spans segments, and
    ``?`` is one character: the semantics anyone who has written a glob expects,
    and small enough to state exactly.
    """
    out: list[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if pattern.startswith("**", index):
            out.append(".*")
            index += 2
        elif char == "*":
            out.append("[^/]*")
            index += 1
        elif char == "?":
            out.append("[^/]")
            index += 1
        else:
            out.append(re.escape(char))
            index += 1
    return re.compile("".join(out) + r"\Z")


@dataclass(frozen=True, slots=True)
class CorpusScope:
    """Which files in a repository are documents."""

    knowledge_dir: str = "knowledge"
    exclude: tuple[str, ...] = ()

    @classmethod
    def of(cls, project: object) -> Self:
        """Build a scope from a ``[project]`` configuration section."""
        return cls(
            knowledge_dir=str(getattr(project, "knowledge_dir", "knowledge")),
            exclude=tuple(getattr(project, "exclude", ()) or ()),
        )

    def excluded(self, relative: PurePosixPath) -> bool:
        """Whether an `exclude` pattern names this path.

        A pattern matches the path itself, any ancestor directory of it, or the
        file's own name — so ``tests`` excludes a tree, ``docs/journal`` excludes
        a subtree, and ``*.draft.md`` excludes by name wherever it appears. One
        pattern, three intuitions, none of them wrong.
        """
        if not self.exclude:
            return False
        candidates = [relative.as_posix(), relative.name]
        candidates.extend(parent.as_posix() for parent in relative.parents if parent.name)
        return any(
            _matcher(pattern).match(candidate)
            for pattern in self.exclude
            for candidate in candidates
        )

    def contains(self, relative: PurePosixPath, *, authored_tree: bool = False) -> bool:
        """Whether the repository-relative path `relative` is a corpus document.

        `authored_tree` says whether `knowledge_dir` exists in this repository;
        when it does, nothing outside it is a document. The caller supplies it
        because it is the one holding the filesystem — and because watch mode
        must answer for paths that do not exist any more.
        """
        parts = relative.parts
        if not parts or any(part.startswith(".") for part in parts):
            return False
        if parts[0] in DERIVED_DIRNAMES:
            return False
        if authored_tree and parts[0] != self.knowledge_dir:
            return False
        return not self.excluded(relative)

    def has_authored_tree(self, root: Path) -> bool:
        """Whether a *separate* authored tree exists to narrow the corpus to.

        ``.`` and the empty string both mean "the repository is the corpus" —
        the setting a documentation repository states when its docs live at the
        root. Reading them as a directory name would narrow the corpus to paths
        beginning ``./``, which nothing produces, and quietly compile nothing.
        """
        if self.knowledge_dir in {"", "."}:
            return False
        return (root / self.knowledge_dir).is_dir()

    def scope_of(self, root: Path) -> Path:
        """The directory a scan starts from: the authored tree, or the repository."""
        return root / self.knowledge_dir if self.has_authored_tree(root) else root


def discover(root: Path, scope: CorpusScope | None = None) -> list[Path]:
    """Every document a build compiles, in deterministic (sorted) order."""
    settings = scope or CorpusScope()
    authored = settings.has_authored_tree(root)
    found = [
        path
        for path in settings.scope_of(root).rglob("*.md")
        if settings.contains(
            PurePosixPath(path.relative_to(root).as_posix()),
            authored_tree=authored,
        )
    ]
    return sorted(found, key=lambda path: path.relative_to(root).as_posix())
