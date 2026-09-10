# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The typed edge vocabulary (roadmap 5.2, spec 03 §6, D-014, ADR-0074).

The claims under test, in the order they matter:

**A section is no longer a dead end.** A heading link resolves to a section
reference, and `part_of` connects that node to its document — so a walk that
reaches a section carries on, which is what graph expansion will need (5.3).
It is emitted for sections the graph already names and for no others.

**A symbol is a node, and both questions about it are one hop.** `defines`
answers *where is this defined*, `references` answers *what uses it*, both are
`extracted` because a grammar found them, and a use becomes an edge only when
the corpus defines what it names.

**`derived_from` says what `cites` cannot.** It is emitted for a *synthesized*
document, at document granularity, from the frontmatter that declares its
origin — the distinction ADR-0018 deferred for want of exactly that field.

**The whole vocabulary reaches the tools.** `mycelium_neighbors` filters by any
of the eight types, accepts a symbol id as its origin, and serves the status and
weight spec 05 §3.3 promises.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mycelium.build import build
from mycelium.cli.app import app
from mycelium.graph import (
    CorpusIndex,
    LinkRef,
    merge_edges,
    neighbours,
    resolve_edges,
    section_ref,
    split_section_ref,
)
from mycelium.mcp import tools as mcp_tools
from mycelium.mcp.errors import ErrorCode, McpToolError
from mycelium.sdk.identity import doc_ref, symbol_id
from mycelium.sdk.types import Edge, EdgeStatus, EdgeType, ProvenanceOrigin
from mycelium.store import SqliteStore
from mycelium.symbols import CODE_FENCE, HEADING, SymbolRef, encode_symbols, symbol_edges

IDS = {
    "api": "01ARZ3NDEKTSV4RRFFQ69G5FE1",
    "guide": "01ARZ3NDEKTSV4RRFFQ69G5FE2",
    "evidence": "01ARZ3NDEKTSV4RRFFQ69G5FE3",
    "candidate": "01ARZ3NDEKTSV4RRFFQ69G5FE4",
}

API = f"""---
mycelium_id: {IDS["api"]}
---

# API

## RetryPolicy

```python
class RetryPolicy:
    def delay(self, attempt):
        return attempt


def build_policy():
    return RetryPolicy()
```
"""

GUIDE = f"""---
mycelium_id: {IDS["guide"]}
---

# Guide

Start at [[api#RetryPolicy]], then read [[api]].

## Usage

```python
policy = build_policy()
print(policy.delay(2))
```
"""

EVIDENCE = f"""---
mycelium_id: {IDS["evidence"]}
origin: ingested
source: "https://example.invalid/spec.pdf"
---

# Delivery (extract)

## Section 4.3

"Attempts are bounded; the final one quarantines."
"""

CANDIDATE = f"""---
mycelium_id: {IDS["candidate"]}
origin: synthesized
source: "https://example.invalid/spec.pdf"
generated_by: anthropic/claude-sonnet-5
---

# Delivery (draft)

Attempts are bounded ([[delivery#Section 4.3]]), and the last one quarantines ([[delivery]]).
"""

CORPUS = {
    "knowledge/verified/api.md": API,
    "knowledge/verified/guide.md": GUIDE,
    "knowledge/evidence/delivery.md": EVIDENCE,
    "knowledge/candidate/draft.md": CANDIDATE,
}

runner = CliRunner()


def repo(tmp_path: Path, files: Mapping[str, str] | None = None) -> Path:
    root = tmp_path / "repo"
    for relative, text in (files or CORPUS).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    return root


def built(tmp_path: Path, files: Mapping[str, str] | None = None) -> Path:
    root = repo(tmp_path, files)
    build(root)
    return root


def edges(root: Path) -> list[tuple[str, str, str, str, str]]:
    """Every edge as (from, to, type, status, provenance kind)."""
    with SqliteStore.open(root, read_only=True) as store:
        return sorted(
            (
                edge.from_,
                edge.to,
                str(edge.type),
                str(edge.status),
                edge.provenance.kind,
            )
            for edge in store.all_edges()
        )


def types_of(root: Path) -> set[str]:
    return {edge[2] for edge in edges(root)}


@pytest.fixture
def grammars() -> None:
    from mycelium.symbols import load_grammar

    if load_grammar("python") is None:
        pytest.skip("the symbols extra is not installed")


# ---------------------------------------------------------------------------
# part_of: a section belongs to its document
# ---------------------------------------------------------------------------


def test_a_section_reference_splits_into_its_document_and_slug() -> None:
    assert split_section_ref("doc:a.md#retries") == ("doc:a.md", "retries")
    assert split_section_ref(section_ref("docs/a.md", "x")) == ("doc:docs/a.md", "x")
    for not_a_section in ("doc:a.md", "sym:python:X", "doc:a.md#", "", "ent:thing"):
        assert split_section_ref(not_a_section) is None


def test_part_of_connects_a_linked_section_to_its_document(tmp_path: Path, grammars: None) -> None:
    root = built(tmp_path)
    section = section_ref("knowledge/verified/api.md", "retrypolicy")

    assert (
        section,
        doc_ref("knowledge/verified/api.md"),
        "part_of",
        "authored",
        "heading",
    ) in edges(root)


def test_part_of_is_not_emitted_for_a_heading_nothing_names(tmp_path: Path) -> None:
    """Bounded emission: one edge per *linked* section, not one per heading."""
    root = built(
        tmp_path,
        {
            "knowledge/a.md": (
                f"---\nmycelium_id: {IDS['api']}\n---\n\n# A\n\n## One\n\nx\n\n## Two\n\ny\n"
            ),
            "knowledge/b.md": f"---\nmycelium_id: {IDS['guide']}\n---\n\n# B\n\nSee [[a#One]].\n",
        },
    )
    part_of = [edge for edge in edges(root) if edge[2] == "part_of"]

    assert len(part_of) == 1
    assert part_of[0][0] == section_ref("knowledge/a.md", "one")


def test_a_walk_reaching_a_section_carries_on_through_its_document(
    tmp_path: Path, grammars: None
) -> None:
    """The dead end this item exists to close: before `part_of`, a heading link
    was the end of every traversal that arrived on it."""
    root = built(tmp_path)
    origin = doc_ref("knowledge/verified/guide.md")

    with SqliteStore.open(root, read_only=True) as store:
        reached = {item.ref for item in neighbours(store, origin, depth=2, limit=50)}

    section = section_ref("knowledge/verified/api.md", "retrypolicy")
    assert section in reached, "the heading link is a neighbour"
    assert doc_ref("knowledge/verified/api.md") in reached, "and its document is reachable"


# ---------------------------------------------------------------------------
# defines / references: the symbol half, and it is `extracted`
# ---------------------------------------------------------------------------


def test_a_document_defines_the_symbols_its_fences_declare(tmp_path: Path, grammars: None) -> None:
    root = built(tmp_path)
    defines = {edge for edge in edges(root) if edge[2] == "defines"}

    assert (
        doc_ref("knowledge/verified/api.md"),
        symbol_id("python", "RetryPolicy.delay"),
        "defines",
        "extracted",
        "code_fence",
    ) in defines
    # Every symbol edge is extracted: a grammar found it, nobody wrote it down.
    assert {edge[3] for edge in defines} == {"extracted"}


def test_a_use_becomes_a_references_edge_when_the_corpus_defines_it(
    tmp_path: Path, grammars: None
) -> None:
    root = built(tmp_path)
    references = {(edge[0], edge[1]) for edge in edges(root) if edge[2] == "references"}
    guide = doc_ref("knowledge/verified/guide.md")

    # `build_policy()` resolves exactly; `policy.delay(2)` captures `delay` and
    # resolves against the last segment of `RetryPolicy.delay`.
    assert (guide, symbol_id("python", "build_policy")) in references
    assert (guide, symbol_id("python", "RetryPolicy.delay")) in references
    # `print` is called and defined nowhere in the corpus, so it is not a node.
    assert not any(target.endswith(":print") for _, target in references)


def test_both_questions_about_a_symbol_are_one_hop(tmp_path: Path, grammars: None) -> None:
    """What doc 00 says agents ask constantly: where is X defined, and what uses it."""
    root = built(tmp_path)
    target = symbol_id("python", "build_policy")

    with SqliteStore.open(root, read_only=True) as store:
        found = neighbours(store, target, depth=1, limit=20)

    by_type = {str(item.edge.type): item.ref for item in found}
    assert by_type["defines"] == doc_ref("knowledge/verified/api.md")
    assert by_type["references"] == doc_ref("knowledge/verified/guide.md")
    assert {item.direction for item in found} == {"in"}


# ---------------------------------------------------------------------------
# The resolution rules, in isolation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _State:
    path: str
    symbols: tuple[Mapping[str, object], ...] = ()
    symbol_uses: tuple[Mapping[str, object], ...] = ()
    symbol_gaps: tuple[str, ...] = ()
    origin: str = ProvenanceOrigin.AUTHORED.value
    links: tuple[Mapping[str, str], ...] = ()
    aliases: tuple[str, ...] = ()
    headings: tuple[str, ...] = field(default=())


def _refs(*items: tuple[str, str, str, int]) -> tuple[Mapping[str, object], ...]:
    """(language, name, kind, line) -> the stored form, at a made-up anchor."""
    return tuple(
        encode_symbols(
            [
                SymbolRef(language, name, kind, CODE_FENCE, line, f"a.md#s/{line}")
                for language, name, kind, line in items
            ]
        )
    )


def _symbols(states: list[_State]) -> tuple[Edge, ...]:
    from mycelium.symbols import resolve_symbols

    return symbol_edges(states, resolve_symbols(states))


def test_an_ambiguous_use_resolves_to_nothing() -> None:
    """Two candidates for one captured name: the wikilink rule refuses to guess."""
    states = [
        _State("a.md", symbols=_refs(("python", "One.run", "method", 1))),
        _State("b.md", symbols=_refs(("python", "Two.run", "method", 1))),
        _State("c.md", symbol_uses=_refs(("python", "run", "call", 1))),
    ]
    assert not [edge for edge in _symbols(states) if edge.type is EdgeType.REFERENCES]


def test_an_unambiguous_last_segment_resolves() -> None:
    states = [
        _State("a.md", symbols=_refs(("python", "One.run", "method", 1))),
        _State("c.md", symbol_uses=_refs(("python", "run", "call", 1))),
    ]
    (edge,) = [edge for edge in _symbols(states) if edge.type is EdgeType.REFERENCES]
    assert edge.from_ == doc_ref("c.md")
    assert edge.to == symbol_id("python", "One.run")


def test_a_use_does_not_cross_languages() -> None:
    states = [
        _State("a.md", symbols=_refs(("rust", "run", "function", 1))),
        _State("c.md", symbol_uses=_refs(("python", "run", "call", 1))),
    ]
    assert not [edge for edge in _symbols(states) if edge.type is EdgeType.REFERENCES]


def test_the_document_that_defines_a_symbol_is_not_also_a_user_of_it() -> None:
    states = [
        _State(
            "a.md",
            symbols=_refs(("python", "helper", "function", 1)),
            symbol_uses=_refs(("python", "helper", "call", 9)),
        )
    ]
    found = _symbols(states)
    assert [str(edge.type) for edge in found] == ["defines"]


def test_a_definition_records_the_syntax_that_carried_it() -> None:
    states = [
        _State(
            "a.md",
            symbols=(
                *encode_symbols(
                    [SymbolRef("doc", "uv.lock", "term", HEADING, 3, "a.md#uv-lock/0")]
                ),
            ),
        )
    ]
    (edge,) = _symbols(states)
    assert edge.provenance.kind == "heading"
    assert edge.provenance.anchor == "a.md#uv-lock/0"
    assert edge.status is EdgeStatus.EXTRACTED


def test_symbol_edges_are_ordered_and_deduplicated_whatever_the_input_order() -> None:
    states = [
        _State("b.md", symbols=_refs(("python", "Shared", "class", 4))),
        _State("a.md", symbols=_refs(("python", "Shared", "class", 2))),
    ]
    forward = _symbols(states)
    backward = _symbols(list(reversed(states)))
    assert forward == backward
    assert [edge.from_ for edge in forward] == [doc_ref("a.md"), doc_ref("b.md")]


def test_merge_edges_is_stable_and_idempotent() -> None:
    states = [
        _State("a.md", symbols=_refs(("python", "One", "class", 1))),
        _State("b.md", symbols=_refs(("python", "Two", "class", 1))),
    ]
    group = _symbols(states)
    halves = (group[:1], group[1:])
    assert merge_edges(*halves) == group
    assert merge_edges(group, group) == group
    assert merge_edges(*reversed(halves)) == group


# ---------------------------------------------------------------------------
# derived_from: what only the origin can say
# ---------------------------------------------------------------------------


def test_a_synthesized_document_is_derived_from_the_evidence_it_cites(
    tmp_path: Path, grammars: None
) -> None:
    root = built(tmp_path)
    draft = doc_ref("knowledge/candidate/draft.md")
    evidence = doc_ref("knowledge/evidence/delivery.md")
    found = edges(root)

    # Two citations, one to a section and one to the document; a single
    # `derived_from` at document granularity, from the frontmatter.
    assert sum(1 for edge in found if edge[2] == "cites") == 2
    assert [edge for edge in found if edge[2] == "derived_from"] == [
        (draft, evidence, "derived_from", "authored", "frontmatter")
    ]


def test_an_authored_document_citing_evidence_is_not_derived_from_it(tmp_path: Path) -> None:
    """The distinction the type exists for: citing evidence is not being written
    from it, and only `origin` can tell the two apart (ADR-0018, ADR-0074)."""
    authored = CANDIDATE.replace("origin: synthesized\n", "").replace(
        "generated_by: anthropic/claude-sonnet-5\n", ""
    )
    root = built(
        tmp_path,
        {
            "knowledge/evidence/delivery.md": EVIDENCE,
            "knowledge/verified/notes.md": authored,
        },
    )
    found = edges(root)

    assert any(edge[2] == "cites" for edge in found)
    assert not any(edge[2] == "derived_from" for edge in found)


def test_resolution_without_origins_emits_no_derived_from() -> None:
    """`resolve_edges` is callable without origins, and then says nothing about them."""
    index = CorpusIndex.build(["knowledge/evidence/e.md", "a.md"])
    links = {"a.md": [LinkRef("wikilink", "e", "", "a.md#s/0")]}
    without, _ = resolve_edges(links, index)
    with_origins, _ = resolve_edges(
        links, index, origins={"a.md": ProvenanceOrigin.SYNTHESIZED.value}
    )

    assert [str(edge.type) for edge in without] == ["cites"]
    assert [str(edge.type) for edge in with_origins] == ["cites", "derived_from"]


# ---------------------------------------------------------------------------
# The vocabulary, and the tools over it
# ---------------------------------------------------------------------------


def test_the_corpus_exercises_six_of_the_eight_types(tmp_path: Path, grammars: None) -> None:
    """Two are deliberately unreachable, each for a stated reason: `mentions`
    belongs to the entity extractor (roadmap 5.4) and `supersedes` needs a
    frontmatter field the closed contract does not have (5.10, ADR-0074)."""
    root = built(tmp_path)
    emitted = types_of(root)

    assert emitted == {
        "links_to",
        "cites",
        "part_of",
        "derived_from",
        "defines",
        "references",
    }
    assert {item.value for item in EdgeType} - emitted == {"mentions", "supersedes"}


def test_every_edge_serves_the_status_and_weight_the_contract_promises(
    tmp_path: Path, grammars: None
) -> None:
    """Spec 05 §3.3: typed, weighted neighbours with a status on every edge."""
    root = built(tmp_path)
    with SqliteStore.open(root, read_only=True) as store:
        found = neighbours(store, doc_ref("knowledge/verified/api.md"), depth=1, limit=50)

    assert found
    for item in found:
        rendered = item.as_dict()
        assert rendered["status"] in {"authored", "extracted"}
        assert rendered["weight"] == 1.0, "weights are 5.3's to earn (ADR-0074)"
        assert str(rendered["type"]) in {item.value for item in EdgeType}


def test_the_spec_example_filter_now_returns_something(tmp_path: Path, grammars: None) -> None:
    """Spec 05 §3.3's own example input names `defines`, which nothing emitted
    until this item."""
    root = built(tmp_path)
    payload = mcp_tools.handle_neighbors(
        root, {"uri": "knowledge/verified/api.md", "types": ["defines", "links_to"]}
    )
    kinds = {str(item["type"]) for item in payload["neighbors"]}  # type: ignore[index,union-attr]

    # `defines` is what nothing emitted before this item; `links_to` is the
    # inbound link from the guide, and the filter admits both and nothing else.
    assert kinds == {"defines", "links_to"}
    assert payload["origin"] == doc_ref("knowledge/verified/api.md")

    narrowed = mcp_tools.handle_neighbors(
        root, {"uri": "knowledge/verified/api.md", "types": ["defines"]}
    )
    assert {str(item["type"]) for item in narrowed["neighbors"]} == {  # type: ignore[index,union-attr]
        "defines"
    }


def test_the_tools_accept_a_symbol_as_the_origin(tmp_path: Path, grammars: None) -> None:
    root = built(tmp_path)
    target = symbol_id("python", "build_policy")

    payload = mcp_tools.handle_neighbors(root, {"uri": target})
    assert payload["origin"] == target
    assert {str(item["type"]) for item in payload["neighbors"]} == {  # type: ignore[index,union-attr]
        "defines",
        "references",
    }

    result = runner.invoke(app, ["neighbors", target, "--path", str(root), "--json"])
    assert result.exit_code == 0, result.output
    assert target in result.stdout


def test_an_unknown_symbol_is_not_found_rather_than_empty(tmp_path: Path, grammars: None) -> None:
    """An empty neighbourhood reads as "nothing defines it", which is a different
    and wrong answer."""
    root = built(tmp_path)

    with pytest.raises(McpToolError) as raised:
        mcp_tools.handle_neighbors(root, {"uri": symbol_id("python", "NoSuchThing")})
    assert raised.value.code is ErrorCode.NOT_FOUND

    result = runner.invoke(
        app, ["neighbors", symbol_id("python", "NoSuchThing"), "--path", str(root)]
    )
    assert result.exit_code == 1
    assert "no symbol" in result.output


def test_a_rebuild_publishes_the_same_typed_graph(tmp_path: Path, grammars: None) -> None:
    """Every type re-derives identically: the edge id is the digest of the
    assertion, so a rebuild converges instead of accumulating (spec 03 §6)."""
    root = built(tmp_path)
    first = edges(root)
    first_digest = build(root).manifest.artifact_digests["edges"]
    second = edges(root)

    assert first == second
    assert build(root, clean=True).manifest.artifact_digests["edges"] == first_digest
