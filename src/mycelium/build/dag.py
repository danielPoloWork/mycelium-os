# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The compiler's stage DAG: build keys, stage versions, artifact envelopes (D-008).

Spec 02 §4.1 fixes the stage contract: every stage is a pure, typed function
whose **build key** is the SHA-256 of the canonical serialization of
``(stage_id, implementation_version, input_digests, config_digest,
schema_version)``. This module is where those keys are minted and where each
stage's cacheable output is encoded to — and decoded from — canonical JSON for
the CAS. The orchestrator owns sequencing; this module owns identity.

The per-document chain in v1 is::

    parse    source text ─▶ frontmatter + KIR            (markdown-it; expensive)
    chunk    KIR ─▶ chunk records                        (heading-bounded packer)
    assemble frontmatter + KIR + chunks + mtime ─▶ Document record   (cheap)

``parse`` and ``chunk`` are cached (CAS blob + ``build_cache`` row); ``assemble``
is recomputed whenever a document is dirty, because it is arithmetic over already
-cached inputs and one of its inputs — the file's mtime, which ADR-0009 turns
into ``created_at``/``updated_at`` — is exactly the input that most often changes
alone. Caching it would trade a dict-build for a CAS round-trip and a second
invalidation axis; not worth it.

**Version discipline.** A stage's ``*_STAGE_VERSION`` must be bumped in the same
commit as any change to what the stage emits for unchanged inputs — that is the
whole mechanism by which code changes invalidate cached artifacts. The release
version deliberately does not participate in build keys: bumping ``__version__``
must not cold-start every cache when the compiler did not change (ADR-0015). The
net a missed bump lands in is gate G6 plus the incremental-equals-clean tests,
which both compare cached against freshly computed output.

Config enters keys as per-stage *slices* — only the settings a stage actually
consumes — so editing ``[embedding]`` does not invalidate chunking. The slice for
``chunk`` excludes ``target_tokens``: the packer does not read it (ADR-0014;
roadmap 3.8 will bump ``CHUNK_STAGE_VERSION`` when it starts to).
"""

import json
from dataclasses import dataclass
from typing import Any, Final

from mycelium.chunking import ChunkingPolicy
from mycelium.markdown import Frontmatter, MarkdownDocument
from mycelium.sdk.identity import canonical_json, digest_json
from mycelium.sdk.schema import record_schema_version
from mycelium.sdk.types import Chunk, Document, KirDocument, Sha256Digest

__all__ = [
    "ASSEMBLE_STAGE_VERSION",
    "CHUNK_STAGE_VERSION",
    "PARSE_STAGE_VERSION",
    "BuildEnv",
    "build_key",
    "decode_chunks_artifact",
    "decode_document_artifact",
    "decode_parse_artifact",
    "encode_chunks_artifact",
    "encode_document_artifact",
    "encode_parse_artifact",
]

PARSE_STAGE_VERSION: Final = 1
"""Bump when the Markdown → KIR mapping changes output for unchanged input."""

CHUNK_STAGE_VERSION: Final = 1
"""Bump when packing, anchoring, or token counting changes output for unchanged input."""

ASSEMBLE_STAGE_VERSION: Final = 1
"""Bump when Document-record derivation (title, stats, trust, …) changes."""


def build_key(
    *,
    stage: str,
    impl_version: int,
    inputs: dict[str, str],
    config_slice: dict[str, Any],
    schema_version: str,
) -> Sha256Digest:
    """The spec 02 §4.1 build key, over canonical JSON (ADR-0005's digest rules)."""
    return digest_json(
        {
            "stage": stage,
            "impl": impl_version,
            "inputs": inputs,
            "config": config_slice,
            "schema": schema_version,
        }
    )


def _counter_id(policy: ChunkingPolicy) -> str:
    """A token counter's cache identity: its qualified name.

    The counter is a Strategy (ADR-0007) — a function, which no digest can see
    inside. Its dotted name is the honest stand-in: the built-in estimator names
    itself stably, and a caller injecting a custom counter gets distinct keys per
    distinct function. A *changed* body under an unchanged name is the same class
    of event as any other code change: bump ``CHUNK_STAGE_VERSION``.
    """
    counter = policy.count_tokens
    return f"{counter.__module__}.{counter.__qualname__}"


@dataclass(frozen=True, slots=True)
class BuildEnv:
    """Everything, apart from a document's own content, that its build keys see.

    Computed once per build. ``digest`` is the doc-level short-circuit: a
    document whose source digest, mtime, and environment digest all match its
    ``doc_state`` row needs no stage run at all.
    """

    namespace: str
    chunk_slice: dict[str, Any]
    kir_schema: str
    chunk_schema: str
    document_schema: str

    @classmethod
    def compute(cls, *, namespace: str, policy: ChunkingPolicy) -> "BuildEnv":
        return cls(
            namespace=namespace,
            chunk_slice={
                "max_tokens": policy.target_max_tokens,
                "counter": _counter_id(policy),
            },
            kir_schema=record_schema_version(KirDocument),
            chunk_schema=record_schema_version(Chunk),
            document_schema=record_schema_version(Document),
        )

    @property
    def digest(self) -> Sha256Digest:
        return digest_json(
            {
                "namespace": self.namespace,
                "parse": {"impl": PARSE_STAGE_VERSION, "schema": self.kir_schema},
                "chunk": {
                    "impl": CHUNK_STAGE_VERSION,
                    "schema": self.chunk_schema,
                    "config": self.chunk_slice,
                },
                "assemble": {"impl": ASSEMBLE_STAGE_VERSION, "schema": self.document_schema},
            }
        )

    def parse_key(self, *, doc_id: str, source_digest: Sha256Digest) -> Sha256Digest:
        """Parse consumes the source text and the pinned identity — nothing else.

        ``doc_id`` is an input because KIR embeds it; the namespace is not,
        because parsing is namespace-blind (it becomes real at chunk/assemble).
        """
        return build_key(
            stage="parse",
            impl_version=PARSE_STAGE_VERSION,
            inputs={"source": source_digest, "doc_id": doc_id},
            config_slice={},
            schema_version=self.kir_schema,
        )

    def chunk_key(self, *, parsed_digest: Sha256Digest, doc_path: str) -> Sha256Digest:
        """Chunk consumes the parse artifact, the path (anchors embed it), and its slice."""
        return build_key(
            stage="chunk",
            impl_version=CHUNK_STAGE_VERSION,
            inputs={"parsed": parsed_digest, "doc_path": doc_path},
            config_slice={**self.chunk_slice, "namespace": self.namespace},
            schema_version=self.chunk_schema,
        )


# ---------------------------------------------------------------------------
# Artifact envelopes — what the CAS holds for each cached stage
# ---------------------------------------------------------------------------


def encode_parse_artifact(parsed: MarkdownDocument) -> str:
    """The parse stage's cacheable output, as canonical JSON."""
    return canonical_json(
        {
            "frontmatter": parsed.frontmatter.model_dump(mode="json"),
            "kir": parsed.kir.model_dump(mode="json"),
            "warnings": list(parsed.warnings),
        }
    )


def decode_parse_artifact(text: str) -> MarkdownDocument:
    """Rebuild a :class:`MarkdownDocument` from a CAS blob, revalidating records.

    Validation is not optional: a cache is an untrusted optimization, and a blob
    that no longer satisfies the KIR contract must surface as an error here, not
    as corrupt rows three stages later.
    """
    payload = json.loads(text)
    return MarkdownDocument(
        kir=KirDocument.model_validate(payload["kir"]),
        frontmatter=Frontmatter.model_validate(payload["frontmatter"]),
        warnings=tuple(payload["warnings"]),
    )


def encode_document_artifact(document: Document) -> str:
    """The assemble stage's output, stored for *restoration* rather than reuse.

    The assemble stage is not cached (its mtime input changes alone too often),
    but the record it produces is content-addressed all the same: its digest is
    what the snapshot manifest folds, and holding the bytes at that address is
    what lets ``mycelium rollback`` rebuild a published corpus without
    recompiling it (ADR-0016). ``cas_put`` of this text returns exactly
    ``digest_json(document.model_dump(mode="json"))`` — one address, two uses.
    """
    return canonical_json(document.model_dump(mode="json"))


def decode_document_artifact(text: str) -> Document:
    return Document.model_validate_json(text)


def encode_chunks_artifact(chunks: tuple[Chunk, ...]) -> str:
    """The chunk stage's cacheable output: the ordered chunk records."""
    return canonical_json([chunk.model_dump(mode="json") for chunk in chunks])


def decode_chunks_artifact(text: str) -> tuple[Chunk, ...]:
    return tuple(Chunk.model_validate(item) for item in json.loads(text))
