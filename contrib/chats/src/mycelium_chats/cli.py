# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""``mycelium chats …`` — the module's CLI surface (doc 08 §9).

D-023's third extension mechanism, and the one this module actually needs: a
Typer sub-app, mounted by the core at ``mycelium chats`` because the
distribution is installed, and refusing to act on a repository whose
``[modules] enabled`` does not name it.

**The core's conventions are followed rather than reinvented** (ADR-0010): one
JSON document on stdout under ``--json``, exit 0/1/2 for ok/failed/usage, colour
only on a TTY, and every read command offering ``--json``. That consistency is
the reason this file imports :mod:`mycelium.cli.output` — a module that printed
its own way would make ``mycelium`` two CLIs wearing one name. It is also a
coupling worth naming: those helpers are a *component*, not part of the plugin
API the 1.0 freeze covers, which ADR-0077 records.

Six commands, each one row of doc 08 §9's table.
"""

import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Final

import typer
from pydantic import ValidationError

from mycelium.cli.output import ExitCode, detail, emit_json, fail, success, warn
from mycelium.config import ConfigError, MyceliumConfig, load_config
from mycelium.modules import ModuleError, require_enabled
from mycelium_chats.archive import (
    ArchiveEntry,
    ImportOutcome,
    find,
    import_text,
    list_archive,
    load_record,
    purge,
)
from mycelium_chats.formats import FORMATS, render, tail
from mycelium_chats.paths import projection_path
from mycelium_chats.readers import READERS, ReaderError
from mycelium_chats.record import Message
from mycelium_chats.settings import ChatsSettings

__all__ = ["MODULE_ID", "app"]

MODULE_ID: Final = "chats"

app = typer.Typer(
    name=MODULE_ID,
    help="Archive, browse and re-export local chat transcripts (module `chats`).",
    no_args_is_help=True,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

_ROOT = Annotated[Path, typer.Option("--root", help="Repository root.")]
_JSON = Annotated[bool, typer.Option("--json", help="Emit JSON.")]


def _settings(root: Path) -> tuple[MyceliumConfig, ChatsSettings]:
    """Load the repository's configuration and this module's own section.

    Three failures, all usage errors, all reported before anything is read or
    written: the file is invalid, the module is not enabled here, or `[chats]`
    says something this module cannot honour. Each is the operator stating an
    intent that cannot be satisfied, which is exactly what exit code 2 is for
    (ADR-0010).
    """
    try:
        config = load_config(root)
    except ConfigError as error:
        raise fail(str(error), code=ExitCode.USAGE) from error
    try:
        require_enabled(MODULE_ID, config.modules.enabled)
    except ModuleError as error:
        raise fail(str(error), code=ExitCode.USAGE) from error
    try:
        settings = ChatsSettings.model_validate(config.module_settings(MODULE_ID))
    except ValidationError as error:
        lines = [f"{root / 'mycelium.toml'}: invalid [chats] section"]
        lines.extend(
            f"  {'.'.join(str(part) for part in item['loc']) or '(root)'}: {item['msg']}"
            for item in error.errors()
        )
        raise fail("\n".join(lines), code=ExitCode.USAGE) from error
    return config, settings


def _resolve(root: Path, conv_id: str) -> ArchiveEntry:
    try:
        entry = find(root, conv_id)
    except ValueError as error:
        raise fail(str(error), code=ExitCode.USAGE) from error
    if entry is None:
        raise fail(
            f"no archived conversation matches {conv_id!r}; `mycelium chats list` shows them",
            code=ExitCode.FAILED,
        )
    return entry


@app.command("import")
def import_(
    sources: Annotated[
        list[str],
        typer.Argument(help="Export files, transcripts, or `-` to read standard input."),
    ],
    project: Annotated[
        str | None, typer.Option("--project", help="Where to file it. Required (doc 08 §5).")
    ] = None,
    provider: Annotated[
        str | None, typer.Option("--provider", help=f"Pin a reader: {READERS}.")
    ] = None,
    title: Annotated[
        str | None, typer.Option("--title", help="Override the export's title.")
    ] = None,
    root: _ROOT = Path(),
    as_json: _JSON = False,
) -> None:
    """Import export files, transcripts, or a paste on stdin."""
    config, settings = _settings(root)
    chosen = project or settings.default_project
    if not chosen:
        raise fail(
            "a conversation needs a project: pass --project, or set "
            "[chats] default_project in mycelium.toml",
            code=ExitCode.USAGE,
        )

    outcomes: list[ImportOutcome] = []
    warnings: list[str] = []
    failures: list[tuple[str, str]] = []
    for source in sources:
        try:
            text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
        except OSError as error:
            failures.append((source, str(error)))
            continue
        try:
            found, notes = import_text(
                root,
                text,
                source_uri=source,
                project=chosen,
                provider=provider,
                title=title,
                settings=settings,
                knowledge_dir=config.project.knowledge_dir,
            )
        except (ReaderError, ValueError) as error:
            # Per input, never the whole run: the quarantine-not-abort rule
            # (spec 02 §5) applied to an authoring command.
            failures.append((source, str(error)))
            continue
        outcomes.extend(found)
        warnings.extend(notes)

    if as_json:
        emit_json(
            {
                "root": str(root),
                "project": chosen,
                "imported": [
                    {
                        "conv_id": item.transcript.conversation.conv_id,
                        "title": item.transcript.conversation.title,
                        "provider": item.transcript.conversation.provider,
                        "record": str(item.record_path),
                        "projection": str(item.projection_path) if item.projection_path else None,
                        "written": item.written,
                        "fidelity": item.fidelity.model_dump(mode="json"),
                    }
                    for item in outcomes
                ],
                "warnings": warnings,
                "failed": [{"source": source, "error": message} for source, message in failures],
            }
        )
    else:
        for item in outcomes:
            conversation = item.transcript.conversation
            success(
                f"archived {conversation.conv_id} — {conversation.title!r} "
                f"({item.fidelity.turns} turn(s) from {conversation.provider})"
            )
            detail(f"  record      {item.record_path}" + ("" if item.written else "  (unchanged)"))
            detail(
                f"  projection  {item.projection_path}"
                if item.projection_path
                else "  projection  none (excluded by retention)"
            )
            report = item.fidelity
            detail(
                f"  fidelity    {report.recognised} recognised, {report.inferred} inferred, "
                f"{report.fragments} fragment(s), {report.lost} lost"
            )
        for note in warnings:
            warn(note)
        for source, message in failures:
            warn(f"{source}: {message}")
        if outcomes:
            typer.echo("Run `mycelium build` to index the new projections.")

    if failures and not outcomes:
        raise typer.Exit(ExitCode.FAILED)


@app.command("list")
def list_(
    project: Annotated[str | None, typer.Option("--project", help="Only this project.")] = None,
    since: Annotated[
        datetime | None,
        typer.Option("--since", formats=["%Y-%m-%d"], help="Only conversations from this date."),
    ] = None,
    root: _ROOT = Path(),
    as_json: _JSON = False,
) -> None:
    """List archived conversations, newest first."""
    _settings(root)
    entries = list_archive(root, project=project)
    if since is not None:
        cutoff = since.replace(tzinfo=UTC) if since.tzinfo is None else since
        entries = tuple(
            entry
            for entry in entries
            if (entry.conversation.started_at or entry.conversation.imported_at) >= cutoff
        )

    if as_json:
        emit_json(
            {
                "root": str(root),
                "conversations": [
                    {
                        "conv_id": entry.conversation.conv_id,
                        "title": entry.conversation.title,
                        "project": entry.conversation.project,
                        "provider": entry.conversation.provider,
                        "started_at": _stamp(entry.conversation.started_at),
                        "imported_at": _stamp(entry.conversation.imported_at),
                        "messages": entry.messages,
                        "structure_inferred": entry.conversation.structure_inferred,
                        "record": str(entry.record_path),
                    }
                    for entry in entries
                ],
            }
        )
        return

    if not entries:
        success("no conversations archived yet")
        detail("  import one with `mycelium chats import <export.json> --project <name>`")
        return
    success(f"{len(entries)} conversation(s)")
    for entry in entries:
        conversation = entry.conversation
        when = (_stamp(conversation.started_at) or _stamp(conversation.imported_at) or "")[:10]
        flag = "  (inferred)" if conversation.structure_inferred else ""
        typer.echo(
            f"  {conversation.conv_id[-6:].lower()}  {when}  {conversation.project:<14}"
            f"  {conversation.provider:<11}  {entry.messages:>3} msg  {conversation.title}{flag}"
        )


@app.command()
def show(
    conv_id: Annotated[str, typer.Argument(help="Conversation id, or a unique prefix of one.")],
    root: _ROOT = Path(),
    as_json: _JSON = False,
) -> None:
    """Render one archived conversation."""
    _settings(root)
    entry = _resolve(root, conv_id)
    transcript = load_record(root / entry.record_path)
    conversation = transcript.conversation

    if as_json:
        emit_json(
            {
                "conversation": conversation.model_dump(mode="json"),
                "lines": [line.model_dump(mode="json") for line in transcript.lines],
                "record": str(entry.record_path),
            }
        )
        return

    success(f"{conversation.conv_id} — {conversation.title}")
    detail(
        f"  {conversation.provider} · project {conversation.project} · "
        f"{len(transcript.messages)} message(s)"
        + (f" · started {_stamp(conversation.started_at)}" if conversation.started_at else "")
    )
    if conversation.structure_inferred:
        warn("turn boundaries in this conversation were inferred, not read")
    if conversation.secrets:
        warn(f"secret-pattern matches recorded: {', '.join(conversation.secrets)}")
    for line in transcript.lines:
        who = line.role if isinstance(line, Message) else "fragment"
        model = f" ({line.model})" if isinstance(line, Message) and line.model else ""
        typer.echo("")
        typer.echo(f"[{line.seq}] {who}{model}")
        typer.echo(line.content)


def _caution_about_secrets(transcript: object) -> None:
    """Warn before a record's own text leaves the archive.

    Doc 08 §6 keeps a secret in the *record* by default and redacts the
    projection, because the record is the archive and the original is already in
    custody. An export is a copy of the record, so it carries what the record
    carries — which is correct and is exactly the moment to say so out loud. The
    remedy is named: `[chats] redact_in_record`, or `--format markdown`, which is
    rendered rather than copied.
    """
    conversation = getattr(transcript, "conversation", None)
    flags = getattr(conversation, "secrets", ()) if conversation is not None else ()
    if not flags:
        return
    warn(
        f"this conversation records secret-pattern matches ({', '.join(flags)}) and the "
        "record keeps the original text, so this export carries them. Set "
        "[chats] redact_in_record = true and re-import to change that."
    )


@app.command()
def export(
    conv_id: Annotated[str, typer.Argument(help="Conversation id, or a unique prefix of one.")],
    fmt: Annotated[str, typer.Option("--format", help=f"One of: {', '.join(FORMATS)}.")] = "jsonl",
    out: Annotated[
        Path | None, typer.Option("--out", help="Write here instead of standard output.")
    ] = None,
    root: _ROOT = Path(),
) -> None:
    """Emit a portable form of one conversation."""
    _settings(root)
    entry = _resolve(root, conv_id)
    transcript = load_record(root / entry.record_path)
    try:
        rendered = render(transcript, fmt)
    except ValueError as error:
        raise fail(str(error), code=ExitCode.USAGE) from error

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered.text, encoding="utf-8", newline="\n")
        success(f"wrote {rendered.messages} message(s) as {rendered.format} to {out}")
    else:
        # The rendering is this command's entire stdout, so notes go to stderr
        # — the same split `--json` commands make (ADR-0010).
        typer.echo(rendered.text, nl=False)
    _caution_about_secrets(transcript)
    for note in rendered.dropped:
        warn(note)


@app.command()
def resume(
    conv_id: Annotated[str, typer.Argument(help="Conversation id, or a unique prefix of one.")],
    fmt: Annotated[
        str, typer.Option("--format", help=f"One of: {', '.join(FORMATS)}.")
    ] = "markdown",
    turns: Annotated[int | None, typer.Option("--tail", help="Only the last N turns.")] = None,
    budget_tokens: Annotated[
        int | None, typer.Option("--budget-tokens", help="Fit the tail into a token budget.")
    ] = None,
    out: Annotated[
        Path | None, typer.Option("--out", help="Write here instead of standard output.")
    ] = None,
    root: _ROOT = Path(),
) -> None:
    """Emit a continuation package: paste it into any chatbot and keep going."""
    _settings(root)
    if turns is not None and budget_tokens is not None:
        raise fail(
            "--tail and --budget-tokens are two ways to say the same thing; pass one",
            code=ExitCode.USAGE,
        )
    entry = _resolve(root, conv_id)
    transcript = load_record(root / entry.record_path)
    selected = tail(transcript, turns=turns, budget_tokens=budget_tokens)
    try:
        rendered = render(transcript, fmt, lines=selected)
    except ValueError as error:
        raise fail(str(error), code=ExitCode.USAGE) from error

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered.text, encoding="utf-8", newline="\n")
        success(f"wrote a {rendered.messages}-message continuation as {rendered.format} to {out}")
    else:
        typer.echo(rendered.text, nl=False)
    if len(selected) < len(transcript.lines):
        warn(
            f"truncated to the last {len(selected)} of {len(transcript.lines)} turn(s), "
            "oldest first — the archive is unchanged"
        )
    _caution_about_secrets(transcript)
    for note in rendered.dropped:
        warn(note)


@app.command()
def delete(
    conv_id: Annotated[str, typer.Argument(help="Conversation id, or a unique prefix of one.")],
    purge_custody: Annotated[
        bool,
        typer.Option("--purge", help="Also delete the archived original from tier-1 custody."),
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Do not ask.")] = False,
    root: _ROOT = Path(),
    as_json: _JSON = False,
) -> None:
    """Delete one conversation: record, projection, and optionally its original."""
    config, _ = _settings(root)
    entry = _resolve(root, conv_id)
    conversation = entry.conversation

    if not yes and not as_json:
        # Deletion is the one command here that destroys something, and doc 08 §8
        # makes it a cascade. Confirming by default is the difference between a
        # tool an operator trusts with an archive and one they do not.
        typer.echo(f"About to delete {conversation.conv_id} — {conversation.title!r}:")
        typer.echo(f"  record      {entry.record_path}")
        typer.echo(
            f"  projection  {projection_path(entry.record_path, config.project.knowledge_dir)}"
        )
        typer.echo(
            f"  original    {'deleted from custody' if purge_custody else 'kept in custody'}"
        )
        if not typer.confirm("Delete it?"):
            raise typer.Exit(ExitCode.OK)

    removed = purge(
        root,
        entry,
        knowledge_dir=config.project.knowledge_dir,
        purge_custody=purge_custody,
    )
    if as_json:
        emit_json(
            {
                "conv_id": conversation.conv_id,
                "removed": [str(path) for path in removed],
                "custody_purged": purge_custody,
            }
        )
        return
    success(f"deleted {conversation.conv_id} — {conversation.title!r}")
    for path in removed:
        detail(f"  removed  {path}")
    if not purge_custody:
        detail("  kept     the original in tier-1 custody (--purge removes it)")
    typer.echo("Run `mycelium build` to drop it from the index.")


def _stamp(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    return value.isoformat()
