# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Ingestion: bytes from outside the repository, compiled into KIR (spec 02 §5).

The evidence lane is a two-step contract — acquire, then parse — and this package
is both halves of it plus the resolution that pins which implementation runs:

- :mod:`mycelium.sdk.protocols` — the ``Connector`` and ``Parser`` Protocols
  themselves, in the SDK because they are contributor-facing contracts that
  freeze at 1.0 (architecture §10).
- :mod:`mycelium.ingest.media` — the dispatch key: what a source's extension
  claims, what its bytes say, and whether they agree.
- :mod:`mycelium.ingest.connectors` — acquisition under custody.
- :mod:`mycelium.ingest.parsers` — the adapters over docling, pandoc, PDFium and
  markdown-it (D-007).
- :mod:`mycelium.ingest.registry` — pinned, ordered resolution; never "best
  available" (spec 05 §4.2).
- :mod:`mycelium.ingest.errors` — the failure taxonomy, because a custody failure
  and a parse failure are answered differently.

What this milestone deliberately does **not** do: write blobs to the CAS
(roadmap 4.2), project evidence Markdown with provenance frontmatter (4.3), or
scan for secrets and quarantine (4.6). A KIR document comes back from here; where
it is stored, and what is written from it, belongs to the items that own those
questions.
"""

from mycelium.ingest.errors import (
    ConnectorError,
    IngestError,
    ParseError,
    PluginError,
    PluginUnavailableError,
    SourceTooLargeError,
    UnknownPluginError,
    UnsupportedMediaTypeError,
)
from mycelium.ingest.media import EXTENSIONS, MEDIA_TYPES, MediaTypeClaim, classify
from mycelium.ingest.registry import (
    BUILTIN_CONNECTORS,
    BUILTIN_PARSERS,
    ENTRY_POINT_GROUP,
    PluginStatus,
    Registry,
    probe,
)

__all__ = [
    "BUILTIN_CONNECTORS",
    "BUILTIN_PARSERS",
    "ENTRY_POINT_GROUP",
    "EXTENSIONS",
    "MEDIA_TYPES",
    "ConnectorError",
    "IngestError",
    "MediaTypeClaim",
    "ParseError",
    "PluginError",
    "PluginStatus",
    "PluginUnavailableError",
    "Registry",
    "SourceTooLargeError",
    "UnknownPluginError",
    "UnsupportedMediaTypeError",
    "classify",
    "probe",
]
