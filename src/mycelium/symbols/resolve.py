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
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import Protocol, runtime_checkable

from mycelium.sdk.identity import digest_json, symbol_id
from mycelium.sdk.types import Sha256Digest, Symbol
from mycelium.symbols.code import EXTRA
from mycelium.symbols.extract import SymbolRef, decode_symbols

__all__ = [
    "SymbolState",
    "describe_gaps",
    "resolve_symbols",
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
    def symbol_gaps(self) -> tuple[str, ...]: ...


def resolve_symbols(
    states: Sequence[SymbolState], namespace: str = "default"
) -> tuple[Symbol, ...]:
    """Fold every document's references into one record per symbol id.

    Deterministic by construction: documents are visited in path order and
    references in line order, so the *first* definition site — the one
    ``defined_in`` names — is the same on every build of the same corpus, and
    the records come out sorted by id. ``doc_refs`` collects every chunk that
    defines the symbol, across documents, which is where it is documented when
    the definition lives in a documentation fence.
    """
    sites: dict[str, list[tuple[str, SymbolRef]]] = {}
    for state in sorted(states, key=lambda item: item.path):
        references = sorted(decode_symbols(state.symbols), key=lambda ref: (ref.line, ref.name))
        for reference in references:
            identity = symbol_id(reference.language, reference.name)
            sites.setdefault(identity, []).append((state.path, reference))

    resolved: list[Symbol] = []
    for identity in sorted(sites):
        path, first = sites[identity][0]
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
