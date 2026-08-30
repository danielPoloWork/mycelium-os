# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Build orchestrator v0: sequential, full-rebuild, torn-free (RFC-0001 §pseudocode).

The v0 orchestrator runs the whole pipeline for every discovered document —
discover → pin identity → parse → chunk → store — then assembles the snapshot
manifest and publishes. The content-addressed incremental DAG, build cache, and
dirty detection are deliberately *not* here (roadmap 3.1); what v0 fixes forever
is the part 3.1 must inherit unchanged: the publication and crash-safety
semantics.

Publication order, and what each crash window means::

    acquire .mycelium/lock                # exactly one writer (BuildLock)
    BEGIN IMMEDIATE                       # readers keep the old committed state
      wipe + rewrite documents/chunks     # v0: clean rebuild
      write snapshots/<ulid>.json         # manifest exists before anything points at it
      meta[current_snapshot] = <ulid>
    COMMIT                                # data + pointer become visible atomically
    swap CURRENT (tmp → replace → fsync)  # the cross-process publish instant
    release lock

- Crash before COMMIT: the transaction rolls back, ``CURRENT`` is untouched, at
  worst an orphaned manifest file exists (harmless; GC at 3.2).
- Crash between COMMIT and the swap: the store is complete and self-consistent
  (its own ``meta`` pointer is new) while the ``CURRENT`` file still names the
  previous snapshot, whose *data* the wipe replaced. This is v0's honest gap:
  with one mutable store there is no torn-free window for a reader that resolves
  through ``CURRENT`` in those microseconds. ``mycelium doctor`` detects the
  disagreement; the next build heals it; the versioned-store machinery that
  closes it entirely is platform-phase work, not v0.

Identity pinning is the build's **only** write into tier 2, per the frontmatter
ownership table (spec 03 §3: ``mycelium_id`` — "written once by `mycelium
build`"). It is what makes rebuilds deterministic (an unpinned document would
mint a fresh ULID every build, G6 dead on arrival) and renames survivable. The
write is textual insertion that preserves every other byte of the file — never a
YAML re-serialization.
"""

import platform
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from mycelium.__about__ import __version__
from mycelium.build.lock import DEFAULT_STALE_AFTER_S, BuildLock
from mycelium.build.publish import (
    append_journal,
    read_current,
    swap_current,
    write_manifest,
)
from mycelium.chunking import ChunkingPolicy, chunk_document
from mycelium.config import MyceliumConfig, load_config
from mycelium.markdown import Frontmatter, parse_markdown
from mycelium.markdown.frontmatter import DELIMITER, parse_frontmatter
from mycelium.sdk.identity import digest_json, new_ulid
from mycelium.sdk.schema import (
    RECORD_MODELS,
    SNAPSHOT_ARTIFACT_CLASSES,
    record_schema_version,
)
from mycelium.sdk.types import (
    Chunk,
    Document,
    DocumentStats,
    KirNode,
    NodeKind,
    Provenance,
    ProvenanceOrigin,
    SnapshotCounts,
    SnapshotManifest,
    Toolchain,
    TrustClass,
    Verification,
    VerificationStatus,
)
from mycelium.store import STORE_DIRNAME, SqliteStore
from mycelium.store.schema import META_CURRENT_SNAPSHOT

__all__ = ["BuildResult", "build"]

_LINK_KINDS: Final = frozenset({NodeKind.LINK, NodeKind.WIKILINK, NodeKind.EMBED})
_STATUS_FOLDERS: Final = {
    "candidate": VerificationStatus.CANDIDATE,
    "evidence": VerificationStatus.EVIDENCE,
    "verified": VerificationStatus.VERIFIED,
}
_BOM: Final = "﻿"


@dataclass(frozen=True, slots=True)
class BuildResult:
    """What one build produced."""

    manifest: SnapshotManifest
    manifest_path: Path
    pinned: tuple[Path, ...]
    """Source files that received a ``mycelium_id`` this build (commit them)."""


@dataclass
class _Compiled:
    """One document's build artifacts, ready for the store."""

    document: Document
    chunks: tuple[Chunk, ...]


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
# Per-document compilation
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


def _compile_document(
    path: Path,
    relative: Path,
    text: str,
    doc_id: str,
    *,
    namespace: str,
    mtime: datetime,
    policy: ChunkingPolicy,
) -> tuple[_Compiled, tuple[str, ...]]:
    doc_path = relative.as_posix()
    parsed = parse_markdown(text, doc_id=doc_id)
    chunks = chunk_document(parsed.kir, doc_path=doc_path, policy=policy, namespace=namespace)
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
    return _Compiled(document=document, chunks=chunks), tuple(warnings)


# ---------------------------------------------------------------------------
# The build
# ---------------------------------------------------------------------------


def build(
    root: Path,
    *,
    namespace: str | None = None,
    config: MyceliumConfig | None = None,
    stale_after_s: float = DEFAULT_STALE_AFTER_S,
) -> BuildResult:
    """Compile the repository at `root` and publish one snapshot.

    `config` defaults to the repository's own `mycelium.toml` (or built-in
    defaults when it has none); `namespace` overrides the configured one, which
    is how a caller scopes a build without editing the file.

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
        append_journal(mycelium_dir, "build.started", root=str(root))
        try:
            result = _build_locked(
                root,
                mycelium_dir,
                lock,
                timer,
                namespace=effective_namespace,
                config=settings,
            )
        except BaseException as error:
            append_journal(mycelium_dir, "build.failed", error=f"{type(error).__name__}: {error}")
            raise
        append_journal(
            mycelium_dir,
            "build.published",
            snapshot_id=result.manifest.snapshot_id,
            documents=result.manifest.counts.documents,
            chunks=result.manifest.counts.chunks,
            quarantined=result.manifest.counts.quarantined,
            duration_ms=result.manifest.timings_ms["total"],
        )
        return result


def _build_locked(
    root: Path,
    mycelium_dir: Path,
    lock: BuildLock,
    timer: _Timer,
    *,
    namespace: str,
    config: MyceliumConfig,
) -> BuildResult:
    snapshot_id = new_ulid()
    parent_id = read_current(mycelium_dir)
    policy = config.chunking.to_policy()
    sources = _discover(root, config.project.knowledge_dir)
    timer.lap("discover")

    compiled: list[_Compiled] = []
    warnings: list[str] = []
    pinned: list[Path] = []
    seen_ids: dict[str, str] = {}
    quarantined = 0

    for path in sources:
        lock.heartbeat()
        relative = path.relative_to(root)
        doc_path = relative.as_posix()
        try:
            # newline="" preserves the file's own line endings: pinning must not
            # silently convert a CRLF file, and Path.read_text would.
            with path.open(encoding="utf-8", newline="") as handle:
                raw = handle.read()
            raw, doc_id, was_pinned = _ensure_identity(raw)
            if was_pinned:
                with path.open("w", encoding="utf-8", newline="") as handle:
                    handle.write(raw)
                pinned.append(path)
            if doc_id in seen_ids:
                quarantined += 1
                warnings.append(
                    f"document quarantined: {doc_path} (duplicate mycelium_id "
                    f"{doc_id}, already claimed by {seen_ids[doc_id]})"
                )
                continue
            seen_ids[doc_id] = doc_path
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            unit, doc_warnings = _compile_document(
                path, relative, raw, doc_id, namespace=namespace, mtime=mtime, policy=policy
            )
        except Exception as error:  # noqa: BLE001 - quarantine is the failure taxonomy
            quarantined += 1
            warnings.append(f"document quarantined: {doc_path} ({type(error).__name__}: {error})")
            continue
        compiled.append(unit)
        warnings.extend(doc_warnings)
    timer.lap("compile")

    with SqliteStore.open(root) as store:
        with store.transaction():
            for doc_id in store.document_ids():  # v0: clean rebuild (3.1 makes this dirty-only)
                store.delete_document(doc_id)
            for unit in compiled:
                store.put_document(unit.document)
                store.put_chunks(unit.chunks)
            counts = store.counts()
            timer.lap("store")

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
                embedding=None,  # no vector stage in v0 (arrives at 3.3)
                counts=SnapshotCounts(
                    documents=counts["documents"],
                    chunks=counts["chunks"],
                    symbols=counts["symbols"],
                    edges=counts["edges"],
                    vectors=counts["vectors"],
                    quarantined=quarantined,
                ),
                artifact_digests={
                    "documents": digest_json(
                        [unit.document.model_dump(mode="json") for unit in compiled]
                    ),
                    "chunks": digest_json(
                        [
                            chunk.model_dump(mode="json")
                            for unit in compiled
                            for chunk in unit.chunks
                        ]
                    ),
                    "edges": digest_json([]),
                },
                degraded=(),
                warnings=tuple(warnings),
                timings_ms=timings,
            )
            # The manifest file must exist before any pointer names it.
            manifest_file = write_manifest(mycelium_dir, manifest)
            store.set_meta(META_CURRENT_SNAPSHOT, snapshot_id)
        # COMMIT happened: data and the store's own pointer are live together.
        swap_current(mycelium_dir, snapshot_id)

    return BuildResult(manifest=manifest, manifest_path=manifest_file, pinned=tuple(pinned))
