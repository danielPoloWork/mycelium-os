# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The embedder, the model registry, and the vector stage (roadmap 3.3, ADR-0017).

Split in two by what each part needs. Everything about *policy* — provider
resolution, the pinned registry, the refusal to reach the network unasked, the
degraded build, incremental embedding, `--require-vectors` — runs everywhere,
using a deterministic stand-in for the model.

The tests that need the 133 MB model itself are marked `embeddings` and skip when
it is not on this machine, which is always in CI. They exist to pin the
properties a stand-in cannot vouch for: that pooling and normalisation match the
model's published contract, that the query prefix is applied, and that related
sentences really do land closer together than unrelated ones. Their numbers are
reproduced by hand and recorded in ADR-0017 rather than asserted from a machine
that cannot run them.
"""

import os
from pathlib import Path

import pytest

from fakes import FakeEmbedder
from mycelium.build import build
from mycelium.config import EmbeddingConfig, MyceliumConfig, RetrievalConfig
from mycelium.embedding import (
    DEFAULT_MODEL_ID,
    MODELS,
    Embedder,
    EmbedderUnavailableError,
    LocalOnnxEmbedder,
    build_embedder,
    model_spec,
    resolve_model,
)
from mycelium.embedding.models import CACHE_ENV_VAR, cache_root
from mycelium.retrieval import search
from mycelium.store import SqliteStore

CORPUS = {
    "knowledge/bus.md": "# Event Bus\n\nThe bus routes messages between agents.\n",
    "knowledge/retries.md": "# Retries\n\nFailed deliveries retry with exponential backoff.\n",
}


def repo(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    root = tmp_path / "repo"
    for relative, text in (files or CORPUS).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


def with_model(root: Path, directory: Path) -> MyceliumConfig:
    """A configuration pointing the embedder at an explicit model directory."""
    return MyceliumConfig(embedding=EmbeddingConfig(model_path=str(directory)))


# ---------------------------------------------------------------------------
# The protocol and the provider seam
# ---------------------------------------------------------------------------


def test_the_fake_satisfies_the_published_protocol() -> None:
    """If a test double cannot satisfy it, neither can a plugin (D-023)."""
    assert isinstance(FakeEmbedder(), Embedder)


def test_provider_none_means_no_vectors_not_a_failure() -> None:
    assert build_embedder(provider="none", model_id=DEFAULT_MODEL_ID) is None


def test_an_unknown_provider_is_refused_by_name() -> None:
    with pytest.raises(EmbedderUnavailableError, match="local-onnx"):
        build_embedder(provider="openai", model_id="text-embedding-3-large")


def test_an_unknown_model_lists_what_this_build_knows() -> None:
    with pytest.raises(EmbedderUnavailableError, match=DEFAULT_MODEL_ID):
        model_spec("some-other-model")


# ---------------------------------------------------------------------------
# The pinned registry and the local cache (D-017)
# ---------------------------------------------------------------------------


def test_every_registered_file_is_pinned_by_digest_and_size() -> None:
    """A model download is a supply-chain event; an unpinned one is a vulnerability."""
    for spec in MODELS.values():
        assert spec.files
        for item in spec.files:
            assert item.url.startswith("https://")
            assert len(item.sha256) == 64
            assert int(item.sha256, 16) >= 0  # hex, not a placeholder
            assert item.size > 0
        assert spec.model_file.name.endswith(".onnx")
        assert spec.tokenizer_file.name == "tokenizer.json"
        assert spec.license
        assert spec.dim > 0


def test_a_missing_model_never_reaches_the_network_unasked(tmp_path: Path) -> None:
    """The whole of D-017's posture, in one assertion: no consent, no download."""
    with pytest.raises(EmbedderUnavailableError) as caught:
        resolve_model(model_spec(DEFAULT_MODEL_ID), allow_download=False)
    message = str(caught.value)
    assert "allow_download" in message  # names the setting that would permit it
    assert "model_path" in message  # and the alternative that needs no network
    assert "MB" in message  # and how much it would cost
    assert "without vectors" in message  # and what happens meanwhile


def test_model_path_short_circuits_the_cache_and_the_network(tmp_path: Path) -> None:
    directory = tmp_path / "vendored"
    directory.mkdir()
    for item in model_spec(DEFAULT_MODEL_ID).files:
        (directory / item.name).write_bytes(b"not really a model, but present")

    assert resolve_model(model_spec(DEFAULT_MODEL_ID), model_path=directory) == directory


def test_an_incomplete_model_path_says_what_is_missing(tmp_path: Path) -> None:
    directory = tmp_path / "half"
    directory.mkdir()
    (directory / "tokenizer.json").write_bytes(b"{}")

    with pytest.raises(EmbedderUnavailableError, match="model.onnx"):
        resolve_model(model_spec(DEFAULT_MODEL_ID), model_path=directory)


def test_the_cache_lives_outside_the_repository(tmp_path: Path) -> None:
    os.environ.pop(CACHE_ENV_VAR, None)
    try:
        root = cache_root()
    finally:
        os.environ[CACHE_ENV_VAR] = str(tmp_path)
    assert root.is_absolute()
    assert "mycelium" in root.parts
    assert Path.cwd() not in root.parents


# ---------------------------------------------------------------------------
# The vector stage in a build
# ---------------------------------------------------------------------------


def _build_with(root: Path, embedder: Embedder, **kwargs: object) -> None:
    """Build `root` with a supplied embedder, bypassing provider resolution."""
    import mycelium.build.orchestrator as orchestrator

    original = orchestrator._resolve_embedder
    orchestrator._resolve_embedder = lambda config, *, require_vectors: (embedder, None)  # type: ignore[assignment]
    try:
        build(root, **kwargs)  # type: ignore[arg-type]
    finally:
        orchestrator._resolve_embedder = original  # type: ignore[assignment]


def test_a_build_without_an_embedder_degrades_and_explains(tmp_path: Path) -> None:
    """Spec 02 §4.3: publish without vectors rather than failing the lexical index."""
    root = repo(tmp_path)
    result = build(root)

    assert result.manifest.degraded == ("vectors",)
    assert result.manifest.embedding is None
    assert result.manifest.counts.vectors == 0
    assert result.stats.embedded == 0
    assert any("allow_download" in reason for reason in result.degraded_reasons)
    with SqliteStore.open(root, read_only=True) as store:
        assert store.search_chunks("backoff")  # lexical search is untouched


def test_require_vectors_turns_the_degradation_into_a_failure(tmp_path: Path) -> None:
    root = repo(tmp_path)
    with pytest.raises(EmbedderUnavailableError):
        build(root, require_vectors=True)


def test_provider_none_publishes_cleanly_without_vectors(tmp_path: Path) -> None:
    """Choosing lexical-only is not a degradation, and must not be reported as one."""
    root = repo(tmp_path)
    config = MyceliumConfig(embedding=EmbeddingConfig(provider="none"))
    result = build(root, config=config)

    assert result.manifest.degraded == ()
    assert result.manifest.embedding is None
    assert result.degraded_reasons == ()


def test_vectors_are_produced_recorded_and_searchable(tmp_path: Path) -> None:
    embedder = FakeEmbedder()
    root = repo(tmp_path)
    _build_with(root, embedder)

    with SqliteStore.open(root, read_only=True) as store:
        counts = store.counts()
        assert counts["vectors"] == counts["chunks"]
        assert store.vector_counts() == {embedder.model_id: counts["chunks"]}
        outcome = search(
            store,
            "messages between agents",
            config=RetrievalConfig(profile="hybrid"),
            embedder=embedder,
        )
        assert outcome.legs == ("lexical", "vector")


def test_the_manifest_declares_the_stage_non_deterministic(tmp_path: Path) -> None:
    """Spec 02 §4.1 allows a non-deterministic stage *if it says so*."""
    embedder = FakeEmbedder()
    root = repo(tmp_path)
    _build_with(root, embedder)

    with SqliteStore.open(root, read_only=True) as store:
        current = store.get_meta("current_snapshot")
    from mycelium.build import read_manifest

    manifest = read_manifest(root / ".mycelium", str(current))
    assert manifest.embedding is not None
    assert manifest.embedding.model_id == embedder.model_id
    assert manifest.embedding.dim == embedder.dim
    assert manifest.embedding.provider == embedder.provider
    assert manifest.degraded == ()


def test_unchanged_text_is_never_re_embedded(tmp_path: Path) -> None:
    """The D-013 keying, observed: `(chunk_digest, model_id)` is the work list."""
    embedder = FakeEmbedder()
    root = repo(tmp_path)
    _build_with(root, embedder)
    with SqliteStore.open(root, read_only=True) as store:
        first = store.counts()["vectors"]

    # Add a document; only its chunks are new text.
    (root / "knowledge" / "extra.md").write_text("# Extra\n\nA new section.\n", encoding="utf-8")
    import mycelium.build.orchestrator as orchestrator

    original = orchestrator._resolve_embedder
    orchestrator._resolve_embedder = lambda config, *, require_vectors: (embedder, None)  # type: ignore[assignment]
    try:
        result = build(root)
    finally:
        orchestrator._resolve_embedder = original  # type: ignore[assignment]

    assert result.stats.embedded == 1  # the new chunk, and nothing else
    with SqliteStore.open(root, read_only=True) as store:
        assert store.counts()["vectors"] == first + 1


def test_vectors_of_deleted_chunks_are_collected(tmp_path: Path) -> None:
    """Chunk digests change when text does; without pruning, the table only grows."""
    embedder = FakeEmbedder()
    root = repo(tmp_path)
    _build_with(root, embedder)
    with SqliteStore.open(root, read_only=True) as store:
        before = store.counts()["vectors"]

    (root / "knowledge" / "retries.md").unlink()
    _build_with(root, embedder)

    with SqliteStore.open(root, read_only=True) as store:
        counts = store.counts()
    assert counts["vectors"] < before
    assert counts["vectors"] == counts["chunks"]


def test_a_snapshot_built_before_embeddings_gains_vectors_on_the_next_build(
    tmp_path: Path,
) -> None:
    """Enabling the embedder later must embed the *existing* corpus, not only new text."""
    root = repo(tmp_path)
    build(root, config=MyceliumConfig(embedding=EmbeddingConfig(provider="none")))
    with SqliteStore.open(root, read_only=True) as store:
        assert store.counts()["vectors"] == 0
        chunks = store.counts()["chunks"]

    embedder = FakeEmbedder()
    _build_with(root, embedder)

    with SqliteStore.open(root, read_only=True) as store:
        assert store.counts()["vectors"] == chunks


# ---------------------------------------------------------------------------
# The real model (skipped without it)
# ---------------------------------------------------------------------------


@pytest.mark.embeddings
def test_the_local_model_loads_and_declares_itself(local_model: Path) -> None:
    embedder = LocalOnnxEmbedder.load(model_id=DEFAULT_MODEL_ID, model_path=local_model)

    assert isinstance(embedder, Embedder)
    assert embedder.model_id == DEFAULT_MODEL_ID
    assert embedder.provider == "local-onnx"
    assert embedder.dim == 384
    # The honest declaration: ONNX picks kernels by instruction set, so identity
    # across machines is not something this stage can promise (ADR-0017).
    assert embedder.deterministic is False


@pytest.mark.embeddings
def test_embeddings_are_unit_vectors_of_the_pinned_dimension(local_model: Path) -> None:
    embedder = LocalOnnxEmbedder.load(model_id=DEFAULT_MODEL_ID, model_path=local_model)
    vectors = embedder.embed_documents(["The bus routes messages.", "Retry with backoff."])

    assert len(vectors) == 2
    for vector in vectors:
        assert len(vector) == 384
        assert sum(value * value for value in vector) == pytest.approx(1.0, abs=1e-4)


@pytest.mark.embeddings
def test_related_text_lands_closer_than_unrelated_text(local_model: Path) -> None:
    """The property that makes a vector leg worth having at all."""
    embedder = LocalOnnxEmbedder.load(model_id=DEFAULT_MODEL_ID, model_path=local_model)
    bus, broker, cat = embedder.embed_documents(
        [
            "The event bus routes messages between agents.",
            "Messages travel between services over the broker.",
            "The cat is asleep on the sofa.",
        ]
    )

    def cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert cosine(bus, broker) > cosine(bus, cat) + 0.2


@pytest.mark.embeddings
def test_the_query_side_applies_the_models_instruction_prefix(local_model: Path) -> None:
    """Asymmetric models expect it; skipping it is a silent recall loss."""
    embedder = LocalOnnxEmbedder.load(model_id=DEFAULT_MODEL_ID, model_path=local_model)
    question = "how are messages delivered between agents?"

    as_query = embedder.embed_query(question)
    as_passage = embedder.embed_documents([question])[0]

    assert as_query != as_passage
    prefixed = embedder.embed_documents([model_spec(DEFAULT_MODEL_ID).query_prefix + question])[0]
    assert as_query == pytest.approx(prefixed, abs=1e-6)


@pytest.mark.embeddings
def test_repeated_inference_on_this_machine_is_identical(local_model: Path) -> None:
    """Bit-identical *here* — which is why the declaration is about *anywhere*."""
    embedder = LocalOnnxEmbedder.load(model_id=DEFAULT_MODEL_ID, model_path=local_model)
    text = "Exponential backoff with jitter controls retries."
    assert embedder.embed_documents([text])[0] == embedder.embed_documents([text])[0]


@pytest.mark.embeddings
def test_a_real_build_embeds_and_serves_hybrid_results(tmp_path: Path, local_model: Path) -> None:
    """End to end with the shipped default: build, embed, then fuse both legs."""
    root = repo(tmp_path)
    result = build(root, config=with_model(root, local_model))

    assert result.manifest.degraded == ()
    assert result.manifest.embedding is not None
    assert result.manifest.embedding.deterministic is False
    assert result.stats.embedded == result.manifest.counts.chunks

    embedder = LocalOnnxEmbedder.load(model_id=DEFAULT_MODEL_ID, model_path=local_model)
    with SqliteStore.open(root, read_only=True) as store:
        outcome = search(
            store,
            "how do failed deliveries get another chance?",
            config=RetrievalConfig(profile="hybrid"),
            embedder=embedder,
        )
    assert outcome.legs == ("lexical", "vector")
    assert outcome.hits
