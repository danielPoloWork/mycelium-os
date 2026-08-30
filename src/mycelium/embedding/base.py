# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The embedder contract (spec 02 §4.1, spec 05 §5, D-012/D-013).

An embedder is the compiler's one **declared non-deterministic stage**. Spec 02
§4.1 allows exactly that — a stage may declare ``deterministic: false`` provided
it records the provider, model, and parameter identity that produced its output —
and the vector stage is where the allowance is spent. Everything else in the
compiler is bit-reproducible; this is the seam where that stops, and the contract
below is what makes the stop *legible* rather than a silent exception.

Two properties carry the weight:

``model_id``
    Vectors are keyed ``(chunk_digest, model_id)`` (D-013, and the DDL has said so
    since roadmap 2.6). The id is therefore not a label but an identity: change it
    and you add rows rather than destroy them, so switching models is reversible
    and two models can coexist in one store.

``deterministic``
    ONNX CPU inference is bit-identical for a fixed model, runtime build, and
    machine — and is *not* guaranteed across platforms, runtime versions, or
    instruction sets, because kernels differ. The honest declaration is
    ``False``: a claim of reproducibility that holds only on the machine that
    made it is not reproducibility, and gate G6 excludes vectors for this reason
    (ADR-0017).

The protocol is deliberately narrow so a plugin (D-023) can satisfy it: text in,
unit vectors out, plus the identity a snapshot manifest must record.
"""

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

__all__ = ["Embedder", "EmbedderUnavailableError", "EmbeddingError"]


class EmbeddingError(RuntimeError):
    """Embedding failed for a reason the caller cannot work around."""


class EmbedderUnavailableError(EmbeddingError):
    """The configured embedder cannot be constructed here, and says why.

    This is the *degradable* failure: a build that meets it publishes without
    vectors and marks the snapshot degraded rather than failing the lexical
    index with it (spec 02 §4.3). Its message is operator-facing — missing
    optional dependency, missing model files, unreadable cache — and always
    names the next action.
    """


@runtime_checkable
class Embedder(Protocol):
    """Turns text into unit vectors, and states what produced them."""

    @property
    def model_id(self) -> str:
        """Vector identity: half of the ``(chunk_digest, model_id)`` key."""
        ...

    @property
    def provider(self) -> str:
        """Where the computation happens — ``local-onnx`` for the v1 default."""
        ...

    @property
    def dim(self) -> int:
        """Vector dimensionality, recorded in the manifest and enforced on write."""
        ...

    @property
    def deterministic(self) -> bool:
        """Whether identical input provably yields identical output *anywhere*."""
        ...

    def embed_documents(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        """Embed passage text, in order, as unit vectors."""
        ...

    def embed_query(self, text: str) -> tuple[float, ...]:
        """Embed a query as a unit vector.

        Separate from :meth:`embed_documents` because asymmetric models expect an
        instruction prefix on the query side only; using the passage encoding for
        a query silently costs recall on exactly the queries hybrid retrieval is
        supposed to win (measured in ADR-0017).
        """
        ...
