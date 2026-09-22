# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The v0 controlled vocabularies — every enumerated field the records use.

These live apart from :mod:`mycelium.sdk.types` for one measured reason. They
are stdlib :class:`~enum.StrEnum`s and cost nothing to import, while `types`
builds twenty-five pydantic models on import; before roadmap 6.36 a consumer
wanting one enum paid **958 ms and 221 modules** for all of them. The command
line needs exactly three of these and none of the records, which is what made
the split worth making rather than merely tidy.

`mycelium.sdk.types` re-exports every name here, so
``from mycelium.sdk.types import EdgeType`` keeps working and remains the
documented import: this module is where they are *defined*, not a second
contract (`docs/compatibility.md`, ADR-0114).
"""

from enum import StrEnum

__all__ = [
    "ChunkKind",
    "EdgeStatus",
    "EdgeType",
    "EvalSlice",
    "NodeKind",
    "OpaqueDisposition",
    "ProvenanceOrigin",
    "SourceTrust",
    "TrustClass",
    "VerificationStatus",
]


class TrustClass(StrEnum):
    """Authority layer of a document (spec 03 §3; retrieval may weight it)."""

    AUTHORED = "authored"
    CURATED = "curated"
    INGESTED = "ingested"
    EXTERNAL = "external"


class VerificationStatus(StrEnum):
    """Folder-derived verification state (D-021): the folder is the source."""

    VERIFIED = "verified"
    CANDIDATE = "candidate"
    EVIDENCE = "evidence"


class SourceTrust(StrEnum):
    """Per-source/connector origin trust, assigned in ``mycelium.toml`` (spec 03 §3)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class ProvenanceOrigin(StrEnum):
    """How a document came to exist (spec 03 §3; absent frontmatter = authored)."""

    AUTHORED = "authored"
    INGESTED = "ingested"
    SYNTHESIZED = "synthesized"


class NodeKind(StrEnum):
    """KIR node kinds v0 — the closed list from spec 03 §4."""

    DOCUMENT = "document"
    SECTION = "section"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    TABLE_ROW = "table_row"
    TABLE_CELL = "table_cell"
    CODE_BLOCK = "code_block"
    EQUATION = "equation"
    IMAGE = "image"
    LINK = "link"
    WIKILINK = "wikilink"
    EMBED = "embed"
    CALLOUT = "callout"
    TAG_REF = "tag_ref"
    FOOTNOTE = "footnote"
    QUOTE = "quote"
    OPAQUE = "opaque"


class OpaqueDisposition(StrEnum):
    """What happened to the source element an ``opaque`` node stands for (ADR-0034).

    KIR models an element or it does not; when it does not, the element still has
    to be *accounted for*, and these are the only two honest answers. There is no
    third value for "dropped by policy": a declared policy is a property of the
    parser, recorded in the KIR document's warnings, not of a node that would then
    have to be emitted for something the adapter decided not to represent.
    """

    DEGRADED = "degraded"
    """Recorded with its payload intact — visible loss of *structure*, not content."""

    LOST = "lost"
    """Its content did not survive. This is what the loss budget counts."""


class ChunkKind(StrEnum):
    """Chunk content kind (spec 03 §5): tables and code blocks are atomic chunks."""

    PROSE = "prose"
    TABLE = "table"
    CODE = "code"


class EdgeType(StrEnum):
    """Controlled edge vocabulary v1 (D-014) — extensible only via RFC (F-9)."""

    LINKS_TO = "links_to"
    DEFINES = "defines"
    REFERENCES = "references"
    PART_OF = "part_of"
    SUPERSEDES = "supersedes"
    DERIVED_FROM = "derived_from"
    CITES = "cites"
    MENTIONS = "mentions"


class EvalSlice(StrEnum):
    """Evaluation slices v1 (spec 04 §7.1).

    Metrics are always reported per slice: an overall win never excuses a
    protected-slice loss.
    """

    EXACT = "exact"
    SYMBOL = "symbol"
    FACT = "fact"
    CONCEPTUAL = "conceptual"
    RELATIONSHIP = "relationship"
    UNANSWERABLE = "unanswerable"
    INJECTION = "injection"
    SYNTHESIZED = "synthesized"


class EdgeStatus(StrEnum):
    """Assertion discipline (spec 03 §6): extracted never becomes authored silently."""

    AUTHORED = "authored"
    EXTRACTED = "extracted"
