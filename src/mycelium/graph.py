# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The authored link graph: extraction, resolution, traversal (D-014, ADR-0018).

Spec 03 §6 makes edges **facts, not entities**: an edge's identity is the digest
of ``(from, to, type, provenance_digest)``, so the same assertion observed twice
is the same edge and re-deriving it is how a rebuild converges. This module
derives them from what a human actually wrote — wikilinks, embeds, and Markdown
links — and nothing else. Mining edges out of prose is an *extractor's* job
(roadmap 5.1/5.2), and spec 03 §6's status discipline exists to keep the two
apart: everything here is ``authored``, and extracted edges never gain that
status silently.

**Extraction and resolution are separate on purpose, and the seam is the whole
design.** Extraction reads one document's KIR and yields :class:`LinkRef`s — what
was written, verbatim, with no knowledge of the corpus. Resolution turns those
into edges, and it *cannot* be per-document: `[[api]]` resolves against every
other document's path, basename, and aliases, so adding one file can change what
an untouched file's links mean. Spec 02 §4.2 anticipates exactly this — "rebuild
global artifacts whose inputs changed" — so extraction is cached with the
document while resolution is a global pass over the corpus's link references,
which are kept in ``doc_state`` for precisely this reason (ADR-0018).

Resolution follows spec 03 §3.1: *"basename if unique, else path, aliases
honored"*, and an unresolvable wikilink is a **build warning listed in the
manifest, not an error** — a vault mid-refactor still compiles.
"""

from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Protocol, runtime_checkable

from mycelium.sdk.identity import digest_json, doc_ref, edge_id, heading_slug
from mycelium.sdk.types import (
    Chunk,
    Edge,
    EdgeProvenance,
    EdgeStatus,
    EdgeType,
    KirDocument,
    KirNode,
    NodeKind,
    Sha256Digest,
)

__all__ = [
    "EVIDENCE_FOLDER",
    "MAX_DEPTH",
    "CorpusIndex",
    "EdgeLookup",
    "GraphState",
    "LinkRef",
    "Neighbour",
    "decode_links",
    "edge_identity",
    "edge_type",
    "edges_digest",
    "encode_links",
    "extract_links",
    "neighbours",
    "resolve_edges",
    "resolve_graph",
    "section_ref",
]

MAX_DEPTH: Final = 3
"""Traversal ceiling. Spec 04 §5 budgets graph *expansion* at one hop; the tool
takes a depth because a human debugging a vault wants two or three, and an
unbounded walk over a dense corpus is a denial of service with a friendly name."""

_EXTERNAL_SCHEMES: Final = frozenset(
    {"http", "https", "mailto", "ftp", "ftps", "data", "tel", "file"}
)
"""Targets that leave the corpus. They are references to the world, not edges in
a knowledge graph, and treating them as unresolvable would warn on every
citation of a URL."""

_LINK_KINDS: Final = {
    NodeKind.LINK: "markdown_link",
    NodeKind.WIKILINK: "wikilink",
    NodeKind.EMBED: "embed",
}
"""KIR node kinds that assert a link, and the `provenance.kind` each records.

Embeds are included because spec 03 §3.1 says so: v1 performs no build-time
transclusion, but ``![[doc]]`` still asserts a relationship and still produces a
``links_to`` edge.
"""


def section_ref(path: str, slug: str) -> str:
    """Reference form for a heading inside a document: ``doc:<path>#<slug>``.

    Spec 03 §3.1 requires ``[[doc#Heading]]`` to "target anchor-level". A chunk
    anchor (`path#slug/ordinal`) is the wrong target: the link names a *section*,
    not whichever chunk the packer happened to cut first. So the graph gets a
    section reference — coarser than a chunk, finer than a document, and stable
    across re-chunking.
    """
    return f"{doc_ref(path)}#{slug}"


# ---------------------------------------------------------------------------
# Extraction: one document's KIR -> what it says, verbatim
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LinkRef:
    """One authored reference, exactly as written, before anything resolves it."""

    kind: str
    """`wikilink`, `embed`, or `markdown_link` — becomes `provenance.kind`."""
    target: str
    """The target as authored, with any heading fragment removed."""
    fragment: str
    """The heading fragment, or `""`. Empty for a link to a whole document."""
    anchor: str
    """The chunk anchor this reference sits in — where a reader would find it."""

    def as_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "target": self.target,
            "fragment": self.fragment,
            "anchor": self.anchor,
        }


def encode_links(links: Sequence[LinkRef]) -> list[dict[str, str]]:
    """The form `doc_state` stores, so resolution can run without re-parsing."""
    return [link.as_dict() for link in links]


def decode_links(raw: Iterable[Mapping[str, str]]) -> tuple[LinkRef, ...]:
    return tuple(
        LinkRef(
            kind=item["kind"],
            target=item["target"],
            fragment=item.get("fragment", ""),
            anchor=item.get("anchor", ""),
        )
        for item in raw
    )


def _split_fragment(target: str) -> tuple[str, str]:
    """Separate ``doc#Heading`` into its parts, tolerating either half's absence."""
    head, separator, fragment = target.partition("#")
    return (head.strip(), fragment.strip() if separator else "")


def _anchor_of(node: KirNode, by_id: Mapping[str, KirNode], anchors: Mapping[str, str]) -> str:
    """The chunk anchor covering `node`, walking up to its enclosing block.

    A reference is usually listed among its chunk's own KIR nodes; when it is not
    — a link directly under a heading, whose text belongs to the heading — the
    parent chain finds the block that was chunked.
    """
    current: KirNode | None = node
    seen = 0
    while current is not None and seen < 32:  # a KIR tree is shallow; this is a cycle guard
        anchor = anchors.get(current.id)
        if anchor is not None:
            return anchor
        current = by_id.get(current.parent) if current.parent else None
        seen += 1
    return ""


def extract_links(kir: KirDocument, chunks: Sequence[Chunk]) -> tuple[LinkRef, ...]:
    """Every authored reference in one document, in document order.

    Pure and per-document: it reads this document's KIR and this document's
    chunks, never the corpus. That is what lets the result be cached with the
    document and re-resolved later against a corpus that has moved on.
    """
    by_id = {node.id: node for node in kir.nodes}
    anchors = {node_id: chunk.anchor for chunk in chunks for node_id in chunk.kir_nodes}

    found: list[LinkRef] = []
    for node in kir.nodes:
        kind = _LINK_KINDS.get(node.kind)
        if kind is None or not node.target:
            continue
        target, fragment = _split_fragment(node.target)
        if not target and not fragment:
            continue
        found.append(
            LinkRef(
                kind=kind,
                target=target,
                fragment=fragment,
                anchor=_anchor_of(node, by_id, anchors),
            )
        )
    return tuple(found)


# ---------------------------------------------------------------------------
# Resolution: link references + the corpus -> edges
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CorpusIndex:
    """What a link can resolve against: every live document, three ways.

    Built once per publication from the documents the snapshot will contain, so
    resolution sees the corpus as it *will be*, not as it was.
    """

    by_path: Mapping[str, str]
    by_basename: Mapping[str, tuple[str, ...]]
    by_alias: Mapping[str, tuple[str, ...]]
    headings: Mapping[str, frozenset[str]]

    @classmethod
    def build(
        cls,
        paths: Iterable[str],
        *,
        aliases: Mapping[str, Sequence[str]] | None = None,
        headings: Mapping[str, Iterable[str]] | None = None,
    ) -> "CorpusIndex":
        by_path: dict[str, str] = {}
        by_basename: dict[str, list[str]] = {}
        for path in sorted(paths):
            by_path[_normalise(path)] = path
            by_basename.setdefault(_normalise(PurePosixPath(path).stem), []).append(path)

        by_alias: dict[str, list[str]] = {}
        for path, names in sorted((aliases or {}).items()):
            for name in names:
                by_alias.setdefault(_normalise(name), []).append(path)

        return cls(
            by_path=by_path,
            by_basename={key: tuple(value) for key, value in by_basename.items()},
            by_alias={key: tuple(value) for key, value in by_alias.items()},
            headings={path: frozenset(slugs) for path, slugs in sorted((headings or {}).items())},
        )


def _normalise(value: str) -> str:
    """Compare links case-insensitively, without a `.md` suffix, in POSIX form."""
    text = value.strip().replace("\\", "/").casefold()
    return text[:-3] if text.endswith(".md") else text


def _resolve_target(index: CorpusIndex, source_path: str, link: LinkRef) -> tuple[str | None, str]:
    """Resolve one link's document. Returns ``(path, reason)``; `reason` explains a miss.

    The order is spec 03 §3.1's: an exact path wins, then a unique basename, then
    a unique alias. Ambiguity is a miss with its own message — silently picking
    one of two documents is how a knowledge graph starts lying.
    """
    if not link.target:
        return source_path, ""  # a bare `#fragment` points inside this document

    wanted = _normalise(link.target)
    if wanted in index.by_path:
        return index.by_path[wanted], ""

    # A relative Markdown link resolves against its own document's directory.
    if link.kind == "markdown_link":
        relative = _normalise(str(PurePosixPath(source_path).parent / link.target))
        if relative in index.by_path:
            return index.by_path[relative], ""

    lookups = (
        (index.by_basename.get(wanted), "basename"),
        (index.by_alias.get(wanted), "alias"),
    )
    for candidates, label in lookups:
        if not candidates:
            continue
        if len(candidates) == 1:
            return candidates[0], ""
        return None, f"{label} matches {len(candidates)} documents ({', '.join(candidates)})"

    return None, "no document matches"


def links_to_a_non_document(root: Path | None, source_path: str, target: str) -> bool:
    """Whether an unresolved link points at something that exists but is not indexed.

    `[LICENSE](LICENSE)`, `[the template](.github/PULL_REQUEST_TEMPLATE.md)`, and a
    link into a directory the corpus excludes are not broken links: the file is
    right there, it simply is not part of the graph, so no edge can exist and the
    author did nothing wrong. Warning about them buried this repository's own
    builds under ~150 lines of noise and taught the reader to skip warnings —
    which is the real cost, because the genuinely *unresolvable* ones matter
    (BUG-0013).

    The test is existence, not extension. A Markdown file the corpus excludes is
    as legitimately unlinked as a PNG; what still warns is a target that is not
    there at all, which is the broken link the graph exists to surface.
    """
    if root is None:
        return False
    head, _ = _split_fragment(target)
    if not head:
        return False
    candidates = (root / Path(source_path).parent / head, root / head)
    return any(candidate.exists() for candidate in candidates)


EVIDENCE_FOLDER: Final = "evidence"
"""The folder that makes a link a citation.

Folder-derived, because the folder *is* the status (D-021) and the graph already
knows every document's path. Nothing else in the corpus has to change for a
citation to be typed as one — no new field, no store migration, no origin flag —
and a document moved out of `evidence/` stops being citable in exactly the way a
human moving it would expect.
"""


def _in_folder(path: str, folder: str) -> bool:
    return folder in PurePosixPath(path).parts


def edge_type(source_path: str, target_path: str) -> EdgeType:
    """Which edge a resolved wikilink asserts (spec 03 §6).

    A link *into* `knowledge/evidence/` from anywhere else is a **citation**: the
    evidence layer is the verbatim projection of acquired sources, so pointing a
    claim at it is the act D-020 requires of every synthesized statement and
    `mycelium verify` measures (roadmap 4.5). Everything else — including a link
    between two evidence documents, which is one projection referring to another
    rather than a claim resting on one — stays `links_to`.

    Note what this deliberately does *not* emit: the `derived_from` edge spec 03
    §6 pairs with `cites`. At document granularity it would be the deduplicated
    projection of the `cites` edges already here — the same assertion at lower
    resolution — and the distinction the spec actually wants, *synthesized* docs
    versus authored ones citing evidence, is not expressible until the graph's
    per-document state carries `origin` (ADR-0035).
    """
    if _in_folder(target_path, EVIDENCE_FOLDER) and not _in_folder(source_path, EVIDENCE_FOLDER):
        return EdgeType.CITES
    return EdgeType.LINKS_TO


def resolve_edges(
    links_by_path: Mapping[str, Sequence[LinkRef]],
    index: CorpusIndex,
    *,
    namespace: str = "default",
    root: Path | None = None,
) -> tuple[tuple[Edge, ...], tuple[str, ...]]:
    """Turn the corpus's link references into edges, plus warnings for the rest.

    Deterministic by construction: documents are visited in path order, links in
    document order, and identical assertions collapse to one edge because the
    edge id is a digest of the assertion (spec 03 §6).
    """
    edges: dict[Sha256Digest, Edge] = {}
    warnings: list[str] = []

    for source_path in sorted(links_by_path):
        for link in links_by_path[source_path]:
            if _is_external(link.target):
                continue
            target_path, reason = _resolve_target(index, source_path, link)
            if target_path is None:
                if links_to_a_non_document(root, source_path, link.target):
                    continue
                warnings.append(
                    f"{source_path}: unresolved {link.kind} [[{link.target}]] - {reason}"
                )
                continue

            reference = doc_ref(target_path)
            if link.fragment:
                slug = heading_slug(link.fragment)
                if slug in index.headings.get(target_path, frozenset()):
                    reference = section_ref(target_path, slug)
                else:
                    warnings.append(
                        f"{source_path}: {link.kind} [[{link.target}#{link.fragment}]] "
                        f"resolves to {target_path}, which has no heading '{link.fragment}'"
                    )

            provenance = EdgeProvenance(kind=link.kind, anchor=link.anchor or None)
            # Built through the alias: `from` is a Python keyword, so the record
            # names the field `from_` and JSON keeps the spec's spelling.
            edge = Edge.model_validate(
                {
                    "from": doc_ref(source_path),
                    "to": reference,
                    "type": edge_type(source_path, target_path),
                    "status": EdgeStatus.AUTHORED,
                    "provenance": provenance,
                    "namespace": namespace,
                }
            )
            edges[edge_identity(edge)] = edge

    ordered = sorted(
        edges.items(), key=lambda item: (item[1].from_, item[1].to, str(item[1].type), item[0])
    )
    return tuple(edge for _, edge in ordered), tuple(warnings)


@runtime_checkable
class GraphState(Protocol):
    """One document's contribution to the graph, as resolution needs it.

    Structural on purpose: :class:`~mycelium.store.base.DocState` satisfies it
    without this module importing the store, which keeps the dependency running
    one way (store → sdk, graph → sdk) and leaves the graph testable with plain
    objects.
    """

    @property
    def path(self) -> str: ...

    @property
    def links(self) -> tuple[Mapping[str, str], ...]: ...

    @property
    def aliases(self) -> tuple[str, ...]: ...

    @property
    def headings(self) -> tuple[str, ...]: ...


def resolve_graph(
    states: Sequence[GraphState], namespace: str = "default", root: Path | None = None
) -> tuple[tuple[Edge, ...], tuple[str, ...]]:
    """Resolve the whole corpus's authored links into edges, plus warnings.

    The one entry point a build and a rollback both use, so a restored snapshot
    reproduces the graph its manifest published rather than something similar.
    """
    index = CorpusIndex.build(
        (state.path for state in states),
        aliases={state.path: state.aliases for state in states},
        headings={state.path: state.headings for state in states},
    )
    return resolve_edges(
        {state.path: decode_links(state.links) for state in states},
        index,
        namespace=namespace,
        root=root,
    )


def edges_digest(edges: Sequence[Edge]) -> Sha256Digest:
    """The manifest's `edges` artifact digest (spec 03 §7).

    Folded from the edge records themselves rather than their ids: an id is a
    digest of the assertion, but `weight` and `status` are not part of it, and a
    corpus digest must move when anything published moves.
    """
    return digest_json([edge.model_dump(mode="json") for edge in edges])


def edge_identity(edge: Edge) -> Sha256Digest:
    """The spec 03 §2 edge id, computed from the record itself."""
    return edge_id(
        edge.from_,
        edge.to,
        str(edge.type),
        digest_json(edge.provenance.model_dump(mode="json")),
    )


def _is_external(target: str) -> bool:
    scheme, separator, _ = target.partition(":")
    return bool(separator) and scheme.casefold() in _EXTERNAL_SCHEMES


# ---------------------------------------------------------------------------
# Traversal
# ---------------------------------------------------------------------------


@runtime_checkable
class EdgeLookup(Protocol):
    """What :func:`neighbours` needs of a store: the edges touching one reference."""

    def edges_of(
        self, ref: str, types: Sequence[EdgeType] | None = None
    ) -> Sequence[tuple[Edge, str]]:
        """Edges incident to `ref`, each paired with ``"out"`` or ``"in"``."""
        ...


@dataclass(frozen=True, slots=True)
class Neighbour:
    """One node reached from the origin, and the edge that reached it."""

    ref: str
    edge: Edge
    direction: str
    """`out` when the origin asserts it, `in` when something asserts the origin."""
    depth: int

    def as_dict(self) -> dict[str, object]:
        return {
            "ref": self.ref,
            "type": str(self.edge.type),
            "status": str(self.edge.status),
            "weight": self.edge.weight,
            "direction": self.direction,
            "depth": self.depth,
            "provenance": self.edge.provenance.model_dump(mode="json"),
        }


def neighbours(
    lookup: EdgeLookup,
    origin: str,
    *,
    types: Sequence[EdgeType] | None = None,
    depth: int = 1,
    limit: int = 20,
) -> tuple[Neighbour, ...]:
    """Breadth-first neighbourhood of `origin`, nearest first.

    Both directions are walked and each result says which it came from: "what
    does this cite" and "what cites this" are different questions, and a graph
    tool that answers only the first is half a tool.

    Bounded twice — by `depth` (capped at :data:`MAX_DEPTH`) and by `limit` — and
    breadth-first, so the budget is spent on the closest neighbours rather than
    on whichever branch the walk entered first.
    """
    if depth < 1:
        return ()
    depth = min(depth, MAX_DEPTH)

    seen = {origin}
    found: list[Neighbour] = []
    frontier: deque[tuple[str, int]] = deque([(origin, 0)])

    while frontier and len(found) < limit:
        ref, distance = frontier.popleft()
        if distance >= depth:
            continue
        for edge, direction in lookup.edges_of(ref, types):
            other = edge.to if direction == "out" else edge.from_
            if other in seen:
                continue
            seen.add(other)
            found.append(Neighbour(ref=other, edge=edge, direction=direction, depth=distance + 1))
            if len(found) >= limit:
                break
            frontier.append((other, distance + 1))
    return tuple(found)
