# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Compiling without writing to the tree (roadmap 4.14).

Identity pinning is the build's only write into tier 2 (ADR-0009), so suppressing it is
the whole of "compile without touching the corpus". The two claims that matter are here
and they are equally load-bearing: the tree is **byte-identical** after a `--no-pin`
build, and two such builds of one corpus **fold identically** — which a pinned build of
an unpinned corpus does not, because it mints a fresh ULID per document every time.

The second claim is the one that makes measurement possible. Not dirtying the tree is a
convenience; producing the same corpus twice is the precondition for comparing two runs
at all (ADR-0046).
"""

import shutil
from pathlib import Path

import pytest

from mycelium.build import build
from mycelium.markdown import parse_frontmatter
from mycelium.sdk.identity import derived_ulid, is_derived_ulid
from mycelium.store import SqliteStore

BARE = "# Bare\n\ntext about retries\n"
WITH_FRONTMATTER = "---\ntitle: A\n---\n\n# A\n\n## Retries\n\nExponential backoff.\n"
PINNED_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"
ALREADY_PINNED = f"---\nmycelium_id: {PINNED_ID}\ntitle: Pinned\n---\n\n# Pinned\n\ntext\n"


def repo(tmp_path: Path, files: dict[str, str]) -> Path:
    for relative, text in files.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
    return tmp_path


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*.md"))
        if ".mycelium" not in path.parts
    }


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    return repo(
        tmp_path,
        {
            "knowledge/bare.md": BARE,
            "knowledge/verified/a.md": WITH_FRONTMATTER,
            "knowledge/pinned.md": ALREADY_PINNED,
        },
    )


# ---------------------------------------------------------------------------
# The tree is not touched
# ---------------------------------------------------------------------------


def test_no_pin_leaves_every_source_byte_where_it_was(corpus: Path) -> None:
    before = tree_bytes(corpus)
    result = build(corpus, pin_identity=False)
    assert tree_bytes(corpus) == before
    assert result.pinned == ()


def test_the_same_corpus_pinned_does_write(corpus: Path) -> None:
    # The control. Without it, the test above could pass because nothing was
    # ever going to be written.
    before = tree_bytes(corpus)
    result = build(corpus)
    assert tree_bytes(corpus) != before
    assert {path.name for path in result.pinned} == {"bare.md", "a.md"}


def test_no_pin_still_publishes_a_usable_snapshot(corpus: Path) -> None:
    result = build(corpus, pin_identity=False)
    assert result.manifest.counts.documents == 3
    assert result.manifest.counts.chunks > 0
    with SqliteStore.open(corpus, read_only=True) as store:
        hits = store.search_chunks("retries", limit=5)
    assert hits, "a snapshot nobody can query is not a published corpus"


# ---------------------------------------------------------------------------
# Reproducibility — the reason the id is derived rather than minted
# ---------------------------------------------------------------------------


def test_two_builds_from_scratch_fold_identically(corpus: Path, tmp_path: Path) -> None:
    twin = tmp_path / "twin"
    shutil.copytree(corpus, twin)

    first = build(corpus, pin_identity=False)
    second = build(twin, pin_identity=False)

    # Different directories, different processes' worth of state, no shared
    # store — and the same corpus. This is what makes two measurements
    # comparable, and it is what a pinned build of an unpinned corpus cannot do.
    assert first.manifest.artifact_digests == second.manifest.artifact_digests
    assert first.manifest.counts == second.manifest.counts


def test_two_pinned_builds_from_scratch_do_not(corpus: Path, tmp_path: Path) -> None:
    """The counterfactual, stated as a test so the claim above is not folklore.

    A pinned build mints a fresh ULID for every document that has none, and
    `Document.doc_id` is inside the record the manifest folds — so the same tree
    compiled twice from scratch yields two different corpora. On a repository
    whose documents are not committed with ids, that is every CI run.
    """
    twin = tmp_path / "twin"
    shutil.copytree(corpus, twin)

    first = build(corpus)
    second = build(twin)

    assert first.manifest.artifact_digests != second.manifest.artifact_digests
    # …and the *only* difference is identity: the content each document carries
    # is the same, which is why the eval fingerprint (ADR-0045) is identity-free.
    assert first.manifest.counts == second.manifest.counts


# ---------------------------------------------------------------------------
# What the derived identity is, and what it is not
# ---------------------------------------------------------------------------


def test_an_unpinned_document_takes_an_id_derived_from_its_path(corpus: Path) -> None:
    build(corpus, pin_identity=False)
    with SqliteStore.open(corpus, read_only=True) as store:
        by_path = {
            document.path: document.doc_id
            for doc_id in store.document_ids()
            if (document := store.get_document(doc_id)) is not None
        }
    assert by_path["knowledge/bare.md"] == derived_ulid("knowledge/bare.md")
    assert is_derived_ulid(by_path["knowledge/bare.md"])


def test_a_document_that_carries_an_id_keeps_it(corpus: Path) -> None:
    # `--no-pin` suppresses a *write*; it does not ignore what is already there.
    build(corpus, pin_identity=False)
    with SqliteStore.open(corpus, read_only=True) as store:
        assert store.get_document(PINNED_ID) is not None
    assert (
        parse_frontmatter(
            (corpus / "knowledge/pinned.md").read_text(encoding="utf-8")
        ).frontmatter.mycelium_id
        == PINNED_ID
    )


def test_the_result_names_the_documents_with_no_committed_identity(corpus: Path) -> None:
    result = build(corpus, pin_identity=False)
    assert {path.name for path in result.derived} == {"bare.md", "a.md"}
    assert result.pinned == ()


def test_the_manifest_says_the_corpus_is_not_pinned(corpus: Path) -> None:
    # A build must be explainable from its manifest alone (spec 05 §4.2), and
    # "these identities are not committed anywhere" is not a detail.
    result = build(corpus, pin_identity=False)
    warning = next(w for w in result.manifest.warnings if "identity not pinned" in w)
    assert "2 document(s)" in warning
    assert "--no-pin" in warning


def test_a_fully_pinned_corpus_earns_no_warning(tmp_path: Path) -> None:
    root = repo(tmp_path, {"knowledge/pinned.md": ALREADY_PINNED})
    result = build(root, pin_identity=False)
    assert not any("identity not pinned" in w for w in result.manifest.warnings)
    assert result.derived == ()


# ---------------------------------------------------------------------------
# Measurement is comparable: the same anchors either way
# ---------------------------------------------------------------------------


def _anchors(root: Path) -> set[str]:
    with SqliteStore.open(root, read_only=True) as store:
        return {
            chunk.anchor for doc_id in store.document_ids() for chunk in store.chunks_of(doc_id)
        }


def test_the_anchors_a_judged_case_cites_do_not_move(corpus: Path, tmp_path: Path) -> None:
    """The property that makes `--no-pin` usable for evaluation.

    An anchor is `<doc-path>#<heading-slug-path>/<ordinal>` (ADR-0005) — path and
    structure, no identity — so a judged case written against a pinned build
    still names the same chunk in an unpinned one. If this were false, `--no-pin`
    would make measurement *easier to run* and *impossible to compare*.
    """
    twin = tmp_path / "twin"
    shutil.copytree(corpus, twin)

    build(corpus, pin_identity=False)
    build(twin)

    assert _anchors(corpus) == _anchors(twin)


# ---------------------------------------------------------------------------
# Incremental behaviour
# ---------------------------------------------------------------------------


def test_a_second_no_pin_build_reuses_everything(corpus: Path) -> None:
    build(corpus, pin_identity=False)
    second = build(corpus, pin_identity=False)
    assert second.stats.rebuilt == 0
    assert second.stats.reused == 3
    assert second.derived, "reused documents still report their derived identity"


def test_pinning_after_an_unpinned_build_replaces_the_derived_ids(corpus: Path) -> None:
    # The migration path, and it is not silent: the documents are rewritten, the
    # ids change, and the build says which files to commit.
    unpinned = build(corpus, pin_identity=False)
    pinned = build(corpus)
    assert {path.name for path in pinned.pinned} == {"bare.md", "a.md"}
    assert pinned.manifest.artifact_digests != unpinned.manifest.artifact_digests
    assert not any("identity not pinned" in w for w in pinned.manifest.warnings)
