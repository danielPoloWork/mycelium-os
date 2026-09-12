# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The extract stage, per document: KIR in, symbol references out (roadmap 5.1).

This is the seam ADR-0018 cut for the link graph, cut again for symbols.
:func:`extract_symbols` reads *one* document's KIR and that document's chunks
and knows nothing about the corpus, so its result is cached with the document
in ``doc_state`` and survives every build that leaves the document untouched.
Turning the references of the whole corpus into :class:`~mycelium.sdk.types.Symbol`
records is a global pass (:mod:`mycelium.symbols.resolve`), because the same
symbol may be defined in two documents and the record is one row.

A :class:`SymbolRef` is deliberately not a :class:`~mycelium.sdk.types.Symbol`.
The record is the spec 03 §6 contract — one per symbol, with ``defined_in`` and
every ``doc_refs`` — and a document cannot know it is the first to define
something or how many others document it. The reference says what *this*
document did: it defined `name` in `language`, of `kind`, at `line`, inside the
chunk at `anchor`.  Everything the record adds is resolution.

One type carries both halves of spec 03 §6's question (roadmap 5.2): what a
document **defines**, and what it **uses**. They are extracted from the same
parse of the same fence and separated in :class:`Extraction`, because they
resolve differently — a definition mints a symbol, a use only ever points at
one the corpus already has.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from mycelium.graph import anchor_of
from mycelium.sdk.types import Chunk, KirDocument, NodeKind
from mycelium.symbols.code import MAX_FENCE_BYTES, grammar_for, load_grammar, read_fence
from mycelium.symbols.docs import DOC_LANGUAGE, TERM_KIND, definition_terms, heading_subject

__all__ = [
    "CODE_FENCE",
    "DEFINITION_LIST",
    "HEADING",
    "Extraction",
    "SymbolRef",
    "decode_symbols",
    "encode_symbols",
    "extract_symbols",
]

CODE_FENCE: Final = "code_fence"
"""A definition or use read from a fenced code block, through its grammar."""

HEADING: Final = "heading"
"""A term defined by a heading whose text is an identifier (ADR-0073)."""

DEFINITION_LIST: Final = "definition_list"
"""A term defined by Markdown's own definition-list syntax."""


@dataclass(frozen=True, slots=True)
class SymbolRef:
    """One definition or use, as a single document asserts it."""

    language: str
    """The symbol's language segment: a grammar's language, or `doc`."""
    name: str
    """For a definition, the qualified name the symbol id will carry. For a use,
    the name as the fence wrote it — resolution qualifies it, not the fence."""
    kind: str
    """A definition's kind (`class`, `term`, …) or a use's (`call`, `type`, …)."""
    source: str
    """Which syntax carried it: :data:`CODE_FENCE`, :data:`HEADING`, or
    :data:`DEFINITION_LIST`. It becomes the edge's `provenance.kind`, so
    `mycelium neighbors` can say *how* a document defines what it defines."""
    line: int
    """1-based line in the Markdown source; 0 when the KIR carried no source
    locator, in which case the chunk anchor stands in."""
    anchor: str
    """The chunk anchor holding it — where a reader would find it."""
    direct: bool = True
    """Whether the syntax names the symbol as its own subject.

    True for a fence definition, a definition-list term, and a heading that *is*
    the name; False for a heading that frames it in a phrase (``## The
    pyproject.toml``). Resolution prefers a direct site for ``defined_in``, so
    widening which headings are read cannot move what a record already named
    (roadmap 5.19, ADR-0091)."""

    def as_dict(self) -> dict[str, object]:
        return {
            "language": self.language,
            "name": self.name,
            "kind": self.kind,
            "source": self.source,
            "line": self.line,
            "anchor": self.anchor,
            "direct": self.direct,
        }


def encode_symbols(symbols: Sequence[SymbolRef]) -> list[dict[str, object]]:
    """The form `doc_state` stores, so resolution can run without re-parsing."""
    return [symbol.as_dict() for symbol in symbols]


def decode_symbols(raw: Iterable[Mapping[str, object]]) -> tuple[SymbolRef, ...]:
    return tuple(
        SymbolRef(
            language=str(item["language"]),
            name=str(item["name"]),
            kind=str(item["kind"]),
            # A row written before roadmap 5.2 has no `source`, and every symbol
            # it holds came from one of the three syntaxes below; the fence is
            # the only one whose absence would misreport a *use*, and rows that
            # old carry no uses at all.
            source=str(item.get("source", CODE_FENCE)),
            line=int(str(item.get("line", 0))),
            anchor=str(item.get("anchor", "")),
            # A row written before roadmap 5.19 holds only sites that named their
            # symbol outright, because that was the only shape the rule read.
            direct=bool(item.get("direct", True)),
        )
        for item in raw
    )


@dataclass(frozen=True, slots=True)
class Extraction:
    """What one document's extract stage produced, and what it could not."""

    symbols: tuple[SymbolRef, ...]
    """What the document defines."""
    references: tuple[SymbolRef, ...] = ()
    """What its fences use, deduplicated per name — the input to the `references`
    edges (roadmap 5.2). Only fences produce these: prose that mentions a symbol
    is mining, which is an entity extractor's job (5.4) and a different status."""
    gaps: tuple[str, ...] = ()
    """Languages of fences this build could not read because their grammar is
    not installed — sorted, unique. The publication folds these into the
    snapshot's `degraded` flag (spec 02 §4.3)."""
    warnings: tuple[str, ...] = ()
    """Per-document, operator-facing: a fence over the byte ceiling, a parse that
    raised. They travel with the document's other warnings into the manifest."""


def _source_line(kir_node_lines: tuple[int, int] | None) -> int:
    return kir_node_lines[0] if kir_node_lines else 0


def extract_symbols(kir: KirDocument, chunks: Sequence[Chunk], *, doc_path: str) -> Extraction:
    """Every symbol one document defines and uses, in document order.

    Pure and per-document, like :func:`mycelium.graph.extract_links`: it reads
    this document's KIR and chunks, never the corpus, which is what lets the
    result be cached with the document and resolved later against a corpus that
    has moved on.

    Code fences go to their grammar's tags queries (:mod:`mycelium.symbols.code`);
    headings and definition-list paragraphs go to the documentation rules
    (:mod:`mycelium.symbols.docs`). A fence whose language has no grammar here is
    a *gap*, not an error — the document compiles, the snapshot says what it is
    missing — and a fence over :data:`~mycelium.symbols.code.MAX_FENCE_BYTES` is a
    warning naming the line.
    """
    by_id = {node.id: node for node in kir.nodes}
    anchors = {node_id: chunk.anchor for chunk in chunks for node_id in chunk.kir_nodes}

    found: list[SymbolRef] = []
    used: dict[tuple[str, str], SymbolRef] = {}
    gaps: set[str] = set()
    warnings: list[str] = []
    for node in kir.nodes:
        if node.kind is NodeKind.CODE_BLOCK:
            grammar = grammar_for(node.lang)
            if grammar is None or not node.text:
                continue
            start = _source_line(node.src.lines if node.src else None)
            source = node.text.encode("utf-8")
            if len(source) > MAX_FENCE_BYTES:
                warnings.append(
                    f"{doc_path}: {grammar.name} fence at line {start} not read for symbols "
                    f"({len(source)} bytes exceeds the {MAX_FENCE_BYTES}-byte ceiling)"
                )
                continue
            loaded = load_grammar(grammar.name)
            if loaded is None:
                gaps.add(grammar.language)
                continue
            try:
                contents = read_fence(loaded, source)
            except Exception as error:  # noqa: BLE001 - one fence failing is not a lost document
                warnings.append(
                    f"{doc_path}: {grammar.name} fence at line {start} not read for symbols "
                    f"({type(error).__name__}: {error})"
                )
                continue
            anchor = anchor_of(node, by_id, anchors)
            for definition in contents.definitions:
                # The fence's own line is the opening ``` — content starts below it.
                line = start + 1 + definition.row if start else 0
                found.append(
                    SymbolRef(
                        grammar.language, definition.name, definition.kind, CODE_FENCE, line, anchor
                    )
                )
            for use in contents.references:
                # One edge per name per document, at its first use: a fence that
                # calls `print` fifteen times has said one thing fifteen times.
                key = (grammar.language, use.name)
                if key in used:
                    continue
                line = start + 1 + use.row if start else 0
                used[key] = SymbolRef(
                    grammar.language, use.name, use.kind, CODE_FENCE, line, anchor
                )
        elif node.kind is NodeKind.HEADING and node.text:
            subject = heading_subject(node.text)
            if subject is None:
                continue
            term, direct = subject
            line = _source_line(node.src.lines if node.src else None)
            found.append(
                SymbolRef(
                    DOC_LANGUAGE,
                    term,
                    TERM_KIND,
                    HEADING,
                    line,
                    anchor_of(node, by_id, anchors),
                    direct=direct,
                )
            )
        elif node.kind is NodeKind.PARAGRAPH and node.text:
            terms = definition_terms(node.text)
            if not terms:
                continue
            start = _source_line(node.src.lines if node.src else None)
            anchor = anchor_of(node, by_id, anchors)
            for offset, term in terms:
                line = start + offset if start else 0
                found.append(
                    SymbolRef(DOC_LANGUAGE, term, TERM_KIND, DEFINITION_LIST, line, anchor)
                )
    return Extraction(
        symbols=tuple(found),
        references=tuple(used.values()),
        gaps=tuple(sorted(gaps)),
        warnings=tuple(warnings),
    )
