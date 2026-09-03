# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The ``mycelium`` command line (spec 05 §1).

v1 has exactly two public surfaces, CLI and MCP (D-011), so every flag here is a
compatibility liability and the skeleton stays deliberately small: ``init``,
``build``, ``snapshots``, ``rollback``, ``gc``, ``search``, ``show``,
``neighbors``, ``export``, ``doctor``, ``eval``, and ``serve``, joined at
milestone 4 by ``ingest``, ``verify``, ``promote`` and ``demote``.

The CLI is a shell, not a layer: it parses arguments, calls one function, and
renders. Nothing here decides anything the library does not already decide.
"""

from contextlib import suppress
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Annotated, Final

import typer

from mycelium.__about__ import __version__
from mycelium.build import BuildResult, collect_garbage, list_snapshots, read_current
from mycelium.build import build as run_build
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
from mycelium.corpus import CorpusScope
from mycelium.embedding import Embedder, EmbeddingError, build_embedder
from mycelium.eval import (
    EvaluationError,
    corpus_fingerprint_of,
    load_cases,
    load_tasks,
    run_evaluation,
    run_task_suite,
    write_baseline,
    write_run,
)
from mycelium.export import DEFAULT_EXPORT_DIRNAME, ExportError, export_bundle
from mycelium.graph import MAX_DEPTH
from mycelium.graph import neighbours as graph_neighbours
from mycelium.ingest import (
    FileConnector,
    Ingested,
    IngestError,
    Quarantine,
    Registry,
    describe_secrets,
    ingest_source,
    write_projection,
)
from mycelium.mcp import serve_stdio
from mycelium.retrieval import search as run_search
from mycelium.sdk.identity import (
    IdentityError,
    anchor,
    citation_uri,
    doc_ref,
    new_ulid,
    parse_anchor,
)
from mycelium.sdk.identity import parse_citation_uri as parse_uri
from mycelium.sdk.types import Chunk, EdgeType, TrustClass, VerificationStatus
from mycelium.store import (
    STORE_DIRNAME,
    SearchFilters,
    SqliteStore,
    StoreError,
)
from mycelium.synthesis import (
    SynthesisError,
    WikiSynthesizer,
    build_synthesizer,
    evidence_of,
    synthesize_candidate,
    write_candidate,
)
from mycelium.verification import (
    VerificationError,
    Verified,
    author_name,
    build_judge,
    verify_tree,
)
from mycelium.verification import (
    demote as demote_document,
)
from mycelium.verification import promote as promote_document
from mycelium.watch import WatcherUnavailableError, watched_paths
from mycelium.watch import watch as run_watch_session

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
_GITIGNORE_ENTRIES: Final = (
    (f"{STORE_DIRNAME}/", "derived store - always ignored"),
    (
        f"{DEFAULT_EXPORT_DIRNAME}/",
        "interchange bundles - regenerable, never committed by default (D-006)",
    ),
)

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

[ingest]                       # which plugins compile a source, in priority order
parsers = ["markdown"]         # add "docling", "pandoc", "pdf" to ingest those formats;
                               # every name must resolve or the command says what to
                               # install - there is no "best available" (spec 05 §4.2)
connectors = ["file"]          # v1 acquires from the local tree only
max_failed_elements = 0.05     # fidelity loss budget: refuse a projection that lost
                               # more than this fraction of a document's elements
redact_secrets = true          # replace credentials found in an ingested source with
                               # a placeholder; the scan runs and flags either way

[chunking]
max_tokens = 800               # hard ceiling: prose splits at the paragraph before it
# target_tokens = 400         # aim smaller than the ceiling; measure before you do
atomic = ["table", "code"]     # tables and code blocks are never split
# pack_atomic = true          # let a table or code block share a chunk with the prose
                               # around it, instead of standing alone. Measured on two
                               # corpora (ADR-0042): on task documentation full of command
                               # blocks it is worth +61% nDCG@10, on long-form prose it is
                               # roughly neutral. Off by default because it moves every
                               # chunk boundary, which re-anchors judged eval cases.

[verification]                 # gate G7: what a synthesized document must clear
cites_coverage_min = 0.95      # of claim-bearing blocks must cite the evidence
entailment_min = 0.90          # of sampled claims must be supported by what they cite
auto_promote = false           # default: promotion is a human act in Git (D-021)
sample_size = 8                # claims judged per document; 0 skips entailment
# model_id = "claude-opus-5"   # have a different model judge than the one that wrote

[sources]                      # trust per origin, stamped at acquisition (D-021)
# "docs.python.org" = "high"
# "internal-wiki" = "medium"
# "*" = "unknown"

[synthesis]                    # the LLM lane of ingestion (D-020); off until a
                               # provider is named, so a default install is offline
enabled = "auto"               # auto = on when a provider is configured; true|false to force
plugin = "wiki"                # the default synthesizer: cited, interlinked candidate docs
# provider = "anthropic"       # naming one is the consent that lets Mycelium call out
# model_id = "claude-opus-5"   # unset = the provider's own default
min_citation_coverage = 1.0    # every claim-bearing block cites the evidence, or nothing
                               # is written. Stricter than gate G7 on purpose

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
    present = {line.strip() for line in lines}
    # Entry by entry rather than all-or-nothing: a repository initialised before
    # an entry existed gains it on the next `init`, which is what makes this
    # command idempotent rather than merely re-runnable.
    wanted = [(entry, note) for entry, note in _GITIGNORE_ENTRIES if entry not in present]
    if not wanted:
        existing.append(".gitignore")
    else:
        with gitignore.open("a", encoding="utf-8", newline="\n") as handle:
            if lines and lines[-1].strip():
                handle.write("\n")
            for entry, note in wanted:
                handle.write(f"# Mycelium OS {note}\n{entry}\n")
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
    no_pin: Annotated[
        bool,
        typer.Option(
            "--no-pin",
            help="Compile without writing a mycelium_id into any document. "
            "Documents that have none take an id derived from their path, so the "
            "snapshot still reproduces - measurement without touching the corpus.",
        ),
    ] = False,
    watch_mode: Annotated[
        bool,
        typer.Option("--watch", help="Rebuild whenever a document changes, until Ctrl-C."),
    ] = False,
) -> None:
    """Compile the repository (incrementally) and publish a snapshot."""
    if watch_mode:
        if as_json:
            # `--json` promises exactly one document on stdout (spec 05 §1) and a
            # watch session is a stream of them. Refusing beats redefining the
            # convention for one flag.
            raise fail(
                "--watch and --json cannot be combined: --json emits one document "
                "and a watch session emits one per build",
                code=ExitCode.USAGE,
            )
        _watch(path, clean=clean, require_vectors=require_vectors, pin_identity=not no_pin)
        return

    try:
        result = run_build(
            path, clean=clean, require_vectors=require_vectors, pin_identity=not no_pin
        )
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
    derived = [str(item.relative_to(path).as_posix()) for item in result.derived]

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
                "derived": derived,
            }
        )
        return

    _report_build(result, clean=clean)
    if pinned:
        typer.echo(f"Pinned mycelium_id into {len(pinned)} file(s) - commit them:")
        for item in pinned:
            detail(f"  {item}")
    if derived:
        # The opposite report, and it has to be as loud: an operator who forgot
        # `--no-pin` was on would otherwise never learn that the identities in
        # this snapshot are not the ones a normal build would have produced.
        typer.echo(
            f"Compiled {len(derived)} file(s) with a path-derived mycelium_id - "
            "nothing was written, and nothing survives a rename."
        )


def _report_build(result: BuildResult, *, clean: bool = False) -> None:
    """Render one build's outcome — shared by a single build and a watch loop."""
    manifest, stats = result.manifest, result.stats
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


def _watch(path: Path, *, clean: bool, require_vectors: bool, pin_identity: bool = True) -> None:
    """Run a watch session, reporting each build as an ordinary one."""
    if clean or require_vectors:
        # Both are single-shot intents: `--clean` says "distrust the cache once",
        # `--require-vectors` says "fail this build". Neither has a meaning that
        # survives an unattended loop, and silently ignoring them would be worse.
        raise fail(
            "--watch cannot be combined with --clean or --require-vectors; "
            "run those as a one-off build first",
            code=ExitCode.USAGE,
        )

    watched = list(watched_paths(path))
    success(f"watching {path} for changes ({len(watched)} document(s)); Ctrl-C to stop")
    try:
        stats = run_watch_session(
            path,
            pin_identity=pin_identity,
            on_change=lambda paths: detail(
                f"  changed: {', '.join(sorted(p.name for p in paths)[:4])}"
                f"{' ...' if len(paths) > 4 else ''}"
            ),
            on_result=_report_build,
            on_failure=lambda error: warn(f"build failed: {error}"),
        )
    except WatcherUnavailableError as error:
        raise fail(str(error), code=ExitCode.USAGE) from error
    except KeyboardInterrupt:  # pragma: no cover - the documented way to stop
        stats = None

    if stats is not None:
        detail(f"  {stats.builds} build(s), {stats.failures} failure(s)")
        if stats.builds > 1:
            # Every build publishes a snapshot (ADR-0009's always-publish
            # semantics), so a long session leaves a long history. Say so rather
            # than deleting anything: what to retain is the operator's call.
            detail(f"  {stats.builds} snapshots published; `mycelium gc` prunes the history")


# ---------------------------------------------------------------------------
# snapshots / rollback / gc
# ---------------------------------------------------------------------------


@app.command()
def ingest(
    sources: Annotated[
        list[Path], typer.Argument(help="Files to ingest. Must live inside the repository.")
    ],
    path: Annotated[Path, typer.Option("--root", help="Repository root.")] = Path(),
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Take custody and report fidelity, but write no evidence document.",
        ),
    ] = False,
    no_synthesize: Annotated[
        bool,
        typer.Option(
            "--no-synthesize",
            help="Skip the LLM synthesis lane even when a provider is configured.",
        ),
    ] = False,
    forget: Annotated[
        bool,
        typer.Option(
            "--forget",
            help="Drop the named sources' quarantine records instead of ingesting them.",
        ),
    ] = False,
) -> None:
    """Acquire, compile and project sources into `knowledge/evidence/` (spec 05 §1).

    Each source is handled on its own: one that cannot be read, or that loses more
    than `[ingest] max_failed_elements`, is reported and the rest continue. The
    exit code is 1 if any source failed, because a script that ingested a folder
    needs to know without parsing the output.

    Ingestion is dual-lane (D-020). The evidence lane always runs. The **synthesis
    lane** additionally authors a cited candidate document under
    `knowledge/candidate/`, and runs only when `[synthesis]` names an LLM provider
    — so a default install ingests offline and writes no prose. A synthesis that
    fails never fails the ingestion that carried it: the evidence is already on
    disk, and the second lane is the additional one.

    A source that fails is **quarantined**: the failure is written to
    `.mycelium/quarantine/` with the stage that refused it and the custody digest
    of the bytes that caused it, so it can be looked at later rather than
    scrolling past (spec 02 §5). Ingesting it successfully clears the record;
    `--forget` clears it without ingesting, for a source that is simply never
    coming back. `mycelium doctor` reports what is quarantined.

    Nothing is indexed here. Both a projected document and a candidate are
    compiled by `mycelium build` like any other file in the authored tree — the
    lane writes Markdown only (D-020).
    """
    try:
        settings = load_config(path)
    except ConfigError as error:
        raise fail(str(error), code=ExitCode.USAGE) from error
    scope = CorpusScope.of(settings.project)
    roots = [root for root in (path, path / settings.project.sources_dir) if root.is_dir()]
    declared = roots or [path]
    if forget:
        _forget(path, sources, connector=FileConnector(declared), as_json=as_json)
        return
    try:
        registry = Registry.resolve(
            parsers=settings.ingest.parsers,
            connectors=settings.ingest.connectors,
            roots=declared,
        )
    except IngestError as error:
        raise fail(str(error), code=ExitCode.USAGE) from error

    mycelium_dir = path / STORE_DIRNAME
    synthesizer = None
    if settings.synthesis.active and not no_synthesize:
        try:
            synthesizer = build_synthesizer(settings.synthesis)
        except SynthesisError as error:
            # Degradable by design: the evidence lane is what ingestion promises.
            warn(f"synthesis lane off: {error}")
    results: list[dict[str, object]] = []
    failures = 0
    for source in sources:
        try:
            ingested = ingest_source(
                mycelium_dir,
                registry,
                str(source),
                doc_id=new_ulid(),
                max_failed_elements=settings.ingest.max_failed_elements,
                redact_secrets=settings.ingest.redact_secrets,
                knowledge_dir=scope.knowledge_dir,
                # Trust is a property of where the bytes came from, so it is
                # stamped once, here, and travels with the document (D-021). The
                # source URI is not known until the connector has resolved it, so
                # the resolver is handed down rather than the answer.
                trust_for=settings.sources.trust_for,
            )
        except IngestError as error:
            failures += 1
            results.append(
                {
                    "source": str(source),
                    "ok": False,
                    "error": str(error),
                    "quarantined": True,
                }
            )
            if not as_json:
                warn(f"{source}: {error}")
                detail("  quarantined; `mycelium doctor` lists what is waiting")
            continue

        written = None if dry_run else write_projection(path, ingested)
        report = ingested.report
        entry: dict[str, object] = {
            "source": str(source),
            "ok": True,
            "parser": ingested.parser_id,
            "source_digest": ingested.original.digest,
            "kir_digest": ingested.kir_digest,
            "fidelity_report": ingested.fidelity_digest,
            "document": str(ingested.projection.path),
            "written": written is not None,
            "elements": report.elements,
            "represented": report.represented,
            "degraded": report.degraded,
            "lost": report.lost,
            "warnings": list(report.warnings),
            "secret_flags": list(ingested.secret_flags),
            "redacted": ingested.redacted,
        }
        if synthesizer is not None:
            entry["synthesis"] = _synthesize(
                path,
                mycelium_dir,
                synthesizer,
                ingested,
                knowledge_dir=scope.knowledge_dir,
                dry_run=dry_run,
                quiet=as_json,
                instructions=settings.synthesis.instructions,
            )
        results.append(entry)
        if not as_json:
            verb = "would write" if dry_run else "wrote"
            success(f"{source} -> {verb} {ingested.projection.path} ({ingested.parser_id})")
            detail(
                f"  {report.represented} represented, {report.degraded} degraded, "
                f"{report.lost} lost of {report.elements} elements"
            )
            for warning in report.warnings:
                detail(f"  note: {warning}")
            if ingested.secret_flags:
                found = describe_secrets(ingested.secret_flags)
                if ingested.redacted:
                    warn(f"  secrets redacted from the projection: {found}")
                else:
                    warn(
                        f"  secrets found and NOT redacted ([ingest] redact_secrets "
                        f"= false): {found}"
                    )

    if as_json:
        emit_json({"root": str(path), "dry_run": dry_run, "sources": results})
    elif not dry_run and failures < len(sources):
        detail("run `mycelium build` to compile what was written")
    if failures:
        raise fail(f"{failures} of {len(sources)} source(s) could not be ingested")


def _forget(root: Path, sources: list[Path], *, connector: FileConnector, as_json: bool) -> None:
    """Drop the named sources' quarantine records (`mycelium ingest --forget`).

    The escape hatch for a source that is never coming back — deleted, replaced,
    or simply not worth ingesting. Everything else clears itself by succeeding,
    which is the lifecycle that keeps the list honest; this is for the case where
    there is nothing left to succeed.

    A source that was not quarantined is not an error. The operator asked for it
    to be absent from the list, and it is.
    """
    quarantine = Quarantine(root / STORE_DIRNAME)
    results = []
    for source in sources:
        # The record is keyed by the URI the connector produced, so the key is
        # asked *of the connector* rather than rebuilt here. A second copy of
        # that rule is exactly how `--forget` stopped finding records the day the
        # URI became relative (BUG-0017).
        uri = connector.uri_of(source) if source.exists() else str(source)
        dropped = quarantine.clear(uri) or quarantine.clear(str(source))
        results.append({"source": str(source), "forgotten": dropped})
        if not as_json:
            if dropped:
                success(f"{source}: quarantine record dropped")
            else:
                detail(f"{source}: was not quarantined")
    if as_json:
        emit_json({"root": str(root), "forgotten": results})


def _synthesize(
    root: Path,
    mycelium_dir: Path,
    synthesizer: WikiSynthesizer,
    ingested: Ingested,
    *,
    knowledge_dir: str,
    dry_run: bool,
    quiet: bool,
    instructions: str,
) -> dict[str, object]:
    """Run the synthesis lane for one ingested source, and report what happened.

    Never raises. A refused document, an unreachable model and a missing key are
    all *results* here, because the evidence lane has already delivered what
    ingestion promises and D-020 makes this the additional lane (spec 02 §5).
    """
    evidence = evidence_of(
        ingested.projection.path,
        ingested.projection.text,
        source_uri=ingested.blob.source_uri,
    )
    try:
        synthesized = synthesize_candidate(
            mycelium_dir,
            synthesizer,
            [evidence],
            topic=evidence.title,
            instructions=instructions,
            knowledge_dir=knowledge_dir,
        )
    except SynthesisError as error:
        if not quiet:
            warn(f"  no candidate written: {error}")
        return {"ok": False, "error": str(error)}

    if not dry_run:
        write_candidate(root, synthesized)
    if not quiet:
        verb = "would write" if dry_run else "wrote"
        success(f"  {verb} {synthesized.candidate.path} ({synthesized.record.model})")
        detail(
            f"  cited {synthesized.report.cited_claims}/{synthesized.report.claims} claim(s) "
            f"across {len(synthesized.report.cited_documents)} evidence document(s), "
            f"{synthesized.record.attempts} attempt(s)"
        )
    return {
        "ok": True,
        "document": str(synthesized.candidate.path),
        "written": not dry_run,
        "record": synthesized.record_digest,
        "provider": synthesized.record.provider,
        "model": synthesized.record.model,
        "attempts": synthesized.record.attempts,
        "claims": synthesized.report.claims,
        "cited_claims": synthesized.report.cited_claims,
        "coverage": round(synthesized.report.coverage, 4),
        "citations": list(synthesized.report.citations),
    }


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
                trust_classes=frozenset({trust}) if trust else None,
                verification_statuses=frozenset({status}) if status else None,
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
def neighbors(
    target: Annotated[
        str, typer.Argument(help="A document path, a mycelium:// URI, or a chunk anchor.")
    ],
    path: Annotated[Path, typer.Option("--path", help="Repository root.")] = Path(),
    types: Annotated[
        list[EdgeType] | None, typer.Option("--type", help="Restrict to an edge type.")
    ] = None,
    depth: Annotated[int, typer.Option("--depth", min=1, max=MAX_DEPTH, help="Hops to walk.")] = 1,
    limit: Annotated[int, typer.Option("-k", "--limit", min=1, help="Maximum results.")] = 20,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """Show the typed neighbourhood of a document or section."""
    store = _open_store(path)
    try:
        origin = _graph_ref(store, target)
        found = graph_neighbours(store, origin, types=types or None, depth=depth, limit=limit)
        results = [item.as_dict() for item in found]
    finally:
        store.close()

    if as_json:
        emit_json({"origin": origin, "neighbors": results})
        return
    if not results:
        typer.echo(f"No neighbors of {origin}.")
        detail("  (edges come from authored links; run `mycelium build` after adding some)")
        return
    typer.echo(f"{origin}")
    for item in results:
        arrow = "->" if item["direction"] == "out" else "<-"
        provenance = item["provenance"]
        assert isinstance(provenance, dict)
        typer.echo(f"  {arrow} {item['ref']}  [{item['type']}, {item['status']}]")
        where = provenance.get("anchor")
        detail(f"     via {provenance['kind']}{f' at {where}' if where else ''}")


def _graph_ref(store: SqliteStore, target: str) -> str:
    """Turn what a human typed into the reference the graph uses.

    A path, a `mycelium://` URI, a chunk anchor, or an already-formed `doc:` ref
    all name the same thing to a reader; the graph keys on `doc:<path>`, and
    making the caller know that would be a leak, not a contract.
    """
    if target.startswith("doc:"):
        return target
    if target.startswith("mycelium://"):
        try:
            parsed = parse_uri(target)
        except IdentityError as error:
            raise fail(str(error), code=ExitCode.USAGE) from error
        document = store.get_document(parsed.doc_id)
        if document is None:
            raise fail(f"no document {parsed.doc_id} in this snapshot")
        return doc_ref(document.path)
    path_part = target.split("#", 1)[0]
    document = store.get_document_by_path(path_part)
    if document is None:
        raise fail(f"no document at {path_part} in this snapshot")
    return doc_ref(document.path)


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


# ---------------------------------------------------------------------------
# verify / promote / demote (D-021, gate G7)
# ---------------------------------------------------------------------------


def _relative(root: Path, document: Path) -> PurePosixPath:
    """A document argument as a repository-relative POSIX path."""
    candidate = document if document.is_absolute() else root / document
    try:
        return PurePosixPath(candidate.resolve().relative_to(root.resolve()).as_posix())
    except ValueError as error:
        raise fail(
            f"{document} is outside {root}; verification only touches the repository",
            code=ExitCode.USAGE,
        ) from error


def _report_grounding(result: Verified) -> None:
    grounding = result.grounding
    entailment = "not measured" if grounding.entailment is None else f"{grounding.entailment:.2f}"
    line = (
        f"{grounding.path.as_posix()}: grounding {grounding.score:.2f} "
        f"(coverage {grounding.coverage:.2f} over {grounding.claims} claims, "
        f"entailment {entailment}"
    )
    if grounding.sampled:
        line += f" on {grounding.sampled} sampled"
    line += ")"
    if result.blockers:
        warn(line)
    else:
        success(line)
    if grounding.self_judged:
        detail("  note: the model that judged is the model that wrote (set")
        detail("        [verification] model_id to have a different one judge)")
    if grounding.weakest_trust is not None:
        detail(f"  weakest cited source trust: {grounding.weakest_trust.value}")
    for blocker in result.blockers:
        detail(f"  blocked [{blocker.code}]: {blocker.message}")
    for judgement in grounding.judgements:
        if not judgement.entailed:
            detail(f"  not entailed: {judgement.claim[:70]!r} - {judgement.reason}")
    if result.stamped:
        detail("  verification block updated (commit it)")
    if result.promoted is not None:
        success(f"  promoted -> {result.promoted.destination.as_posix()}")


@app.command()
def verify(
    documents: Annotated[
        list[Path] | None,
        typer.Argument(help="Documents to verify. Default: every synthesized document."),
    ] = None,
    path: Annotated[Path, typer.Option("--root", help="Repository root.")] = Path(),
    gate: Annotated[
        bool, typer.Option("--gate", help="Exit non-zero when gate G7 is not satisfied.")
    ] = False,
    no_entailment: Annotated[
        bool,
        typer.Option("--no-entailment", help="Measure coverage only; make no LLM call."),
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Report, and write no verification block.")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """Measure grounding on synthesized documents (gate G7, D-021).

    Two components, and they are not the same kind of thing. **Citation coverage**
    is recomputed here against the corpus *as it is* — which is the point of the
    command: the evidence a candidate cites may have been edited, re-projected or
    deleted since it was written, and no care at writing time can catch that.
    **Sampled entailment** asks whether the cited evidence actually says what the
    claim says, which needs a judge; with no LLM provider configured it is
    reported as *not measured* rather than as a number nobody computed.

    The score is written into each document's frontmatter, and only when it
    changed — so a nightly run over a corpus nothing happened to produces no diff.
    Verification never moves a document unless `[verification] auto_promote` says
    so; promotion is a human act in Git (D-021).

    `--gate` is the CI form and fails on a *measured* shortfall. An unmeasured
    entailment is reported and does not fail the gate, because a gate that were
    red on every offline checkout is a gate everyone learns to ignore. Promotion
    is stricter: there, an unmeasured half needs `mycelium promote --force`.
    """
    try:
        settings = load_config(path)
    except ConfigError as error:
        raise fail(str(error), code=ExitCode.USAGE) from error
    scope = CorpusScope.of(settings.project)

    judge = None
    self_judged = False
    if not no_entailment:
        judge, self_judged, reason = build_judge(settings.synthesis, settings.verification)
        if judge is None and not as_json:
            warn(reason)

    try:
        results = verify_tree(
            path,
            scope,
            thresholds=settings.verification.thresholds(),
            judge=judge,
            sample_size=settings.verification.sample_size,
            self_judged=self_judged,
            only=[_relative(path, item) for item in documents or []],
            write=not dry_run,
            auto_promote=settings.verification.auto_promote,
        )
    except (VerificationError, SynthesisError) as error:
        raise fail(str(error)) from error

    if as_json:
        emit_json(
            {
                "root": str(path),
                "thresholds": {
                    "coverage": settings.verification.cites_coverage_min,
                    "entailment": settings.verification.entailment_min,
                },
                "documents": [item.as_dict() for item in results],
            }
        )
    else:
        for result in results:
            _report_grounding(result)
        if not results:
            detail("no synthesized documents to verify")

    failures = [
        item
        for item in results
        if item.grounding.blockers(settings.verification.thresholds(), require_entailment=False)
    ]
    if gate and failures:
        raise fail(f"gate G7: {len(failures)} of {len(results)} document(s) below threshold")


@app.command()
def promote(
    document: Annotated[Path, typer.Argument(help="The candidate document to promote.")],
    path: Annotated[Path, typer.Option("--root", help="Repository root.")] = Path(),
    by: Annotated[
        str | None,
        typer.Option("--by", help="Who is promoting. Default: your git user.name."),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Promote below gate G7, recorded in the document.")
    ] = False,
    no_entailment: Annotated[
        bool,
        typer.Option("--no-entailment", help="Measure coverage only; make no LLM call."),
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """Move a candidate into `knowledge/verified/` (D-021).

    Gate G7 is measured first — not read from the document, which may carry a
    number from before the evidence moved — and a document below it is refused
    with the specific component named. `--force` is the human override the spec
    provides, and it writes *why* it was forced into `verified_by`, so the
    override is visible in the file and in every diff after it.

    The move is a file move: verification status is the folder (D-021), so `git
    status` shows what happened and nothing else has to be trusted. Run
    `mycelium build` afterwards to serve the new status.
    """
    try:
        settings = load_config(path)
    except ConfigError as error:
        raise fail(str(error), code=ExitCode.USAGE) from error
    scope = CorpusScope.of(settings.project)
    relative = _relative(path, document)

    judge = None
    self_judged = False
    if not no_entailment:
        judge, self_judged, reason = build_judge(settings.synthesis, settings.verification)
        if judge is None and not as_json:
            warn(reason)

    thresholds = settings.verification.thresholds()
    try:
        measured = verify_tree(
            path,
            scope,
            thresholds=thresholds,
            judge=judge,
            sample_size=settings.verification.sample_size,
            self_judged=self_judged,
            only=[relative],
            write=False,
        )
    except (VerificationError, SynthesisError) as error:
        raise fail(str(error)) from error
    if not measured:
        raise fail(
            f"{relative.as_posix()} is not a synthesized document; only the synthesis "
            "lane's output has grounding to gate (D-021)",
            code=ExitCode.USAGE,
        )

    result = measured[0]
    blockers = result.blockers
    if blockers and not force:
        for blocker in blockers:
            detail(f"  blocked [{blocker.code}]: {blocker.message}")
        raise fail(
            f"{relative.as_posix()} does not satisfy gate G7; read it and use --force to "
            "promote it on your own authority"
        )

    # Who vouches. Below the gate that is the human, by name, with the reason in
    # the field: the override has to be legible in the document itself, not only
    # in whatever scrollback the operator had open. Above it, the check vouches.
    if blockers:
        codes = ", ".join(item.code for item in blockers)
        verified_by = f"{by or author_name()} (forced: {codes})"
    else:
        verified_by = result.checker
    try:
        moved = promote_document(
            path,
            relative,
            verified_by=verified_by,
            grounding=result.grounding.score,
            at=date.today(),
            forced=bool(blockers),
        )
    except VerificationError as error:
        raise fail(str(error)) from error

    if as_json:
        emit_json({"root": str(path), "promoted": moved.as_dict()})
        return
    success(f"{moved.source.as_posix()} -> {moved.destination.as_posix()}")
    detail(f"  verified_by: {moved.verified_by}")
    detail(f"  grounding:   {moved.grounding}")
    if moved.forced:
        warn("promoted below gate G7 on your authority; the document records that")
    detail("commit the move, then run `mycelium build`")


@app.command()
def demote(
    document: Annotated[Path, typer.Argument(help="The verified document to demote.")],
    path: Annotated[Path, typer.Option("--root", help="Repository root.")] = Path(),
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """Move a verified document back to `knowledge/candidate/` (D-021).

    The verification block is removed on the way down. A demoted document is not
    poorly grounded, it is no longer vouched for — and a `verified_by` left behind
    would be a false claim sitting in the file, which is the drift folder-encoded
    status exists to prevent.
    """
    try:
        settings = load_config(path)
    except ConfigError as error:
        raise fail(str(error), code=ExitCode.USAGE) from error
    _ = settings
    relative = _relative(path, document)
    try:
        moved = demote_document(path, relative)
    except VerificationError as error:
        raise fail(str(error)) from error

    if as_json:
        emit_json({"root": str(path), "demoted": moved.as_dict()})
        return
    success(f"{moved.source.as_posix()} -> {moved.destination.as_posix()}")
    detail("  verification block removed")
    detail("commit the move, then run `mycelium build`")


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


def _run_task_suite(path: Path, *, as_json: bool) -> None:
    """Run the agent-task suite: what each strategy puts in front of a model, and its cost."""
    suite = path / "eval" / "tasks.jsonl"
    try:
        loaded = load_tasks(suite)
    except (OSError, ValueError) as error:
        raise fail(f"cannot read {suite}: {error}") from error

    try:
        report = run_task_suite(path, loaded)
    except StoreError as error:
        raise fail(str(error)) from error

    if as_json:
        emit_json(report.as_dict())
        return

    success(f"{report.tasks} agent tasks, two strategies")
    for name in ("mycelium", "grep"):
        summary = report.summary(name)
        if not summary:
            continue
        detail(
            f"  {name:<9} evidence found {summary['success_rate']:.0%}  "
            f"mean {summary['mean_tokens']:.0f} tokens  "
            f"{summary['mean_documents_read']:.1f} documents  "
            f"p95 {summary['p95_latency_ms']:.0f} ms"
        )
    mycelium_tokens = report.summary("mycelium").get("total_tokens", 0.0)
    grep_tokens = report.summary("grep").get("total_tokens", 0.0)
    if mycelium_tokens:
        detail(f"  grep spends {grep_tokens / mycelium_tokens:.1f}x the context to answer")


@app.command()
def eval(  # noqa: A001 - the spec names this command `mycelium eval`
    path: Annotated[Path, typer.Argument(help="Repository root.")] = Path(),
    case_set: Annotated[Path, typer.Option("--set", help="Judged case set (JSONL).")] = Path(
        "eval/release.jsonl"
    ),
    retriever: Annotated[
        str, typer.Option("--retriever", help="mycelium | grep (the D-010 baseline).")
    ] = "mycelium",
    tasks: Annotated[
        bool,
        typer.Option("--tasks", help="Run the agent-task suite against the grep loop."),
    ] = False,
    bless: Annotated[
        bool,
        typer.Option(
            "--bless",
            help="Freeze this run as the baseline gate G3 compares against.",
        ),
    ] = False,
    gate: Annotated[
        bool, typer.Option("--gate", help="Exit non-zero if a gate fails (CI mode).")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """Score a judged case set against the published snapshot."""
    if tasks:
        _run_task_suite(path, as_json=as_json)
        return

    resolved = case_set if case_set.is_absolute() else path / case_set
    try:
        cases = load_cases(resolved)
    except (OSError, ValueError) as error:
        raise fail(f"cannot read {resolved}: {error}") from error

    # The dev set is scored beside the release set and reported, never gated: the
    # gap between them is the overfitting signal the split exists to expose
    # (spec 04 §7.1, ADR-0027).
    companion_path = resolved.with_name("dev.jsonl")
    companion = None
    if resolved.stem == "release" and companion_path.is_file():
        try:
            companion = load_cases(companion_path)
        except (OSError, ValueError):
            companion = None

    try:
        manifest = run_evaluation(
            path,
            cases,
            retriever_name=retriever,
            case_set=resolved.name,
            companion=companion,
            companion_set=companion_path.name if companion else None,
        )
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
        if manifest.companion_overall is not None:
            beside = manifest.companion_overall
            gap = beside.ndcg_at_10 - overall.ndcg_at_10
            detail(
                f"  {manifest.companion_set}: nDCG@10 {beside.ndcg_at_10:.3f} on "
                f"{beside.cases} cases, gap {gap:+.3f} - the dev set is what tuning "
                "sees, so a gap that grows is a change fitting it (spec 04 7.1)"
            )
        for result in manifest.gates:
            line = f"{'ok  ' if result.passed else 'FAIL'} {result.gate}: {result.detail}"
            if result.passed:
                success(line)
            else:
                typer.echo(line, err=True)
        detail(f"  run manifest: {written}")

    if bless:
        frozen = write_baseline(path, manifest, corpus_fingerprint_of(path, manifest.snapshot_id))
        detail(f"  baseline: {frozen}")

    if gate and failed:
        raise typer.Exit(int(ExitCode.FAILED))


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


@app.command()
def export(
    path: Annotated[Path, typer.Argument(help="Repository root.")] = Path(),
    out: Annotated[
        Path | None, typer.Option("--out", help="Where bundles go (default: <root>/export).")
    ] = None,
    with_markdown: Annotated[
        bool, typer.Option("--with-markdown", help="Copy the compiled sources into the bundle.")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Emit JSON.")] = False,
) -> None:
    """Write the published snapshot as a JSONL interchange bundle."""
    try:
        result = export_bundle(path, out=out, with_markdown=with_markdown)
    except ExportError as error:
        raise fail(str(error)) from error
    except (StoreError, OSError) as error:
        raise fail(f"export failed: {error}") from error

    if as_json:
        emit_json(result.as_dict())
        return
    success(f"exported snapshot {result.snapshot_id}")
    detail(f"  {result.bundle}")
    counts = ", ".join(f"{count} {name}" for name, count in sorted(result.counts.items()))
    detail(f"  {counts}")
    if with_markdown:
        detail(f"  {result.markdown_files} markdown file(s)")


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
