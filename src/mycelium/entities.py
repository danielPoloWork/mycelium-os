# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The optional entity stage: declared names, and where the corpus names them.

Spec 02 §4.1 draws ``extract`` producing *symbols, links, entities°*, where the
degree sign marks the optional one, and spec 03 §6 gives the record its shape and
one instruction: *"optional stage, off by default in v1 — same status
discipline"*. This module is that stage (roadmap 5.4, ADR-0076).

**An entity is a name the corpus declares, never one guessed from its prose.**
That is the whole design, and it was chosen from a measurement rather than from
taste. The Mycelium Markdown Profile (spec 03 §3.1) has exactly three authored
ways to name a thing that is not a document and not a code symbol, and all three
are already parsed:

``tags``
    Frontmatter ``tags`` and inline ``#tag`` — a label a human attached. Kind
    ``tag``.
``aliases``
    Frontmatter ``aliases`` — *this document is also known as* — which names the
    thing the document is about and gives it its other names. Kind ``topic``.

A fourth was available and is **refused**: matching document *titles* in prose.
Measured over the three corpora the evaluation runs on (2026-09-10), titles
produce 227, 197 and 163 prose matches, and the most frequent are ``README``
(42), ``Documentation`` (41), ``Changelog`` (28), ``Projects`` (23) and ``Tools``
(21) — ordinary words that are not references to a document. An entity table
built from them would be mostly wrong, and wrong in a way that reads as coverage.

Mentions follow ADR-0074's rule for symbol uses, for the same reason: **a mention
resolves against the declared vocabulary or produces nothing.** No name enters
the graph because prose looked promising. That is D-014's anti-ontology-sprawl
valve (F-9) applied to the one stage most likely to breach it, and it is why the
formal ontology and the entity acceptance workflow can stay deferred (spec 06 §3)
without this stage becoming their unbudgeted first draft.

**Declaration is per document; resolution is global** — ADR-0018's seam, cut a
third time. A document's declarations are cached in ``doc_state`` and cost
nothing to keep, so the stage's flag gates *publication* rather than extraction
and turning it on needs no recompile. Resolution needs the corpus: one entity is
one row however many documents declare it, and a mention can only be found once
every declaration is known.
"""

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Protocol, runtime_checkable

from mycelium.graph import anchor_of, edge_identity
from mycelium.sdk.identity import derived_ulid, digest_json, doc_ref, entity_ref, heading_slug
from mycelium.sdk.types import (
    Chunk,
    ChunkKind,
    Edge,
    EdgeProvenance,
    EdgeStatus,
    EdgeType,
    Entity,
    KirDocument,
    NodeKind,
    ProvenanceOrigin,
    Sha256Digest,
)

__all__ = [
    "ALIAS",
    "FRONTMATTER_TAG",
    "INLINE_TAG",
    "MIN_NAME_LENGTH",
    "PROSE",
    "TAG_KIND",
    "TOPIC_KIND",
    "DeclaringFrontmatter",
    "EntityDeclaration",
    "EntityState",
    "declare_document",
    "declare_entities",
    "decode_declarations",
    "encode_declarations",
    "entities_digest",
    "entity_mentions",
    "resolve_entities",
]

FRONTMATTER_TAG: Final = "frontmatter_tag"
"""A name declared by the ``tags`` frontmatter key."""

INLINE_TAG: Final = "inline_tag"
"""A name declared by an inline ``#tag`` in the document's body."""

ALIAS: Final = "alias"
"""A name declared by the ``aliases`` frontmatter key (D-022, Obsidian-standard)."""

PROSE: Final = "prose"
"""How a mention was found: the entity's name written in a passage. It becomes
the edge's ``provenance.kind``, so `mycelium neighbors` can say that the link is
an extracted mention and not something anybody wrote as a link."""

TAG_KIND: Final = "tag"
TOPIC_KIND: Final = "topic"

MIN_NAME_LENGTH: Final = 4
"""The shortest declared name that is searched for in prose.

Not a tuning knob, and deliberately not configurable: a declared name is still an
ordinary word, and below four characters the ordinary word wins — `api`, `uv`
and `ci` occur in prose constantly without naming the thing the tag names. The
entity itself is still minted at any length; only the *mention* scan has a floor,
so a short tag keeps its record and its `defines`-side truth without generating a
page of false edges (ADR-0076)."""


def _has_no_letter(name: str) -> bool:
    """Whether a tag has no letter in it, in *any* script.

    Measured across the three corpora: 85 inline tags, of which 84 are GitHub
    issue references (`#1`, `#313`, `#2252`). A tag that is a number names an
    issue in somebody else's tracker, not a thing in this corpus, so it declares
    nothing.

    `str.isalpha` rather than a Latin character class, and the difference is not
    theoretical: the first version of this test was ``[^A-Za-z]*`` and it threw
    away the multilingual fixture's own ``設計`` tag as though it were an issue
    number. The corpus is multilingual by decision (D-028) and the anchor
    slugger already keeps non-Latin scripts intact; a filter written in ASCII
    would have quietly made this stage Latin-only.
    """
    return not any(character.isalpha() for character in name)


@dataclass(frozen=True, slots=True)
class EntityDeclaration:
    """One authored declaration of a named thing, as a single document makes it."""

    slug: str
    """`heading_slug` of the surface name — the `ent:<slug>` identity."""
    name: str
    """The surface form, exactly as written."""
    kind: str
    """:data:`TAG_KIND` or :data:`TOPIC_KIND`."""
    source: str
    """:data:`FRONTMATTER_TAG`, :data:`INLINE_TAG` or :data:`ALIAS`."""
    anchor: str
    """The chunk an inline tag sits in; empty for a frontmatter declaration,
    which belongs to the document rather than to any passage of it."""

    def as_dict(self) -> dict[str, str]:
        return {
            "slug": self.slug,
            "name": self.name,
            "kind": self.kind,
            "source": self.source,
            "anchor": self.anchor,
        }


def encode_declarations(declarations: Sequence[EntityDeclaration]) -> list[dict[str, str]]:
    """The form `doc_state` stores, so resolution can run without re-parsing."""
    return [declaration.as_dict() for declaration in declarations]


def decode_declarations(raw: Iterable[Mapping[str, str]]) -> tuple[EntityDeclaration, ...]:
    return tuple(
        EntityDeclaration(
            slug=item["slug"],
            name=item["name"],
            kind=item["kind"],
            source=item["source"],
            anchor=item.get("anchor", ""),
        )
        for item in raw
    )


@runtime_checkable
class EntityState(Protocol):
    """One document's contribution to the entity vocabulary, as resolution needs it.

    Structural, like :class:`~mycelium.graph.GraphState` and
    :class:`~mycelium.symbols.SymbolState`: the store's ``DocState`` satisfies it
    without this module importing the store.
    """

    @property
    def path(self) -> str: ...

    @property
    def entities(self) -> tuple[Mapping[str, str], ...]: ...

    @property
    def origin(self) -> str: ...


# ---------------------------------------------------------------------------
# Declaration: one document's frontmatter and tags -> what it names
# ---------------------------------------------------------------------------


def declare_entities(
    *,
    tags: Sequence[str],
    aliases: Sequence[str],
    title: str,
    inline_tags: Sequence[tuple[str, str]] = (),
) -> tuple[EntityDeclaration, ...]:
    """Every entity one document declares, in a deterministic order.

    Pure and per-document, so the result caches with the document. `inline_tags`
    are ``(tag text, chunk anchor)`` pairs read from the KIR's ``tag_ref`` nodes;
    everything else comes from frontmatter.

    An ``aliases`` key declares a **topic**: the document says the thing it is
    about answers to other names, so the entity's name is the document's title
    and each alias is one of its names. A document with no aliases declares no
    topic — its title alone is not a declaration, which is this stage's central
    refusal.
    """
    found: list[EntityDeclaration] = []
    for tag in tags:
        declaration = _tag_declaration(tag, FRONTMATTER_TAG, "")
        if declaration is not None:
            found.append(declaration)
    for tag, anchor in inline_tags:
        declaration = _tag_declaration(tag, INLINE_TAG, anchor)
        if declaration is not None:
            found.append(declaration)
    topic = _slug_of(title) if aliases else None
    if topic is not None:
        # One entity, several names. The aliases take the *title's* slug rather
        # than one each, because that is what an alias is: `aliases: [Arch]` says
        # the thing this document is about answers to `Arch` too, not that there
        # is a second thing called `Arch`. Three names for one entity is exactly
        # the shape spec 03 §6 gives the record.
        for name in (title, *aliases):
            if name.strip():
                found.append(
                    EntityDeclaration(
                        slug=topic, name=name.strip(), kind=TOPIC_KIND, source=ALIAS, anchor=""
                    )
                )
    return tuple(found)


@runtime_checkable
class DeclaringFrontmatter(Protocol):
    """The two frontmatter keys that declare a name (spec 03 §3's contract).

    Structural so this module does not import the Markdown package:
    :class:`~mycelium.markdown.Frontmatter` satisfies it, and a test satisfies
    it with four lines.
    """

    @property
    def tags(self) -> tuple[str, ...]: ...

    @property
    def aliases(self) -> tuple[str, ...]: ...


def declare_document(
    kir: KirDocument,
    chunks: Sequence[Chunk],
    *,
    frontmatter: DeclaringFrontmatter,
    title: str,
) -> tuple[EntityDeclaration, ...]:
    """What one compiled document declares — the per-document half of the stage.

    Reads this document's frontmatter and its KIR's ``tag_ref`` nodes, and
    nothing about the corpus, so the result caches in ``doc_state`` beside the
    links and the symbols (ADR-0018's seam).
    """
    by_id = {node.id: node for node in kir.nodes}
    anchors = {node_id: chunk.anchor for chunk in chunks for node_id in chunk.kir_nodes}
    inline = [
        (node.text or "", anchor_of(node, by_id, anchors))
        for node in kir.nodes
        if node.kind is NodeKind.TAG_REF and node.text
    ]
    return declare_entities(
        tags=frontmatter.tags,
        aliases=frontmatter.aliases,
        title=title,
        inline_tags=inline,
    )


def _tag_declaration(tag: str, source: str, anchor: str) -> EntityDeclaration | None:
    name = tag.strip().lstrip("#").strip()
    if not name or _has_no_letter(name):
        return None
    slug = _slug_of(name)
    if slug is None:
        return None
    return EntityDeclaration(slug=slug, name=name, kind=TAG_KIND, source=source, anchor=anchor)


def _slug_of(name: str) -> str | None:
    """The `ent:` slug of a surface name, or ``None`` when it has none.

    A name with no alphanumeric character at all slugs to the empty-slug
    sentinel, which is a heading anchor's answer and not an identity; such a name
    declares nothing rather than declaring the sentinel.
    """
    slug = heading_slug(name.strip())
    return None if not slug or slug == heading_slug("") else slug


# ---------------------------------------------------------------------------
# Resolution: the corpus's declarations -> the `entities` table
# ---------------------------------------------------------------------------


def resolve_entities(
    states: Sequence[EntityState], namespace: str = "default"
) -> tuple[Entity, ...]:
    """Fold every document's declarations into one record per ``ent:<slug>``.

    Deterministic by construction: documents are visited in path order and
    declarations in document order, so the surface form that becomes ``name`` and
    the order of ``aliases`` and ``doc_refs`` are the same on every build of the
    same corpus, and the records come out sorted by slug.

    Two surface forms that slug alike are **one entity with two names** rather
    than two entities: `Event Bus` and `event-bus` are the same thing, and the
    forms that did not become the name are kept in ``aliases`` so nothing is
    lost and the collision is visible in the record.

    ``kind`` is ``topic`` when any document declared the slug through its
    ``aliases`` — a document saying what a thing *is* outranks a label attached
    to it — and ``tag`` otherwise.

    ``status`` follows **who declared it**. A human wrote the tags and aliases in
    an authored document, so those entities are ``authored``. An *ingested*
    document declared nothing: it was acquired, D-017 calls its content
    untrusted, and a `#production` sitting in a PDF's prose is a string a scan
    found — ``extracted``. An entity both kinds of document declare is
    ``authored``, because a human really did declare it; the ingested document
    only adds a `doc_ref`. That rule is spec 03 §6's, and roadmap 5.7 found it
    was not being applied: every entity was ``authored`` whatever declared it
    (ADR-0079).
    """
    names: dict[str, list[str]] = {}
    titles: dict[str, str] = {}
    kinds: dict[str, set[str]] = {}
    homes: dict[str, list[str]] = {}
    declared_by_hand: set[str] = set()
    for state in sorted(states, key=lambda item: item.path):
        authored = state.origin != ProvenanceOrigin.INGESTED.value
        for declaration in decode_declarations(state.entities):
            slug = declaration.slug
            surfaces = names.setdefault(slug, [])
            if declaration.name not in surfaces:
                surfaces.append(declaration.name)
            if declaration.kind == TOPIC_KIND:
                titles.setdefault(slug, declaration.name)
            kinds.setdefault(slug, set()).add(declaration.kind)
            if authored:
                declared_by_hand.add(slug)
            reference = doc_ref(state.path)
            if reference not in homes.setdefault(slug, []):
                homes[slug].append(reference)

    resolved: list[Entity] = []
    for slug in sorted(names):
        # A topic's own title is the display name when there is one — a document
        # saying what a thing is names it better than a label attached to it —
        # and every other surface form seen becomes an alias, in the order the
        # corpus declared them.
        surfaces = names[slug]
        display = titles.get(slug, surfaces[0])
        resolved.append(
            Entity(
                entity_id=derived_ulid(entity_ref(slug)),
                slug=slug,
                name=display,
                aliases=tuple(name for name in surfaces if name != display),
                kind=TOPIC_KIND if TOPIC_KIND in kinds[slug] else TAG_KIND,
                status=(EdgeStatus.AUTHORED if slug in declared_by_hand else EdgeStatus.EXTRACTED),
                doc_refs=tuple(homes[slug]),
                namespace=namespace,
            )
        )
    return tuple(resolved)


def entities_digest(entities: Sequence[Entity]) -> Sha256Digest:
    """The manifest's `entities` artifact digest (spec 03 §7), over the records."""
    return digest_json([entity.model_dump(mode="json") for entity in entities])


# ---------------------------------------------------------------------------
# Mentions: where the corpus names what it declared
# ---------------------------------------------------------------------------


def entity_mentions(
    entities: Sequence[Entity],
    passages: Iterable[tuple[str, Chunk]],
    namespace: str = "default",
) -> tuple[Edge, ...]:
    """The `mentions` edges: a document naming an entity it did not declare.

    The eighth and last of D-014's edge types, and the one ADR-0074 deferred to
    this stage rather than mining out of prose without a vocabulary to mine
    against. It runs from ``doc:<path>`` to ``ent:<slug>``, is ``extracted``
    (nobody wrote it down — a scan found it), and carries the chunk it was found
    in, so `mycelium neighbors` answers *what does this document talk about* and
    *what talks about this* on the same node in opposite directions.

    Four rules, each of which removes a class of false edge:

    - **A declarer is not a mentioner.** A document that tagged itself
      ``#architecture`` already says so through ``doc_refs``; the mention type is
      for the documents that talk about a thing *without* declaring it — the same
      rule ADR-0074 gave symbol uses.
    - **One edge per document and entity**, at its first occurrence. A passage
      naming the same thing nine times has said one thing nine times.
    - **Code passages are not prose.** A name inside a fence is a token in a
      program, and the symbol table already owns what fences say (ADR-0073).
    - **A name shorter than** :data:`MIN_NAME_LENGTH` **is not searched for.**

    Matching is case-insensitive on whole words, longest name first, so an entity
    whose name contains a shorter entity's name wins at that position. The word
    boundary is ``\\w``-based, which means a name inside an unbroken run of
    Chinese or Japanese characters does not match: those scripts do not separate
    words, and a substring hit there would be a coincidence rather than a mention.
    """
    by_name: dict[str, str] = {}
    for entity in entities:
        for surface in (entity.name, *entity.aliases):
            folded = surface.casefold()
            if len(folded) >= MIN_NAME_LENGTH:
                by_name.setdefault(folded, entity.slug)
    if not by_name:
        return ()

    declared: dict[str, frozenset[str]] = {
        entity.slug: frozenset(entity.doc_refs) for entity in entities
    }
    # One pass per passage rather than one per (passage, name): the alternation is
    # ordered longest-first so the longest name wins at any position.
    pattern = re.compile(
        r"(?<![\w-])("
        + "|".join(re.escape(name) for name in sorted(by_name, key=_longest))
        + r")(?![\w-])",
        re.IGNORECASE,
    )

    edges: dict[Sha256Digest, Edge] = {}
    seen: set[tuple[str, str]] = set()
    for path, chunk in passages:
        if chunk.kind is ChunkKind.CODE:
            continue
        source = doc_ref(path)
        for match in pattern.finditer(chunk.text):
            slug = by_name.get(match.group(1).casefold())
            if slug is None or (path, slug) in seen:
                continue
            if source in declared.get(slug, frozenset()):
                continue
            seen.add((path, slug))
            edge = Edge.model_validate(
                {
                    "from": source,
                    "to": entity_ref(slug),
                    "type": EdgeType.MENTIONS,
                    "status": EdgeStatus.EXTRACTED,
                    "provenance": EdgeProvenance(kind=PROSE, anchor=chunk.anchor),
                    "namespace": namespace,
                }
            )
            edges[edge_identity(edge)] = edge

    ordered = sorted(edges.items(), key=lambda item: (item[1].from_, item[1].to, item[0]))
    return tuple(edge for _, edge in ordered)


def _longest(name: str) -> tuple[int, str]:
    return (-len(name), name)
