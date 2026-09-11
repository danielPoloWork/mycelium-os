# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Where a conversation's two files live (doc 08 §§5, 7).

A leaf module, for the reason :mod:`mycelium.layout` is one: the archive writes
records and the projection writes Markdown, each needs to know where the other
one puts things — a deletion finds a projection from a record, a projection
names its record as its `source` — and if either owned the layout the other
would have to import it. Two modules and one cycle, or three modules and none.
"""

from datetime import UTC, datetime, tzinfo
from pathlib import PurePosixPath
from typing import Final

from mycelium.ingest import EVIDENCE_DIRNAME
from mycelium.sdk.identity import heading_slug

__all__ = [
    "ARCHIVE_DIRNAME",
    "MYCELIUM_DIRNAME",
    "PROJECTION_SUFFIX",
    "RECORD_SUFFIX",
    "archive_path",
    "projection_path",
    "slug",
]

MYCELIUM_DIRNAME: Final = ".mycelium"
"""The derived store, where tier-1 custody lives (architecture §3).

Named here rather than spelled in each caller: the archive puts an imported
original into custody and the distillation lane puts a synthesis record there,
and two spellings of one directory is how a module ends up writing to two.
The core keeps its own constant for its own use; this is the module's, because
`mycelium.store` is not module-facing and reaching into it for a string would be
a coupling the surface test exists to catch (ADR-0086)."""

ARCHIVE_DIRNAME: Final = "chats"
"""Doc 08 §5's own directory, at the repository root beside `knowledge/`.

Deliberately *not* under `knowledge/`: a record is the canonical machine-owned
archive, and `knowledge/` is the authored tree a human edits (architecture §2).
The projection is what crosses over.

The compiler never reads it, and needed no change not to: `discover()` globs
`*.md`, and a `.chat.jsonl` is not one.
"""

RECORD_SUFFIX: Final = ".chat.jsonl"
PROJECTION_SUFFIX: Final = ".md"

_SLUG_LIMIT: Final = 48
_ULID_TAIL: Final = 6


def slug(text: str, limit: int = _SLUG_LIMIT) -> str:
    """A path-safe slug, using the core's own heading slugger.

    Reused rather than reimplemented so a conversation's filename slugs by the
    same rule a heading anchor does — one slug function per repository is what
    stops two subsystems disagreeing about what `C++` becomes.
    """
    found = heading_slug(text) or "conversation"
    return found[:limit].rstrip("-") or "conversation"


def archive_path(
    *,
    project: str,
    title: str,
    conv_id: str,
    dated: datetime,
    zone: tzinfo | None = None,
) -> PurePosixPath:
    """``chats/<project>/<year>/<month>/<date>-<slug>-<ulid6>.chat.jsonl`` (doc 08 §5).

    `dated` is the conversation's own start when the export knew it, else its
    import time; it is rendered in `[chats] timezone` — doc 08 §5's rule, and the
    reason that setting exists. The record's timestamps stay UTC, so the path is
    a filing convenience and never the source of truth.

    The ULID tail disambiguates two conversations that share a day and a title,
    which a re-exported thread does; `conv_id` is the identity and the filename
    is convenience, so a rename breaks nothing.
    """
    stamp = dated.astimezone(zone or UTC)
    name = f"{stamp:%Y-%m-%d}-{slug(title)}-{conv_id[-_ULID_TAIL:].lower()}{RECORD_SUFFIX}"
    return PurePosixPath(ARCHIVE_DIRNAME, slug(project), f"{stamp:%Y}", f"{stamp:%m}", name)


def projection_path(record: PurePosixPath, knowledge_dir: str = "knowledge") -> PurePosixPath:
    """The evidence document mirroring `record` (doc 08 §7).

    Derived from the record's own path so the two trees mirror each other exactly
    — "same-basename", in §7's words — which is what lets a deletion find the
    projection without an index, and what makes the pair obvious in a diff.
    """
    relative = record.relative_to(ARCHIVE_DIRNAME)
    renamed = relative.with_name(relative.name.removesuffix(RECORD_SUFFIX) + PROJECTION_SUFFIX)
    return PurePosixPath(knowledge_dir, EVIDENCE_DIRNAME, ARCHIVE_DIRNAME) / renamed
