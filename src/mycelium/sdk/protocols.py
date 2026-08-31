# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The plugin contracts an ingestion source is compiled through (spec 05 §4).

Two Protocols, one transport object, one identity record. They are the fourth of
the five contracts architecture §10 freezes at 1.0, so the shapes here are chosen
to survive the platform phase rather than to be convenient today:

``Connector``
    Turns a *source reference* into bytes with custody — a digest, a media type,
    and the URI it came from. Acquisition is where untrusted input enters the
    system (D-017), so a connector is also where path safety, size limits, and
    scheme allow-listing live.

``Parser``
    Turns those bytes into KIR. Mycelium OS owns the representation and its
    guarantees, never the parsing research (D-007): every parser here is an
    adapter over an existing engine, and the adapter's whole job is to lose
    nothing silently.

The split matters because the two fail differently. A connector failure is about
*custody* — the file is outside the declared roots, too large, unreadable — and a
parser failure is about *content*. Ingestion quarantines the second per document
and refuses the first outright, which is only expressible if they are separate
protocols (spec 02 §5).

Both are `runtime_checkable`, so `isinstance` answers "does this plugin satisfy
the shape" at the registry boundary rather than at the first call, where the
failure would be a confusing `AttributeError` deep inside a build.
"""

from dataclasses import dataclass
from typing import Final, Protocol, Self, runtime_checkable

from mycelium.sdk.identity import digest_bytes
from mycelium.sdk.types import KirDocument, Sha256Digest, Ulid

__all__ = [
    "MYCELIUM_API_VERSION",
    "Blob",
    "Connector",
    "Parser",
    "PluginMeta",
]

MYCELIUM_API_VERSION: Final = 0
"""The plugin API generation this build speaks.

A single integer, not the release version. The compatibility policy (spec 05 §5)
requires every plugin to declare the range it supports and the registry to refuse
the rest with a precise error; an integer generation says exactly what that check
needs to know — *did the protocol shapes change* — and says it without a PEP 440
parser in the runtime closure. It bumps only when a Protocol in this module
changes in a way a plugin can observe, which pre-1.0 is a CHANGELOG migration
note and post-1.0 is a major release.
"""


@dataclass(frozen=True, slots=True)
class PluginMeta:
    """Who a plugin is, and what a build must record about it.

    Every field is recorded in the snapshot manifest and the build key of the
    stage that used it, because spec 05 §4.2 admits no "best available" magic: a
    build is explainable from its manifest alone, which means the manifest names
    the exact implementation and version that produced each artifact.
    """

    id: str
    """The one identifier, used in config, entry points, manifests and logs (D-026)."""

    version: str
    """The implementation's own version — the engine's, not Mycelium's.

    A parser is an adapter, so the number that explains its output is the number
    of the thing doing the parsing: pandoc 3.10, docling 2.124, markdown-it-py 3.0.
    """

    description: str
    """One line, operator-facing. The technology belongs here, never in `id` (D-026)."""

    deterministic: bool = True
    """Whether identical input provably yields identical output *anywhere*.

    The same declaration the embedder makes (ADR-0017), for the same reason: gate
    G6 excludes what cannot promise it, and a stage that lies here corrupts a
    guarantee rather than a document.
    """

    api_min: int = 0
    """Lowest :data:`MYCELIUM_API_VERSION` this plugin supports (inclusive)."""

    api_max: int = MYCELIUM_API_VERSION + 1
    """First :data:`MYCELIUM_API_VERSION` this plugin does *not* support (exclusive)."""

    def supports(self, api_version: int = MYCELIUM_API_VERSION) -> bool:
        """Whether this plugin declares support for `api_version`."""
        return self.api_min <= api_version < self.api_max


@dataclass(frozen=True, slots=True)
class Blob:
    """Acquired bytes, with the custody facts that make them citable (tier 1).

    Not a :class:`~mycelium.sdk.types.Record`: records are the JSON contracts
    spec 03 exports schemas for, and raw bytes are never JSON. A blob is the
    transport object between the two protocols in this module — it is what the
    CAS stores (roadmap 4.2) and what a parser reads, and it carries the digest
    that ties every citation back to the exact bytes that were acquired.
    """

    data: bytes
    media_type: str
    source_uri: str
    digest: Sha256Digest
    warnings: tuple[str, ...] = ()
    """What acquisition noticed but did not act on — a media type whose bytes
    contradict its extension, for instance. They travel into the KIR document's
    own warnings, so a fidelity report (roadmap 4.3) sees custody problems and
    parsing problems in one list."""

    @classmethod
    def of(
        cls,
        data: bytes,
        *,
        media_type: str,
        source_uri: str,
        warnings: tuple[str, ...] = (),
    ) -> Self:
        """Build a blob, digesting the bytes verbatim (the CAS rule, spec 03 §1)."""
        return cls(
            data=data,
            media_type=media_type,
            source_uri=source_uri,
            digest=digest_bytes(data),
            warnings=warnings,
        )

    @property
    def size(self) -> int:
        """Length in bytes, as recorded for loss budgets and quarantine reports."""
        return len(self.data)


@runtime_checkable
class Connector(Protocol):
    """Acquires the original bytes of a source, under custody (spec 02 §5)."""

    meta: PluginMeta

    schemes: tuple[str, ...]
    """URI schemes this connector answers for — ``("file",)`` for the local tree."""

    def acquire(self, source: str) -> Blob:
        """Fetch `source` and return its bytes, digest, and detected media type.

        Raises a :class:`~mycelium.ingest.errors.ConnectorError` when the source
        cannot be taken into custody — outside the declared roots, absent,
        oversized, or unreadable.
        """
        ...


@runtime_checkable
class Parser(Protocol):
    """Adapts one engine's output into KIR (D-007)."""

    meta: PluginMeta

    media_types: tuple[str, ...]
    """The media types this parser declares it can read, in no particular order."""

    def parse(self, blob: Blob, *, doc_id: Ulid) -> KirDocument:
        """Compile acquired bytes into a KIR document.

        `doc_id` is supplied rather than minted because identity belongs to the
        caller: spec 03 §3 makes a document's id logical and stable across
        re-ingestion, and ADR-0009 made pinning it the build's own write. A parser
        that minted one would hand back a different identity on every run and
        quietly break incremental rebuilds.

        Raises a :class:`~mycelium.ingest.errors.ParseError` when the bytes cannot
        be represented — the per-document failure ingestion quarantines rather
        than aborting the build for (spec 02 §5).
        """
        ...
