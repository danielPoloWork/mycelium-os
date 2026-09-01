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
- :mod:`mycelium.ingest.safety` — the bounds hostile input is refused by, before
  an engine is asked to read it.
- :mod:`mycelium.ingest.custody` — tier-1 custody: the acquired original and its
  KIR, kept, and never garbage-collected.
- :mod:`mycelium.ingest.fidelity` — the loss accounting, and the budget it is
  measured against.
- :mod:`mycelium.ingest.projection` — KIR back to Markdown, under
  `knowledge/evidence/`, where the compiler picks it up like any authored file.
- :mod:`mycelium.ingest.pipeline` — the evidence lane end to end: acquire, store,
  guard, parse, store, account, project.
- :mod:`mycelium.ingest.errors` — the failure taxonomy, because a custody failure
  and a parse failure are answered differently.

What this package deliberately does **not** do yet: author candidate documents
with an LLM (roadmap 4.4), compute grounding (4.5), scan for secrets, or decide
what happens to a document that fails (4.6). `ingest_source` raises a typed error
and leaves that decision to its caller.
"""

from mycelium.ingest.custody import Custody, CustodyIntegrity, custody_root
from mycelium.ingest.errors import (
    ConnectorError,
    CustodyError,
    IngestError,
    ParseError,
    PluginError,
    PluginUnavailableError,
    SourceTooLargeError,
    UnknownPluginError,
    UnsupportedMediaTypeError,
)
from mycelium.ingest.fidelity import build_report, check_budget, encode_report
from mycelium.ingest.media import EXTENSIONS, MEDIA_TYPES, MediaTypeClaim, classify
from mycelium.ingest.pipeline import Ingested, encode_kir, ingest_source, write_projection
from mycelium.ingest.projection import EVIDENCE_DIRNAME, Projection, evidence_path, project
from mycelium.ingest.registry import (
    BUILTIN_CONNECTORS,
    BUILTIN_PARSERS,
    ENTRY_POINT_GROUP,
    PluginStatus,
    Registry,
    probe,
)
from mycelium.ingest.safety import DEFAULT_LIMITS, Limits, guard

__all__ = [
    "BUILTIN_CONNECTORS",
    "BUILTIN_PARSERS",
    "ENTRY_POINT_GROUP",
    "EVIDENCE_DIRNAME",
    "EXTENSIONS",
    "MEDIA_TYPES",
    "DEFAULT_LIMITS",
    "ConnectorError",
    "Custody",
    "CustodyError",
    "CustodyIntegrity",
    "IngestError",
    "Ingested",
    "Limits",
    "MediaTypeClaim",
    "ParseError",
    "Projection",
    "PluginError",
    "PluginStatus",
    "PluginUnavailableError",
    "Registry",
    "SourceTooLargeError",
    "UnknownPluginError",
    "UnsupportedMediaTypeError",
    "build_report",
    "check_budget",
    "classify",
    "custody_root",
    "encode_kir",
    "encode_report",
    "evidence_path",
    "guard",
    "ingest_source",
    "probe",
    "project",
    "write_projection",
]
