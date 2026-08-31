# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The incremental compiler (roadmap 3.1, D-008, ADR-0015).

Two claims are enforced here. **Equality:** an incremental build of a mutated
tree is observation-identical to a from-scratch build of the same tree — the
milestone's exit gate, checked after every kind of mutation (edit, add, delete,
rename, touch, config change, duplicate identity, quarantine transitions) and
property-tested over random mutation sequences. **Minimality:** the build only
recompiles what changed — asserted through :class:`BuildStats`, which counts
actual stage executions against cache hits.

The clean-build reference is produced by the same code with empty caches, so
equality here is meaningful only together with gate G6 (the committed golden),
which pins what a clean build produces in the first place.
"""

import json
import os
import shutil
import sqlite3
import string
import tempfile
from contextlib import closing
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from mycelium.build import build
from mycelium.build.cas import cas_get, cas_put
from mycelium.build.dag import (
    build_key,
    decode_chunks_artifact,
    decode_parse_artifact,
    encode_chunks_artifact,
    encode_parse_artifact,
)
from mycelium.chunking import ChunkingPolicy, chunk_document
from mycelium.determinism import observe_build
from mycelium.markdown import parse_markdown
from mycelium.sdk.identity import digest_json
from mycelium.store import SqliteStore
from mycelium.store.schema import META_SCHEMA_VERSION

# Pre-pinned identities: tests edit files the way an editor would — keeping the
# frontmatter `mycelium build` wrote — so identity churn is a scenario tests opt
# into (by dropping the pin), never an accident of a helper.
_IDS = {
    "architecture": "01ARZ3NDEKTSV4RRFFQ69G5FA1",
    "api": "01ARZ3NDEKTSV4RRFFQ69G5FA2",
    "notes": "01ARZ3NDEKTSV4RRFFQ69G5FA3",
    "guide": "01ARZ3NDEKTSV4RRFFQ69G5FA4",
}

CORPUS = {
    "knowledge/verified/architecture.md": (
        f"---\nmycelium_id: {_IDS['architecture']}\n---\n\n"
        "# Architecture\n\nThe event bus routes messages between agents.\n\n"
        "## Retries\n\nExponential backoff with jitter.\n"
    ),
    "knowledge/verified/api.md": (
        f"---\nmycelium_id: {_IDS['api']}\n---\n\n"
        "# API\n\nEndpoints are versioned. See [[architecture]].\n"
    ),
    "knowledge/candidate/notes.md": (
        f"---\nmycelium_id: {_IDS['notes']}\n---\n\n"
        "# Notes\n\nUnreviewed synthesis about the queue.\n"
    ),
    "knowledge/guide.md": (
        f"---\nmycelium_id: {_IDS['guide']}\n---\n\n"
        "# Guide\n\nHow to operate the system day to day.\n"
    ),
}


def repo(tmp_path: Path, files: dict[str, str] | None = None, name: str = "repo") -> Path:
    root = tmp_path / name
    for relative, text in (files or CORPUS).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="") as handle:
            handle.write(text)
    return root


def edit(root: Path, relative: str, text: str) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def assert_equal_to_clean(tmp_path: Path, root: Path, name: str = "fresh") -> None:
    """The exit-gate property: a pristine copy of `root`'s sources, built from
    scratch, observes identically to the incrementally-maintained `root`."""
    fresh = tmp_path / name
    sources = [path for path in sorted(root.rglob("*.md")) if ".mycelium" not in path.parts]
    if (root / "mycelium.toml").exists():
        sources.append(root / "mycelium.toml")
    for path in sources:
        target = fresh / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)  # copy2: mtime is an input (ADR-0009)
    incremental = observe_build(root, pin=False)
    from_scratch = observe_build(fresh, pin=False)
    assert incremental == from_scratch


def journal_events(root: Path) -> list[dict[str, object]]:
    lines = (root / ".mycelium" / "journal.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


# ---------------------------------------------------------------------------
# Minimality: only what changed is recompiled
# ---------------------------------------------------------------------------


def test_first_build_compiles_everything_and_second_reuses_it(tmp_path: Path) -> None:
    root = repo(tmp_path)
    first = build(root)
    assert first.stats.rebuilt == 4
    assert first.stats.reused == 0
    assert first.stats.parsed == 4

    second = build(root)
    assert second.stats.reused == 4
    assert second.stats.rebuilt == 0
    assert second.stats.parsed == 0
    assert second.stats.chunked == 0
    # A no-op build still publishes: fresh snapshot, recorded parentage,
    # identical artifacts (v0's always-publish semantics, kept deliberately).
    assert second.manifest.snapshot_id != first.manifest.snapshot_id
    assert second.manifest.parent_id == first.manifest.snapshot_id
    assert second.manifest.artifact_digests == first.manifest.artifact_digests
    assert second.manifest.counts == first.manifest.counts


def test_single_edit_rebuilds_only_that_document(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root)
    edit(
        root,
        "knowledge/guide.md",
        f"---\nmycelium_id: {_IDS['guide']}\n---\n\n# Guide\n\nRewritten operations guide.\n",
    )

    result = build(root)
    assert result.stats.rebuilt == 1
    assert result.stats.reused == 3
    assert result.stats.parsed == 1  # new content: a real parse, not a cache hit
    assert result.stats.parse_hits == 0
    assert result.stats.removed == 0
    assert_equal_to_clean(tmp_path, root)


def test_touching_a_file_reruns_only_the_assemble_stage(tmp_path: Path) -> None:
    """Same bytes, new mtime: mtime is an input (it becomes ``created_at``,
    ADR-0009), so the document is dirty — but parse and chunk hit the cache."""
    root = repo(tmp_path)
    build(root)
    target = root / "knowledge/guide.md"
    later = int(target.stat().st_mtime) + 100  # integral: datetime keeps microseconds only
    os.utime(target, (later, later))

    result = build(root)
    assert result.stats.rebuilt == 1
    assert result.stats.reused == 3
    assert result.stats.parsed == 0
    assert result.stats.parse_hits == 1
    assert result.stats.chunked == 0
    assert result.stats.chunk_hits == 1
    with SqliteStore.open(root, read_only=True) as store:
        document = store.get_document_by_path("knowledge/guide.md")
        assert document is not None
        assert document.created_at.timestamp() == later
    assert_equal_to_clean(tmp_path, root)


def test_added_and_deleted_documents_diff_cleanly(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root)

    edit(root, "knowledge/verified/runbook.md", "# Runbook\n\nRestart procedure.\n")
    added = build(root)
    assert added.stats.rebuilt == 1
    assert added.stats.reused == 4
    assert added.manifest.counts.documents == 5
    assert_equal_to_clean(tmp_path, root, "fresh-after-add")

    (root / "knowledge/verified/runbook.md").unlink()
    (root / "knowledge/candidate/notes.md").unlink()
    removed = build(root)
    assert removed.stats.removed == 2
    assert removed.stats.rebuilt == 0
    assert removed.stats.reused == 3
    assert removed.manifest.counts.documents == 3
    with SqliteStore.open(root, read_only=True) as store:
        assert store.get_document_by_path("knowledge/candidate/notes.md") is None
        assert not store.search_chunks("Restart")  # the lexical index forgot it too
    assert_equal_to_clean(tmp_path, root, "fresh-after-delete")


def test_rename_hits_the_parse_cache_and_moves_the_anchors(tmp_path: Path) -> None:
    """A rename preserves content and identity but moves every anchor (paths are
    anchor prefixes), so: parse hit, chunk re-run, no removal — one document."""
    root = repo(tmp_path)
    build(root)
    os.replace(root / "knowledge/guide.md", root / "knowledge/verified/guide.md")

    result = build(root)
    assert result.stats.rebuilt == 1
    assert result.stats.reused == 3
    assert result.stats.removed == 0  # same doc_id, new path: moved, not removed
    assert result.stats.parse_hits == 1
    assert result.stats.chunked == 1  # doc_path participates in the chunk key
    with SqliteStore.open(root, read_only=True) as store:
        assert store.get_document_by_path("knowledge/guide.md") is None
        moved = store.get_document_by_path("knowledge/verified/guide.md")
        assert moved is not None
        for chunk in store.chunks_of(moved.doc_id):
            assert chunk.anchor.startswith("knowledge/verified/guide.md#")
    assert_equal_to_clean(tmp_path, root)


def test_swapping_two_paths_is_survived(tmp_path: Path) -> None:
    """The UNIQUE(path) hazard: both documents keep their ids but trade paths."""
    root = repo(tmp_path)
    build(root)
    a, b = root / "knowledge/verified/api.md", root / "knowledge/guide.md"
    spare = root / "knowledge/.swap"
    os.replace(a, spare)
    os.replace(b, a)
    os.replace(spare, b)

    result = build(root)
    assert result.stats.rebuilt == 2
    assert result.stats.removed == 0
    assert_equal_to_clean(tmp_path, root)


# ---------------------------------------------------------------------------
# Config and environment changes invalidate exactly the affected stages
# ---------------------------------------------------------------------------


def test_chunking_change_reuses_every_parse(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root)
    edit(root, "mycelium.toml", "[chunking]\nmax_tokens = 100\ntarget_tokens = 50\n")

    result = build(root)
    assert result.stats.rebuilt == 4  # every chunk key moved with the config slice
    assert result.stats.parsed == 0
    assert result.stats.parse_hits == 4  # …but no document was re-parsed
    assert_equal_to_clean(tmp_path, root)


def test_flipping_config_back_restores_full_cache_hits(tmp_path: Path) -> None:
    """A → B → A: the content-addressed cache still holds A's artifacts, so the
    third build runs no stage at all — the reuse a store-only diff cannot give."""
    root = repo(tmp_path)
    first = build(root)
    edit(root, "mycelium.toml", "[chunking]\nmax_tokens = 100\ntarget_tokens = 50\n")
    build(root)
    (root / "mycelium.toml").unlink()

    third = build(root)
    assert third.stats.parsed == 0
    assert third.stats.chunked == 0
    assert third.stats.chunk_hits == 4
    assert third.manifest.artifact_digests == first.manifest.artifact_digests


def test_editing_the_target_recompiles_every_document(tmp_path: Path) -> None:
    """`target_tokens` steers chunk size since ADR-0023, so the chunk slice carries
    it and editing it must dirty every document — the opposite of what it did while
    the knob was advisory (ADR-0014)."""
    root = repo(tmp_path)
    build(root)
    edit(root, "mycelium.toml", "[chunking]" + chr(10) + "target_tokens = 33" + chr(10))

    result = build(root)
    assert result.stats.rebuilt == 4
    assert result.stats.reused == 0
    assert result.stats.parse_hits == 4  # a size knob is not a parsing knob
    assert_equal_to_clean(tmp_path, root)


def test_namespace_change_invalidates_chunks_but_not_parses(tmp_path: Path) -> None:
    root = repo(tmp_path)
    first = build(root)

    result = build(root, namespace="team")
    assert result.stats.rebuilt == 4
    assert result.stats.parse_hits == 4  # parsing is namespace-blind
    assert result.stats.chunked == 4  # chunk records carry the namespace
    assert result.manifest.config_digest != first.manifest.config_digest


# ---------------------------------------------------------------------------
# Identity conflicts and quarantine transitions
# ---------------------------------------------------------------------------


def test_a_new_duplicate_identity_evicts_like_a_clean_build(tmp_path: Path) -> None:
    """First claim in path order wins — even when the loser was happily indexed
    and the thief is the newcomer. Exactly what a from-scratch build decides."""
    root = repo(tmp_path)
    build(root)
    original = root / "knowledge/verified/api.md"
    thief = root / "knowledge/verified/aaa-copy.md"  # sorts before api.md
    shutil.copy2(original, thief)  # same pinned mycelium_id, twice

    result = build(root)
    assert result.stats.quarantined == 1
    assert result.stats.rebuilt == 1  # the thief compiles under the stolen id
    assert result.stats.removed == 0  # the id is still live — just moved
    assert any("duplicate mycelium_id" in warning for warning in result.manifest.warnings)
    assert any("api.md" in warning for warning in result.manifest.warnings)
    with SqliteStore.open(root, read_only=True) as store:
        assert store.get_document_by_path("knowledge/verified/api.md") is None
        assert store.get_document_by_path("knowledge/verified/aaa-copy.md") is not None
    assert_equal_to_clean(tmp_path, root)


def test_quarantine_round_trip(tmp_path: Path) -> None:
    """Healthy → broken → healed: rows leave the store while a document is
    quarantined and come back — through the parse cache — once it is fixed."""
    root = repo(tmp_path)
    build(root)
    healthy = (root / "knowledge/guide.md").read_text(encoding="utf-8")

    # Declared frontmatter with an unusable identity raises (identity is never
    # guessed) — the quarantine case, unlike a mere thematic break opening.
    edit(root, "knowledge/guide.md", "---\nmycelium_id: not-a-valid-ulid\n---\n\n# Guide\n")
    broken = build(root)
    assert broken.stats.quarantined == 1
    assert broken.manifest.counts.documents == 3
    assert any("guide.md" in warning for warning in broken.manifest.warnings)
    with SqliteStore.open(root, read_only=True) as store:
        assert store.get_document_by_path("knowledge/guide.md") is None
    assert_equal_to_clean(tmp_path, root, "fresh-broken")

    edit(root, "knowledge/guide.md", healthy)
    healed = build(root)
    assert healed.stats.quarantined == 0
    assert healed.stats.rebuilt == 1
    assert healed.stats.parse_hits == 1  # original content: the cache remembers
    assert healed.manifest.counts.documents == 4
    assert_equal_to_clean(tmp_path, root, "fresh-healed")


# ---------------------------------------------------------------------------
# The cache is an optimization, never an authority
# ---------------------------------------------------------------------------


def test_clean_build_bypasses_the_cache_and_agrees(tmp_path: Path) -> None:
    root = repo(tmp_path)
    incremental = build(root)

    result = build(root, clean=True)
    assert result.stats.rebuilt == 4
    assert result.stats.parsed == 4
    assert result.stats.parse_hits == 0
    assert result.manifest.artifact_digests == incremental.manifest.artifact_digests


def test_a_deleted_cas_tree_heals_itself(tmp_path: Path) -> None:
    root = repo(tmp_path)
    first = build(root)
    shutil.rmtree(root / ".mycelium" / "cas")
    target = root / "knowledge/guide.md"
    later = target.stat().st_mtime + 100
    os.utime(target, (later, later))  # dirty enough to need the parse artifact

    result = build(root)
    assert result.stats.parsed == 1  # the row was there; the blob was not
    assert result.stats.parse_hits == 0
    assert result.manifest.artifact_digests["chunks"] == first.manifest.artifact_digests["chunks"]


def test_a_corrupted_cas_blob_is_discarded_not_believed(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root)
    blobs = sorted((root / ".mycelium" / "cas").rglob("*"))
    for blob in blobs:
        if blob.is_file():
            blob.write_bytes(b"not the bytes this name promises")
    target = root / "knowledge/guide.md"
    later = target.stat().st_mtime + 100
    os.utime(target, (later, later))

    result = build(root)
    assert result.stats.parsed == 1
    assert result.stats.parse_hits == 0
    assert_equal_to_clean(tmp_path, root)


def test_a_foreign_store_version_is_rebuilt_in_place(tmp_path: Path) -> None:
    """The upgrade path from any earlier store: the writer recreates and the
    build repopulates — no manual deletion, no reinterpretation (D-016)."""
    root = repo(tmp_path)
    build(root)
    with closing(sqlite3.connect(root / ".mycelium" / "store.db")) as connection, connection:
        connection.execute(
            "UPDATE meta SET value = 'mycelium/store/v0' WHERE key = ?", (META_SCHEMA_VERSION,)
        )

    result = build(root)
    assert result.stats.rebuilt == 4  # doc_state went with the foreign store
    assert result.manifest.counts.documents == 4
    assert any(event["event"] == "store.recreated" for event in journal_events(root))
    assert_equal_to_clean(tmp_path, root)


# ---------------------------------------------------------------------------
# Build keys and artifact envelopes
# ---------------------------------------------------------------------------


def test_every_build_key_component_matters() -> None:
    base = {
        "stage": "parse",
        "impl_version": 1,
        "inputs": {"source": "sha256:aa"},
        "config_slice": {"max_tokens": 800},
        "schema_version": "mycelium/kir/v0",
    }
    key = build_key(**base)  # type: ignore[arg-type]
    assert key == build_key(**base)  # type: ignore[arg-type]
    variations: list[dict[str, object]] = [
        {**base, "stage": "chunk"},
        {**base, "impl_version": 2},
        {**base, "inputs": {"source": "sha256:bb"}},
        {**base, "config_slice": {"max_tokens": 400}},
        {**base, "schema_version": "mycelium/kir/v1"},
    ]
    keys = {build_key(**variation) for variation in variations}  # type: ignore[arg-type]
    assert len(keys) == 5
    assert key not in keys


def test_artifact_envelopes_round_trip(tmp_path: Path) -> None:
    """decode(encode(x)) preserves the records — and re-encoding is byte-stable,
    so a cached artifact's digest never depends on which build wrote it."""
    parsed = parse_markdown(
        "---\ntitle: Envelope\ntags: [a, b]\n---\n\n# Envelope\n\nBody with [[link]].\n",
        doc_id="01HZZZZZZZZZZZZZZZZZZZZZZZ",
    )
    blob = encode_parse_artifact(parsed)
    decoded = decode_parse_artifact(blob)
    assert decoded.kir == parsed.kir
    assert decoded.frontmatter == parsed.frontmatter
    assert decoded.warnings == parsed.warnings
    assert encode_parse_artifact(decoded) == blob

    digest = cas_put(tmp_path, blob)
    assert cas_get(tmp_path, digest) == blob

    chunks = chunk_document(parsed.kir, doc_path="a.md", policy=ChunkingPolicy())
    chunk_blob = encode_chunks_artifact(chunks)
    assert decode_chunks_artifact(chunk_blob) == chunks
    assert encode_chunks_artifact(decode_chunks_artifact(chunk_blob)) == chunk_blob


def test_manifest_digests_fold_per_document_digests_in_path_order(tmp_path: Path) -> None:
    """The ADR-0015 construction, asserted literally against doc_state."""
    root = repo(tmp_path)
    manifest = build(root).manifest
    with SqliteStore.open(root) as store:
        states = store.doc_states()  # ordered by path
    assert manifest.artifact_digests["documents"] == digest_json(
        [state.document_digest for state in states]
    )
    assert manifest.artifact_digests["chunks"] == digest_json(
        [state.chunks_digest for state in states]
    )


# ---------------------------------------------------------------------------
# The property, generalized: any mutation sequence, same observation
# ---------------------------------------------------------------------------

_WORDS = st.lists(
    st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=8), min_size=1, max_size=12
)
_DOC_NAMES = ("alpha.md", "beta.md", "gamma.md")


@st.composite
def _mutations(draw: st.DrawFn) -> list[tuple[str, str, str]]:
    """(action, relative path, body) triples; body is unused for deletes."""
    steps = draw(st.integers(min_value=1, max_value=3))
    result: list[tuple[str, str, str]] = []
    for _ in range(steps):
        action = draw(st.sampled_from(["write", "delete"]))
        name = draw(st.sampled_from(_DOC_NAMES))
        body = " ".join(draw(_WORDS))
        result.append((action, f"knowledge/{name}", body))
    return result


@settings(max_examples=8, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(mutations=_mutations())
def test_any_mutation_sequence_stays_equal_to_clean(
    mutations: list[tuple[str, str, str]],
) -> None:
    with tempfile.TemporaryDirectory() as scratch:
        tmp_path = Path(scratch)
        root = repo(tmp_path, {"knowledge/alpha.md": "# Alpha\n\nSeed content.\n"})
        build(root)
        for action, relative, body in mutations:
            if action == "delete":
                (root / relative).unlink(missing_ok=True)
            else:
                edit(root, relative, f"# Doc\n\n{body}\n")
            build(root)
        assert_equal_to_clean(tmp_path, root)
