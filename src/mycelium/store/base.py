# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The store interface (spec 02 §10).

SQLite is a *secondary store component*, explicitly replaceable — a claim that is
worth nothing unless something states what a replacement must do. This protocol is
that statement: every operation the compiler and the serving layer need, expressed
in records rather than rows, with no SQL in the signatures.

A Postgres/OpenSearch store at the platform phase (D-019) implements this and
nothing else changes. Anything that reaches for `SqliteStore` directly, rather than
for this protocol, is what would make that phase a rewrite.
"""

from collections.abc import Iterable
from contextlib import AbstractContextManager
from typing import Protocol, runtime_checkable

from mycelium.sdk.types import Chunk, Document

__all__ = ["Store"]


@runtime_checkable
class Store(Protocol):
    """What the pipeline requires of a store, and all it may assume."""

    def transaction(self) -> AbstractContextManager[None]:
        """Run a unit of work, rolled back whole if it raises."""
        ...

    def close(self) -> None: ...

    # -- writes ------------------------------------------------------------

    def put_document(self, document: Document) -> None: ...

    def put_chunks(self, chunks: Iterable[Chunk]) -> int: ...

    def delete_document(self, doc_id: str) -> None: ...

    def set_meta(self, key: str, value: str) -> None: ...

    # -- reads -------------------------------------------------------------

    def get_document(self, doc_id: str) -> Document | None: ...

    def document_ids(self) -> tuple[str, ...]: ...

    def get_document_by_path(self, path: str) -> Document | None: ...

    def get_chunk(self, anchor: str) -> Chunk | None: ...

    def chunks_of(self, doc_id: str) -> tuple[Chunk, ...]: ...

    def get_meta(self, key: str) -> str | None: ...

    def counts(self) -> dict[str, int]: ...
