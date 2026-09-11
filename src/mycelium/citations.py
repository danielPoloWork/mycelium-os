# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Citations: minting them, and telling a consumer when one has gone stale.

A citation URI is the one durable thing this product hands an agent
(spec 03 §2). It keys on ``doc_id`` so it survives a rename or a
``candidate/`` → ``verified/`` promotion (D-021), and it names a *section and an
ordinal* rather than a byte range so it survives an edit elsewhere in the
document. What it cannot survive is a heading being renamed, and spec 03 §3.1
is explicit about what must happen then: ``mycelium_fetch`` returns a typed
``ANCHOR_GONE`` with the nearest surviving ancestor *"rather than silently wrong
content"*.

Roadmap 5.6 set out to prove that on a heavily refactored corpus and found the
promise half-kept. A renamed heading, a re-nested section and a deleted document
all behave exactly as designed. But an anchor is
``(path, heading-slug-path, ordinal)``, and the **ordinal is a position**: delete
a paragraph from the middle of a section, insert one, reorder two sections, or
rename the first of two headings that slugify alike, and the anchor still
resolves — to a *different passage*. Measured on the proof corpus
(`tests/test_stale_anchors.py`), six citations across five refactorings resolved
to content they were never minted against, and none of them said so.

This module is the sentence that was missing. Every URI this product mints
carries ``?lines=a-b`` — :func:`chunk_uri` has always written it, and
``mycelium_fetch`` has always parsed it and then ignored it. Honouring it is the
whole fix: if the cited line range is not where that anchor sits now, the passage
has moved, and a consumer that is about to re-quote it must be told.

**What this catches, and what it does not.** The line range is *positional*, so
it sees every refactoring that moves a passage — five of the six drifts the proof
corpus produces. It cannot see an edit that rewrites a passage in place without
changing its length: the anchor resolves, the range matches, and the text is new.
Detecting that needs *content* identity in the citation, which is a change to one
of the five contracts that freeze at 1.0 (spec 02 §10) and is filed as roadmap
5.17 rather than smuggled in here. The limit is stated in the tool description
and in `ADR-0078`, because an undocumented blind spot is worse than a known one.

Drift is **not** an error. The anchor exists and its current content is the
truth at that anchor; refusing to serve it would break every consumer that holds
a citation into a document under active editing, which is every consumer. So the
content is returned and the response says, in one block, what was cited, what is
there now, and the URI to cite instead.
"""

from dataclasses import dataclass

from mycelium.sdk.identity import CitationUri, citation_uri, parse_anchor
from mycelium.sdk.types import Chunk

__all__ = ["Drift", "chunk_uri", "citation_drift"]


def chunk_uri(chunk: Chunk) -> str:
    """The public citation URI for `chunk`, line range included (spec 03 §2).

    One implementation, because the CLI and the MCP server hand out the *same*
    citation and a consumer may hold one from either. Two copies of this
    function agreed only by coincidence, and the line range they both write is
    now load-bearing: :func:`citation_drift` reads it back.
    """
    parts = parse_anchor(chunk.anchor)
    return citation_uri(chunk.doc_id, parts.heading_slugs, parts.ordinal, lines=chunk.lines)


@dataclass(frozen=True, slots=True)
class Drift:
    """A citation that still resolves, but not to what it was minted against."""

    cited_lines: tuple[int, int]
    """The line range the consumer's URI claimed."""
    current_lines: tuple[int, int]
    """Where that anchor's content sits now."""
    uri: str
    """The citation to use instead — this anchor, with its current range."""

    @property
    def reason(self) -> str:
        """One operator- and agent-facing sentence. The wording is the contract."""
        return (
            f"the passage at this anchor has moved since the citation was made "
            f"(cited lines {self.cited_lines[0]}-{self.cited_lines[1]}, now "
            f"{self.current_lines[0]}-{self.current_lines[1]}); the content below is "
            f"what the anchor holds today, so re-read it before re-quoting it"
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "cited_lines": list(self.cited_lines),
            "current_lines": list(self.current_lines),
            "uri": self.uri,
            "reason": self.reason,
        }


def citation_drift(citation: CitationUri, chunk: Chunk) -> Drift | None:
    """Whether `chunk` is still where `citation` said it was.

    ``None`` means no disagreement to report — either the ranges match, or the
    URI carried none to check, which is the honest answer for a citation somebody
    typed by hand rather than one this product minted.
    """
    if citation.lines is None or citation.lines == chunk.lines:
        return None
    return Drift(cited_lines=citation.lines, current_lines=chunk.lines, uri=chunk_uri(chunk))
