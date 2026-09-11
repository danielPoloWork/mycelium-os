# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The authored link graph: extraction, resolution, traversal (D-014, ADR-0018).

Spec 03 §6 makes edges **facts, not entities**: an edge's identity is the digest
of ``(from, to, type, provenance_digest)``, so the same assertion observed twice
is the same edge and re-deriving it is how a rebuild converges. Everything this
module derives is ``authored``: what a human wrote (wikilinks, embeds, Markdown
links), what a document's own structure says (a section belongs to its
document), and what its frontmatter declares (a synthesized document was written
from its evidence). Mining assertions out of prose or code is an *extractor's*
job — :mod:`mycelium.symbols` derives ``defines`` and ``references`` and marks
them ``extracted`` — and spec 03 §6's status discipline exists to keep the two
apart: extracted edges never gain authored status silently.

Four of the eight types in D-014's vocabulary are emitted here (``links_to``,
``cites``, ``part_of``, ``derived_from``), two by the symbol stage, and
``mentions`` waits for the entity extractor it belongs to (roadmap 5.4). Every
weight is 1.0: the field is served because spec 05 §3.3 promises it, and what
the values should be is a ranking question for the ablation that will use them
(roadmap 5.3, ADR-0074).

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

**An ingested document is a special case in both directions** (roadmap 5.7,
ADR-0079). Its links name the *source* tree — `../../reference/settings.md`, a
path that meant something where the file was acquired — while the projection of
it landed in a flat `knowledge/evidence/` tree under a slugified name. So they
are resolved through the source URI each projected document carries: join the
link to the source's own directory, drop the extension, and look the result up
among the sources the corpus was built from. And the edges that come out are
**`extracted`, never `authored`**, because nobody wrote them here — a parser
found them in content D-017 calls untrusted. That is spec 03 §6's assertion
discipline doing the exact job it was written for, and it closes a hole the
threat model claimed was already closed: reference syntax cannot survive as a
*node* through projection, but `[[api]]` sitting in a PDF's prose survives as
*text*, and the compiler re-parsed it into an authored edge.
"""

from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
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
    ProvenanceOrigin,
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
    "anchor_of",
    "decode_links",
    "edge_identity",
    "edge_type",
    "edges_digest",
    "encode_links",
    "extract_links",
    "merge_edges",
    "neighbours",
    "nodes_of_anchor",
    "resolve_edges",
    "resolve_graph",
    "section_ref",
    "source_stem",
    "split_section_ref",
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


def nodes_of_anchor(anchor: str) -> tuple[str, ...]:
    """The graph nodes a chunk anchor belongs to: its section, then its document.

    A chunk is not a node — chunk boundaries are a packing decision and the graph
    refuses to key on them (ADR-0018) — so a retrieval candidate reaches the
    graph through the two nodes that contain it. Section first, because it is the
    more specific of the two, and a walk that starts there reaches the document
    anyway through the containment edge (`part_of`, ADR-0074).

    A chunk in a document's preamble has no heading, and then the document is the
    only node it has.
    """
    path, _, rest = anchor.partition("#")
    if not path:
        return ()
    slug = rest.rsplit("/", 1)[0] if rest else ""
    if not slug:
        return (doc_ref(path),)
    return (section_ref(path, slug), doc_ref(path))


def split_section_ref(reference: str) -> tuple[str, str] | None:
    """``doc:a.md#retries`` → ``("doc:a.md", "retries")``; ``None`` for anything else.

    The inverse of :func:`section_ref`, and the test for *is this node a section*
    that ``part_of`` resolution needs. A document reference has no fragment and a
    ``sym:`` node has no document, so both answer ``None``.
    """
    if not reference.startswith("doc:"):
        return None
    document, separator, slug = reference.partition("#")
    if not separator or not slug:
        return None
    return document, slug


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


def anchor_of(node: KirNode, by_id: Mapping[str, KirNode], anchors: Mapping[str, str]) -> str:
    """The chunk anchor covering `node`, walking up to its enclosing block.

    A reference is usually listed among its chunk's own KIR nodes; when it is not
    — a link directly under a heading, whose text belongs to the heading — the
    parent chain finds the block that was chunked. Public because the symbol
    stage (roadmap 5.1) asks the same question of a fence or a heading.
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
                anchor=anchor_of(node, by_id, anchors),
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
    by_source: Mapping[str, str] = field(default_factory=dict)
    """Source stem path -> the document projected from it (roadmap 5.7).

    Keyed *without* a file extension, because the two ends rarely agree on one: a
    page rendered to HTML keeps the `.md` hrefs it was written with, and the
    source beside it is `.html`. The stem is the part that identifies the
    document in both trees."""

    @classmethod
    def build(
        cls,
        paths: Iterable[str],
        *,
        aliases: Mapping[str, Sequence[str]] | None = None,
        headings: Mapping[str, Iterable[str]] | None = None,
        sources: Mapping[str, str] | None = None,
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

        by_source: dict[str, str] = {}
        for path, uri in sorted((sources or {}).items()):
            stem = source_stem(uri)
            # First writer wins, in path order, so a corpus that somehow projected
            # one source twice still resolves deterministically.
            if stem and stem not in by_source:
                by_source[stem] = path

        return cls(
            by_path=by_path,
            by_basename={key: tuple(value) for key, value in by_basename.items()},
            by_alias={key: tuple(value) for key, value in by_alias.items()},
            headings={path: frozenset(slugs) for path, slugs in sorted((headings or {}).items())},
            by_source=by_source,
        )


def _normalise(value: str) -> str:
    """Compare links case-insensitively, without a `.md` suffix, in POSIX form."""
    text = value.strip().replace("\\", "/").casefold()
    return text[:-3] if text.endswith(".md") else text


_LOCAL_SCHEME: Final = "file:"
"""The only source URI shape a link can be resolved against.

A source acquired over HTTP has a directory too, in principle, but resolving a
relative link against it would produce a URL, and a URL is not a node in this
graph (ADR-0018 refuses external targets for exactly that reason). So a remote
source contributes no source-tree resolution and its links fall through to the
ordinary rules."""


def source_stem(uri: str) -> str:
    """A local source URI as a normalised, extension-free path — or ``""``.

    The comparison key for :attr:`CorpusIndex.by_source`. Empty for anything this
    cannot place in a tree: a remote URI, or no URI at all.
    """
    if not uri:
        return ""
    path = uri.removeprefix(_LOCAL_SCHEME)
    if ":" in path.split("/", 1)[0]:
        return ""  # some other scheme; a relative Windows drive letter is not one
    return _strip_suffix(_flatten(path))


def _flatten(path: str) -> str:
    """POSIX form with `.` and `..` segments applied, case-folded.

    Resolved textually and never against the filesystem: the source tree may not
    be present on the machine doing the build — an evidence document is compiled
    from tier 2 alone — and a rebuild must reach the same answer either way.
    """
    parts: list[str] = []
    for part in path.replace("\\", "/").casefold().split("/"):
        if part == "..":
            if parts:
                parts.pop()
        elif part not in ("", "."):
            parts.append(part)
    return "/".join(parts)


def _strip_suffix(path: str) -> str:
    """Drop a trailing file extension, leaving the identifying stem."""
    head, separator, tail = path.rpartition(".")
    return head if separator and "/" not in tail else path


def _resolve_target(
    index: CorpusIndex, source_path: str, link: LinkRef, source_uri: str = ""
) -> tuple[str | None, str]:
    """Resolve one link's document. Returns ``(path, reason)``; `reason` explains a miss.

    The order is spec 03 §3.1's: an exact path wins, then — for a reference
    written inside a document, a Markdown link or a `supersedes:` target — a path
    relative to that document, then a unique basename, then a unique alias.
    Ambiguity is a miss with its own message — silently picking one of two
    documents is how a knowledge graph starts lying.

    `source_uri` inserts one step before the weaker heuristics, and only for a
    document that has one. A link inside an ingested document was written in the
    source tree's coordinates, so it is joined to the source's own directory and
    looked up among the corpus's sources (roadmap 5.7). It sits above `basename`
    because it is a *path* match — precise — and below the corpus's own paths
    because a link that already names a document in this corpus means what it
    says.
    """
    if not link.target:
        return source_path, ""  # a bare `#fragment` points inside this document

    wanted = _normalise(link.target)
    if wanted in index.by_path:
        return index.by_path[wanted], ""

    # A relative path *written inside* a document resolves against that
    # document's directory — true of a Markdown link, and equally true of a
    # `supersedes:` target, which an author writes as the filename they would
    # have linked (roadmap 5.10). Doing it here rather than in the caller keeps
    # one resolution order for one syntax.
    if link.kind in {"markdown_link", "frontmatter"}:
        relative = _normalise(str(PurePosixPath(source_path).parent / link.target))
        if relative in index.by_path:
            return index.by_path[relative], ""

    stem = source_stem(source_uri)
    if stem:
        head, _, _ = stem.rpartition("/")
        wanted_source = _strip_suffix(_flatten(f"{head}/{link.target}" if head else link.target))
        if wanted_source in index.by_source:
            return index.by_source[wanted_source], ""

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


def _supersedes_edges(
    declared: Mapping[str, Sequence[str]],
    index: CorpusIndex,
    *,
    namespace: str,
    origins: Mapping[str, str],
) -> tuple[tuple[Edge, ...], tuple[str, ...]]:
    """The `supersedes` edges a corpus's frontmatter declares (roadmap 5.10).

    Resolved exactly as a wikilink is, through the same :class:`CorpusIndex` and
    the same rules (spec 03 §3.1): basename if unique, else path, aliases
    honoured, and an ambiguous name naming its candidates rather than guessing
    one of them. Reusing the index is the point — a corpus where `[[api]]`
    resolves and `supersedes: [api]` does not would be a second resolution rule
    for one syntax.

    **Unresolvable is a warning**, unlike an unresolvable symbol use (ADR-0074).
    The difference is what the author asserted: a call site asserts nothing about
    the corpus, while `supersedes:` asserts that a particular document exists and
    has been replaced — the same claim a wikilink makes, so it gets the same
    warning ADR-0018 gave that claim.

    **A self-reference is dropped with a warning.** A document cannot replace
    itself, and the id would collapse onto a node pointing at its own origin,
    which every traversal would then report as a neighbour of itself.

    The status follows the document, not the key: an *ingested* document carrying
    `supersedes:` in its projected frontmatter is asserting nothing anybody here
    wrote, so its edge is `extracted` (:func:`_status_of`, ADR-0079's rule).
    """
    edges: dict[Sha256Digest, Edge] = {}
    warnings: list[str] = []
    for source_path in sorted(declared):
        status = _status_of(origins.get(source_path, ""))
        for target in declared[source_path]:
            if _is_external(target):
                warnings.append(
                    f"{source_path}: supersedes '{target}' is an external reference; "
                    "the relation is between documents in this corpus"
                )
                continue
            link = LinkRef(kind="frontmatter", target=target, fragment="", anchor="")
            target_path, reason = _resolve_target(index, source_path, link, "")
            if target_path is None:
                warnings.append(f"{source_path}: unresolved supersedes '{target}' - {reason}")
                continue
            if target_path == source_path:
                warnings.append(f"{source_path}: supersedes itself; the declaration is dropped")
                continue
            edge = Edge.model_validate(
                {
                    "from": doc_ref(source_path),
                    "to": doc_ref(target_path),
                    "type": EdgeType.SUPERSEDES,
                    "status": status,
                    "provenance": EdgeProvenance(kind="frontmatter"),
                    "namespace": namespace,
                }
            )
            edges[edge_identity(edge)] = edge
    return tuple(edges[key] for key in sorted(edges)), tuple(warnings)


def resolve_edges(
    links_by_path: Mapping[str, Sequence[LinkRef]],
    index: CorpusIndex,
    *,
    namespace: str = "default",
    root: Path | None = None,
    origins: Mapping[str, str] | None = None,
    sources: Mapping[str, str] | None = None,
    supersedes: Mapping[str, Sequence[str]] | None = None,
) -> tuple[tuple[Edge, ...], tuple[str, ...]]:
    """Turn the corpus's link references into edges, plus warnings for the rest.

    Deterministic by construction: documents are visited in path order, links in
    document order, and identical assertions collapse to one edge because the
    edge id is a digest of the assertion (spec 03 §6).

    `origins` maps a document's path to its `provenance.origin`, and it does two
    jobs: it makes ``derived_from`` expressible (see :func:`_derived_from_edges`),
    and it decides an edge's **status**. A link found in an *ingested* document is
    `extracted` — a parser found it in untrusted content — while a link in a
    document a person wrote is `authored`. `sources` maps a document's path to
    its source URI, which is what an ingested document's links resolve against
    (roadmap 5.7, ADR-0079).
    """
    edges: dict[Sha256Digest, Edge] = {}
    warnings: list[str] = []

    for source_path in sorted(links_by_path):
        source_uri = (sources or {}).get(source_path, "")
        status = _status_of((origins or {}).get(source_path, ""))
        for link in links_by_path[source_path]:
            if _is_external(link.target):
                continue
            target_path, reason = _resolve_target(index, source_path, link, source_uri)
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
                    "status": status,
                    "provenance": provenance,
                    "namespace": namespace,
                }
            )
            edges[edge_identity(edge)] = edge

    # Frontmatter-declared supersession, resolved through the same index and the
    # same rules as a wikilink (roadmap 5.10, ADR-0082). It runs before the
    # derived types so `part_of` sees every node the corpus asserts.
    declared, declared_warnings = _supersedes_edges(
        supersedes or {}, index, namespace=namespace, origins=origins or {}
    )
    for edge in declared:
        edges[edge_identity(edge)] = edge
    warnings.extend(declared_warnings)

    for edge in (
        *_part_of_edges(edges.values(), namespace),
        *_derived_from_edges(edges.values(), origins or {}, namespace),
    ):
        edges[edge_identity(edge)] = edge

    ordered = sorted(
        edges.items(), key=lambda item: (item[1].from_, item[1].to, str(item[1].type), item[0])
    )
    return tuple(edge for _, edge in ordered), tuple(warnings)


def _status_of(origin: str) -> EdgeStatus:
    """Whether a document's links are assertions or findings (spec 03 §6).

    A human wrote the links in an authored document, and the synthesis lane's
    citations are written under a contract that refuses the document if they do
    not resolve (D-020) — both are `authored`. An ingested document was *acquired*:
    its text is untrusted by D-017, and any link syntax in it was put there by
    whoever wrote the source, not by anyone here. That is `extracted`, and the
    distinction is the one thing spec 03 §6 insists on — "extracted edges never
    gain authored status silently" (roadmap 5.7, ADR-0079).
    """
    if origin == ProvenanceOrigin.INGESTED.value:
        return EdgeStatus.EXTRACTED
    return EdgeStatus.AUTHORED


def _part_of_edges(edges: Iterable[Edge], namespace: str) -> tuple[Edge, ...]:
    """``part_of`` from every section this graph already names to its document.

    A heading link (`[[doc#Heading]]`) resolves to a *section* reference, which
    is finer than a document and coarser than a chunk (ADR-0018) — and until this
    item that node was a **dead end**: nothing connected it to the document it
    sits in, so a walk that reached a section could go no further, while a walk
    that reached a whole document carried on through its links. On the vendored
    uv corpus that is 290 of 657 links, 226 distinct sections (ADR-0074).

    Emitted only for sections some edge already names, which is what keeps the
    node set unchanged: one `part_of` per heading in the corpus would add
    thousands of edges nobody asked about and would crowd every neighbour query
    that has a limit. The containment is structural, so it is `authored` — the
    author wrote the heading and the link, and nothing here was inferred.
    """
    documents = {edge.from_ for edge in edges} | {
        split_section_ref(edge.to)[0]  # type: ignore[index]
        for edge in edges
        if split_section_ref(edge.to) is not None
    }
    sections: set[str] = set()
    for edge in edges:
        for endpoint in (edge.from_, edge.to):
            parts = split_section_ref(endpoint)
            if parts is not None and parts[0] in documents:
                sections.add(endpoint)

    return tuple(
        Edge.model_validate(
            {
                "from": section,
                "to": split_section_ref(section)[0],  # type: ignore[index]
                "type": EdgeType.PART_OF,
                "status": EdgeStatus.AUTHORED,
                "provenance": EdgeProvenance(kind="heading"),
                "namespace": namespace,
            }
        )
        for section in sorted(sections)
    )


def _derived_from_edges(
    edges: Iterable[Edge], origins: Mapping[str, str], namespace: str
) -> tuple[Edge, ...]:
    """``derived_from`` from a synthesized document to each document it cites.

    ADR-0018 deferred this type with a precise reason: at document granularity it
    was *"the deduplicated projection of the `cites` edges already here — the same
    assertion at lower resolution"*, and the distinction spec 03 §6 actually
    wants — a synthesized document versus an authored one citing evidence — was
    not expressible until the graph's per-document state carried `origin`. It
    does now (roadmap 5.2), so the type says what it was meant to say: **this
    document was written from that one**, which is a fact about the document, not
    about any one of its claims.

    `authored`, because it is derived from frontmatter the ingest lane wrote
    (spec 03 §6 counts frontmatter as authored) — and orthogonal to whether the
    prose has been checked, which `verification_status` carries per document.
    """
    synthesized = {
        doc_ref(path) for path, origin in origins.items() if origin == ProvenanceOrigin.SYNTHESIZED
    }
    if not synthesized:
        return ()

    targets: dict[str, set[str]] = {}
    for edge in edges:
        if edge.type is not EdgeType.CITES or edge.from_ not in synthesized:
            continue
        parts = split_section_ref(edge.to)
        targets.setdefault(edge.from_, set()).add(parts[0] if parts is not None else edge.to)

    return tuple(
        Edge.model_validate(
            {
                "from": source,
                "to": target,
                "type": EdgeType.DERIVED_FROM,
                "status": EdgeStatus.AUTHORED,
                "provenance": EdgeProvenance(kind="frontmatter"),
                "namespace": namespace,
            }
        )
        for source in sorted(targets)
        for target in sorted(targets[source])
    )


def merge_edges(*groups: Sequence[Edge]) -> tuple[Edge, ...]:
    """Every edge from every group, deduplicated by identity and ordered.

    The graph is published whole and its digest is folded from the record list
    (:func:`edges_digest`), so the *order* of two independently-derived groups —
    the authored ones here, the extracted ones from the symbol stage — has to be
    settled in one place rather than by whichever caller concatenates them.
    """
    edges = {edge_identity(edge): edge for group in groups for edge in group}
    ordered = sorted(
        edges.items(), key=lambda item: (item[1].from_, item[1].to, str(item[1].type), item[0])
    )
    return tuple(edge for _, edge in ordered)


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

    @property
    def origin(self) -> str: ...

    @property
    def source(self) -> str: ...

    @property
    def supersedes(self) -> tuple[str, ...]: ...


def resolve_graph(
    states: Sequence[GraphState], namespace: str = "default", root: Path | None = None
) -> tuple[tuple[Edge, ...], tuple[str, ...]]:
    """Resolve the whole corpus's authored links into edges, plus warnings.

    The one entry point a build and a rollback both use, so a restored snapshot
    reproduces the graph its manifest published rather than something similar.
    """
    sources = {state.path: state.source for state in states if state.source}
    supersedes = {
        state.path: state.supersedes for state in states if getattr(state, "supersedes", ())
    }
    index = CorpusIndex.build(
        (state.path for state in states),
        aliases={state.path: state.aliases for state in states},
        headings={state.path: state.headings for state in states},
        sources=sources,
    )
    return resolve_edges(
        {state.path: decode_links(state.links) for state in states},
        index,
        namespace=namespace,
        root=root,
        origins={state.path: state.origin for state in states},
        sources=sources,
        supersedes=supersedes,
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
