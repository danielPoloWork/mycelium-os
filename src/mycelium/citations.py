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
``mycelium_fetch`` has always parsed it and then ignored it. Honouring it is half
the fix: if the cited line range is not where that anchor sits now, the passage
has moved, and a consumer that is about to re-quote it must be told.

**The other half is content, and roadmap 5.17 added it.** A line range is
*positional*, so it sees every refactoring that moves a passage — five of the six
drifts the proof corpus produces — and cannot see the sixth: an edit that
rewrites a passage without changing its length keeps the anchor, keeps the range,
and changes the words. So a minted citation now also carries ``&digest=<hex>``,
twelve characters of the chunk's own `chunk_digest`, and the two signals are
checked independently. Extending the URI grammar meant touching one of the five
contracts that freeze at 1.0 (spec 02 §10), which is why it waited for an item of
its own and an argument about what an older client does with it (`ADR-0089`).

Neither signal masks the other, and the report says which fired: a passage that
*moved* is the text that was cited, at a new address, so the remedy is the
corrected URI. A passage that was *rewritten* is different text at the same
address, so the remedy is to read it again. One sentence used to cover both and
had to say "has moved" even when the words were what differed.

Drift is **not** an error. The anchor exists and its current content is the
truth at that anchor; refusing to serve it would break every consumer that holds
a citation into a document under active editing, which is every consumer. So the
content is returned and the response says, in one block, what was cited, what is
there now, and the URI to cite instead.
"""

from dataclasses import dataclass
from typing import Final

from mycelium.sdk.identity import CitationUri, citation_uri, parse_anchor
from mycelium.sdk.types import Chunk

__all__ = [
    "MOVED",
    "MOVED_AND_REWRITTEN",
    "REWRITTEN",
    "Drift",
    "chunk_uri",
    "citation_drift",
]


def chunk_uri(chunk: Chunk) -> str:
    """The public citation URI for `chunk`: range and digest (spec 03 §2).

    One implementation, because the CLI and the MCP server hand out the *same*
    citation and a consumer may hold one from either. Two copies of this
    function agreed only by coincidence, and what they write is load-bearing
    twice over: :func:`citation_drift` reads both halves back.

    **Every mint carries the digest**, which is the half of roadmap 5.17 that had
    to come with the other. A citation is *born* in `mycelium_search`; a content
    check reachable only through `mycelium_fetch` would be a tool nobody can pick
    up at the moment they need it, because by then they are holding a URI that
    was minted without one (ADR-0078's own reason for refusing the half-measure).
    There is exactly one mint point, so "every mint" costs nothing to guarantee.
    """
    parts = parse_anchor(chunk.anchor)
    return citation_uri(
        chunk.doc_id,
        parts.heading_slugs,
        parts.ordinal,
        lines=chunk.lines,
        digest=chunk.chunk_digest,
    )


MOVED: Final = "moved"
"""The passage is somewhere else in the file; its words are unchanged."""

REWRITTEN: Final = "rewritten"
"""The words changed. The anchor and the line range may be untouched — this is the
case a positional check cannot see, and the one roadmap 5.17 exists for."""

MOVED_AND_REWRITTEN: Final = "moved_and_rewritten"
"""Both, which is what most real edits to a cited section look like."""


@dataclass(frozen=True, slots=True)
class Drift:
    """A citation that still resolves, but not to what it was minted against.

    Two independent signals, and naming which one fired is most of the value
    (roadmap 5.17). A passage can move without changing — an edit above it in the
    file — and change without moving, which is the blind spot ADR-0078 had to
    state and leave open. Before the digest there was one sentence for both, and
    it had to say *"has moved"* even when the words were what actually differed.
    """

    kind: str
    """:data:`MOVED`, :data:`REWRITTEN`, or :data:`MOVED_AND_REWRITTEN`."""
    uri: str
    """The citation to use instead — this anchor, as it is today."""
    cited_lines: tuple[int, int] | None = None
    """The line range the consumer's URI claimed, or ``None`` if it carried none."""
    current_lines: tuple[int, int] | None = None
    cited_digest: str | None = None
    """The content prefix the URI claimed, or ``None`` if it carried none."""
    current_digest: str | None = None

    @property
    def reason(self) -> str:
        """One operator- and agent-facing sentence. The wording is the contract.

        Each kind gets its own, because they call for different reading. A moved
        passage is still the text that was cited, so the remedy is to update the
        URI; a rewritten one is *different text at the same address*, so the
        remedy is to read it again before standing behind the quotation.
        """
        tail = "the content below is what the anchor holds today"
        if self.kind == MOVED:
            return (
                f"the passage at this anchor has moved since the citation was made "
                f"({self._range}), and its text is unchanged; {tail}, and the URI above "
                "is the one to cite from now on"
            )
        if self.kind == REWRITTEN:
            return (
                "the passage at this anchor has been rewritten since the citation was "
                f"made ({self._content}) — same anchor, same lines, different words; "
                f"{tail}, so re-read it before re-quoting it"
            )
        return (
            f"the passage at this anchor has moved and been rewritten since the citation "
            f"was made ({self._range}; {self._content}); {tail}, so re-read it before "
            "re-quoting it"
        )

    @property
    def _range(self) -> str:
        if self.cited_lines is None or self.current_lines is None:
            return "line range unknown"
        return (
            f"cited lines {self.cited_lines[0]}-{self.cited_lines[1]}, now "
            f"{self.current_lines[0]}-{self.current_lines[1]}"
        )

    @property
    def _content(self) -> str:
        return f"cited content {self.cited_digest}, now {self.current_digest}"

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "cited_lines": None if self.cited_lines is None else list(self.cited_lines),
            "current_lines": None if self.current_lines is None else list(self.current_lines),
            "cited_digest": self.cited_digest,
            "current_digest": self.current_digest,
            "uri": self.uri,
            "reason": self.reason,
        }


def citation_drift(citation: CitationUri, chunk: Chunk) -> Drift | None:
    """Whether `chunk` is still what, and where, `citation` said it was.

    ``None`` means no disagreement to report: every signal the URI carried
    agrees with the chunk, or it carried none — the honest answer for a citation
    somebody typed by hand rather than one this product minted.

    The two signals are checked independently and neither masks the other. A
    citation minted before roadmap 5.17 has no digest and gets exactly ADR-0078's
    answer; one minted since is also held to its content, which is what closes
    `test_an_in_place_edit_is_the_blind_spot`.
    """
    moved = citation.lines is not None and citation.lines != chunk.lines
    current_digest = _prefix(chunk.chunk_digest, citation.digest)
    rewritten = citation.digest is not None and citation.digest != current_digest
    if not moved and not rewritten:
        return None
    kind = MOVED_AND_REWRITTEN if moved and rewritten else MOVED if moved else REWRITTEN
    return Drift(
        kind=kind,
        uri=chunk_uri(chunk),
        cited_lines=citation.lines,
        current_lines=chunk.lines if citation.lines is not None else None,
        cited_digest=citation.digest,
        current_digest=current_digest if citation.digest is not None else None,
    )


def _prefix(chunk_digest: str, cited: str | None) -> str | None:
    """The chunk's digest cut to the length the citation offered.

    Comparison is by prefix so a URI carrying the full 64-character
    `chunk_digest` — written by hand from an export bundle — works beside the
    twelve characters a mint writes. Cutting the *current* value down to the
    cited length, rather than padding the cited one out, is what makes the two
    comparable without either side having to know what the other chose.
    """
    if cited is None:
        return None
    return chunk_digest.removeprefix("sha256:")[: len(cited)]
