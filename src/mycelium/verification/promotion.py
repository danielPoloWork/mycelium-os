# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Promotion and demotion: a file move, in Git, by a human (D-021).

Verification status is the folder and nothing else. There is no `status:` field
to go stale, no row in the store to disagree with the tree — so changing a
document's status *is* moving the file, and the audit trail is the one every team
already reads: a diff.

That shape is what the three rules here protect:

**Promotion is a decision, not a computation.** `mycelium promote` measures gate
G7 first and refuses below it, but the refusal is overridable — `--force` is in
the spec (05 §1) because a human who has read the document outranks a judge that
could not be reached. A forced promotion writes *why* it was forced into
`verified_by`, so the override is visible in the document, in Git, forever. A
`--force` that only warned on stderr would be an override nobody could audit six
months later.

**Demotion strips the verification block.** A document moved out of `verified/`
is not verified any more, and leaving `verified_by` behind would be a false claim
sitting in the file — the exact drift folder-encoded status exists to prevent.

**Nothing here writes an index.** Both commands touch tier 2 only. The store
learns about the move from the next `mycelium build`, which is the same way it
learns about any edit, and is why a promotion cannot leave the served snapshot
disagreeing with the tree.
"""

import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Final

from mycelium.markdown.frontmatter import upsert
from mycelium.synthesis.candidate import CANDIDATE_DIRNAME
from mycelium.verification.errors import PromotionError

__all__ = [
    "VERIFIED_DIRNAME",
    "Moved",
    "author_name",
    "demote",
    "promote",
    "stamp",
]

VERIFIED_DIRNAME: Final = "verified"
"""Under `knowledge/`: the folder that *is* the verified status (D-021)."""


@dataclass(frozen=True, slots=True)
class Moved:
    """One completed status change."""

    source: PurePosixPath
    destination: PurePosixPath
    verified_by: str | None
    verified_at: date | None
    grounding: float | None
    forced: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "from": self.source.as_posix(),
            "to": self.destination.as_posix(),
            "verified_by": self.verified_by,
            "verified_at": None if self.verified_at is None else self.verified_at.isoformat(),
            "grounding": self.grounding,
            "forced": self.forced,
        }


def _swap_status(relative: PurePosixPath, *, expected: str, wanted: str) -> PurePosixPath:
    """Rewrite the status segment of a repository-relative path.

    The *first* matching segment, so a nested document keeps its subtree:
    `knowledge/candidate/api/retries.md` becomes `knowledge/verified/api/retries.md`.
    """
    parts = list(relative.parts)
    for index, part in enumerate(parts):
        if part == expected:
            parts[index] = wanted
            return PurePosixPath(*parts)
    msg = (
        f"{relative.as_posix()} is not under a {expected}/ folder; verification status is "
        "the folder (D-021), so there is nothing to move"
    )
    raise PromotionError(msg)


def stamp(
    text: str,
    *,
    verified_by: str | None = None,
    verified_at: date | None = None,
    grounding: float | None = None,
    clear: bool = False,
) -> str:
    """Write, or remove, a document's verification block.

    `clear` removes all three fields; otherwise each named field is set and the
    unnamed ones are left alone. The three are a unit as far as the compiler is
    concerned — it ignores a partial block and warns (spec 03 §3) — so a caller
    that sets one must set all three, which is why `promote` measures before it
    moves rather than trusting a number a previous run left behind.
    """
    if clear:
        return upsert(text, {"verified_by": None, "verified_at": None, "grounding": None})
    fields: dict[str, object] = {}
    if verified_by is not None:
        fields["verified_by"] = verified_by
    if verified_at is not None:
        fields["verified_at"] = verified_at
    if grounding is not None:
        fields["grounding"] = round(grounding, 4)
    return upsert(text, fields)


def promote(
    root: Path,
    relative: PurePosixPath,
    *,
    verified_by: str,
    grounding: float,
    at: date,
    forced: bool = False,
) -> Moved:
    """Move a candidate document into `verified/`, stamped with its evidence.

    The gate decision belongs to the caller: this function performs a promotion
    that has already been authorised, and its own refusals are about the move
    being *impossible* rather than unwise.
    """
    destination = _swap_status(relative, expected=CANDIDATE_DIRNAME, wanted=VERIFIED_DIRNAME)
    source_file, destination_file = root / relative, root / destination
    _check_move(source_file, destination_file)

    stamped = stamp(
        source_file.read_text(encoding="utf-8"),
        verified_by=verified_by,
        verified_at=at,
        grounding=grounding,
    )
    destination_file.parent.mkdir(parents=True, exist_ok=True)
    destination_file.write_text(stamped, encoding="utf-8", newline="")
    source_file.unlink()
    return Moved(
        source=relative,
        destination=destination,
        verified_by=verified_by,
        verified_at=at,
        grounding=round(grounding, 4),
        forced=forced,
    )


def demote(root: Path, relative: PurePosixPath) -> Moved:
    """Move a verified document back to `candidate/`, dropping its verification.

    No score is recorded on the way down and none is kept: a demoted document's
    grounding is not *bad*, it is no longer vouched for, and a number left in the
    file would read as the second thing.
    """
    destination = _swap_status(relative, expected=VERIFIED_DIRNAME, wanted=CANDIDATE_DIRNAME)
    source_file, destination_file = root / relative, root / destination
    _check_move(source_file, destination_file)

    cleared = stamp(source_file.read_text(encoding="utf-8"), clear=True)
    destination_file.parent.mkdir(parents=True, exist_ok=True)
    destination_file.write_text(cleared, encoding="utf-8", newline="")
    source_file.unlink()
    return Moved(
        source=relative,
        destination=destination,
        verified_by=None,
        verified_at=None,
        grounding=None,
    )


def _check_move(source: Path, destination: Path) -> None:
    if not source.is_file():
        msg = f"{source} is not a file"
        raise PromotionError(msg)
    if destination.exists():
        msg = (
            f"{destination} already exists; move or delete it first — overwriting a "
            "document in the other status folder would lose whichever one is there"
        )
        raise PromotionError(msg)


def author_name() -> str:
    """Who is performing a promotion, for `verified_by`.

    Git's configured name first, because a promotion is a commit waiting to
    happen and the two should agree. The OS user is the fallback; `--by` is the
    override. Never `@me`-style magic: the name lands in a tracked file, so it has
    to be a name a reviewer recognises.
    """
    try:
        completed = subprocess.run(  # fixed argument vector, no shell
            ["git", "config", "user.name"],  # noqa: S607 - resolved through PATH by design
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        completed = None
    if completed is not None and completed.returncode == 0:
        name = completed.stdout.decode("utf-8", errors="replace").strip()
        if name:
            return name
    return _os_user()


def _os_user() -> str:
    import getpass  # noqa: PLC0415 - only needed on the fallback path

    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - getuser raises OSError, KeyError, ImportError...
        return "unknown"
