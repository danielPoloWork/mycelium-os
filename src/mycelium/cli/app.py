# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The ``mycelium`` command line (spec 05 §1).

v1 has exactly two public surfaces, CLI and MCP (D-011), so every flag here is a
compatibility liability and the skeleton stays deliberately small: ``init``,
``build``, ``search``, ``show``, ``doctor``, ``eval``, and ``serve``. The rest of the
spec's table arrives with the features behind it — ``ingest`` with milestone 4, and
``snapshots``/``rollback`` with 3.2.

The CLI is a shell, not a layer: it parses arguments, calls one function, and
renders. Nothing here decides anything the library does not already decide.
"""

from contextlib import suppress
from pathlib import Path
from typing import Annotated, Final

import typer

from mycelium.__about__ import __version__
from mycelium.build import build as run_build
from mycelium.build import read_current
from mycelium.build.lock import BuildLockedError
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
from mycelium.config import ConfigError
from mycelium.eval import EvaluationError, load_cases, run_evaluation, write_run
from mycelium.mcp import serve_stdio
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

[embedding]                    # honoured from roadmap 3.3; recorded in the build now
provider = "local-onnx"        # default: zero keys, offline
model_id = "bge-small-en-v1.5"

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
) -> None:
    """Compile the repository and publish a snapshot."""
    try:
        result = run_build(path)
    except ConfigError as error:
        # A stated intent that cannot be satisfied is a usage error, not a build
        # failure: nothing was attempted, and the fix is in the operator's file.
        raise fail(str(error), code=ExitCode.USAGE) from error
    except BuildLockedError as error:
        raise fail(str(error)) from error
    except (StoreError, OSError) as error:
        raise fail(f"build failed: {error}") from error

    manifest = result.manifest
    pinned = [str(item.relative_to(path).as_posix()) for item in result.pinned]

    if as_json:
        emit_json(
            {
                "snapshot_id": manifest.snapshot_id,
                "parent_id": manifest.parent_id,
                "counts": manifest.counts.model_dump(),
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
    for warning in manifest.warnings:
        warn(warning)
    if pinned:
        typer.echo(f"Pinned mycelium_id into {len(pinned)} file(s) - commit them:")
        for item in pinned:
            detail(f"  {item}")


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
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """Query the published snapshot."""
    store = _open_store(path)
    try:
        snapshot = read_current(path / STORE_DIRNAME)
        hits = store.search_chunks(
            query,
            limit=limit,
            filters=SearchFilters(
                collection=collection,
                trust_class=trust,
                verification_status=status,
                path_prefix=path_prefix,
            ),
        )
        results = [
            {
                "uri": _chunk_uri(hit.chunk),
                "path": hit.path,
                "title": hit.title,
                "heading_path": list(hit.chunk.heading_path),
                "lines": list(hit.chunk.lines),
                "score": round(hit.score, 4),
                "trust_class": hit.trust_class.value,
                "verification_status": hit.verification_status.value,
                "text": hit.chunk.text,
            }
            for hit in hits
        ]
    finally:
        store.close()

    if as_json:
        emit_json({"snapshot_id": snapshot, "query": query, "results": results})
        return
    if not results:
        typer.echo("No results.")
        return
    for rank, result in enumerate(results, start=1):
        heading = " / ".join(str(part) for part in result["heading_path"])  # type: ignore[union-attr]
        typer.echo(f"{rank}. {result['title']} - {heading}  ({result['score']})")
        detail(f"   {result['uri']}")
        typer.echo(f"   {_snippet(str(result['text']))}")


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
