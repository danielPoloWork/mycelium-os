# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Record contracts v0 — the typed schemas everything else builds on (spec 03 §§3-7).

Every record is a frozen pydantic model carrying an explicit ``schema_version``
(D-016; migration policy v1: rebuild). Records are build artifacts — facts derived
from sources — so they are immutable after construction and reject unknown fields.
JSON Schema 2020-12 documents for non-Python consumers are exported from these
models by :mod:`mycelium.sdk.schema` (D-003).

Contract conventions (spec 03 §1):

- Content digests are SHA-256 over normalized bytes, rendered ``sha256:<64 hex>``.
- Entity identity uses ULIDs; content identity uses digests — never conflated.
- Timestamps are RFC 3339 UTC; aware non-UTC inputs are normalized, naive rejected.
- ``namespace`` (default ``"default"``) is reserved on query-scoped records so
  Phase-5 tenancy is a data backfill, not an identity migration (D-002).

Scope notes: identity *generation* (hashing, ULID minting, anchor slugs) is
roadmap 2.3; this module only validates the formats. The KIR (§4) and snapshot
manifest (§7) schemas are two of the five stable contracts that freeze at 1.0
(architecture §10) — v0 is their pre-freeze shape.
"""

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated, Final, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    NonNegativeInt,
    PlainSerializer,
    StringConstraints,
    model_validator,
)

__all__ = [
    "Anchor",
    "Chunk",
    "ChunkKind",
    "Document",
    "DocumentStats",
    "CaseResult",
    "Edge",
    "EdgeProvenance",
    "EdgeStatus",
    "EdgeType",
    "EvalCase",
    "EvalRunManifest",
    "EvalSlice",
    "GateResult",
    "MetricSummary",
    "RelevantAnchor",
    "EmbeddingInfo",
    "Entity",
    "KirDocument",
    "KirNode",
    "NodeKind",
    "Provenance",
    "ProvenanceOrigin",
    "Record",
    "Sha256Digest",
    "SnapshotCounts",
    "SnapshotManifest",
    "SourceTrust",
    "SrcLocator",
    "Symbol",
    "Synthesizer",
    "Toolchain",
    "TrustClass",
    "Ulid",
    "UtcDatetime",
    "Verification",
    "VerificationStatus",
]


# ---------------------------------------------------------------------------
# Scalar contracts (spec 03 §§1-2)
# ---------------------------------------------------------------------------

type Ulid = Annotated[
    str,
    StringConstraints(pattern=r"^[0-7][0-9A-HJKMNP-TV-Z]{25}$"),
]
"""Entity identity: 26 chars of Crockford base32 (sortable, no coordination).

26 characters carry 130 bits but a ULID is 128, so the leading character is
capped at ``7`` — the two high bits must be zero. Without that cap the pattern
would admit strings :func:`mycelium.sdk.identity.decode_ulid` rejects as
overflowing (ADR-0005).
"""

type Sha256Digest = Annotated[
    str,
    StringConstraints(pattern=r"^sha256:[0-9a-f]{64}$"),
]
"""Content identity: SHA-256 over normalized bytes, ``sha256:`` prefixed."""

type Anchor = Annotated[
    str,
    StringConstraints(pattern=r"^[^#]+#[^#]*/(?:0|[1-9][0-9]*)$"),
]
"""Logical chunk identity: ``<doc-path>#<heading-slug-path>/<ordinal>``.

Survives edits that keep the heading path; slug construction rules are the
identity library's contract (roadmap 2.3) — this validates the shape only.
"""

type NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]

type EntitySlug = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"),
]
"""Readable entity slug (the ``ent:<slug>`` ID form, spec 03 §2, without prefix)."""

type SymbolId = Annotated[
    str,
    StringConstraints(pattern=r"^sym:[a-z0-9_+-]+:.+$"),
]
"""Symbol identity: ``sym:<language>:<qualified-name>`` (spec 03 §2)."""


def _ensure_utc(value: datetime) -> datetime:
    """Reject naive datetimes; normalize aware ones to UTC (spec 03 §1)."""
    if value.tzinfo is None:
        msg = "timestamp must be timezone-aware (RFC 3339 UTC, spec 03 §1)"
        raise ValueError(msg)
    return value.astimezone(UTC)


def _rfc3339(value: datetime) -> str:
    """Serialize a UTC datetime in the spec's ``Z``-suffixed RFC 3339 form."""
    return value.isoformat().replace("+00:00", "Z")


type UtcDatetime = Annotated[
    datetime,
    AfterValidator(_ensure_utc),
    PlainSerializer(_rfc3339, return_type=str, when_used="json"),
]
"""RFC 3339 UTC timestamp: aware-only in, ``Z``-suffixed out."""


# ---------------------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Base record
# ---------------------------------------------------------------------------


class Record(BaseModel):
    """Base of every v0 record: immutable, closed shape, alias-faithful JSON.

    ``frozen`` — records are facts shared across pipeline stages; post-construction
    mutation is a defect class removed at the type layer (Immutable Object,
    ADR-0004). ``extra="forbid"`` — unknown fields are producer drift, caught at
    the boundary; adding fields is a deliberate schema-version event (D-016).
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
    )


# ---------------------------------------------------------------------------
# Document record (spec 03 §3)
# ---------------------------------------------------------------------------


class Synthesizer(Record):
    """Identity of the LLM lane that authored a synthesized document (D-020)."""

    provider: NonEmptyStr
    model: NonEmptyStr
    prompt_digest: Sha256Digest
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class Provenance(Record):
    """Where a document's bytes came from; orthogonal to verification status."""

    origin: ProvenanceOrigin = ProvenanceOrigin.AUTHORED
    source_uri: str | None = None
    source_digest: Sha256Digest | None = Field(
        default=None, description="CAS blob of the acquired original (tier 1)."
    )
    source_trust: SourceTrust | None = None
    connector: str | None = None
    connector_version: str | None = None
    synthesizer: Synthesizer | None = None
    ingested_at: UtcDatetime | None = None


class Verification(Record):
    """Evidence block written by ``mycelium verify`` / ``mycelium promote`` (D-021)."""

    verified_by: NonEmptyStr
    verified_at: date
    grounding: float = Field(
        ge=0.0, le=1.0, description="Grounding score from the last `mycelium verify` run."
    )


class DocumentStats(Record):
    """Build-time document statistics (spec 03 §3)."""

    tokens: NonNegativeInt
    headings: NonNegativeInt
    chunks: NonNegativeInt
    links_out: NonNegativeInt


class Document(Record):
    """Document record v0 (spec 03 §3).

    ``doc_id`` is logical identity (pinned in frontmatter for authored Markdown,
    survives renames); ``content_digest`` is content identity (changes on every
    edit, drives dirty detection). ``verification_status`` is derived from the
    folder at build time — the folder is the single source of status (D-021).
    """

    schema_version: Literal["mycelium/document/v0"] = "mycelium/document/v0"
    doc_id: Ulid
    path: NonEmptyStr
    title: str
    namespace: str = "default"
    collection: str | None = None
    tags: tuple[str, ...] = ()
    content_digest: Sha256Digest
    trust_class: TrustClass
    curated: bool = False
    verification_status: VerificationStatus
    verification: Verification | None = None
    provenance: Provenance
    fidelity_report: Sha256Digest | None = Field(
        default=None, description="CAS blob of the ingestion fidelity report."
    )
    secret_flags: tuple[str, ...] = ()
    stats: DocumentStats
    created_at: UtcDatetime
    updated_at: UtcDatetime


# ---------------------------------------------------------------------------
# KIR — Knowledge Intermediate Representation (spec 03 §4; stable contract)
# ---------------------------------------------------------------------------


class SrcLocator(Record):
    """Source locator: the smallest practical unit the connector can provide.

    Spec 03 §4 names the units — page/bbox, byte range, cell range, timecode —
    all optional; a connector fills what it can. ``lines`` is the same idea for
    line-oriented formats, where it is both the smallest unit a Markdown parser
    reports and the unit :class:`Chunk` already stores (ADR-0006).
    """

    page: int | None = Field(default=None, ge=1)
    bbox: tuple[float, float, float, float] | None = Field(
        default=None, description="(x0, y0, x1, y1) on the given page."
    )
    byte_range: tuple[NonNegativeInt, NonNegativeInt] | None = None
    lines: tuple[NonNegativeInt, NonNegativeInt] | None = Field(
        default=None, description="Inclusive 1-based (start, end) line span in the source."
    )
    cell_range: str | None = None
    timecode: str | None = None

    @model_validator(mode="after")
    def _lines_ordered(self) -> Self:
        if self.lines is not None and self.lines[0] > self.lines[1]:
            msg = f"lines start {self.lines[0]} > end {self.lines[1]}"
            raise ValueError(msg)
        return self


_KIND_FIELDS: Final[dict[NodeKind, frozenset[str]]] = {
    NodeKind.HEADING: frozenset({"level"}),
    NodeKind.CODE_BLOCK: frozenset({"lang"}),
    NodeKind.LIST: frozenset({"variant"}),
    NodeKind.TABLE_ROW: frozenset({"variant"}),
    NodeKind.CALLOUT: frozenset({"variant", "title"}),
    NodeKind.LINK: frozenset({"target", "title"}),
    NodeKind.IMAGE: frozenset({"target", "title"}),
    NodeKind.WIKILINK: frozenset({"target"}),
    NodeKind.EMBED: frozenset({"target"}),
    NodeKind.OPAQUE: frozenset({"media_type", "blob", "note"}),
}
"""Which optional fields each kind may carry; every other kind takes none.

The vocabulary is closed (spec 03 §4) but the per-kind field sets are not stated,
so they are declared here and enforced — adding one is a deliberate, reviewable
schema event rather than a field quietly appearing on a node kind (ADR-0006).
"""

_KIND_SPECIFIC: Final[frozenset[str]] = frozenset(
    {"level", "lang", "variant", "title", "target", "media_type", "blob", "note"}
)


class KirNode(Record):
    """One node of the KIR document AST v0.

    A single open record rather than a per-kind discriminated union: spec 03 §4
    fixes the kind vocabulary but not every kind's field set, and the ingestion
    connectors (roadmap 4.1) will bring kinds this milestone cannot see. What the
    union would buy — no nonsense combinations — is bought instead by
    :data:`_KIND_FIELDS`, which declares the optional fields each kind may carry
    and is enforced on construction (ADR-0006).

    ``text``, ``parent``, ``ord`` and ``src`` are the common core every kind may
    use. KIR adds fields by minor version and never repurposes them.
    """

    id: NonEmptyStr
    kind: NodeKind
    text: str | None = None
    level: int | None = Field(default=None, ge=1, description="Heading depth, 1-6.")
    lang: str | None = Field(default=None, description="Code-block language tag.")
    variant: str | None = Field(
        default=None,
        description="Kind-specific subtype: callout type, list ordering, row role.",
    )
    title: str | None = Field(default=None, description="Link/image title or callout title.")
    target: str | None = Field(
        default=None, description="Link, image, wikilink, or embed destination."
    )
    media_type: str | None = None
    blob: Sha256Digest | None = None
    note: str | None = None
    parent: str | None = None
    ord: NonNegativeInt
    src: SrcLocator | None = None

    @model_validator(mode="after")
    def _fields_are_legal_for_kind(self) -> Self:
        allowed = _KIND_FIELDS.get(self.kind, frozenset())
        used = {
            name
            for name in _KIND_SPECIFIC
            if getattr(self, name) is not None and name not in allowed
        }
        if used:
            msg = f"{self.kind.value} node must not carry {sorted(used)}"
            raise ValueError(msg)
        if self.kind is NodeKind.HEADING and self.level is None:
            msg = "heading node requires a level"
            raise ValueError(msg)
        return self


class KirDocument(Record):
    """KIR document v0 (spec 03 §4): thin, ordered, versioned AST, stored in CAS."""

    schema_version: Literal["mycelium/kir/v0"] = "mycelium/kir/v0"
    doc_id: Ulid
    source_digest: Sha256Digest
    nodes: tuple[KirNode, ...]
    warnings: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Chunk record (spec 03 §5)
# ---------------------------------------------------------------------------


class Chunk(Record):
    """Chunk record v0 (spec 03 §5): heading-bounded retrieval unit.

    Invariant owned by the chunker (roadmap 2.5), stated here for consumers:
    ordered chunk texts ⊇ normalized document text (property-tested there).
    """

    schema_version: Literal["mycelium/chunk/v0"] = "mycelium/chunk/v0"
    anchor: Anchor
    doc_id: Ulid
    chunk_digest: Sha256Digest
    heading_path: tuple[str, ...]
    kir_nodes: tuple[NonEmptyStr, ...]
    text: str
    tokens: NonNegativeInt
    lines: tuple[NonNegativeInt, NonNegativeInt] = Field(
        description="Inclusive (start, end) line span in the normalized source."
    )
    kind: ChunkKind = ChunkKind.PROSE
    namespace: str = "default"

    @model_validator(mode="after")
    def _lines_ordered(self) -> Self:
        start, end = self.lines
        if start > end:
            msg = f"lines start {start} > end {end}"
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# Symbols, edges, entities (spec 03 §6)
# ---------------------------------------------------------------------------


class Symbol(Record):
    """Symbol record v0: a code/docs definition site and its documentation refs."""

    schema_version: Literal["mycelium/symbol/v0"] = "mycelium/symbol/v0"
    symbol: SymbolId
    kind: NonEmptyStr
    defined_in: NonEmptyStr
    doc_refs: tuple[NonEmptyStr, ...] = ()
    namespace: str = "default"


class EdgeProvenance(Record):
    """Where an edge was observed (e.g. ``markdown_link``, ``wikilink``)."""

    kind: NonEmptyStr
    anchor: Anchor | None = None


class Edge(Record):
    """Edge record v0: a typed fact between two identified things, not an entity.

    Edge identity is the digest of ``(from, to, type, provenance_digest)``
    (spec 03 §2) — computed by the identity library (roadmap 2.3), so the record
    itself carries no id field. ``from`` is a Python keyword: the field is
    ``from_`` in Python and ``from`` in JSON (validation and serialization are
    alias-faithful by model config).
    """

    schema_version: Literal["mycelium/edge/v0"] = "mycelium/edge/v0"
    from_: NonEmptyStr = Field(alias="from")
    to: NonEmptyStr
    type: EdgeType
    status: EdgeStatus
    provenance: EdgeProvenance
    weight: float = Field(default=1.0, ge=0.0)
    namespace: str = "default"


class Entity(Record):
    """Entity record v0 (optional extraction stage, off by default in v1).

    Spec 03 §6 lists the field set in abbreviated form; per §1's conventions the
    record also carries ``schema_version`` (D-016) and ``namespace`` (D-002),
    exactly like its sibling query-scoped records.
    """

    schema_version: Literal["mycelium/entity/v0"] = "mycelium/entity/v0"
    entity_id: Ulid
    slug: EntitySlug
    name: NonEmptyStr
    aliases: tuple[str, ...] = ()
    kind: NonEmptyStr
    status: EdgeStatus
    doc_refs: tuple[NonEmptyStr, ...] = ()
    namespace: str = "default"


# ---------------------------------------------------------------------------
# Snapshot manifest (spec 03 §7; stable contract)
# ---------------------------------------------------------------------------


class Toolchain(Record):
    """Toolchain that produced a snapshot."""

    mycelium: NonEmptyStr
    python: NonEmptyStr


class EmbeddingInfo(Record):
    """Embedding configuration of a snapshot; vectors key on (chunk_digest, model_id)."""

    model_id: NonEmptyStr
    dim: int = Field(ge=1)
    deterministic: bool
    provider: NonEmptyStr


class SnapshotCounts(Record):
    """Artifact counts recorded in the manifest."""

    documents: NonNegativeInt
    chunks: NonNegativeInt
    symbols: NonNegativeInt
    edges: NonNegativeInt
    vectors: NonNegativeInt
    quarantined: NonNegativeInt


class SnapshotManifest(Record):
    """Snapshot manifest v0 (spec 03 §7): the immutable description of one build.

    ``embedding`` is ``None`` on snapshots built without a vector stage — a
    degraded-but-published snapshot records the gap in ``degraded`` rather than
    tearing the publish (RFC-0001 failure taxonomy).
    """

    schema_version: Literal["mycelium/manifest/v0"] = "mycelium/manifest/v0"
    snapshot_id: Ulid
    parent_id: Ulid | None = None
    created_at: UtcDatetime
    config_digest: Sha256Digest
    toolchain: Toolchain
    schema_versions: dict[str, NonEmptyStr]
    embedding: EmbeddingInfo | None = None
    counts: SnapshotCounts
    artifact_digests: dict[str, Sha256Digest]
    degraded: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    timings_ms: dict[str, NonNegativeInt]


# ---------------------------------------------------------------------------
# Evaluation records (spec 03 §10, spec 04 §7)
# ---------------------------------------------------------------------------


class RelevantAnchor(Record):
    """One judged passage: where the answer lives, and how good it is.

    Grades are the usual graded-relevance scale — 3 answers the query outright,
    2 is strongly supporting, 1 is related context. 0 is not recorded: an
    unjudged anchor is simply absent.
    """

    anchor: Anchor
    grade: int = Field(ge=1, le=3)


class EvalCase(Record):
    """One judged query (spec 03 §10)."""

    schema_version: Literal["mycelium/eval-case/v0"] = "mycelium/eval-case/v0"
    case_id: NonEmptyStr
    query: NonEmptyStr
    slices: tuple[EvalSlice, ...] = ()
    relevant: tuple[RelevantAnchor, ...] = ()
    answerable: bool = True
    note: str | None = Field(
        default=None, description="Why this case exists, for whoever re-judges it."
    )

    @model_validator(mode="after")
    def _judgments_match_answerability(self) -> Self:
        if self.answerable and not self.relevant:
            msg = f"{self.case_id}: an answerable case needs at least one relevant anchor"
            raise ValueError(msg)
        if not self.answerable and self.relevant:
            msg = f"{self.case_id}: an unanswerable case must have no relevant anchors"
            raise ValueError(msg)
        return self


class CaseResult(Record):
    """What one retriever did with one case."""

    case_id: NonEmptyStr
    retrieved: tuple[Anchor, ...] = ()
    ndcg_at_10: float = Field(ge=0.0, le=1.0)
    recall_at_10: float = Field(ge=0.0, le=1.0)
    recall_at_50: float = Field(ge=0.0, le=1.0)
    reciprocal_rank: float = Field(ge=0.0, le=1.0)
    citation_coverage: float = Field(ge=0.0, le=1.0)
    abstained: bool = False
    latency_ms: NonNegativeInt = 0


class MetricSummary(Record):
    """Averaged metrics over a set of cases (spec 04 §7.2)."""

    cases: NonNegativeInt
    ndcg_at_10: float = Field(ge=0.0, le=1.0)
    recall_at_10: float = Field(ge=0.0, le=1.0)
    recall_at_50: float = Field(ge=0.0, le=1.0)
    mrr: float = Field(ge=0.0, le=1.0)
    citation_coverage: float = Field(ge=0.0, le=1.0)
    false_answer_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Unanswerable cases that returned results."
    )
    latency_p50_ms: NonNegativeInt = 0
    latency_p95_ms: NonNegativeInt = 0


class GateResult(Record):
    """One CI-enforced gate's verdict (spec 04 §7.3)."""

    gate: NonEmptyStr
    passed: bool
    detail: NonEmptyStr


class EvalRunManifest(Record):
    """An evaluation run, reproducible from what it records (spec 04 §7.5).

    A report without a manifest is exploratory and cannot satisfy a gate.
    """

    schema_version: Literal["mycelium/eval-run/v0"] = "mycelium/eval-run/v0"
    run_id: Ulid
    snapshot_id: Ulid
    created_at: UtcDatetime
    config_digest: Sha256Digest
    case_set: NonEmptyStr
    retriever: NonEmptyStr
    retriever_config: dict[str, JsonValue] = Field(default_factory=dict)
    toolchain: Toolchain
    overall: MetricSummary
    per_slice: dict[str, MetricSummary] = Field(default_factory=dict)
    results: tuple[CaseResult, ...] = ()
    gates: tuple[GateResult, ...] = ()
