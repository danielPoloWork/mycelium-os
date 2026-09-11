# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The archive: identity, custody, secrets, fidelity, and where a record lives.

What a reader hands back is *what it found*; everything that makes it an archive
entry happens here, and each step is one of doc 08's own rules.

**Identity is derived, not minted** (ADR-0046's mechanism, borrowed). ``conv_id``
is a ULID derived from the original's content digest and the provider's own
conversation id, so importing the same export twice produces the same id, the
same path, and byte-identical files — an import is *idempotent*, which is what
lets a nightly re-export be a safe habit rather than a way to accumulate
duplicates. ADR-0046's warning about derived ids does not bite here: it says a
derived id renames when its *name* does, and this name is a content digest.

**The original is kept** (doc 08 §4, invariant 5). The bytes that arrived go into
tier-1 custody under their own digest before anything is written, so the archive
is re-derivable and every quote has something behind it. This is the same
:class:`mycelium.ingest.Custody` the evidence lane uses — one tier-1 store per
repository, not one per module.

**Secrets are redacted where they would spread, and kept where they are
evidence** (doc 08 §6). The scan runs on the conversation's own text. A hit is
recorded in the header, redacted in the projection — the file that reaches Git
and the index — and left in the *record* unless ``[chats] redact_in_record``
says otherwise, because the record is the archive and the original is already
in custody. The asymmetry is deliberate and is the same one ADR-0037 made for
ingestion.

**The fidelity report is this module's own record, and that is a finding.**
:class:`mycelium.sdk.types.FidelityReport` requires a ``kir_digest`` and counts
KIR nodes: it describes a parser's output, and a chat import has no KIR at all
until the compiler later parses the projection. So "every import emits a fidelity
report" (spec 02 §5) is a doctrine the core's *record* cannot express for a
non-KIR source, and :class:`ChatFidelity` is what that costs — noted for the 1.0
freeze in ADR-0077 rather than worked around silently.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Final, Literal

from pydantic import NonNegativeInt

from mycelium.ingest import Custody, redact_text, scan_text
from mycelium.sdk.identity import canonical_json, derived_ulid, digest_bytes
from mycelium.sdk.types import CustodyKind, Record, Sha256Digest, Ulid
from mycelium_chats.paths import ARCHIVE_DIRNAME, RECORD_SUFFIX, archive_path, projection_path
from mycelium_chats.projection import project_transcript
from mycelium_chats.readers import ImportContext, ReadResult, reader_for
from mycelium_chats.readers.base import ReadConversation
from mycelium_chats.record import (
    Conversation,
    Fragment,
    Message,
    Transcript,
    decode_transcript,
    encode_transcript,
    participants_of,
    renumber,
)
from mycelium_chats.settings import ChatsSettings

__all__ = [
    "CHATS_MEDIA_TYPE",
    "ArchiveEntry",
    "ChatFidelity",
    "ImportOutcome",
    "archive_dir",
    "find",
    "import_text",
    "list_archive",
    "load_record",
    "purge",
    "record_path_of",
]

CHATS_MEDIA_TYPE: Final = "application/x-mycelium-chat"
"""What the original input is filed as in custody.

A made-up media type, and honestly so: the bytes may be JSON, Markdown or a
paste, and custody records what the *module* took in rather than what a sniffer
would call it. The reader that read it is in the record.
"""


class ChatFidelity(Record):
    """What one import accounted for (doc 08 §6), in this module's own shape."""

    schema_version: Literal["mycelium/chat-fidelity/v0"] = "mycelium/chat-fidelity/v0"
    conv_id: Ulid
    source_digest: Sha256Digest
    reader: str
    turns: NonNegativeInt
    """Every source turn accounted for: ``recognised + inferred + fragments``."""
    recognised: NonNegativeInt
    """Read from structure the source states — a provider's message list, a
    transcript's role marker."""
    inferred: NonNegativeInt
    """Boundaries or roles guessed, content still verbatim (invariant 2)."""
    fragments: NonNegativeInt
    """Residue kept whole because no reader could segment it — preamble, an
    abandoned edit branch, an unlabelled paste."""
    lost: NonNegativeInt = 0
    """Source content that reached no line of the record.

    Zero for every reader in v1, by construction rather than by luck: a reader
    that cannot place text raises rather than skipping it, and text it can place
    but not attribute becomes a fragment. The field exists so that a reader which
    one day *can* lose something has somewhere honest to say so — the same reason
    :class:`~mycelium.sdk.types.FidelityReport` keeps a ``lost`` count that is
    usually zero.
    """
    warnings: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        """Whether every turn was read from stated structure."""
        return self.lost == 0 and self.inferred == 0 and self.fragments == 0


@dataclass(frozen=True, slots=True)
class ImportOutcome:
    """One conversation, archived."""

    transcript: Transcript
    record_path: PurePosixPath
    """Repository-relative, POSIX — under `chats/`."""
    projection_path: PurePosixPath | None
    """``None`` when retention excluded it from the vault (doc 08 §8)."""
    fidelity: ChatFidelity
    written: bool
    """False when the record on disk was already byte-identical — a re-import."""


@dataclass(frozen=True, slots=True)
class ArchiveEntry:
    """One record on disk, as `chats list` reads it: the header and its path."""

    conversation: Conversation
    record_path: PurePosixPath
    messages: int


def archive_dir(root: Path) -> Path:
    return root / ARCHIVE_DIRNAME


def record_path_of(conversation: Conversation, settings: ChatsSettings) -> PurePosixPath:
    """Where this conversation's record lives, dated in the configured timezone."""
    return archive_path(
        project=conversation.project,
        title=conversation.title,
        conv_id=conversation.conv_id,
        dated=conversation.started_at or conversation.imported_at,
        zone=settings.tzinfo(),
    )


def import_text(
    root: Path,
    text: str,
    *,
    source_uri: str,
    project: str,
    provider: str | None = None,
    title: str | None = None,
    settings: ChatsSettings | None = None,
    knowledge_dir: str = "knowledge",
    now: datetime | None = None,
) -> tuple[tuple[ImportOutcome, ...], tuple[str, ...]]:
    """Read `text`, archive every conversation in it, and project each one.

    Returns the outcomes and the warnings the whole import wants said. Raises
    :class:`~mycelium_chats.readers.ReaderError` when no reader can read the
    input — a per-input failure the caller reports and carries on from, which is
    the quarantine-not-abort rule (spec 02 §5) applied to an authoring command.
    """
    options = settings or ChatsSettings()
    imported = now or datetime.now(tz=UTC)
    data = text.encode("utf-8")
    source_digest = digest_bytes(data)

    reader = reader_for(
        text, provider=provider, source_uri=source_uri, mapping=options.mapping or None
    )
    result: ReadResult = reader.read(
        text,
        ImportContext(project=project, title=title, source_uri=source_uri, mapping=options.mapping),
    )

    # Custody before anything is written: the original is the evidence, and a
    # record whose original never landed would be a citation with nothing behind
    # it. Idempotent by digest, so a re-import stores nothing new.
    custody = Custody(root / ".mycelium")
    held = custody.put(
        data,
        kind=CustodyKind.ORIGINAL,
        media_type=CHATS_MEDIA_TYPE,
        source_uri=source_uri or "-",
        connector=f"chats/{reader.id}",
        now=imported,
    )
    # And `imported_at` is custody's `first_seen`, not this run's clock. Custody
    # never moves that timestamp (ADR-0033), so a second import of the same
    # bytes rebuilds the identical header — which is what makes the whole
    # operation idempotent rather than merely repeatable. Taking `now` here
    # instead would rewrite the record and its committed projection on every
    # run, for no change in the conversation.
    imported = held.first_seen

    outcomes: list[ImportOutcome] = []
    warnings = list(result.warnings)
    for index, found in enumerate(result.conversations):
        outcome, notes = _archive_one(
            root,
            found,
            index=index,
            reader_id=reader.id,
            project=project,
            source_digest=source_digest,
            imported=imported,
            options=options,
            knowledge_dir=knowledge_dir,
            custody=custody,
        )
        outcomes.append(outcome)
        warnings.extend(notes)
    return tuple(outcomes), tuple(warnings)


def _archive_one(  # noqa: PLR0913 - every argument is a fact the caller already has
    root: Path,
    found: ReadConversation,
    *,
    index: int,
    reader_id: str,
    project: str,
    source_digest: Sha256Digest,
    imported: datetime,
    options: ChatsSettings,
    knowledge_dir: str,
    custody: Custody,
) -> tuple[ImportOutcome, list[str]]:
    conv_id = derived_ulid(f"{source_digest}|{found.provider_conv_id or index}")
    lines = tuple(renumber(found.lines))
    lines = tuple(line.model_copy(update={"conv_id": conv_id}) for line in lines)

    inferred = 0
    if found.structure_inferred:
        # A reader that guessed says so once, for the header; the per-message
        # flag is what makes it visible in the record (invariant 2).
        marked: list[Message | Fragment] = []
        for line in lines:
            if isinstance(line, Message):
                marked.append(line.model_copy(update={"meta": {**line.meta, "inferred": True}}))
                inferred += 1
            else:
                marked.append(line)
        lines = tuple(marked)

    findings = scan_text("\n".join(line.content for line in lines))
    flags = tuple(sorted({finding.rule_id for finding in findings}))
    if flags and options.redact_in_record:
        lines = tuple(
            line.model_copy(update={"content": redact_text(line.content, scan_text(line.content))})
            for line in lines
        )

    conversation = Conversation(
        conv_id=conv_id,
        title=found.title,
        project=project,
        provider=reader_id,
        provider_conv_id=found.provider_conv_id,
        started_at=found.started_at,
        imported_at=imported,
        source_digest=source_digest,
        structure_inferred=found.structure_inferred,
        participants=participants_of(lines),
        tags=found.tags,
        secrets=flags,
    )
    transcript = Transcript(conversation=conversation, lines=lines)

    fragments = len(transcript.fragments)
    fidelity = ChatFidelity(
        conv_id=conv_id,
        source_digest=source_digest,
        reader=reader_id,
        turns=len(lines),
        recognised=max(len(transcript.messages) - inferred, 0),
        inferred=inferred,
        fragments=fragments,
        warnings=(),
    )
    custody.put(
        canonical_json(fidelity.model_dump(mode="json")).encode("utf-8"),
        kind=CustodyKind.FIDELITY,
        media_type="application/json",
        derived_from=source_digest,
        now=imported,
    )

    record = record_path_of(conversation, options)
    written = _write_if_changed(root / record, encode_transcript(transcript))

    notes: list[str] = []
    projected: PurePosixPath | None = None
    if _retained(conversation, options, imported):
        rendered = project_transcript(
            transcript,
            record,
            projection=projection_path(record, knowledge_dir),
            findings=bool(flags),
        )
        _write_if_changed(root / rendered.path, rendered.text)
        projected = rendered.path
    else:
        notes.append(
            f"{record}: older than [chats] retention_months = "
            f"{options.retention_months}; archived but not projected or indexed"
        )
    if flags:
        notes.append(
            f"{record}: secret-pattern match ({', '.join(flags)}); redacted in the projection"
            + ("" if options.redact_in_record else " (the record keeps the original text)")
        )
    return (
        ImportOutcome(
            transcript=transcript,
            record_path=record,
            projection_path=projected,
            fidelity=fidelity,
            written=written,
        ),
        notes,
    )


def _retained(conversation: Conversation, options: ChatsSettings, now: datetime) -> bool:
    """Whether doc 08 §8's retention window admits this conversation.

    Counted in whole months from the conversation's own start — its import time
    when the export knew no start — because an archive's window is about when the
    conversation *happened*, not when somebody got round to importing it.
    """
    if options.retention_months is None:
        return True
    stamp = conversation.started_at or conversation.imported_at
    months = (now.year - stamp.year) * 12 + (now.month - stamp.month)
    return months < options.retention_months


def _write_if_changed(path: Path, text: str) -> bool:
    """Write `text` unless the file already holds it. Returns whether it wrote.

    The same idempotence `write_projection` has (roadmap 4.3): a re-import must
    leave no spurious diff, which is what makes re-running an import safe.
    """
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def load_record(path: Path) -> Transcript:
    """Read one `.chat.jsonl` from disk."""
    return decode_transcript(path.read_text(encoding="utf-8"))


def list_archive(root: Path, *, project: str | None = None) -> tuple[ArchiveEntry, ...]:
    """Every archived conversation, newest first (doc 08 §9's `chats list`).

    Reads the whole record rather than only its first line, because the count of
    messages is what a listing is for and a header cannot know it. At archive
    sizes this is a few thousand small files; when that stops being true the
    listing wants an index, and an index wants a reason.
    """
    base = archive_dir(root)
    if not base.is_dir():
        return ()
    entries: list[ArchiveEntry] = []
    for path in sorted(base.rglob(f"*{RECORD_SUFFIX}")):
        try:
            transcript = load_record(path)
        except (OSError, ValueError):
            continue  # `doctor`'s business, not a listing's
        if project is not None and transcript.conversation.project != project:
            continue
        entries.append(
            ArchiveEntry(
                conversation=transcript.conversation,
                record_path=PurePosixPath(path.relative_to(root).as_posix()),
                messages=len(transcript.messages),
            )
        )
    entries.sort(
        key=lambda entry: (
            entry.conversation.started_at or entry.conversation.imported_at,
            entry.conversation.conv_id,
        ),
        reverse=True,
    )
    return tuple(entries)


def find(root: Path, conv_id: str) -> ArchiveEntry | None:
    """The entry whose id matches `conv_id` whole, by prefix, or by **suffix**.

    The suffix is the one that matters, and running the CLI is what showed it.
    `chats list` prints the last six characters as the handle and the filename
    ends with the same six — because identity here is *derived* (ADR-0046), so
    every id begins with ten zeros and a prefix distinguishes nothing. Matching
    only the front would have printed a handle no command accepted.

    A prefix is still accepted, for an operator reading a full id out of a
    record. Ambiguity raises rather than resolving to one of two conversations,
    which is the rule the wikilink resolver follows for the same reason
    (ADR-0018): silently picking one is how a tool starts lying.
    """
    wanted = conv_id.strip().upper()
    if not wanted:
        return None
    matches = [
        entry
        for entry in list_archive(root)
        if entry.conversation.conv_id == wanted
        or entry.conversation.conv_id.startswith(wanted)
        or entry.conversation.conv_id.endswith(wanted)
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        return None
    ids = ", ".join(entry.conversation.conv_id for entry in matches)
    msg = f"{conv_id!r} matches more than one conversation ({ids}); give more characters"
    raise ValueError(msg)


def purge(
    root: Path,
    entry: ArchiveEntry,
    *,
    knowledge_dir: str = "knowledge",
    purge_custody: bool = False,
) -> tuple[PurePosixPath, ...]:
    """Delete one conversation: record, projection, and optionally its original.

    Doc 08 §8's cascade. The **custody blob is kept by default**, which is the one
    decision here worth arguing: it is tier-1 evidence, and ADR-0033 makes
    deleting evidence an explicit act rather than a side effect — so `--purge`
    is what removes it. The index entry needs no action: the next build sees the
    projection gone and drops its rows.
    """
    removed: list[PurePosixPath] = []
    for relative in (entry.record_path, projection_path(entry.record_path, knowledge_dir)):
        target = root / relative
        if target.exists():
            target.unlink()
            removed.append(relative)
    if purge_custody:
        custody = Custody(root / ".mycelium")
        blob = custody.blob_path(entry.conversation.source_digest)
        record = custody.record_path(entry.conversation.source_digest)
        for target in (blob, record):
            if target.exists():
                target.unlink()
                removed.append(PurePosixPath(target.relative_to(root).as_posix()))
    _prune_empty(root / entry.record_path.parent, root)
    return tuple(removed)


def _prune_empty(directory: Path, root: Path) -> None:
    """Remove directories a deletion emptied, up to the archive root.

    An archive tree is dated, so a deleted conversation often leaves an empty
    month behind; leaving those is untidy in a way a human notices in Git.
    """
    current = directory
    limit = archive_dir(root)
    while current != limit and limit in current.parents and current.is_dir():
        if any(current.iterdir()):
            return
        current.rmdir()
        current = current.parent
