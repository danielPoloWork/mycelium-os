# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Ingestion's failure taxonomy (spec 02 §5, spec 05 §3).

The distinctions are not decoration — each one is answered differently:

- :class:`ConnectorError` — custody failed. The build refuses; nothing about the
  source is trustworthy enough to record.
- :class:`ParseError` — one document could not be represented. Ingestion
  quarantines it, reports it, and carries on (roadmap 4.6).
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
    "IngestError",
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
