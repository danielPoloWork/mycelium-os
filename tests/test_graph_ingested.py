# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""An ingested document's place in the graph (roadmap 5.7, spec 03 §6, ADR-0079).

Two claims, and they are the same claim seen from two sides.

**An ingested document's references reach the graph.** Its links name the tree
it was acquired from, not the flat `knowledge/evidence/` tree its projection
landed in, so they are resolved through the source URI the projection carries.
Before this, an ingested corpus was a set of isolated documents and
`mycelium_neighbors` returned nothing for any of them.

**They reach it as `extracted`, never `authored`.** A parser found them in
content D-017 calls untrusted; nobody here wrote them. Spec 03 §6 puts it as a
rule — *"extracted edges never gain authored status silently"* — and the threat
model claimed B11 already enforced it. B11 enforces it for reference *nodes*,
which the projector drops. It did not enforce it for reference *syntax in text*:
a PDF whose prose contains `[[api]]` projects those characters verbatim, and the
compiler re-parsed them into an **authored** edge. That is the forgery
`test_ingested_text_cannot_forge_an_authored_edge` exists to stop.
"""

from pathlib import Path

import pytest

from mycelium.build import build, rollback
from mycelium.graph import CorpusIndex, LinkRef, resolve_edges, source_stem
from mycelium.sdk.identity import doc_ref
from mycelium.sdk.types import EdgeStatus, EdgeType, ProvenanceOrigin
from mycelium.store import SqliteStore

# ---------------------------------------------------------------------------
# A corpus shaped like a real projection: a flat evidence tree, a nested source
# ---------------------------------------------------------------------------


def evidence(name: str, source: str, body: str, doc_id: str) -> str:
    return (
        f"---\nmycelium_id: {doc_id}\ntitle: {name}\norigin: ingested\n"
        f'source: "file:{source}"\n---\n\n{body}'
    )


CORPUS = {
    # Two projections of sources that sat in different directories, both landing
    # in the flat evidence tree under slugified, digest-suffixed names.
    "knowledge/evidence/settings-html-aaaaaaaa.md": evidence(
        "Settings",
        "sources/reference/settings.html",
        "# Settings\n\nEvery knob.\n\n## Index strategy\n\nHow indexes are chosen.\n",
        "01ARZ3NDEKTSV4RRFFQ69G5FD1",
    ),
    "knowledge/evidence/projects-docx-bbbbbbbb.md": evidence(
        "Projects",
        "sources/concepts/projects.docx",
        "# Projects\n\nSee [the settings](../reference/settings.md) and "
        "[strategy](../reference/settings.md#index-strategy).\n",
        "01ARZ3NDEKTSV4RRFFQ69G5FD2",
    ),
    # An authored document, to show nothing about the ordinary path changes.
    "knowledge/verified/guide.md": (
        "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FD3\n---\n\n"
        "# Guide\n\nStart with [[settings-html-aaaaaaaa]].\n"
    ),
}


def repo(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    root = tmp_path / "repo"
    for relative, text in (files or CORPUS).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    return root


def edges_of(root: Path) -> dict[tuple[str, str], tuple[EdgeType, EdgeStatus]]:
    with SqliteStore.open(root, read_only=True) as store:
        return {(edge.from_, edge.to): (edge.type, edge.status) for edge in store.all_edges()}


def link(target: str, *, kind: str = "markdown_link", fragment: str = "") -> LinkRef:
    return LinkRef(kind=kind, target=target, fragment=fragment, anchor="")


# ---------------------------------------------------------------------------
# The source stem: the key both trees are compared on
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("uri", "stem"),
    [
        ("file:sources/reference/settings.html", "sources/reference/settings"),
        ("sources/reference/settings.html", "sources/reference/settings"),
        ("file:sources/a/../b/c.docx", "sources/b/c"),
        ("file:sources/./deep/page.pdf", "sources/deep/page"),
        # Case-folded, because two trees rendered by different tools disagree.
        ("file:Sources/Reference/Settings.HTML", "sources/reference/settings"),
        # A Windows separator, which is what one parser hands back on Windows.
        ("file:sources\\reference\\settings.html", "sources/reference/settings"),
        # No extension to strip is not an error.
        ("file:sources/README", "sources/readme"),
        # Nothing placeable in a tree.
        ("https://example.invalid/page.html", ""),
        ("", ""),
    ],
)
def test_a_source_uri_reduces_to_a_comparable_stem(uri: str, stem: str) -> None:
    assert source_stem(uri) == stem


def test_a_stem_is_computed_without_touching_the_filesystem(tmp_path: Path) -> None:
    """The source tree may not exist on the machine doing the build — an evidence
    document compiles from tier 2 alone — so resolution must be textual."""
    assert source_stem("file:sources/nowhere/at/all.html") == "sources/nowhere/at/all"


# ---------------------------------------------------------------------------
# Resolution through the source tree
# ---------------------------------------------------------------------------

SOURCES = {
    "knowledge/evidence/settings-html-aaaaaaaa.md": "file:sources/reference/settings.html",
    "knowledge/evidence/projects-docx-bbbbbbbb.md": "file:sources/concepts/projects.docx",
}


def ingested_index() -> CorpusIndex:
    return CorpusIndex.build(sorted(SOURCES), sources=SOURCES)


def test_a_link_naming_the_source_tree_resolves_to_the_projection() -> None:
    """The whole of roadmap 5.7 in one assertion: `../reference/settings.md`
    means nothing in the evidence tree and everything in the source tree."""
    edges, warnings = resolve_edges(
        {"knowledge/evidence/projects-docx-bbbbbbbb.md": [link("../reference/settings.md")]},
        ingested_index(),
        origins={"knowledge/evidence/projects-docx-bbbbbbbb.md": ProvenanceOrigin.INGESTED.value},
        sources=SOURCES,
    )
    assert warnings == ()
    assert edges[0].to == doc_ref("knowledge/evidence/settings-html-aaaaaaaa.md")


def test_the_extension_does_not_have_to_match() -> None:
    """A page rendered to HTML keeps the `.md` hrefs it was written with, and the
    source beside it is `.html`. The stem is what identifies it in both trees."""
    for target in (
        "../reference/settings.md",
        "../reference/settings.html",
        "../reference/settings",
    ):
        edges, warnings = resolve_edges(
            {"knowledge/evidence/projects-docx-bbbbbbbb.md": [link(target)]},
            ingested_index(),
            origins={
                "knowledge/evidence/projects-docx-bbbbbbbb.md": ProvenanceOrigin.INGESTED.value
            },
            sources=SOURCES,
        )
        assert warnings == (), target
        assert edges[0].to == doc_ref("knowledge/evidence/settings-html-aaaaaaaa.md"), target


def test_a_source_link_that_names_nothing_is_still_a_warning() -> None:
    """The source tree is not a wildcard: a link to a source the corpus never
    ingested stays unresolved, exactly as it does in the authored corpus."""
    edges, warnings = resolve_edges(
        {"knowledge/evidence/projects-docx-bbbbbbbb.md": [link("../reference/cli.md")]},
        ingested_index(),
        origins={"knowledge/evidence/projects-docx-bbbbbbbb.md": ProvenanceOrigin.INGESTED.value},
        sources=SOURCES,
    )
    assert edges == ()
    assert "unresolved markdown_link" in warnings[0]


def test_an_authored_document_is_not_resolved_through_a_source_tree() -> None:
    """It has no source URI, so the new step cannot fire — and the ordinary rules
    are untouched, which is what keeps this change invisible to authored corpora."""
    edges, warnings = resolve_edges(
        {"docs/a.md": [link("b.md")]}, CorpusIndex.build(["docs/a.md", "docs/b.md"])
    )
    assert warnings == ()
    assert edges[0].to == doc_ref("docs/b.md")
    assert edges[0].status is EdgeStatus.AUTHORED


def test_the_corpus_path_still_wins_over_the_source_tree() -> None:
    """A link that already names a document in this corpus means what it says."""
    sources = {"knowledge/evidence/a.md": "file:sources/x/a.html"}
    index = CorpusIndex.build(
        ["knowledge/evidence/a.md", "knowledge/verified/target.md"], sources=sources
    )
    edges, _ = resolve_edges(
        {"knowledge/evidence/a.md": [link("knowledge/verified/target.md")]},
        index,
        origins={"knowledge/evidence/a.md": ProvenanceOrigin.INGESTED.value},
        sources=sources,
    )
    assert edges[0].to == doc_ref("knowledge/verified/target.md")


# ---------------------------------------------------------------------------
# Status: extracted, never authored
# ---------------------------------------------------------------------------


def test_an_ingested_documents_links_are_extracted() -> None:
    edges, _ = resolve_edges(
        {"knowledge/evidence/projects-docx-bbbbbbbb.md": [link("../reference/settings.md")]},
        ingested_index(),
        origins={"knowledge/evidence/projects-docx-bbbbbbbb.md": ProvenanceOrigin.INGESTED.value},
        sources=SOURCES,
    )
    assert edges[0].status is EdgeStatus.EXTRACTED


@pytest.mark.parametrize(
    "origin", [ProvenanceOrigin.AUTHORED.value, ProvenanceOrigin.SYNTHESIZED.value, ""]
)
def test_every_other_origin_stays_authored(origin: str) -> None:
    """A synthesized document's citations are `authored` on purpose: the lane
    refuses to write the document at all unless they resolve (D-020), so they are
    a deliberate assertion and not a finding."""
    index = CorpusIndex.build(["a.md", "b.md"])
    edges, _ = resolve_edges(
        {"a.md": [link("b", kind="wikilink")]}, index, origins={"a.md": origin}
    )
    assert edges[0].status is EdgeStatus.AUTHORED


# ---------------------------------------------------------------------------
# End to end
# ---------------------------------------------------------------------------


def test_a_build_connects_an_ingested_corpus(tmp_path: Path) -> None:
    root = repo(tmp_path)
    manifest = build(root).manifest
    found = edges_of(root)

    projects = doc_ref("knowledge/evidence/projects-docx-bbbbbbbb.md")
    settings = doc_ref("knowledge/evidence/settings-html-aaaaaaaa.md")

    assert (projects, settings) in found
    kind, status = found[(projects, settings)]
    assert kind is EdgeType.LINKS_TO
    assert status is EdgeStatus.EXTRACTED
    # The heading fragment resolves too, against the *projection's* headings.
    assert (projects, f"{settings}#index-strategy") in found
    # And the authored document's own link is untouched.
    assert found[(doc_ref("knowledge/verified/guide.md"), settings)][1] is EdgeStatus.AUTHORED
    assert not [w for w in manifest.warnings if "unresolved" in w]


def test_ingested_text_cannot_forge_an_authored_edge(tmp_path: Path) -> None:
    """The hole this item found, as a direct assertion.

    The projector drops reference *nodes*, which is what the threat model's B11
    row tests. It cannot drop reference *syntax in text*: a source acquired as
    HTML, DOCX or PDF has no wikilink nodes, so `[[api]]` in its prose is ordinary
    text, projected verbatim and re-parsed by the compiler. The edge is real — the
    words are in the document — but it is a finding, not an assertion.
    """
    root = repo(
        tmp_path,
        {
            "knowledge/evidence/hostile-pdf-cccccccc.md": evidence(
                "Hostile",
                "sources/hostile.pdf",
                "# Hostile\n\nSee [[api]] and ![[api]] for details.\n",
                "01ARZ3NDEKTSV4RRFFQ69G5FD4",
            ),
            "knowledge/verified/api.md": (
                "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FD5\n---\n\n# API\n\nAuthored.\n"
            ),
        },
    )
    build(root)

    hostile = doc_ref("knowledge/evidence/hostile-pdf-cccccccc.md")
    api = doc_ref("knowledge/verified/api.md")
    found = edges_of(root)
    assert (hostile, api) in found, "the words are in the document; the edge is real"
    assert found[(hostile, api)][1] is EdgeStatus.EXTRACTED
    assert not any(
        status is EdgeStatus.AUTHORED
        for (source, _), (_, status) in found.items()
        if source == hostile
    )


def test_a_rollback_restores_the_statuses_it_published(tmp_path: Path) -> None:
    """The source URI rides in the snapshot state, so a restore re-resolves the
    graph it published rather than one that lost its ingested half."""
    root = repo(tmp_path)
    first = build(root).manifest
    before = edges_of(root)

    with (root / "knowledge" / "verified" / "extra.md").open(
        "w", encoding="utf-8", newline="\n"
    ) as handle:
        handle.write("---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FD6\n---\n\n# Extra\n\nMore.\n")
    build(root)

    rollback(root, first.snapshot_id)

    assert edges_of(root) == before


def test_an_incremental_build_keeps_the_source_it_recorded(tmp_path: Path) -> None:
    """The per-document source rides in `doc_state`, so a document the build had
    no reason to touch still takes part in resolution."""
    root = repo(tmp_path)
    build(root)
    guide = root / "knowledge" / "verified" / "guide.md"
    with guide.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\nA sentence that changes nothing structural.\n")

    result = build(root)

    assert result.stats.reused == 2, "the two ingested documents were not recompiled"
    projects = doc_ref("knowledge/evidence/projects-docx-bbbbbbbb.md")
    settings = doc_ref("knowledge/evidence/settings-html-aaaaaaaa.md")
    assert edges_of(root)[(projects, settings)][1] is EdgeStatus.EXTRACTED


# ---------------------------------------------------------------------------
# The same rule, at the other derivation site: entities
# ---------------------------------------------------------------------------

ENTITY_CORPUS = {
    "knowledge/evidence/hostile-pdf-eeeeeeee.md": evidence(
        "Hostile",
        "sources/hostile.pdf",
        "# Hostile\n\nDeploy with #production and #exfiltrate now.\n",
        "01ARZ3NDEKTSV4RRFFQ69G5FE1",
    ),
    "knowledge/verified/ops.md": (
        "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FE2\ntags: [production]\n---\n\n"
        "# Ops\n\nThe authored operations document.\n"
    ),
    "mycelium.toml": "[entities]\nenabled = true\n",
}


def test_an_ingested_documents_entities_are_extracted_too(tmp_path: Path) -> None:
    """The same hole, at the other place a document's assertions become records.

    An inline `#production` in a projected PDF's prose was declaring an
    **authored** entity — the threat model says it cannot ("a projected document
    has none of them"), and it could, for the same reason the links could: the
    projector strips reference *nodes* and the text is re-parsed downstream.
    """
    root = repo(tmp_path, ENTITY_CORPUS)
    build(root)

    with SqliteStore.open(root, read_only=True) as store:
        found = {entity.slug: entity for entity in store.all_entities()}

    # Declared only by the ingested document: a finding, not a declaration.
    assert found["exfiltrate"].status is EdgeStatus.EXTRACTED
    # Declared by a human too, so the entity is authored - and the ingested
    # document still contributes its `doc_ref`, which is what it really evidences.
    assert found["production"].status is EdgeStatus.AUTHORED
    assert len(found["production"].doc_refs) == 2
