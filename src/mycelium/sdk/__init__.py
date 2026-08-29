# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Public plugin/consumer SDK for Mycelium OS.

The SDK is the contributor-facing contract surface (RFC-0001 "API contract"):

- :mod:`mycelium.sdk.types` — the v0 record contracts (spec 03 §§3-7).
- :mod:`mycelium.sdk.schema` — JSON Schema 2020-12 export of those contracts.
- :mod:`mycelium.sdk.identity` — canonical hashing, ULIDs, anchors, citation URIs
  (spec 03 §§1-2): the constructors that produce the shapes ``types`` validates.

The typed plugin Protocols (``Parser``, ``Chunker``, ``Embedder``, ``Extractor``,
``Synthesizer``, ``Reranker``) land with the pipeline milestones (D-012/D-023).
"""
