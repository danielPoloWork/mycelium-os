# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Resolution: the corpus's symbol references -> the `symbols` table (roadmap 5.1).

Global, and run on every build, for the reason ADR-0018 gave for edges: a
symbol is one row keyed by its id, and two documents may each define it. Which
one is ``defined_in`` and which anchors are ``doc_refs`` is a question about
the corpus, not about either document — so the per-document references live in
``doc_state`` and this pass reads them all, in path order, every time. It is
dictionary work over a few thousand references; the parsing that produced them
stayed cached with the documents.

The same pass derives the two typed edges the symbol table makes possible
(roadmap 5.2, ADR-0074): ``defines`` from a document to what it defines, and
``references`` from a document to what it uses. Both are ``extracted`` — a
grammar found them, nobody wrote them down — which is the first time spec 03
§6's status discipline has had anything to discipline.
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import Protocol, runtime_checkable

from mycelium.sdk.identity import digest_json, doc_ref, symbol_id
from mycelium.sdk.types import Edge, EdgeProvenance, EdgeStatus, EdgeType, Sha256Digest, Symbol
from mycelium.symbols.code import EXTRA
from mycelium.symbols.extract import SymbolRef, decode_symbols

__all__ = [
    "SymbolState",
    "describe_gaps",
    "resolve_symbols",
    "symbol_edges",
    "symbols_digest",
]


@runtime_checkable
class SymbolState(Protocol):
    """One document's contribution to the symbol table, as resolution needs it.

    Structural, like :class:`~mycelium.graph.GraphState`: the store's ``DocState``
    satisfies it without this module importing the store.
    """

    @property
    def path(self) -> str: ...

    @property
    def symbols(self) -> tuple[Mapping[str, object], ...]: ...

    @property
    def symbol_uses(self) -> tuple[Mapping[str, object], ...]: ...

    @property
    def symbol_gaps(self) -> tuple[str, ...]: ...


def resolve_symbols(
    states: Sequence[SymbolState], namespace: str = "default"
) -> tuple[Symbol, ...]:
    """Fold every document's references into one record per symbol id.

    Deterministic by construction: documents are visited in path order and
    references in line order, so the site ``defined_in`` names is the same on
    every build of the same corpus, and the records come out sorted by id.
    ``doc_refs`` collects every chunk that defines the symbol, across documents.

    **``defined_in`` is the most *direct* naming site**: one whose syntax makes
    the symbol its own subject — a fence definition, a definition-list term, or a
    heading that *is* the name — before one that frames it in a phrase, and path
    order between equals. That ordering is what makes roadmap 5.19's widening
    purely additive: reading ``## The pyproject.toml`` as well as
    ``### pyproject.toml`` adds a site to ``doc_refs`` and cannot move what
    ``defined_in`` already said.

    **It is deliberately not "where the thing is documented", and that is a
    refusal with measurements behind it** (ADR-0091). On uv's four sites for
    ``pyproject.toml`` every rankable signal disagrees with every other and with
    the judge: most prose picks the guide's tour entry (247 tokens), most
    mentions picks ``docs/pip/dependencies.md`` (six), and the section a judged
    case grades relevant — ``docs/concepts/projects/layout.md`` — is the
    *smallest* of the four and mentions the name *least*. Plain path order, tried
    on the widened table, moved three records: one onto that judged section and
    two onto pages that document nothing (a Renovate integration guide, for
    ``uv.lock``). Which page of a corpus is its reference and which is its tour
    is an editorial fact about the whole corpus, and a stage that sees one
    document at a time cannot read it. So no field here claims to, and
    ``doc_refs`` carries every site instead — where a reader can weigh them and
    where the symbol leg ranks them by BM25 anyway, which is why *ordering* them
    would be inert even if an order could be justified.
    """
    sites: dict[str, list[tuple[str, SymbolRef]]] = {}
    for state in sorted(states, key=lambda item: item.path):
        references = sorted(decode_symbols(state.symbols), key=lambda ref: (ref.line, ref.name))
        for reference in references:
            identity = symbol_id(reference.language, reference.name)
            sites.setdefault(identity, []).append((state.path, reference))

    resolved: list[Symbol] = []
    for identity in sorted(sites):
        path, first = min(
            sites[identity], key=lambda site: (not site[1].direct, site[0], site[1].line)
        )
        defined_in = f"{path}#L{first.line}" if first.line > 0 else (first.anchor or path)
        doc_refs = tuple(
            sorted({reference.anchor for _, reference in sites[identity] if reference.anchor})
        )
        resolved.append(
            Symbol(
                symbol=identity,
                kind=first.kind,
                defined_in=defined_in,
                doc_refs=doc_refs,
                namespace=namespace,
            )
        )
    return tuple(resolved)


def symbol_edges(
    states: Sequence[SymbolState], symbols: Sequence[Symbol], namespace: str = "default"
) -> tuple[Edge, ...]:
    """The `defines` and `references` edges the resolved symbol table supports.

    Both point at ``sym:`` nodes rather than at documents, which is what makes
    the two questions spec 03 §6 pairs answerable in one hop each: *what defines
    this* is the `defines` edges into the symbol, *what uses it* the `references`
    edges into it. A document-to-document path exists at depth two, through the
    symbol, which is the shape graph expansion can walk (roadmap 5.3).

    **A use resolves against the corpus or produces nothing.** The name a fence
    captured is unqualified (`delay`, not `RetryPolicy.delay`), so it is matched
    first as a whole symbol name and then, failing that, against the last segment
    of every symbol *in the same language* — spec 03 §3.1's wikilink rule applied
    to symbols, ambiguity included: two candidates yield no edge. A name nothing
    defines yields no edge either, and that is what keeps the type honest rather
    than noisy: a documentation corpus calls `print`, `json` and `getLogger` far
    more often than it defines anything, and an edge to a symbol the corpus does
    not hold would be a neighbour nothing can fetch — ADR-0018's reason for
    refusing external URLs.

    Unlike an unresolvable wikilink, an unresolvable use is **not** a warning: a
    wikilink asserts that a document exists, and a call site asserts nothing at
    all. Warning on every library call would bury the manifest.
    """
    from mycelium.graph import edge_identity

    by_id = {symbol.symbol: symbol for symbol in symbols}
    by_tail: dict[tuple[str, str], set[str]] = {}
    for identity in by_id:
        _, language, name = identity.split(":", 2)
        by_tail.setdefault((language, name.rsplit(".", 1)[-1]), set()).add(identity)

    definers: dict[str, set[str]] = {}
    for state in states:
        for reference in decode_symbols(state.symbols):
            definers.setdefault(symbol_id(reference.language, reference.name), set()).add(
                state.path
            )

    edges: dict[Sha256Digest, Edge] = {}

    def put(source: str, target: str, edge_type: EdgeType, reference: SymbolRef) -> None:
        edge = Edge.model_validate(
            {
                "from": source,
                "to": target,
                "type": edge_type,
                # A grammar found this, not a human (spec 03 §6): extracted never
                # becomes authored silently, and until this item nothing in the
                # graph was anything but authored.
                "status": EdgeStatus.EXTRACTED,
                "provenance": EdgeProvenance(
                    kind=reference.source, anchor=reference.anchor or None
                ),
                "namespace": namespace,
            }
        )
        edges[edge_identity(edge)] = edge

    for state in sorted(states, key=lambda item: item.path):
        source = doc_ref(state.path)
        for reference in sorted(
            decode_symbols(state.symbols), key=lambda ref: (ref.line, ref.name)
        ):
            identity = symbol_id(reference.language, reference.name)
            if identity in by_id:
                put(source, identity, EdgeType.DEFINES, reference)

        for use in sorted(decode_symbols(state.symbol_uses), key=lambda ref: (ref.line, ref.name)):
            identity_or_none = _resolve_use(use, by_id, by_tail)
            if identity_or_none is None:
                continue
            if state.path in definers.get(identity_or_none, set()):
                # A document that defines a symbol is not also a *user* of it:
                # the `defines` edge already says so, at a stronger type.
                continue
            put(source, identity_or_none, EdgeType.REFERENCES, use)

    ordered = sorted(
        edges.items(), key=lambda item: (item[1].from_, item[1].to, str(item[1].type), item[0])
    )
    return tuple(edge for _, edge in ordered)


def _resolve_use(
    use: SymbolRef, by_id: Mapping[str, Symbol], by_tail: Mapping[tuple[str, str], set[str]]
) -> str | None:
    """Which symbol a captured name means, or ``None`` when the corpus cannot say."""
    exact = symbol_id(use.language, use.name)
    if exact in by_id:
        return exact
    candidates = by_tail.get((use.language, use.name.rsplit(".", 1)[-1]))
    if candidates is not None and len(candidates) == 1:
        return next(iter(candidates))
    return None


def symbols_digest(symbols: Sequence[Symbol]) -> Sha256Digest:
    """The manifest's `symbols` artifact digest (spec 03 §7), over the records."""
    return digest_json([symbol.model_dump(mode="json") for symbol in symbols])


def describe_gaps(states: Iterable[SymbolState]) -> str | None:
    """Why the snapshot's `symbols` are incomplete, or ``None`` when they are not.

    One sentence for the manifest's `degraded` reason and the operator: how many
    documents hold fences in which languages that no installed grammar could
    read, and what to install. Counted from the documents rather than from the
    environment, so a corpus with no such fences is never called degraded by a
    missing extra it does not need.
    """
    affected = [state for state in states if state.symbol_gaps]
    if not affected:
        return None
    languages = sorted({language for state in affected for language in state.symbol_gaps})
    return (
        f"code symbols not extracted: {len(affected)} document(s) hold "
        f"{', '.join(languages)} fences and no installed grammar reads them; "
        f"install {EXTRA} and rebuild"
    )
