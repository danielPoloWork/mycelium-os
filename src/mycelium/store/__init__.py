# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The derived store: catalog, lexical index, and meta (spec 03 §8, spec 02 §10).

- :mod:`mycelium.store.base` — the :class:`Store` protocol a replacement must satisfy.
- :mod:`mycelium.store.schema` — the SQLite DDL and connection settings.
- :mod:`mycelium.store.sqlite` — the v1 implementation.

Everything under ``.mycelium/`` is derived and disposable (D-005): the store is a
cache of a deterministic function of the sources, and rebuilding is always a
lawful repair.
"""

from mycelium.store.base import CacheEntry, DocState, SnapshotState, Store
from mycelium.store.schema import SCHEMA_VERSION
from mycelium.store.sqlite import (
    STEM_WEIGHT,
    STORE_DIRNAME,
    STORE_FILENAME,
    SearchFilters,
    SearchHit,
    SqliteStore,
    StoreError,
    StoreVersionError,
    TermHits,
    expanded_query,
    foothold_query,
    fts_query,
)

__all__ = [
    "SCHEMA_VERSION",
    "STORE_DIRNAME",
    "STORE_FILENAME",
    "CacheEntry",
    "DocState",
    "SearchFilters",
    "SearchHit",
    "SnapshotState",
    "SqliteStore",
    "Store",
    "StoreError",
    "StoreVersionError",
    "STEM_WEIGHT",
    "TermHits",
    "expanded_query",
    "foothold_query",
    "fts_query",
]
