# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The ``mycelium`` command line (spec 05 §1).

v1 has exactly two public surfaces, CLI and MCP (D-011), so every flag here is a
compatibility liability and the skeleton stays deliberately small: ``init``,
``build``, ``snapshots``, ``rollback``, ``gc``, ``search``, ``show``, ``doctor``,
``eval``, and ``serve``. The rest of the spec's table arrives with the features
behind it — ``ingest``, ``verify``, and ``promote`` with milestone 4,
``neighbors`` with 3.4, ``export`` with 3.6.

The CLI is a shell, not a layer: it parses arguments, calls one function, and
renders. Nothing here decides anything the library does not already decide.
"""

from contextlib import suppress
from pathlib import Path
from typing import Annotated, Final

import typer

from mycelium.__about__ import __version__
from mycelium.build import build as run_build
from mycelium.build import collect_garbage, list_snapshots, read_current
from mycelium.build import rollback as run_rollback
from mycelium.build.lock import BuildLockedError
from mycelium.build.snapshots import (
    DEFAULT_CACHE_MAX_AGE_DAYS,
    DEFAULT_KEEP,
    SnapshotError,
)
from mycelium.cli.doctor import diagnose, worst_status
from mycelium.cli.output import (
    ExitCode,
    configure_streams,
    detail,
    emit_json,
    fail,
    success,
    warn,
)
from mycelium.config import ConfigError, MyceliumConfig, RetrievalConfig, load_config
from mycelium.embedding import Embedder, EmbeddingError, build_embedder
from mycelium.eval import EvaluationError, load_cases, run_evaluation, write_run
from mycelium.mcp import serve_stdio
from mycelium.retrieval import search as run_search
from mycelium.sdk.identity import IdentityError, anchor, citation_uri, parse_anchor
from mycelium.sdk.identity import parse_citation_uri as parse_uri
from mycelium.sdk.types import Chunk, TrustClass, VerificationStatus
from mycelium.store import (
    STORE_DIRNAME,
    SearchFilters,
    SqliteStore,
    StoreError,
)

__all__ = ["app", "main"]

app = typer.Typer(
    name="mycelium",
    help="The knowledge compiler for AI agents.",
    no_args_is_help=True,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

_CONFIG_FILENAME: Final = "mycelium.toml"
_KNOWLEDGE_LANES: Final = ("verified", "candidate", "evidence")
_GITIGNORE_LINE: Final = f"{STORE_DIRNAME}/"

_CONFIG_TEMPLATE: Final = """# Mycelium OS configuration (spec 05 §2).
#
# These are the defaults, written out so they are visible and editable. Deleting
# the file is equivalent to keeping it exactly as generated; deleting a single key
# restores that key's default. `mycelium doctor` validates this file and reports
# which settings are not honoured yet.

[project]
name = "{name}"
namespace = "default"          # reserved for the team phase; single value in v1
knowledge_dir = "knowledge"    # the authored tree; the whole repo is scanned if absent
sources_dir = "sources"        # honoured from milestone 4 (ingestion)

[chunking]
max_tokens = 800               # hard ceiling: prose splits at the paragraph before it
target_tokens = 400            # advisory today - the packer fills toward max_tokens
atomic = ["table", "code"]     # tables and code blocks are never split

[embedding]                    # the vector stage; "none" switches it off entirely
provider = "local-onnx"        # default: zero keys, offline
model_id = "bge-small-en-v1.5"
allow_download = false         # no network call unless you say so; 133 MB from HuggingFace
# model_path = "vendor/bge"    # or point at files you placed yourself, and never download

[retrieval]
profile = "lexical"            # "hybrid" adds the vector leg - opt-in: it has not
                               # earned the default on our own eval set (ADR-0017)
k = 10                         # default result count
budget_tokens = 4000           # default packing budget for MCP responses

[modules]
enabled = []                   # the first module ships at roadmap 5.5
"""


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"mycelium {__version__}")
        raise typer.Exit(int(ExitCode.OK))


@app.callback()
def _root(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version_callback, is_eager=True, help="Show the version."
        ),
    ] = False,
) -> None:
    """The knowledge compiler for AI agents."""


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@app.command()
def init(
    path: Annotated[Path, typer.Argument(help="Repository root.")] = Path(),
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """Scaffold `mycelium.toml`, `knowledge/`, and the gitignore entry. Idempotent."""
    created: list[str] = []
    existing: list[str] = []

    for lane in _KNOWLEDGE_LANES:
        lane_dir = path / "knowledge" / lane
        keep = lane_dir / ".gitkeep"
        if keep.exists():
            existing.append(str(keep.relative_to(path).as_posix()))
            continue
        lane_dir.mkdir(parents=True, exist_ok=True)
        keep.touch()
        created.append(str(keep.relative_to(path).as_posix()))

    config = path / _CONFIG_FILENAME
    if config.exists():
        existing.append(_CONFIG_FILENAME)
    else:
        config.write_text(
            _CONFIG_TEMPLATE.format(name=path.resolve().name), encoding="utf-8", newline="\n"
        )
        created.append(_CONFIG_FILENAME)

    gitignore = path / ".gitignore"
    lines = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    if _GITIGNORE_LINE in {line.strip() for line in lines}:
        existing.append(".gitignore")
    else:
        with gitignore.open("a", encoding="utf-8", newline="\n") as handle:
            if lines and lines[-1].strip():
                handle.write("\n")
            handle.write(f"# Mycelium OS derived store - always ignored\n{_GITIGNORE_LINE}\n")
        created.append(".gitignore")

    if as_json:
        emit_json({"root": str(path), "created": created, "unchanged": existing})
        return
    if created:
        success(f"initialised {path}")
        for item in created:
            detail(f"  created  {item}")
    else:
        success(f"{path} is already initialised")
    for item in existing:
        detail(f"  present  {item}")
    typer.echo("Write Markdown under knowledge/, then run `mycelium build`.")


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------


@app.command()
def build(
    path: Annotated[Path, typer.Argument(help="Repository root.")] = Path(),
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
    clean: Annotated[
        bool,
        typer.Option(
            "--clean",
            help="Recompile everything, consulting no cache. Output is identical "
            "either way; this is the escape hatch, not a stronger build.",
        ),
    ] = False,
    require_vectors: Annotated[
        bool,
        typer.Option(
            "--require-vectors",
            help="Fail instead of publishing a snapshot without vectors.",
        ),
    ] = False,
) -> None:
    """Compile the repository (incrementally) and publish a snapshot."""
    try:
        result = run_build(path, clean=clean, require_vectors=require_vectors)
    except EmbeddingError as error:
        # Only reachable under --require-vectors: otherwise a missing embedder
        # degrades the snapshot instead of failing the build.
        raise fail(str(error)) from error
    except ConfigError as error:
        # A stated intent that cannot be satisfied is a usage error, not a build
        # failure: nothing was attempted, and the fix is in the operator's file.
        raise fail(str(error), code=ExitCode.USAGE) from error
    except BuildLockedError as error:
        raise fail(str(error)) from error
    except (StoreError, OSError) as error:
        raise fail(f"build failed: {error}") from error

    manifest = result.manifest
    stats = result.stats
    pinned = [str(item.relative_to(path).as_posix()) for item in result.pinned]

    if as_json:
        emit_json(
            {
                "snapshot_id": manifest.snapshot_id,
                "parent_id": manifest.parent_id,
                "counts": manifest.counts.model_dump(),
                "incremental": {
                    "reused": stats.reused,
                    "rebuilt": stats.rebuilt,
                    "removed": stats.removed,
                    "parse_cache_hits": stats.parse_hits,
                    "chunk_cache_hits": stats.chunk_hits,
                    "embedded": stats.embedded,
                    "clean": clean,
                },
                "degraded": list(manifest.degraded),
                "timings_ms": manifest.timings_ms,
                "warnings": list(manifest.warnings),
                "pinned": pinned,
            }
        )
        return

    counts = manifest.counts
    success(f"published snapshot {manifest.snapshot_id}")
    detail(
        f"  {counts.documents} documents, {counts.chunks} chunks"
        f"{f', {counts.quarantined} quarantined' if counts.quarantined else ''}"
        f" in {manifest.timings_ms['total']} ms"
    )
    detail(
        f"  rebuilt {stats.rebuilt}, reused {stats.reused}"
        f"{f', removed {stats.removed}' if stats.removed else ''}"
        f"{f', embedded {stats.embedded}' if stats.embedded else ''}"
        f"{' (clean build)' if clean else ''}"
    )
    for warning in manifest.warnings:
        warn(warning)
    for reason in result.degraded_reasons:
        warn(reason)
    if pinned:
        typer.echo(f"Pinned mycelium_id into {len(pinned)} file(s) - commit them:")
        for item in pinned:
            detail(f"  {item}")


# ---------------------------------------------------------------------------
# snapshots / rollback / gc
# ---------------------------------------------------------------------------


@app.command()
def snapshots(
    path: Annotated[Path, typer.Argument(help="Repository root.")] = Path(),
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """List published snapshots, newest first."""
    found = list_snapshots(path)
    if as_json:
        emit_json(
            {
                "current": read_current(path / STORE_DIRNAME),
                "snapshots": [item.as_dict() for item in found],
            }
        )
        return
    if not found:
        typer.echo("No snapshots yet. Run `mycelium build`.")
        return
    for item in found:
        marker = "*" if item.is_current else " "
        typer.echo(
            f"{marker} {item.snapshot_id}  {item.created_at}  "
            f"{item.documents} docs, {item.chunks} chunks"
        )
        notes = []
        if item.quarantined:
            notes.append(f"{item.quarantined} quarantined")
        if item.warnings:
            notes.append(f"{item.warnings} warning(s)")
        if not item.restorable:
            notes.append("not restorable")
        if notes:
            detail(f"    {', '.join(notes)}")
    detail("  (* = CURRENT; `mycelium rollback <id>` restores another)")


@app.command()
def rollback(
    snapshot_id: Annotated[str, typer.Argument(help="The snapshot to restore.")],
    path: Annotated[Path, typer.Option("--path", help="Repository root.")] = Path(),
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """Restore a published snapshot and serve it — nothing is recompiled."""
    try:
        result = run_rollback(path, snapshot_id)
    except SnapshotError as error:
        raise fail(str(error)) from error
    except BuildLockedError as error:
        raise fail(str(error)) from error
    except (StoreError, OSError) as error:
        raise fail(f"rollback failed: {error}") from error

    if as_json:
        emit_json(result.as_dict())
        return
    success(f"rolled back to {result.snapshot_id}")
    detail(f"  restored {result.documents} documents, {result.chunks} chunks")
    if result.previous_id is not None:
        detail(f"  was serving {result.previous_id}")


@app.command()
def gc(
    path: Annotated[Path, typer.Argument(help="Repository root.")] = Path(),
    keep: Annotated[
        int, typer.Option("--keep", min=0, help="Snapshots to retain (CURRENT always kept).")
    ] = DEFAULT_KEEP,
    cache_max_age: Annotated[
        int,
        typer.Option(
            "--cache-max-age",
            min=0,
            help="Retain cached artifacts written within this many days.",
        ),
    ] = DEFAULT_CACHE_MAX_AGE_DAYS,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Report what would be removed; change nothing.")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """Remove snapshots beyond retention, aged cache entries, and orphaned blobs."""
    try:
        result = collect_garbage(path, keep=keep, cache_max_age_days=cache_max_age, dry_run=dry_run)
    except SnapshotError as error:
        raise fail(str(error), code=ExitCode.USAGE) from error
    except BuildLockedError as error:
        raise fail(str(error)) from error
    except (StoreError, OSError) as error:
        raise fail(f"gc failed: {error}") from error

    if as_json:
        emit_json(result.as_dict())
        return
    verb = "would remove" if result.dry_run else "removed"
    success(
        f"gc {verb}: {len(result.removed_snapshots)} snapshot(s), {result.removed_blobs} blob(s)"
    )
    detail(
        f"  {result.removed_cache_entries} cache entries, {result.removed_debris} temp file(s), "
        f"{result.reclaimed_bytes / 1024:.1f} KiB reclaimed"
    )
    detail(f"  kept {len(result.kept_snapshots)} snapshot(s)")


# ---------------------------------------------------------------------------
# search / show
# ---------------------------------------------------------------------------


def _open_store(path: Path) -> SqliteStore:
    try:
        return SqliteStore.open(path, read_only=True)
    except StoreError as error:
        raise fail(str(error)) from error


def _chunk_uri(chunk: Chunk) -> str:
    parts = parse_anchor(chunk.anchor)
    return citation_uri(chunk.doc_id, parts.heading_slugs, parts.ordinal, lines=chunk.lines)


def _snippet(text: str, limit: int = 240) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search terms.")],
    path: Annotated[Path, typer.Option("--path", help="Repository root.")] = Path(),
    limit: Annotated[int, typer.Option("-k", "--limit", min=1, help="Maximum results.")] = 10,
    collection: Annotated[str | None, typer.Option(help="Restrict to a collection.")] = None,
    trust: Annotated[TrustClass | None, typer.Option(help="Restrict by trust class.")] = None,
    status: Annotated[
        VerificationStatus | None, typer.Option(help="Restrict by verification status.")
    ] = None,
    path_prefix: Annotated[str | None, typer.Option(help="Restrict by path prefix.")] = None,
    hybrid: Annotated[
        bool,
        typer.Option(
            "--hybrid",
            help="Add the vector leg for this query (opt-in: it has not earned the default).",
        ),
    ] = False,
    explain: Annotated[
        bool, typer.Option("--explain", help="Show which legs produced each result.")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """Query the published snapshot."""
    try:
        settings = load_config(path)
    except ConfigError as error:
        raise fail(str(error), code=ExitCode.USAGE) from error
    retrieval = settings.retrieval
    if hybrid:
        retrieval = retrieval.model_copy(update={"profile": "hybrid"})

    store = _open_store(path)
    try:
        snapshot = read_current(path / STORE_DIRNAME)
        outcome = run_search(
            store,
            query,
            limit=limit,
            filters=SearchFilters(
                collection=collection,
                trust_class=trust,
                verification_status=status,
                path_prefix=path_prefix,
            ),
            config=retrieval,
            embedder=_query_embedder(settings, retrieval),
        )
        results = [
            {
                "uri": _chunk_uri(fused.hit.chunk),
                "path": fused.hit.path,
                "title": fused.hit.title,
                "heading_path": list(fused.hit.chunk.heading_path),
                "lines": list(fused.hit.chunk.lines),
                "score": round(fused.score, 6),
                "trust_class": fused.hit.trust_class.value,
                "verification_status": fused.hit.verification_status.value,
                "text": fused.hit.chunk.text,
                "explain": fused.explain(),
            }
            for fused in outcome.hits
        ]
    finally:
        store.close()

    if as_json:
        emit_json(
            {
                "snapshot_id": snapshot,
                "query": query,
                "retrieval": outcome.explain(),
                "results": results,
            }
        )
        return
    for note in outcome.degraded:
        warn(note)
    if not results:
        typer.echo("No results.")
        return
    for rank, (result, fused) in enumerate(zip(results, outcome.hits, strict=True), start=1):
        heading = " / ".join(fused.hit.chunk.heading_path)
        typer.echo(f"{rank}. {result['title']} - {heading}  ({result['score']})")
        detail(f"   {result['uri']}")
        if explain:
            detail(f"   via {'+'.join(fused.legs)} at {fused.ranks}")
        typer.echo(f"   {_snippet(str(result['text']))}")


def _query_embedder(settings: MyceliumConfig, retrieval: RetrievalConfig) -> Embedder | None:
    """The embedder for the query side, or ``None`` when search stays lexical.

    A query-time failure is never fatal: an operator whose model has gone missing
    still gets lexical results, and :func:`mycelium.retrieval.search` reports the
    missing leg. Refusing to answer would be a strictly worse trade.
    """
    if not retrieval.hybrid:
        return None
    try:
        return build_embedder(
            provider=settings.embedding.provider,
            model_id=settings.embedding.model_id,
            model_path=Path(settings.embedding.model_path)
            if settings.embedding.model_path
            else None,
            allow_download=settings.embedding.allow_download,
        )
    except EmbeddingError:
        return None


@app.command()
def show(
    target: Annotated[str, typer.Argument(help="A mycelium:// URI or a chunk anchor.")],
    path: Annotated[Path, typer.Option("--path", help="Repository root.")] = Path(),
    context: Annotated[
        str, typer.Option("--context", help="chunk | section | document.")
    ] = "chunk",
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """Print a chunk, its section, or its whole document, with provenance."""
    if context not in {"chunk", "section", "document"}:
        raise fail(
            f"unknown context {context!r}; expected chunk, section, or document",
            code=ExitCode.USAGE,
        )

    store = _open_store(path)
    try:
        try:
            resolved = _resolve(store, target)
        except IdentityError as error:
            raise fail(f"not a citation URI or anchor: {error}", code=ExitCode.USAGE) from error

        chunk = store.get_chunk(resolved)
        if chunk is None:
            raise fail(_missing_anchor_help(store, resolved))

        document = store.get_document(chunk.doc_id)
        if document is None:  # pragma: no cover - a foreign key forbids this
            raise fail(f"chunk {resolved} has no document")

        if context == "chunk":
            chunks = [chunk]
        elif context == "section":
            chunks = [
                candidate
                for candidate in store.chunks_of(chunk.doc_id)
                if candidate.heading_path == chunk.heading_path
            ]
        else:
            chunks = list(store.chunks_of(chunk.doc_id))

        payload = {
            "uri": _chunk_uri(chunk),
            "context": context,
            "path": document.path,
            "title": document.title,
            "trust_class": document.trust_class.value,
            "verification_status": document.verification_status.value,
            "provenance": document.provenance.model_dump(mode="json"),
            "chunks": [
                {
                    "anchor": item.anchor,
                    "heading_path": list(item.heading_path),
                    "lines": list(item.lines),
                    "kind": item.kind.value,
                    "text": item.text,
                }
                for item in chunks
            ],
        }
    finally:
        store.close()

    if as_json:
        emit_json(payload)
        return
    typer.echo(f"{document.title} - {document.path}")
    detail(
        f"  {document.trust_class.value} | {document.verification_status.value} "
        f"| {_chunk_uri(chunk)}"
    )
    for item in chunks:
        typer.echo("")
        detail(f"  [{item.anchor}] lines {item.lines[0]}-{item.lines[1]}")
        typer.echo(item.text)


def _resolve(store: SqliteStore, target: str) -> str:
    """Turn a citation URI or an anchor into an anchor this store can look up.

    A ``mycelium://`` URI keys on ``doc_id`` precisely so it survives folder
    moves (D-021), so resolving one means asking the store where that document
    lives *now*.
    """
    if target.startswith("mycelium://"):
        citation = parse_uri(target)
        document = store.get_document(citation.doc_id)
        if document is None:
            raise IdentityError(f"no document {citation.doc_id} in this snapshot")
        return anchor(document.path, citation.heading_slugs, citation.ordinal)
    parse_anchor(target)  # validates the shape, raising IdentityError if malformed
    return target


def _missing_anchor_help(store: SqliteStore, target: str) -> str:
    """Explain a dead anchor, naming survivors — the CLI's ANCHOR_GONE.

    The typed `ANCHOR_GONE` error with its nearest surviving ancestor is an MCP
    contract (roadmap 2.9); here the same information is prose.
    """
    parts = parse_anchor(target)
    document = store.get_document_by_path(parts.doc_path)
    if document is None:
        return f"no document {parts.doc_path} in the published snapshot"
    survivors = [chunk.anchor for chunk in store.chunks_of(document.doc_id)][:5]
    listed = "".join(f"\n  {item}" for item in survivors)
    return f"anchor {target} is gone; {parts.doc_path} currently has:{listed}"


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


@app.command()
def doctor(
    path: Annotated[Path, typer.Argument(help="Repository root.")] = Path(),
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """Check the environment, the store, the published snapshot, and the lock."""
    checks = diagnose(path)
    overall = worst_status(checks)

    if as_json:
        emit_json({"status": overall, "checks": [check.as_dict() for check in checks]})
    else:
        for check in checks:
            if check.status == "ok":
                success(f"ok    {check.name}: {check.detail}")
            elif check.status == "warn":
                warn(f"{check.name}: {check.detail}")
            else:
                typer.echo(f"FAIL  {check.name}: {check.detail}", err=True)
    if overall == "fail":
        raise typer.Exit(int(ExitCode.FAILED))


# ---------------------------------------------------------------------------
# eval
# ---------------------------------------------------------------------------


@app.command()
def eval(  # noqa: A001 - the spec names this command `mycelium eval`
    path: Annotated[Path, typer.Argument(help="Repository root.")] = Path(),
    case_set: Annotated[Path, typer.Option("--set", help="Judged case set (JSONL).")] = Path(
        "eval/cases.jsonl"
    ),
    retriever: Annotated[
        str, typer.Option("--retriever", help="mycelium | grep (the D-010 baseline).")
    ] = "mycelium",
    gate: Annotated[
        bool, typer.Option("--gate", help="Exit non-zero if a gate fails (CI mode).")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """Score a judged case set against the published snapshot."""
    resolved = case_set if case_set.is_absolute() else path / case_set
    try:
        cases = load_cases(resolved)
    except (OSError, ValueError) as error:
        raise fail(f"cannot read {resolved}: {error}") from error

    try:
        manifest = run_evaluation(path, cases, retriever_name=retriever, case_set=resolved.name)
    except ValueError as error:  # unknown retriever
        raise fail(str(error), code=ExitCode.USAGE) from error
    except EvaluationError as error:
        raise fail(str(error)) from error

    written = write_run(path, manifest)
    failed = [result for result in manifest.gates if not result.passed]

    if as_json:
        emit_json({**manifest.model_dump(mode="json"), "manifest_path": str(written)})
    else:
        overall = manifest.overall
        success(f"{manifest.retriever}: {overall.cases} cases from {resolved.name}")
        detail(
            f"  nDCG@10 {overall.ndcg_at_10:.3f}  R@10 {overall.recall_at_10:.3f}  "
            f"R@50 {overall.recall_at_50:.3f}  MRR {overall.mrr:.3f}"
        )
        detail(
            f"  citations {overall.citation_coverage:.3f}  "
            f"false answers {overall.false_answer_rate:.1%}  "
            f"p95 {overall.latency_p95_ms} ms"
        )
        for name, summary in sorted(manifest.per_slice.items()):
            detail(f"  {name:<14} nDCG@10 {summary.ndcg_at_10:.3f}  ({summary.cases} cases)")
        for result in manifest.gates:
            line = f"{'ok  ' if result.passed else 'FAIL'} {result.gate}: {result.detail}"
            if result.passed:
                success(line)
            else:
                typer.echo(line, err=True)
        detail(f"  run manifest: {written}")

    if gate and failed:
        raise typer.Exit(int(ExitCode.FAILED))


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------


@app.command()
def serve(
    path: Annotated[Path, typer.Argument(help="Repository root.")] = Path(),
    transport: Annotated[str, typer.Option("--transport", help="Only stdio in v1.")] = "stdio",
) -> None:
    """Start the read-only MCP server (stdio)."""
    if transport != "stdio":
        raise fail(
            f"unsupported transport {transport!r}; v1 speaks stdio only", code=ExitCode.USAGE
        )
    # Nothing may be written to stdout but protocol messages, so the readiness
    # line goes to stderr — where a client's logs collect it.
    typer.echo(f"mycelium {__version__} serving MCP over stdio from {path}", err=True)
    with suppress(KeyboardInterrupt):  # a client detaching is not an error
        serve_stdio(path)


def main() -> None:
    """Console-script entry point."""
    configure_streams()
    app()
