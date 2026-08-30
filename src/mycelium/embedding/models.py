# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The pinned model registry and its local cache (D-013, D-017).

D-013 wants the default embedder local and key-free so first value never depends
on an account. D-017 wants **zero network calls unless configured**. Those two
pull against each other the moment a 133 MB model has to come from somewhere, and
this module is where the tension is resolved rather than papered over:

- The registry pins every file by **URL, size, and SHA-256**. Fetching a model is
  a supply-chain event, so the bytes are verified against the pin before they are
  installed, and a mismatch is an error, never a warning.
- Fetching happens **only** when the operator sets ``[embedding] allow_download``.
  The default is off; the error raised in that state names the exact command that
  would fix it, so nobody has to guess what the tool wanted.
- Resolution order is ``[embedding] model_path`` → the local cache → refuse. An
  air-gapped install points `model_path` at a vendored directory and never
  touches this module's network code at all.

The cache lives outside the repository, because a 133 MB artifact is not project
state: ``%LOCALAPPDATA%\\mycelium\\models`` on Windows, ``$XDG_CACHE_HOME`` (or
``~/.cache``) ``/mycelium/models`` elsewhere. ``MYCELIUM_MODEL_CACHE`` overrides
both, which is how tests and CI point at a fixture without a home directory.
"""

import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final, Literal

from mycelium.embedding.base import EmbedderUnavailableError, EmbeddingError

__all__ = [
    "CACHE_ENV_VAR",
    "MODELS",
    "DEFAULT_MODEL_ID",
    "ModelFile",
    "ModelSpec",
    "cache_root",
    "model_spec",
    "resolve_model",
]

CACHE_ENV_VAR: Final = "MYCELIUM_MODEL_CACHE"
DEFAULT_MODEL_ID: Final = "bge-small-en-v1.5"


@dataclass(frozen=True, slots=True)
class ModelFile:
    """One pinned artifact of a model."""

    name: str
    url: str
    sha256: str
    size: int


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Everything needed to run a model and to record what ran."""

    model_id: str
    dim: int
    max_tokens: int
    pooling: Literal["cls", "mean"]
    normalize: bool
    query_prefix: str
    """Instruction prefix for the query side of an asymmetric model; ``""`` if symmetric."""
    license: str
    source: str
    files: tuple[ModelFile, ...]

    @property
    def model_file(self) -> ModelFile:
        return next(item for item in self.files if item.name.endswith(".onnx"))

    @property
    def tokenizer_file(self) -> ModelFile:
        return next(item for item in self.files if item.name == "tokenizer.json")


MODELS: Final[dict[str, ModelSpec]] = {
    DEFAULT_MODEL_ID: ModelSpec(
        model_id=DEFAULT_MODEL_ID,
        dim=384,
        max_tokens=512,
        # BAAI's own guidance for the BGE family: the [CLS] token is the sentence
        # representation, and it is L2-normalised so cosine similarity is a dot
        # product. Verified against the published reference behaviour (ADR-0017).
        pooling="cls",
        normalize=True,
        query_prefix="Represent this sentence for searching relevant passages: ",
        license="MIT",
        source="https://huggingface.co/BAAI/bge-small-en-v1.5",
        files=(
            ModelFile(
                name="model.onnx",
                url="https://huggingface.co/BAAI/bge-small-en-v1.5/resolve/main/onnx/model.onnx",
                sha256="828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35",
                size=133_093_490,
            ),
            ModelFile(
                name="tokenizer.json",
                url="https://huggingface.co/BAAI/bge-small-en-v1.5/resolve/main/tokenizer.json",
                sha256="d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66",
                size=711_396,
            ),
        ),
    )
}
"""Models this build knows how to run, pinned by digest.

One entry, on purpose (D-011: every supported surface is a compatibility
liability). A second model is a decision with eval evidence behind it, not a
convenience.
"""


def model_spec(model_id: str) -> ModelSpec:
    spec = MODELS.get(model_id)
    if spec is None:
        known = ", ".join(sorted(MODELS))
        msg = (
            f"unknown embedding model {model_id!r}; this build knows: {known}. "
            "Point `[embedding] model_path` at a local directory to use another."
        )
        raise EmbedderUnavailableError(msg)
    return spec


def cache_root() -> Path:
    """Where downloaded models live — never inside the repository."""
    override = os.environ.get(CACHE_ENV_VAR)
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return Path(base) / "mycelium" / "models"
    xdg = os.environ.get("XDG_CACHE_HOME")
    base_path = Path(xdg) if xdg else Path.home() / ".cache"
    return base_path / "mycelium" / "models"


def _verify(path: Path, expected: ModelFile) -> bool:
    """Whether `path` is exactly the pinned artifact."""
    try:
        if path.stat().st_size != expected.size:
            return False
        digest = sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1 << 20):
                digest.update(chunk)
    except OSError:
        return False
    return digest.hexdigest() == expected.sha256


def _download(target: Path, expected: ModelFile) -> None:
    """Fetch one pinned file, verify it, and install it atomically.

    Verification happens on the temporary file, so a corrupted or substituted
    download never appears at the destination path even for an instant.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".part")
    try:
        with urllib.request.urlopen(expected.url, timeout=300) as response, tmp.open("wb") as out:
            while chunk := response.read(1 << 20):
                out.write(chunk)
    except (urllib.error.URLError, OSError) as error:
        tmp.unlink(missing_ok=True)
        msg = f"could not download {expected.name} from {expected.url}: {error}"
        raise EmbedderUnavailableError(msg) from error

    if not _verify(tmp, expected):
        tmp.unlink(missing_ok=True)
        msg = (
            f"{expected.name} downloaded from {expected.url} does not match its pinned "
            f"SHA-256 ({expected.sha256}); refusing to install it"
        )
        raise EmbeddingError(msg)
    os.replace(tmp, target)


def resolve_model(
    spec: ModelSpec, *, model_path: Path | None = None, allow_download: bool = False
) -> Path:
    """Return a directory holding every file `spec` needs.

    `model_path` short-circuits everything: an operator who vendored the model
    (or an air-gapped install) never reaches the cache or the network. Otherwise
    the cache is consulted, and only a configured `allow_download` may fill it.
    """
    if model_path is not None:
        missing = [item.name for item in spec.files if not (model_path / item.name).is_file()]
        if missing:
            msg = (
                f"[embedding] model_path {model_path} does not contain {', '.join(missing)}; "
                f"expected the files of {spec.model_id} ({spec.source})"
            )
            raise EmbedderUnavailableError(msg)
        return model_path

    directory = cache_root() / spec.model_id
    absent = [item for item in spec.files if not _verify(directory / item.name, item)]
    if not absent:
        return directory

    if not allow_download:
        names = ", ".join(item.name for item in absent)
        total_mb = sum(item.size for item in absent) / 1_000_000
        msg = (
            f"embedding model {spec.model_id} is not available locally ({names} missing or "
            f"failing its checksum in {directory}). Mycelium makes no network call unless you "
            f"ask it to: set `allow_download = true` under [embedding] in mycelium.toml to "
            f"fetch {total_mb:.0f} MB from {spec.source} (license {spec.license}), or set "
            f"`model_path` to a directory you populated yourself. Builds continue without "
            f"vectors until then."
        )
        raise EmbedderUnavailableError(msg)

    for item in absent:
        _download(directory / item.name, item)
    return directory
