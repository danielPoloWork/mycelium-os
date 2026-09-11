# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The ``[chats]`` section — the module's own configuration (doc 08 §§5, 6, 8).

**The core carries this table and does not read it.** `mycelium.toml` is loaded
strictly (ADR-0014) and refused every section spec 05 §2 does not print, which
is why this module could not be configured at all until roadmap 5.5 taught the
loader that a section named after an *installed module* belongs to that module
(ADR-0077). What arrives here is plain data from
:meth:`mycelium.config.MyceliumConfig.module_settings`, and the schema is this
module's — so a field added here is not a core release, which is the whole
point of the split.

The strictness is inherited on purpose: unknown keys are refused with the list
of known ones, exactly as the core's own sections do, because a silently ignored
setting is the failure mode ADR-0014 refuses.
"""

from datetime import UTC, datetime, timedelta, timezone, tzinfo
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = ["LOCAL", "ChatsSettings", "resolve_timezone"]

LOCAL: Final = "local"
"""The default `timezone` value: whatever the importing machine is set to.

Doc 08 §5's reasoning, kept: *"import is an authoring action, so machine-local
dates match user intuition"*. It does make an archive **path** machine-dependent,
which is why the setting exists — pin it to `UTC` or an offset and two machines
importing the same export file agree. The record's timestamps are UTC either way,
so nothing about the conversation itself moves.
"""

_UTC_NAMES: Final = frozenset({"utc", "z"})


class ChatsSettings(BaseModel):
    """`[chats]`, validated. Every field has a spec section behind it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    default_project: str | None = None
    """Used when `--project` is absent. Doc 08 §5 makes `project` required and
    offers two ways to supply it; with neither, `import` refuses and says so."""

    timezone: str = LOCAL
    """`local`, `UTC`, a fixed offset (`+02:00`), or an IANA name (doc 08 §5)."""

    redact_in_record: bool = False
    """Doc 08 §6's default, unchanged. A secret found on import is *always*
    redacted in the projection and the index and flagged in the header; this
    switch decides whether the **record** is rewritten too. Off, because the
    record is the archive and the original is already in custody — turning it on
    trades auditability for a smaller blast radius, which is the operator's call
    and not a default worth making for them."""

    retention_months: int | None = Field(default=None, ge=1)
    """Doc 08 §8. Conversations older than the window are excluded from the
    projection and the index; the archive itself is kept unless `--purge`. `None`
    keeps everything, which is what an archive is for."""

    segmenter: Literal["none", "llm"] = "none"
    """Doc 08 §6's last row: *"Off by default; when enabled, it may propose
    boundaries/roles only"*. `llm` lets an unlabelled paste — the one input the
    deterministic readers keep whole rather than guess at — be segmented by the
    model `[synthesis] provider` names.

    Off by default for the reason every other lane here is: a fresh install makes
    no network call (D-013), and naming a provider is the operator's consent
    (D-017). With this set to `llm` and no provider configured, `import` says so
    and archives the paste exactly as it does today — the floor is a correct
    record, not a failure state (ADR-0088)."""

    mapping: dict[str, str] = Field(default_factory=dict)
    """Field mapping for the `generic` JSON reader (doc 08 §6) — the escape hatch
    for an export shape no built-in reader knows. Keys are this module's field
    names, values are dotted paths into the provider's JSON."""

    @model_validator(mode="after")
    def _timezone_resolves(self) -> Self:
        resolve_timezone(self.timezone)
        return self

    def tzinfo(self) -> tzinfo:
        """The timezone archive paths are dated in."""
        return resolve_timezone(self.timezone)


def resolve_timezone(name: str) -> tzinfo:
    """Turn a `[chats] timezone` value into a real timezone, or say why not.

    Four accepted forms, and the order matters: `local` and `UTC` are answered
    without touching the timezone database, and a fixed offset is parsed here —
    so the common cases need no `tzdata` package. An IANA name is tried through
    :mod:`zoneinfo`, which on Windows has no system database and needs `tzdata`
    installed; the refusal names it rather than leaving a `ZoneInfoNotFoundError`
    to explain itself.
    """
    text = name.strip()
    if not text or text.casefold() == LOCAL:
        return datetime.now().astimezone().tzinfo or UTC
    if text.casefold() in _UTC_NAMES:
        return UTC
    offset = _offset(text)
    if offset is not None:
        return offset
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    except ImportError:  # pragma: no cover - zoneinfo is stdlib from 3.9
        msg = f"[chats] timezone = {name!r} needs the zoneinfo module"
        raise ValueError(msg) from None
    try:
        return ZoneInfo(text)
    except (ZoneInfoNotFoundError, ValueError) as error:
        msg = (
            f"[chats] timezone = {name!r} is not a timezone this machine knows "
            f"({error}). Use 'local', 'UTC', a fixed offset such as '+02:00', or an "
            "IANA name with the `tzdata` package installed."
        )
        raise ValueError(msg) from error


def _offset(text: str) -> tzinfo | None:
    """`+HH:MM` / `-HHMM` / `+HH` as a fixed offset, or ``None`` if it is not one."""
    if not text or text[0] not in "+-":
        return None
    body = text[1:].replace(":", "")
    if not body.isdigit() or len(body) not in (2, 4):
        return None
    hours = int(body[:2])
    minutes = int(body[2:]) if len(body) == 4 else 0
    if hours > 23 or minutes > 59:
        return None
    delta = timedelta(hours=hours, minutes=minutes)
    return timezone(-delta if text[0] == "-" else delta)
