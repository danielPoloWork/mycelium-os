# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Parsers: adapters from one engine's output to KIR (D-007).

Four ship in the core, and the split between them is a weight-class decision
argued in ADR-0032 rather than a taxonomy:

- :mod:`~mycelium.ingest.parsers.markdown` — the authored path, markdown-it-py,
  no optional runtime, exercised on every CI cell.
- :mod:`~mycelium.ingest.parsers.docling` — DOCX and HTML structure through
  docling's declarative backends: offline, model-free, deterministic.
- :mod:`~mycelium.ingest.parsers.pandoc` — the fallback and the widest reader,
  one sandboxed binary, six formats, no Python closure.
- :mod:`~mycelium.ingest.parsers.pdf` — PDFium's text layer, the only reader v1
  has for PDF, honest about carrying no structure.

Every one of them emits KIR through :mod:`~mycelium.ingest.parsers.builder`, so
a DOCX and the Markdown describing it chunk the same way.
"""
