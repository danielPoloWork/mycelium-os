# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The quarantine: sources the evidence lane refused, kept where they can be seen.

Spec 02 §5 says a malformed or hostile file is *recorded, skipped, and reported*,
and never aborts the build. `mycelium ingest` has skipped and reported since
roadmap 4.1 — a warning on stderr and a non-zero exit. What was missing is the
first verb, and it is the one that matters most in practice: an operator ingests
a directory, sees three warnings scroll past, and an hour later has no way to
answer *which three, and why*.

So a refusal writes a :class:`~mycelium.sdk.types.QuarantineRecord` under
`.mycelium/quarantine/`, one file per source, named by a digest of the source URI
so re-ingesting the same failing file amends its record rather than accumulating
another. Three properties are deliberate:

**A quarantine points at the bytes that caused it.** Ingestion stores the
acquired original before it tries to parse it (ADR-0033), so every failure past
acquisition already has its input in tier-1 custody, and the record carries that
digest. That is what makes a quarantine *re-examinable* rather than merely
counted.

**Success clears it.** A source that is fixed, re-exported, or ingested with a
parser that can read it drops out of the quarantine as a side effect of working —
because a list that only grows is a list nobody reads. This is the one write that
deletes, and it is why :func:`clear` exists beside :func:`record`.

**Nothing sweeps it and nothing digests it.** `mycelium gc` leaves quarantine
records alone for the same reason it leaves custody alone: an operator's evidence
that something is wrong is not litter (ADR-0033). They take part in no build key
and no manifest — a quarantine is a fact about a *machine's* attempt to ingest,
not about a published snapshot — so the `last_seen` timestamp that moves on every
attempt cannot make anything non-reproducible.
"""

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from mycelium.ingest.errors import (
    ConnectorError,
    GuardError,
    IngestError,
    LossBudgetError,
    UnsupportedMediaTypeError,
)
from mycelium.layout import QUARANTINE_DIRNAME, atomic_write_bytes
from mycelium.sdk.identity import digest_text
from mycelium.sdk.types import QuarantineRecord, QuarantineStage, Sha256Digest

__all__ = ["Quarantine", "quarantine_root", "stage_of"]

_RECORD_SUFFIX: Final = ".json"


def quarantine_root(mycelium_dir: Path) -> Path:
    """Where quarantine records live: ``.mycelium/quarantine/``."""
    return mycelium_dir / QUARANTINE_DIRNAME


def stage_of(error: IngestError) -> QuarantineStage:
    """Which step of the lane an error came from.

    Read off the error's *type*, never its message. The failure taxonomy already
    encodes the answer (:mod:`mycelium.ingest.errors`), and that is why 4.6 split
    `GuardError` and `LossBudgetError` out of `ParseError` rather than pattern-
    matching on prose: a stage classifier that reads sentences is one reworded
    message away from being wrong, and nothing would catch it.
    """
    if isinstance(error, UnsupportedMediaTypeError):
        return QuarantineStage.DISPATCH
    if isinstance(error, ConnectorError):
        return QuarantineStage.ACQUIRE
    if isinstance(error, GuardError):
        return QuarantineStage.GUARD
    if isinstance(error, LossBudgetError):
        return QuarantineStage.BUDGET
    return QuarantineStage.PARSE


class Quarantine:
    """The quarantine for one repository."""

    def __init__(self, mycelium_dir: Path) -> None:
        self._root = quarantine_root(mycelium_dir)

    @property
    def root(self) -> Path:
        return self._root

    def path_for(self, source_uri: str) -> Path:
        """One file per source URI, named by its digest.

        The URI itself cannot be the filename — it carries `/`, `:` and whatever
        else the source's own name contained — and a digest is stable across
        platforms, which a sanitised name is not.
        """
        return self._root / (digest_text(source_uri).removeprefix("sha256:") + _RECORD_SUFFIX)

    # -- writing ----------------------------------------------------------

    def record(
        self,
        source_uri: str,
        error: IngestError,
        *,
        media_type: str | None = None,
        source_digest: Sha256Digest | None = None,
        now: datetime | None = None,
    ) -> QuarantineRecord:
        """Quarantine `source_uri`, or refresh the record it already has."""
        moment = now or datetime.now(tz=UTC)
        existing = self.get(source_uri)
        record = QuarantineRecord(
            source_uri=source_uri,
            stage=stage_of(error),
            reason=type(error).__name__,
            detail=str(error),
            media_type=media_type,
            source_digest=source_digest,
            # Set once and never moved — the same rule custody's `first_seen`
            # obeys, and for the same reason: "since when" is the question.
            first_seen=existing.first_seen if existing else moment,
            last_seen=moment,
        )
        self._root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
        atomic_write_bytes(self.path_for(source_uri), payload.encode("utf-8"))
        return record

    def clear(self, source_uri: str) -> bool:
        """Drop `source_uri`'s record; ``True`` when there was one.

        Called on every successful ingestion, so a repaired source leaves the
        quarantine without anyone having to remember to say so.
        """
        path = self.path_for(source_uri)
        try:
            path.unlink()
        except (FileNotFoundError, NotADirectoryError):
            return False
        return True

    # -- reading ----------------------------------------------------------

    def get(self, source_uri: str) -> QuarantineRecord | None:
        """The record for `source_uri`, or ``None``."""
        return self._read(self.path_for(source_uri))

    def records(self) -> Iterator[QuarantineRecord]:
        """Every quarantine record, oldest failure first.

        Ordered by `first_seen` rather than by filename: the filename is a digest,
        so its order is noise, and the question an operator opens this list with
        is "what has been broken longest".
        """
        if not self._root.is_dir():
            return
        found = [
            record
            for path in sorted(self._root.iterdir())
            if path.suffix == _RECORD_SUFFIX and path.is_file()
            for record in (self._read(path),)
            if record is not None
        ]
        yield from sorted(found, key=lambda item: (item.first_seen, item.source_uri))

    def count(self) -> int:
        """How many sources are quarantined."""
        return sum(1 for _ in self.records())

    def _read(self, path: Path) -> QuarantineRecord | None:
        """One record, or ``None`` when it is absent or unreadable.

        Unreadable is `None` rather than an exception on purpose: this is a
        *diagnostic* store, and a corrupt note about a failed document must not
        become a second failure that hides the first.
        """
        try:
            raw = path.read_text(encoding="utf-8")
        except (FileNotFoundError, NotADirectoryError):
            return None
        try:
            return QuarantineRecord.model_validate_json(raw)
        except ValueError:
            return None
