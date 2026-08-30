# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Build orchestrator: content-addressed, incremental, torn-free (D-008, ADR-0015).

The v0 orchestrator recompiled every document every build. This one runs the
spec 02 §4.2 algorithm: plan the corpus, detect what is dirty, recompile only
that through cache-aware stages, and fold the snapshot manifest from
per-document artifact digests. What it inherits from v0 **unchanged** is the
part ADR-0009 fixed forever — the publication and crash-safety semantics::

    acquire .mycelium/lock                 # exactly one writer (BuildLock)
    plan: read + pin + digest every file   # per-doc source digests (spec 02 §4.2)
    compile dirty docs                     # parse → chunk cached (CAS + build_cache),
                                           # assemble recomputed (mtime is its input)
    BEGIN IMMEDIATE                        # readers keep the old committed state
      delete removed + displaced + rebuilt rows
      insert rebuilt rows + doc_state + cache index
      write snapshots/<ulid>.json          # manifest exists before anything names it
      meta[current_snapshot] = <ulid>
    COMMIT                                 # data + pointer become visible atomically
    swap CURRENT (tmp → replace → fsync)   # the cross-process publish instant
    release lock

Dirty detection is deliberately conservative: every discovered file is read and
digested every build — the fast path skips *parsing, chunking, and record
construction*, never the read. An mtime-trust shortcut would make "clean" a
guess (renames preserve mtimes; pinned-mtime trees defeat it entirely), and a
false "clean" is the one failure a determinism product cannot afford. Watch
mode (roadmap 3.5) is the place where event-driven read-skipping can be argued
safely. A document is untouched only when its source digest, its mtime (which
ADR-0009 turns into ``created_at``), and the build environment digest all match
its ``doc_state`` row; a matching digest under a new mtime reruns only the
assemble stage.

The manifest's corpus digests are folded from per-document artifact digests
(``digest_json`` over the path-ordered digest list) rather than from the full
record set, so manifest assembly costs O(changed), not O(corpus) — the
construction ADR-0015 records, and the reason the G6 golden was re-blessed.

Identity pinning is the build's **only** write into tier 2, per the frontmatter
ownership table (spec 03 §3). The write is textual insertion that preserves
every other byte of the file — never a YAML re-serialization.
"""

import platform
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Final

from mycelium.__about__ import __version__
from mycelium.build.cas import cas_get, cas_path, cas_put
from mycelium.build.dag import (
    BuildEnv,
    decode_chunks_artifact,
    decode_parse_artifact,
    encode_chunks_artifact,
    encode_document_artifact,
    encode_parse_artifact,
)
from mycelium.build.lock import DEFAULT_STALE_AFTER_S, BuildLock
from mycelium.build.publish import (
    append_journal,
    read_current,
    swap_current,
    write_manifest,
)
from mycelium.build.snapshots import record_snapshot_state
from mycelium.chunking import ChunkingPolicy, chunk_document
from mycelium.config import MyceliumConfig, load_config
from mycelium.embedding import Embedder, EmbedderUnavailableError, build_embedder
from mycelium.markdown import Frontmatter, MarkdownDocument, parse_markdown
from mycelium.markdown.frontmatter import DELIMITER, parse_frontmatter
from mycelium.sdk.identity import digest_json, digest_text, new_ulid
from mycelium.sdk.schema import (
    RECORD_MODELS,
    SNAPSHOT_ARTIFACT_CLASSES,
    record_schema_version,
)
from mycelium.sdk.types import (
    Chunk,
    Document,
    DocumentStats,
    EmbeddingInfo,
    KirNode,
    NodeKind,
    Provenance,
    ProvenanceOrigin,
    Sha256Digest,
    SnapshotCounts,
    SnapshotManifest,
    Toolchain,
    TrustClass,
    Verification,
    VerificationStatus,
)
from mycelium.store import STORE_DIRNAME, DocState, SqliteStore
from mycelium.store.schema import META_CURRENT_SNAPSHOT

__all__ = ["BuildResult", "BuildStats", "build"]

_LINK_KINDS: Final = frozenset({NodeKind.LINK, NodeKind.WIKILINK, NodeKind.EMBED})
_STATUS_FOLDERS: Final = {
    "candidate": VerificationStatus.CANDIDATE,
    "evidence": VerificationStatus.EVIDENCE,
    "verified": VerificationStatus.VERIFIED,
}
_BOM: Final = "﻿"
_EMBED_BATCH: Final = 64
"""Chunks per embedder call. Bounded so a large corpus does not build one giant
tensor, and so the build lock's heartbeat is refreshed while a cold embed runs."""


@dataclass(frozen=True, slots=True)
class BuildStats:
    """How much of the corpus one build actually recompiled (ADR-0015).

    ``reused + rebuilt + quarantined`` accounts for every discovered document;
    ``parsed + parse_hits`` (and the chunk pair) account for every rebuilt one.
    The stats are diagnostics — they are journaled and reported, never part of
    the snapshot manifest, because two correct builds of the same tree may
    legitimately differ in how much they reused.
    """

    documents: int
    reused: int
    rebuilt: int
    removed: int
    quarantined: int
    parsed: int
    parse_hits: int
    chunked: int
    chunk_hits: int
    embedded: int = 0
    """Chunks sent to the embedder — 0 when vectors are off, cached, or unavailable."""


@dataclass(frozen=True, slots=True)
class BuildResult:
    """What one build produced."""

    manifest: SnapshotManifest
    manifest_path: Path
    pinned: tuple[Path, ...]
    """Source files that received a ``mycelium_id`` this build (commit them)."""
    stats: BuildStats
    degraded_reasons: tuple[str, ...] = ()
    """Why each ``manifest.degraded`` flag is set — operator-facing, and actionable."""


class _Outcome(Enum):
    """What the plan decided about one discovered file."""

    PENDING = "pending"  # read fine; dirty/clean not yet decided
    REUSED = "reused"  # untouched — doc_state row is the artifact record
    REBUILT = "rebuilt"  # at least one stage ran
    QUARANTINED = "quarantined"  # unreadable, unparseable, or a duplicate identity


@dataclass
class _Entry:
    """One discovered file's journey through the build."""

    path: Path
    doc_path: str
    outcome: _Outcome
    doc_id: str = ""
    raw: str = ""
    source_digest: str = ""
    mtime: datetime | None = None
    mtime_key: str = ""
    prev: DocState | None = None
    warnings: tuple[str, ...] = ()
    document: Document | None = None
    chunks: tuple[Chunk, ...] = ()
    document_digest: str = ""
    chunks_digest: str = ""


@dataclass
class _Timer:
    """Accumulates per-stage wall time in integer milliseconds."""

    started: float = field(default_factory=time.monotonic)
    stages: dict[str, int] = field(default_factory=dict)
    _mark: float = field(default_factory=time.monotonic)

    def lap(self, stage: str) -> None:
        now = time.monotonic()
        self.stages[stage] = self.stages.get(stage, 0) + int((now - self._mark) * 1000)
        self._mark = now

    def total(self) -> dict[str, int]:
        return {"total": int((time.monotonic() - self.started) * 1000), **self.stages}


# ---------------------------------------------------------------------------
# Discovery (v0 rule, ADR-0009)
# ---------------------------------------------------------------------------


def _discover(root: Path, knowledge_dir: str = "knowledge") -> list[Path]:
    """The documents a build compiles, in deterministic (sorted) order.

    The authored tree is `knowledge_dir` when it exists (spec 02 §3, configurable
    via ``[project] knowledge_dir``); otherwise the whole root is scanned so a
    plain docs repository gets value with zero layout ceremony (TTFV, doc 01 §3).
    Dot-prefixed directories are never entered — that one rule excludes
    ``.mycelium``, ``.git``, and editor litter.
    """
    base = root / knowledge_dir
    scope = base if base.is_dir() else root
    found = [
        path
        for path in scope.rglob("*.md")
        if not any(part.startswith(".") for part in path.relative_to(root).parts)
    ]
    return sorted(found, key=lambda path: path.relative_to(root).as_posix())


# ---------------------------------------------------------------------------
# Identity pinning (the build's only tier-2 write)
# ---------------------------------------------------------------------------


def _ensure_identity(text: str) -> tuple[str, str, bool]:
    """Return ``(text, doc_id, pinned)``, minting and inserting an id if needed.

    A fresh ``mycelium_id`` is inserted textually — never via YAML
    re-serialization — preserving every other byte: the file's own newline
    convention is kept, and a BOM stays where it is.
    """
    bom, body = (_BOM, text[len(_BOM) :]) if text.startswith(_BOM) else ("", text)
    parsed = parse_frontmatter(body)
    if parsed.frontmatter.mycelium_id is not None:
        return text, parsed.frontmatter.mycelium_id, False

    doc_id = new_ulid()
    newline = "\r\n" if "\r\n" in body else "\n"
    line = f"mycelium_id: {doc_id}"
    if parsed.body_line_offset > 0:
        # A real frontmatter block: insert directly after the opening fence line.
        head, _, tail = body.partition("\n")
        new_body = f"{head}\n{line}{newline}{tail}"
    else:
        new_body = f"{DELIMITER}{newline}{line}{newline}{DELIMITER}{newline}{newline}{body}"
    return bom + new_body, doc_id, True


# ---------------------------------------------------------------------------
# The assemble stage (Document-record derivation)
# ---------------------------------------------------------------------------


def _verification_status(relative: Path) -> VerificationStatus:
    """Folder-derived status (D-021). Outside the scheme, authored docs are the
    trusted default lane: the folders exist to gate *synthesized* content."""
    for part in relative.parts:
        status = _STATUS_FOLDERS.get(part)
        if status is not None:
            return status
    return VerificationStatus.VERIFIED


def _title_of(frontmatter: Frontmatter, nodes: tuple[KirNode, ...], path: Path) -> str:
    """Title precedence (spec 03 §3): frontmatter, else the first H1, else the stem."""
    if frontmatter.title:
        return frontmatter.title
    for node in nodes:
        if node.kind is NodeKind.HEADING and node.level == 1 and node.text:
            return node.text
    return path.stem


def _verification_of(
    frontmatter: Frontmatter, warnings: list[str], path: str
) -> Verification | None:
    by, at, grounding = frontmatter.verified_by, frontmatter.verified_at, frontmatter.grounding
    if by is None and at is None and grounding is None:
        return None
    if by is None or at is None or grounding is None:
        warnings.append(
            f"{path}: partial verification block ignored (needs verified_by, "
            "verified_at, and grounding together)"
        )
        return None
    return Verification(verified_by=by, verified_at=at, grounding=grounding)


def _assemble(
    parsed: MarkdownDocument,
    chunks: tuple[Chunk, ...],
    *,
    path: Path,
    relative: Path,
    doc_id: str,
    namespace: str,
    mtime: datetime,
) -> tuple[Document, tuple[str, ...]]:
    """Derive the Document record — cheap arithmetic over the cached stages' output.

    Deliberately uncached (ADR-0015): one of its inputs is the file's mtime,
    which becomes ``created_at``/``updated_at`` (ADR-0009) and is exactly the
    input that most often changes alone.
    """
    doc_path = relative.as_posix()
    frontmatter = parsed.frontmatter
    warnings = [f"{doc_path}: {warning}" for warning in parsed.warnings]

    origin = frontmatter.origin or ProvenanceOrigin.AUTHORED
    provenance = Provenance(
        origin=origin,
        source_uri=frontmatter.source,
        source_trust=frontmatter.source_trust,
    )
    document = Document(
        doc_id=doc_id,
        path=doc_path,
        title=_title_of(frontmatter, parsed.kir.nodes, path),
        namespace=namespace,
        collection=frontmatter.collection,
        tags=frontmatter.tags,
        content_digest=parsed.kir.source_digest,
        # v0 mapping: ingested origins carry ingested trust; everything else is
        # the authored layer. The curated/external classes arrive with ingestion
        # (milestone 4), which owns the real assignment.
        trust_class=(
            TrustClass.INGESTED if origin is ProvenanceOrigin.INGESTED else TrustClass.AUTHORED
        ),
        verification_status=_verification_status(relative),
        verification=_verification_of(frontmatter, warnings, doc_path),
        provenance=provenance,
        stats=DocumentStats(
            tokens=sum(chunk.tokens for chunk in chunks),
            headings=sum(1 for node in parsed.kir.nodes if node.kind is NodeKind.HEADING),
            chunks=len(chunks),
            links_out=sum(1 for node in parsed.kir.nodes if node.kind in _LINK_KINDS),
        ),
        created_at=mtime,
        updated_at=mtime,
    )
    return document, tuple(warnings)


# ---------------------------------------------------------------------------
# Cached stages (spec 02 §4.1: key → CAS blob, miss → run)
# ---------------------------------------------------------------------------


def _cached_blob(store: SqliteStore, mycelium_dir: Path, key: str) -> tuple[str, str] | None:
    """Look one build key up in the two-level cache; ``None`` is a plain miss.

    A row without its blob, a blob that fails its own integrity check, or a blob
    whose records no longer validate are all the same thing to the caller — run
    the stage. The last case is journaled: it means an artifact changed shape
    under an unchanged key, which is a stage-version bump someone owes.
    """
    digest = store.cache_get(key)
    if digest is None:
        return None
    blob = cas_get(mycelium_dir, digest)
    if blob is None:
        return None
    return digest, blob


def _stage_parse(
    store: SqliteStore,
    mycelium_dir: Path,
    env: BuildEnv,
    entry: _Entry,
    *,
    use_cache: bool,
    cache_rows: list[tuple[str, str]],
) -> tuple[MarkdownDocument, Sha256Digest, bool]:
    key = env.parse_key(doc_id=entry.doc_id, source_digest=entry.source_digest)
    if use_cache:
        cached = _cached_blob(store, mycelium_dir, key)
        if cached is not None:
            digest, blob = cached
            try:
                return decode_parse_artifact(blob), digest, True
            except Exception:  # noqa: BLE001 - a bad cache heals; it never quarantines
                append_journal(mycelium_dir, "cache.invalid", stage="parse", build_key=key)
    parsed = parse_markdown(entry.raw, doc_id=entry.doc_id)
    digest = cas_put(mycelium_dir, encode_parse_artifact(parsed))
    cache_rows.append((key, digest))
    return parsed, digest, False


def _stage_chunk(
    store: SqliteStore,
    mycelium_dir: Path,
    env: BuildEnv,
    entry: _Entry,
    parsed: MarkdownDocument,
    parsed_digest: Sha256Digest,
    *,
    policy: ChunkingPolicy,
    use_cache: bool,
    cache_rows: list[tuple[str, str]],
) -> tuple[tuple[Chunk, ...], Sha256Digest, bool]:
    key = env.chunk_key(parsed_digest=parsed_digest, doc_path=entry.doc_path)
    if use_cache:
        cached = _cached_blob(store, mycelium_dir, key)
        if cached is not None:
            digest, blob = cached
            try:
                return decode_chunks_artifact(blob), digest, True
            except Exception:  # noqa: BLE001 - a bad cache heals; it never quarantines
                append_journal(mycelium_dir, "cache.invalid", stage="chunk", build_key=key)
    chunks = chunk_document(
        parsed.kir, doc_path=entry.doc_path, policy=policy, namespace=env.namespace
    )
    digest = cas_put(mycelium_dir, encode_chunks_artifact(chunks))
    cache_rows.append((key, digest))
    return chunks, digest, False


# ---------------------------------------------------------------------------
# Snapshot restorability (roadmap 3.2)
# ---------------------------------------------------------------------------


def _state_of(entry: "_Entry", env_digest: str) -> DocState:
    """The index state one live document leaves behind — reused or rebuilt alike."""
    return DocState(
        doc_id=entry.doc_id,
        path=entry.doc_path,
        source_digest=entry.source_digest,
        source_mtime=entry.mtime_key,
        env_digest=env_digest,
        document_digest=entry.document_digest,
        chunks_digest=entry.chunks_digest,
        warnings=entry.warnings,
    )


def _restorability(mycelium_dir: Path, states: tuple[DocState, ...]) -> tuple[bool, int]:
    """Whether every live document's artifacts are still in the cache.

    Two stats per document — cheap enough to run on every build, and the only
    way to keep ``mycelium snapshots`` honest: a snapshot is recorded as
    restorable when it *is*, not when it was expected to be. A reused document's
    artifacts normally persist because garbage collection keeps whatever a
    retained snapshot names; what this catches is a hand-deleted cache
    (documented as safe, and it is — at the price of restorability until the
    next clean build).
    """
    missing = sum(
        1
        for state in states
        if not cas_path(mycelium_dir, state.document_digest).exists()
        or not cas_path(mycelium_dir, state.chunks_digest).exists()
    )
    return missing == 0, missing


# ---------------------------------------------------------------------------
# The embed stage (roadmap 3.3) — the one declared non-deterministic stage
# ---------------------------------------------------------------------------


def _resolve_embedder(
    config: MyceliumConfig, *, require_vectors: bool
) -> tuple[Embedder | None, str | None]:
    """Construct the configured embedder, or explain its absence.

    Three outcomes, deliberately distinct: an embedder; ``(None, None)`` when the
    operator configured ``provider = "none"`` and wants no vectors; and
    ``(None, reason)`` when they want vectors and cannot have them here — which
    degrades the snapshot instead of failing the build (spec 02 §4.3), unless
    `require_vectors` says a build without them is worthless.
    """
    settings = config.embedding
    try:
        embedder = build_embedder(
            provider=settings.provider,
            model_id=settings.model_id,
            model_path=Path(settings.model_path) if settings.model_path else None,
            allow_download=settings.allow_download,
        )
    except EmbedderUnavailableError as error:
        if require_vectors:
            raise
        return None, f"vectors unavailable: {error}"
    return embedder, None


def _embed_missing(
    store: SqliteStore,
    embedder: Embedder,
    pending: dict[str, str],
    lock: BuildLock,
) -> int:
    """Embed every chunk digest this model has not seen, and store the vectors.

    Runs *inside* the publication transaction, after the chunks are written, for
    two reasons: the work list is then exactly what the published corpus needs
    (``digests_without_vectors`` sees the new rows), and the vectors commit
    atomically with the chunks they describe — a crash cannot leave a snapshot
    whose manifest counts vectors that were rolled back.

    The work list is O(new text), not O(corpus), because vectors are keyed
    ``(chunk_digest, model_id)`` (D-013): an edit that leaves a section untouched
    re-uses its vector, and two documents sharing a chunk share one.
    """
    missing = store.digests_without_vectors(embedder.model_id)
    if not missing:
        return 0

    texts: list[str] = []
    digests: list[str] = []
    for digest in missing:
        text = pending.get(digest)
        if text is None:
            # A chunk this build did not recompile: it predates the embedder
            # being enabled, so its text comes from the store rather than memory.
            chunk = store.get_chunk_by_digest(digest)
            if chunk is None:  # pragma: no cover - the digest came from this table
                continue
            text = chunk.text
        texts.append(text)
        digests.append(digest)

    written = 0
    for start in range(0, len(texts), _EMBED_BATCH):
        lock.heartbeat()
        window = slice(start, start + _EMBED_BATCH)
        vectors = embedder.embed_documents(texts[window])
        written += store.put_vectors(embedder.model_id, zip(digests[window], vectors, strict=True))
    return written


def _embedding_info(embedder: Embedder) -> EmbeddingInfo:
    return EmbeddingInfo(
        model_id=embedder.model_id,
        dim=embedder.dim,
        deterministic=embedder.deterministic,
        provider=embedder.provider,
    )


# ---------------------------------------------------------------------------
# The build
# ---------------------------------------------------------------------------


def build(
    root: Path,
    *,
    namespace: str | None = None,
    config: MyceliumConfig | None = None,
    stale_after_s: float = DEFAULT_STALE_AFTER_S,
    clean: bool = False,
    require_vectors: bool = False,
) -> BuildResult:
    """Compile the repository at `root` and publish one snapshot.

    Incremental by default: only documents whose source digest, mtime, or build
    environment changed since the store's ``doc_state`` are recompiled, and their
    parse/chunk stages consult the content-addressed cache before running. The
    published snapshot is **byte-identical** to a from-scratch build of the same
    tree — the property the incremental gate enforces. `clean=True` is the
    escape hatch: recompile everything and consult no cache (it still refreshes
    the cache for the builds after it).

    `config` defaults to the repository's own `mycelium.toml` (or built-in
    defaults when it has none); `namespace` overrides the configured one, which
    is how a caller scopes a build without editing the file.

    `require_vectors` turns the vector stage's absence into a failure. By default
    a build whose embedder cannot be constructed publishes a *degraded* snapshot
    — lexical search keeps working, and the manifest says vectors are missing
    (spec 02 §4.3) — which is right for a laptop that has not fetched a model and
    wrong for a release pipeline that promised hybrid retrieval.

    Raises :class:`~mycelium.config.ConfigError` when the file exists and is
    invalid, and :class:`~mycelium.build.lock.BuildLockedError` when a live build
    holds the lock; store and filesystem failures propagate typed. Per-document
    failures never fail the build: the document is quarantined with a warning in
    the manifest (RFC-0001 failure taxonomy).
    """
    settings = config if config is not None else load_config(root)
    effective_namespace = namespace if namespace is not None else settings.project.namespace
    mycelium_dir = root / STORE_DIRNAME
    timer = _Timer()
    with BuildLock.acquire(mycelium_dir, stale_after_s=stale_after_s) as lock:
        append_journal(mycelium_dir, "build.started", root=str(root), clean=clean)
        try:
            result = _build_locked(
                root,
                mycelium_dir,
                lock,
                timer,
                namespace=effective_namespace,
                config=settings,
                clean=clean,
                require_vectors=require_vectors,
            )
        except BaseException as error:
            append_journal(mycelium_dir, "build.failed", error=f"{type(error).__name__}: {error}")
            raise
        stats = result.stats
        append_journal(
            mycelium_dir,
            "build.published",
            snapshot_id=result.manifest.snapshot_id,
            documents=stats.documents,
            chunks=result.manifest.counts.chunks,
            quarantined=stats.quarantined,
            reused=stats.reused,
            rebuilt=stats.rebuilt,
            removed=stats.removed,
            parse_hits=stats.parse_hits,
            chunk_hits=stats.chunk_hits,
            embedded=stats.embedded,
            clean=clean,
            duration_ms=result.manifest.timings_ms["total"],
        )
        return result


def _plan(
    root: Path,
    sources: list[Path],
    lock: BuildLock,
    pinned: list[Path],
    prev_by_path: dict[str, DocState],
) -> list[_Entry]:
    """Read, pin, and digest every discovered file — the spec's `plan` step.

    Reading everything is the conservative dirty detector: content truth comes
    from the digest, never from metadata. What *is* skipped for a file whose
    digest matches its ``doc_state`` row is the frontmatter parse: an indexed
    document was pinned, its pinned identity is frontmatter, frontmatter is
    content — so an unchanged content digest proves the id is still in the file,
    and the row already says which one it is. That turns the per-file plan cost
    into read + hash, the floor an every-build scan cannot go below.

    A file that cannot be read or whose declared frontmatter cannot be parsed is
    quarantined here, exactly as a clean build would quarantine it.
    """
    entries: list[_Entry] = []
    for index, path in enumerate(sources):
        if index % 64 == 0:  # staleness is measured in minutes; per-file utime is waste
            lock.heartbeat()
        relative = path.relative_to(root)
        doc_path = relative.as_posix()
        entry = _Entry(path=path, doc_path=doc_path, outcome=_Outcome.PENDING)
        try:
            # Bytes + explicit decode preserves the file's own line endings
            # (pinning must not silently convert a CRLF file, and Path.read_text
            # would) and is the cheapest read Python offers — this loop runs for
            # every file on every build, and is the incremental floor.
            raw = path.read_bytes().decode("utf-8")
            digest = digest_text(raw)
            prev = prev_by_path.get(doc_path)
            if prev is not None and prev.source_digest == digest:
                doc_id = prev.doc_id
            else:
                raw, doc_id, was_pinned = _ensure_identity(raw)
                if was_pinned:
                    with path.open("w", encoding="utf-8", newline="") as handle:
                        handle.write(raw)
                    pinned.append(path)
                    digest = digest_text(raw)
            entry.raw = raw
            entry.doc_id = doc_id
            entry.source_digest = digest
            entry.mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            entry.mtime_key = entry.mtime.isoformat()
        except Exception as error:  # noqa: BLE001 - quarantine is the failure taxonomy
            entry.outcome = _Outcome.QUARANTINED
            entry.warnings = (
                f"document quarantined: {doc_path} ({type(error).__name__}: {error})",
            )
        entries.append(entry)

    # Duplicate identities resolve over the *whole* plan, first claim (in path
    # order) wins — the same outcome a clean rebuild produces, which is what
    # keeps incremental and clean builds equal when a duplicate appears.
    seen: dict[str, str] = {}
    for entry in entries:
        if entry.outcome is not _Outcome.PENDING:
            continue
        claimant = seen.get(entry.doc_id)
        if claimant is not None:
            entry.outcome = _Outcome.QUARANTINED
            entry.warnings = (
                f"document quarantined: {entry.doc_path} (duplicate mycelium_id "
                f"{entry.doc_id}, already claimed by {claimant})",
            )
        else:
            seen[entry.doc_id] = entry.doc_path
    return entries


def _build_locked(
    root: Path,
    mycelium_dir: Path,
    lock: BuildLock,
    timer: _Timer,
    *,
    namespace: str,
    config: MyceliumConfig,
    clean: bool,
    require_vectors: bool,
) -> BuildResult:
    snapshot_id = new_ulid()
    parent_id = read_current(mycelium_dir)
    policy = config.chunking.to_policy()
    embedder, embed_reason = _resolve_embedder(config, require_vectors=require_vectors)
    env = BuildEnv.compute(namespace=namespace, policy=policy)
    env_digest = env.digest
    sources = _discover(root, config.project.knowledge_dir)
    timer.lap("discover")

    store = SqliteStore.open(root)
    with store:
        if store.recreated:
            append_journal(
                mycelium_dir,
                "store.recreated",
                reason="foreign schema version (D-016 rebuild policy)",
            )
        prev_states = store.doc_states()
        prev_by_path = {state.path: state for state in prev_states}

        pinned: list[Path] = []
        entries = _plan(root, sources, lock, pinned, prev_by_path)
        timer.lap("plan")

        # -- dirty detection ------------------------------------------------
        for entry in entries:
            if entry.outcome is not _Outcome.PENDING:
                continue
            prev = prev_by_path.get(entry.doc_path)
            entry.prev = prev
            if (
                not clean
                and prev is not None
                and prev.doc_id == entry.doc_id
                and prev.source_digest == entry.source_digest
                and prev.source_mtime == entry.mtime_key
                and prev.env_digest == env_digest
            ):
                entry.outcome = _Outcome.REUSED
                entry.warnings = prev.warnings
                entry.document_digest = prev.document_digest
                entry.chunks_digest = prev.chunks_digest

        # -- compile what is dirty, through the cache -------------------------
        parsed_count = parse_hits = chunked_count = chunk_hits = 0
        cache_rows: list[tuple[str, str]] = []
        for entry in entries:
            if entry.outcome is not _Outcome.PENDING:
                continue
            lock.heartbeat()
            try:
                parsed, parsed_digest, parse_hit = _stage_parse(
                    store, mycelium_dir, env, entry, use_cache=not clean, cache_rows=cache_rows
                )
                chunks, chunks_digest, chunk_hit = _stage_chunk(
                    store,
                    mycelium_dir,
                    env,
                    entry,
                    parsed,
                    parsed_digest,
                    policy=policy,
                    use_cache=not clean,
                    cache_rows=cache_rows,
                )
                assert entry.mtime is not None  # set whenever the plan read succeeded
                document, warnings = _assemble(
                    parsed,
                    chunks,
                    path=entry.path,
                    relative=entry.path.relative_to(root),
                    doc_id=entry.doc_id,
                    namespace=namespace,
                    mtime=entry.mtime,
                )
            except Exception as error:  # noqa: BLE001 - quarantine is the failure taxonomy
                entry.outcome = _Outcome.QUARANTINED
                entry.warnings = (
                    f"document quarantined: {entry.doc_path} ({type(error).__name__}: {error})",
                )
                continue
            parse_hits += int(parse_hit)
            parsed_count += int(not parse_hit)
            chunk_hits += int(chunk_hit)
            chunked_count += int(not chunk_hit)
            entry.outcome = _Outcome.REBUILT
            entry.document = document
            entry.chunks = chunks
            entry.warnings = warnings
            # Storing the record returns exactly the digest the manifest folds
            # (canonical JSON, one address): the assemble stage is not *cached*,
            # but its output is addressable so a snapshot can be restored from
            # it without recompiling (ADR-0016).
            entry.document_digest = cas_put(mycelium_dir, encode_document_artifact(document))
            entry.chunks_digest = chunks_digest
        timer.lap("compile")

        # -- diff against the previous build ----------------------------------
        live = [e for e in entries if e.outcome in (_Outcome.REUSED, _Outcome.REBUILT)]
        rebuilt = [e for e in entries if e.outcome is _Outcome.REBUILT]
        live_ids = {entry.doc_id for entry in live}
        removed_ids = sorted({state.doc_id for state in prev_states} - live_ids)
        # Every row being replaced is deleted before any row is inserted, so the
        # UNIQUE(path) constraints cannot fire on renames or path swaps.
        doomed = sorted(set(removed_ids) | {entry.doc_id for entry in rebuilt})
        quarantined = sum(1 for e in entries if e.outcome is _Outcome.QUARANTINED)
        cache_stamp = datetime.now(tz=UTC).isoformat()

        live_states = {entry.doc_path: _state_of(entry, env_digest) for entry in live}
        restorable, unrestorable = _restorability(mycelium_dir, tuple(live_states.values()))
        manifest_warnings = [w for entry in entries for w in entry.warnings]
        degraded: list[str] = []
        reasons: list[str] = []
        if embed_reason is not None:
            # Spec 02 §4.3 designates `degraded` for exactly this ("vectors:
            # absent when the embedder was unavailable"), so the flag goes in the
            # manifest and the explanation goes to the journal and the operator.
            # Repeating the same sentence in `warnings` on every build would bury
            # the per-document problems that field exists for.
            degraded.append("vectors")
            reasons.append(embed_reason)
            append_journal(mycelium_dir, "build.degraded", flag="vectors", reason=embed_reason)
        if not restorable:
            # Recorded as a warning rather than hidden: the snapshot publishes and
            # serves normally, it just cannot be rolled back to (ADR-0016).
            manifest_warnings.append(
                f"snapshot not restorable: {unrestorable} document(s) have no cached "
                "artifacts (the cache was cleared or collected); "
                "run `mycelium build --clean` to make snapshots restorable again"
            )

        with store.transaction():
            for doc_id in doomed:
                store.delete_document(doc_id)
            for entry in rebuilt:
                assert entry.document is not None  # rebuilt entries always carry one
                store.put_document(entry.document)
                store.put_chunks(entry.chunks)
                store.put_doc_state(live_states[entry.doc_path])
            for key, digest in cache_rows:
                store.cache_put(key, digest, cache_stamp)
            if restorable:
                record_snapshot_state(mycelium_dir, store, snapshot_id, tuple(live_states.values()))
            timer.lap("store")

            embedded = 0
            if embedder is not None:
                pending = {
                    chunk.chunk_digest: chunk.text for entry in rebuilt for chunk in entry.chunks
                }
                embedded = _embed_missing(store, embedder, pending, lock)
                store.delete_orphan_vectors()
                timer.lap("embed")

            counts = store.counts()

            timings = timer.total()
            manifest = SnapshotManifest(
                snapshot_id=snapshot_id,
                parent_id=parent_id,
                created_at=datetime.now(tz=UTC),
                # The effective configuration, not the file's bytes: formatting and
                # comments must not invalidate a build, but every setting that
                # reaches the compiler must (spec 05 §2). `namespace` is digested
                # separately because a caller may override it per build.
                config_digest=digest_json({"config": config.digest(), "namespace": namespace}),
                toolchain=Toolchain(mycelium=__version__, python=platform.python_version()),
                schema_versions={
                    name: record_schema_version(RECORD_MODELS[name]).rsplit("/", 1)[-1]
                    for name in SNAPSHOT_ARTIFACT_CLASSES
                },
                embedding=_embedding_info(embedder) if embedder is not None else None,
                counts=SnapshotCounts(
                    documents=counts["documents"],
                    chunks=counts["chunks"],
                    symbols=counts["symbols"],
                    edges=counts["edges"],
                    vectors=counts["vectors"],
                    quarantined=quarantined,
                ),
                # Corpus digests fold per-document artifact digests in path order
                # (ADR-0015): O(changed) to assemble, identical between an
                # incremental and a clean build by construction.
                artifact_digests={
                    "documents": digest_json([entry.document_digest for entry in live]),
                    "chunks": digest_json([entry.chunks_digest for entry in live]),
                    "edges": digest_json([]),
                },
                degraded=tuple(degraded) if restorable else (*degraded, "snapshot_state"),
                warnings=tuple(manifest_warnings),
                timings_ms=timings,
            )
            # The manifest file must exist before any pointer names it.
            manifest_file = write_manifest(mycelium_dir, manifest)
            store.set_meta(META_CURRENT_SNAPSHOT, snapshot_id)
        # COMMIT happened: data and the store's own pointer are live together.
        swap_current(mycelium_dir, snapshot_id)

    stats = BuildStats(
        documents=len(live),
        reused=sum(1 for e in entries if e.outcome is _Outcome.REUSED),
        rebuilt=len(rebuilt),
        removed=len(removed_ids),
        quarantined=quarantined,
        parsed=parsed_count,
        parse_hits=parse_hits,
        chunked=chunked_count,
        chunk_hits=chunk_hits,
        embedded=embedded,
    )
    return BuildResult(
        manifest=manifest,
        manifest_path=manifest_file,
        pinned=tuple(pinned),
        stats=stats,
        degraded_reasons=tuple(reasons),
    )
