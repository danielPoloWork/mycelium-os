# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The local ONNX embedder — the v1 default (D-013).

Zero API keys, zero accounts, and no network at query or build time once the
model is on disk. What it costs instead is an optional dependency set
(``onnxruntime``, ``tokenizers``, ``numpy``) that the core install deliberately
does not carry: twenty-odd packages is a large price to charge someone who only
wants lexical search, so ``pip install mycelium-os[embeddings]`` is the opt-in
and its absence degrades a build rather than breaking it (spec 02 §4.3).

Imports of those packages happen inside :meth:`LocalOnnxEmbedder.load`, not at
module import, so ``mycelium.embedding`` stays importable — and its errors stay
*explainable* — in an install that never asked for embeddings.
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Self

from mycelium.embedding.base import EmbedderUnavailableError, EmbeddingError
from mycelium.embedding.models import ModelSpec, model_spec, resolve_model

__all__ = ["PROVIDER", "LocalOnnxEmbedder"]

PROVIDER: Final = "local-onnx"

_BATCH: Final = 16
"""Texts per inference call. Large enough to amortise the call, small enough that
a long document does not allocate a padded tensor measured in hundreds of MB."""


@dataclass(frozen=True, slots=True)
class LocalOnnxEmbedder:
    """A BERT-family sentence encoder running on the CPU through ONNX Runtime."""

    spec: ModelSpec
    _session: Any
    _tokenizer: Any
    _input_names: frozenset[str]

    # -- identity ----------------------------------------------------------

    @property
    def model_id(self) -> str:
        return self.spec.model_id

    @property
    def provider(self) -> str:
        return PROVIDER

    @property
    def dim(self) -> int:
        return self.spec.dim

    @property
    def deterministic(self) -> bool:
        """False, and deliberately so.

        Inference here is bit-identical for a fixed model, runtime build, and
        machine — but ONNX Runtime selects kernels by instruction set, so two
        correct machines may differ in the last bits. Declaring ``True`` would
        make gate G6 assert something this stage cannot promise (ADR-0017).
        """
        return False

    # -- construction ------------------------------------------------------

    @classmethod
    def load(
        cls,
        *,
        model_id: str,
        model_path: Path | None = None,
        allow_download: bool = False,
    ) -> Self:
        """Build an embedder, or raise :class:`EmbedderUnavailableError` saying why.

        Every failure a *deployment* can have — dependencies absent, model absent,
        cache unreadable — arrives as that one type, because the build treats them
        identically: publish without vectors, mark the snapshot degraded, and say
        so. A corrupt model file is a different animal and raises
        :class:`EmbeddingError`.
        """
        spec = model_spec(model_id)
        try:
            import numpy  # noqa: F401 - imported for the failure check only
            import onnxruntime
            from tokenizers import Tokenizer
        except ImportError as error:
            msg = (
                "the local embedder needs the optional embedding dependencies; install "
                "`mycelium-os[embeddings]` (onnxruntime, tokenizers, numpy) or set "
                f'`[embedding] provider = "none"` to build without vectors ({error})'
            )
            raise EmbedderUnavailableError(msg) from error

        directory = resolve_model(spec, model_path=model_path, allow_download=allow_download)
        try:
            session = onnxruntime.InferenceSession(
                str(directory / spec.model_file.name),
                providers=["CPUExecutionProvider"],
            )
            tokenizer = Tokenizer.from_file(str(directory / spec.tokenizer_file.name))
        except Exception as error:  # noqa: BLE001 - onnxruntime raises broadly
            msg = f"could not load {spec.model_id} from {directory}: {error}"
            raise EmbeddingError(msg) from error

        tokenizer.enable_truncation(max_length=spec.max_tokens)
        tokenizer.enable_padding()

        outputs = session.get_outputs()
        if not outputs or outputs[0].shape[-1] != spec.dim:
            shape = outputs[0].shape if outputs else None
            msg = f"{spec.model_id} emits {shape}, which is not the pinned dim {spec.dim}"
            raise EmbeddingError(msg)

        return cls(
            spec=spec,
            _session=session,
            _tokenizer=tokenizer,
            _input_names=frozenset(item.name for item in session.get_inputs()),
        )

    # -- inference ---------------------------------------------------------

    def embed_documents(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        return [vector for batch in _batched(texts, _BATCH) for vector in self._encode(batch)]

    def embed_query(self, text: str) -> tuple[float, ...]:
        """Encode a query, with the model's instruction prefix where it has one.

        BGE is asymmetric: passages are encoded bare, queries with a prefix that
        tells the model it is looking *for* something. Skipping it is a silent
        recall loss on exactly the natural-language questions hybrid retrieval
        exists to answer.
        """
        return self._encode([self.spec.query_prefix + text])[0]

    def _encode(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        import numpy as np

        if not texts:
            return []
        encoded = self._tokenizer.encode_batch(list(texts))
        feed = {
            "input_ids": np.array([item.ids for item in encoded], dtype=np.int64),
            "attention_mask": np.array([item.attention_mask for item in encoded], dtype=np.int64),
        }
        if "token_type_ids" in self._input_names:
            feed["token_type_ids"] = np.array([item.type_ids for item in encoded], dtype=np.int64)

        hidden = self._session.run(None, feed)[0]
        if self.spec.pooling == "cls":
            pooled = hidden[:, 0]
        else:
            mask = feed["attention_mask"][..., None].astype(hidden.dtype)
            pooled = (hidden * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)

        if self.spec.normalize:
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            pooled = pooled / np.clip(norms, 1e-12, None)
        return [tuple(float(value) for value in row) for row in pooled.astype(np.float32)]


def _batched(items: Sequence[str], size: int) -> Iterator[Sequence[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]
