# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Shared test fixtures.

The one rule enforced here is that **a test's outcome must not depend on what
this machine happens to have downloaded**. The default embedding provider is
`local-onnx` (D-013), so a developer who has fetched the 133 MB model would
otherwise run a different suite from CI: builds would embed, counts would carry
vectors, and the determinism corpus would drift with the runtime's kernels.

So every test runs against an *empty* model cache by default and sees the
behaviour a fresh install sees — vectors unavailable, snapshot degraded, lexical
search intact. Tests that genuinely need the model ask for the `local_model`
fixture, which finds the real cache and skips when it is absent.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from fakes import FakeEmbedder
from mycelium.embedding.models import CACHE_ENV_VAR, DEFAULT_MODEL_ID, MODELS, cache_root


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture(autouse=True)
def _isolated_model_cache(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Point the model cache at an empty directory for the whole suite."""
    empty = tmp_path_factory.mktemp("empty-model-cache")
    previous = os.environ.get(CACHE_ENV_VAR)
    os.environ[CACHE_ENV_VAR] = str(empty)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(CACHE_ENV_VAR, None)
        else:
            os.environ[CACHE_ENV_VAR] = previous


@pytest.fixture
def local_model(request: pytest.FixtureRequest) -> Path:
    """The real model directory, or a skip.

    Restores the developer's cache location for this test only — the isolation
    above is a default, not a prohibition. CI has no model, so every test using
    this fixture skips there; the numbers they produce are reproduced by hand and
    recorded in ADR-0017 rather than asserted from a machine that cannot run them.
    """
    request.getfixturevalue("_isolated_model_cache")
    os.environ.pop(CACHE_ENV_VAR, None)
    directory = cache_root() / DEFAULT_MODEL_ID
    spec = MODELS[DEFAULT_MODEL_ID]
    missing = [item.name for item in spec.files if not (directory / item.name).is_file()]
    if missing:
        pytest.skip(f"{DEFAULT_MODEL_ID} not cached locally (missing {', '.join(missing)})")
    return directory
