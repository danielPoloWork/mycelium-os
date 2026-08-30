# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The authored link graph (roadmap 3.4, spec 03 §§3.1, 6, ADR-0018).

The claims under test, in the order they matter:

**Only what was written becomes an edge.** Wikilinks, embeds, and Markdown links
between documents — everything `authored`, nothing mined. External URLs are
references to the world, not edges in this graph.

**Resolution is global, and the build stays incremental anyway.** Adding a
document settles dangling links in documents this build never recompiled, which
is the property that would quietly break if extraction and resolution were not
split (and the one the incremental tests below actually exercise).

**A rollback restores the graph it published**, rather than inheriting the newer
build's edges — verified through the manifest's own `edges` digest.
"""

from pathlib import Path

from mycelium.build import build, rollback
from mycelium.graph import (
    MAX_DEPTH,
    CorpusIndex,
    LinkRef,
    edges_digest,
    extract_links,
    neighbours,
    resolve_edges,
    section_ref,
)
from mycelium.markdown import parse_markdown
from mycelium.sdk.identity import doc_ref
from mycelium.sdk.types import EdgeStatus, EdgeType
from mycelium.store import SqliteStore

CORPUS = {
    "knowledge/architecture.md": (
        "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FC1\naliases: [the design]\n---\n\n"
        "# Architecture\n\nThe bus routes messages. See [[retries]] and "
        "[the spec](https://example.invalid/spec).\n\n"
        "## Delivery\n\nGuaranteed once, per [[retries#Schedule]].\n"
    ),
    "knowledge/retries.md": (
        "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FC2\n---\n\n"
        "# Retries\n\nBackoff is exponential. Context: ![[architecture]].\n\n"
        "## Schedule\n\nFive attempts.\n"
    ),
    "knowledge/guide.md": (
        "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FC3\n---\n\n"
        "# Guide\n\nStart at [[the design]], then read [retries](retries.md).\n"
    ),
}


def repo(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    root = tmp_path / "repo"
    for relative, text in (files or CORPUS).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


def edges_of(root: Path) -> list[tuple[str, str, str, str]]:
    """Every edge as ``(from, to, type, provenance kind)``, in a readable order."""
    with SqliteStore.open(root, read_only=True) as store:
        found = set()
        for doc_id in store.document_ids():
            document = store.get_document(doc_id)
            assert document is not None
            for edge, direction in store.edges_of(doc_ref(document.path)):
                if direction == "out":
                    found.add((edge.from_, edge.to, str(edge.type), edge.provenance.kind))
    return sorted(found)


# ---------------------------------------------------------------------------
# Extraction: what was written, verbatim
# ---------------------------------------------------------------------------


def test_extraction_reads_every_authored_reference() -> None:
    from mycelium.chunking import ChunkingPolicy, chunk_document

    parsed = parse_markdown(
        "# Doc\n\nSee [[other]], ![[embedded]], [text](target.md) and "
        "[out](https://example.invalid).\n",
        doc_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
    )
    chunks = chunk_document(parsed.kir, doc_path="a.md", policy=ChunkingPolicy())
    links = extract_links(parsed.kir, chunks)

    assert [(link.kind, link.target) for link in links] == [
        ("wikilink", "other"),
        ("embed", "embedded"),
        ("markdown_link", "target.md"),
        ("markdown_link", "https://example.invalid"),
    ]
    # Each reference knows where a reader would find it.
    assert all(link.anchor.startswith("a.md#") for link in links)


def test_extraction_splits_a_heading_fragment() -> None:
    from mycelium.chunking import ChunkingPolicy, chunk_document

    parsed = parse_markdown(
        "# Doc\n\nSee [[other#Some Heading]].\n", doc_id="01ARZ3NDEKTSV4RRFFQ69G5FAV"
    )
    chunks = chunk_document(parsed.kir, doc_path="a.md", policy=ChunkingPolicy())
    (link,) = extract_links(parsed.kir, chunks)

    assert link.target == "other"
    assert link.fragment == "Some Heading"


# ---------------------------------------------------------------------------
# Resolution (spec 03 §3.1)
# ---------------------------------------------------------------------------


def index(
    *paths: str,
    aliases: dict[str, list[str]] | None = None,
    headings: dict[str, list[str]] | None = None,
) -> CorpusIndex:
    return CorpusIndex.build(paths, aliases=aliases or {}, headings=headings or {})


def link(target: str, *, kind: str = "wikilink", fragment: str = "") -> LinkRef:
    return LinkRef(kind=kind, target=target, fragment=fragment, anchor="a.md#h/0")


def test_a_unique_basename_resolves() -> None:
    edges, warnings = resolve_edges(
        {"a.md": [link("retries")]}, index("a.md", "knowledge/deep/retries.md")
    )
    assert warnings == ()
    assert edges[0].to == doc_ref("knowledge/deep/retries.md")
    assert edges[0].type is EdgeType.LINKS_TO
    assert edges[0].status is EdgeStatus.AUTHORED


def test_an_exact_path_beats_a_basename() -> None:
    edges, _ = resolve_edges(
        {"a.md": [link("docs/retries.md")]}, index("a.md", "docs/retries.md", "other/retries.md")
    )
    assert edges[0].to == doc_ref("docs/retries.md")


def test_an_ambiguous_basename_warns_and_names_the_candidates() -> None:
    """Picking one of two documents is how a knowledge graph starts lying."""
    edges, warnings = resolve_edges(
        {"a.md": [link("retries")]}, index("a.md", "one/retries.md", "two/retries.md")
    )
    assert edges == ()
    assert "one/retries.md" in warnings[0]
    assert "two/retries.md" in warnings[0]


def test_an_alias_resolves_when_it_is_unique() -> None:
    edges, warnings = resolve_edges(
        {"a.md": [link("the design")]},
        index("a.md", "b.md", aliases={"b.md": ["the design"]}),
    )
    assert warnings == ()
    assert edges[0].to == doc_ref("b.md")


def test_an_unresolvable_link_is_a_warning_not_an_error() -> None:
    """Spec 03 §3.1: a vault mid-refactor still compiles."""
    edges, warnings = resolve_edges({"a.md": [link("nowhere")]}, index("a.md"))
    assert edges == ()
    assert "unresolved wikilink" in warnings[0]
    assert "nowhere" in warnings[0]


def test_a_heading_fragment_targets_the_section() -> None:
    edges, warnings = resolve_edges(
        {"a.md": [link("b", fragment="The Schedule")]},
        index("a.md", "b.md", headings={"b.md": ["the-schedule"]}),
    )
    assert warnings == ()
    assert edges[0].to == section_ref("b.md", "the-schedule")


def test_a_missing_heading_falls_back_to_the_document_and_says_so() -> None:
    edges, warnings = resolve_edges(
        {"a.md": [link("b", fragment="Nope")]},
        index("a.md", "b.md", headings={"b.md": ["something-else"]}),
    )
    assert edges[0].to == doc_ref("b.md")
    assert "has no heading 'Nope'" in warnings[0]


def test_external_targets_are_not_edges_and_not_warnings() -> None:
    external = [
        link("https://example.invalid", kind="markdown_link"),
        link("mailto:someone@example.invalid", kind="markdown_link"),
    ]
    edges, warnings = resolve_edges({"a.md": external}, index("a.md"))
    assert edges == ()
    assert warnings == ()


def test_a_relative_markdown_link_resolves_against_its_own_directory() -> None:
    edges, _ = resolve_edges(
        {"docs/a.md": [link("b.md", kind="markdown_link")]}, index("docs/a.md", "docs/b.md")
    )
    assert edges[0].to == doc_ref("docs/b.md")


def test_identical_assertions_collapse_to_one_edge() -> None:
    """Edges are facts (spec 03 §6): the same assertion twice is the same edge."""
    twice = [link("b"), link("b")]
    edges, _ = resolve_edges({"a.md": twice}, index("a.md", "b.md"))
    assert len(edges) == 1


def test_the_same_target_from_two_places_stays_two_edges() -> None:
    """Different provenance is a different assertion, and both are worth keeping."""
    edges, _ = resolve_edges(
        {
            "a.md": [
                LinkRef(kind="wikilink", target="b", fragment="", anchor="a.md#one/0"),
                LinkRef(kind="wikilink", target="b", fragment="", anchor="a.md#two/0"),
            ]
        },
        index("a.md", "b.md"),
    )
    assert len(edges) == 2


def test_resolution_is_deterministic() -> None:
    links = {"b.md": [link("a")], "a.md": [link("b")]}
    first, _ = resolve_edges(links, index("a.md", "b.md"))
    second, _ = resolve_edges(dict(reversed(list(links.items()))), index("a.md", "b.md"))
    assert edges_digest(first) == edges_digest(second)


# ---------------------------------------------------------------------------
# The graph a build publishes
# ---------------------------------------------------------------------------


def test_a_build_publishes_the_authored_graph(tmp_path: Path) -> None:
    root = repo(tmp_path)
    manifest = build(root).manifest

    assert manifest.counts.edges == 5
    assert edges_of(root) == sorted(
        [
            (
                doc_ref("knowledge/architecture.md"),
                doc_ref("knowledge/retries.md"),
                "links_to",
                "wikilink",
            ),
            (
                doc_ref("knowledge/architecture.md"),
                section_ref("knowledge/retries.md", "schedule"),
                "links_to",
                "wikilink",
            ),
            (
                doc_ref("knowledge/retries.md"),
                doc_ref("knowledge/architecture.md"),
                "links_to",
                "embed",
            ),
            (
                doc_ref("knowledge/guide.md"),
                doc_ref("knowledge/architecture.md"),
                "links_to",
                "wikilink",
            ),
            (
                doc_ref("knowledge/guide.md"),
                doc_ref("knowledge/retries.md"),
                "links_to",
                "markdown_link",
            ),
        ]
    )
    # The external link produced neither an edge nor a warning.
    assert not any("example.invalid" in warning for warning in manifest.warnings)


def test_adding_a_document_settles_a_dangling_link_in_an_untouched_one(tmp_path: Path) -> None:
    """The property that justifies splitting extraction from resolution (ADR-0018)."""
    root = repo(
        tmp_path,
        {
            "knowledge/a.md": (
                "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FD1\n---\n\n# A\n\nSee [[b]].\n"
            )
        },
    )
    first = build(root).manifest
    assert first.counts.edges == 0
    assert any("unresolved wikilink" in warning for warning in first.warnings)

    (root / "knowledge" / "b.md").write_text(
        "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FD2\n---\n\n# B\n\nContent.\n", encoding="utf-8"
    )
    second = build(root)

    # a.md was not recompiled — and its link resolves anyway.
    assert second.stats.rebuilt == 1
    assert second.stats.reused == 1
    assert second.manifest.counts.edges == 1
    assert not any("unresolved" in warning for warning in second.manifest.warnings)


def test_removing_a_document_dangles_the_links_that_pointed_at_it(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root)
    (root / "knowledge" / "retries.md").unlink()

    manifest = build(root).manifest

    assert not any(edge[1].startswith(doc_ref("knowledge/retries.md")) for edge in edges_of(root))
    assert any("unresolved" in warning for warning in manifest.warnings)


def test_the_edges_digest_is_part_of_the_manifest(tmp_path: Path) -> None:
    root = repo(tmp_path)
    manifest = build(root).manifest
    empty = build(repo(tmp_path / "other", {"knowledge/x.md": "# X\n\nNo links.\n"})).manifest

    assert manifest.artifact_digests["edges"] != empty.artifact_digests["edges"]


def test_a_rollback_restores_the_graph_it_published(tmp_path: Path) -> None:
    """Not the newer build's edges — the ones this snapshot's manifest describes."""
    root = repo(tmp_path)
    first = build(root).manifest
    before = edges_of(root)

    (root / "knowledge" / "guide.md").unlink()
    (root / "knowledge" / "extra.md").write_text(
        "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FD9\n---\n\n# Extra\n\nSee [[retries]].\n",
        encoding="utf-8",
    )
    second = build(root).manifest
    assert edges_of(root) != before
    assert second.artifact_digests["edges"] != first.artifact_digests["edges"]

    rollback(root, first.snapshot_id)

    assert edges_of(root) == before


# ---------------------------------------------------------------------------
# Traversal
# ---------------------------------------------------------------------------


def test_neighbours_reports_both_directions(tmp_path: Path) -> None:
    """ "What does this cite" and "what cites this" are different questions."""
    root = repo(tmp_path)
    build(root)

    with SqliteStore.open(root, read_only=True) as store:
        found = neighbours(store, doc_ref("knowledge/retries.md"), depth=1, limit=20)

    directions = {item.direction for item in found}
    assert directions == {"in", "out"}
    assert all(item.depth == 1 for item in found)


def test_neighbours_filters_by_type(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root)

    with SqliteStore.open(root, read_only=True) as store:
        links_to = neighbours(store, doc_ref("knowledge/retries.md"), types=[EdgeType.LINKS_TO])
        defines = neighbours(store, doc_ref("knowledge/retries.md"), types=[EdgeType.DEFINES])

    assert links_to
    assert defines == ()  # nothing extracts `defines` edges before roadmap 5.1


def test_neighbours_walks_further_when_asked(tmp_path: Path) -> None:
    root = repo(
        tmp_path,
        {
            "knowledge/a.md": "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FE1\n---\n\n# A\n\n[[b]]\n",
            "knowledge/b.md": "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FE2\n---\n\n# B\n\n[[c]]\n",
            "knowledge/c.md": "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FE3\n---\n\n# C\n\nEnd.\n",
        },
    )
    build(root)

    with SqliteStore.open(root, read_only=True) as store:
        one = neighbours(store, doc_ref("knowledge/a.md"), depth=1)
        two = neighbours(store, doc_ref("knowledge/a.md"), depth=2)

    assert [item.ref for item in one] == [doc_ref("knowledge/b.md")]
    assert [item.ref for item in two] == [doc_ref("knowledge/b.md"), doc_ref("knowledge/c.md")]
    assert [item.depth for item in two] == [1, 2]


def test_traversal_is_bounded_by_depth_and_limit(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root)

    with SqliteStore.open(root, read_only=True) as store:
        origin = doc_ref("knowledge/retries.md")
        assert neighbours(store, origin, depth=0) == ()
        assert len(neighbours(store, origin, limit=1)) == 1
        # A request past the ceiling is clamped, not honoured.
        deep = neighbours(store, origin, depth=MAX_DEPTH + 5)
        assert all(item.depth <= MAX_DEPTH for item in deep)


def test_a_cycle_does_not_loop_forever(tmp_path: Path) -> None:
    root = repo(
        tmp_path,
        {
            "knowledge/a.md": "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FF1\n---\n\n# A\n\n[[b]]\n",
            "knowledge/b.md": "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FF2\n---\n\n# B\n\n[[a]]\n",
        },
    )
    build(root)

    with SqliteStore.open(root, read_only=True) as store:
        found = neighbours(store, doc_ref("knowledge/a.md"), depth=MAX_DEPTH)

    assert [item.ref for item in found] == [doc_ref("knowledge/b.md")]


def test_an_unknown_origin_has_no_neighbours(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root)
    with SqliteStore.open(root, read_only=True) as store:
        assert neighbours(store, doc_ref("knowledge/nothing.md")) == ()
