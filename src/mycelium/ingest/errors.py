# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Ingestion's failure taxonomy (spec 02 §5, spec 05 §3).

The distinctions are not decoration — each one is answered differently:

- :class:`ConnectorError` — custody failed. The build refuses; nothing about the
  source is trustworthy enough to record.
- :class:`ParseError` — one document could not be represented. Ingestion
  quarantines it, reports it, and carries on (roadmap 4.6). Two subclasses name
  *where* it happened, because a quarantine record has to say: :class:`GuardError`
  refused the bytes before an engine saw them, :class:`LossBudgetError` accepted
  them and refused the projection.
- :class:`UnsupportedMediaTypeError` — no *configured* parser declares the type.
  Also a quarantine, but the remedy is a configuration edit, so the message names
  the media type and what is pinned.
- :class:`CustodyError` — tier-1 evidence is missing, unreadable, or contradicts
  itself. Never quarantined and never degraded past: custody is the thing a
  citation rests on, so a build that cannot trust it must stop and say so
  (ADR-0033).
- :class:`PluginUnavailableError` — a pinned plugin's runtime is not installed
  here. This is a hard error at resolution time, never a silent fall-through to
  the next parser in the list: "best available" is exactly what spec 05 §4.2
  forbids, because it makes a build unexplainable from its manifest.
"""

__all__ = [
    "ConnectorError",
    "CustodyError",
    "GuardError",
    "IngestError",
    "LossBudgetError",
    "ParseError",
    "PluginError",
    "PluginUnavailableError",
    "SourceTooLargeError",
    "UnknownPluginError",
    "UnsupportedMediaTypeError",
]


class IngestError(RuntimeError):
    """Base of every ingestion failure."""


class ConnectorError(IngestError):
    """A source could not be taken into custody."""


class SourceTooLargeError(ConnectorError):
    """The source exceeds the connector's byte ceiling.

    A ceiling exists because acquisition reads into memory and the input is
    untrusted (D-017): "read whatever the file claims to be" is how a hostile
    fixture takes a build down instead of being quarantined by it.
    """


class CustodyError(IngestError):
    """Tier-1 custody is missing, unreadable, or self-contradictory.

    Distinct from every other failure here because it is the only one that is
    not about *this* document: the build cache going bad costs a recompile
    (D-005), but evidence going bad means a citation has nothing behind it.
    """


class ParseError(IngestError):
    """The acquired bytes could not be compiled into KIR."""


class GuardError(ParseError):
    """The bytes were refused *before* an engine was asked to read them.

    A subclass rather than a sibling because every caller that quarantines a
    parse failure quarantines this one identically — the distinction exists so a
    quarantine record can say which step refused (roadmap 4.6), and a
    hand-written check of the error's *message* would be a stage classifier one
    reworded sentence away from being wrong.
    """


class LossBudgetError(ParseError):
    """The document parsed, and lost more than `[ingest] max_failed_elements` allows.

    Also a `ParseError`: the outcome is the same per-document quarantine. The
    separate type is what lets a quarantine record distinguish "this file cannot
    be read" from "this file was read and arrived too damaged to project", which
    are different problems with different answers (ADR-0034).
    """


class UnsupportedMediaTypeError(IngestError):
    """No pinned parser declares the source's media type."""


class PluginError(IngestError):
    """A plugin could not be resolved."""


class UnknownPluginError(PluginError):
    """The configuration names a plugin id nothing provides."""


class PluginUnavailableError(PluginError):
    """A pinned plugin exists but its runtime is missing here.

    Its message is operator-facing and always names the next action — the extra
    to install, the binary to put on PATH — because the alternative is a build
    that quietly parses with something else.
    """
