# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Fixtures for the `chats` module's suite.

Collected by the root `pytest` run (`testpaths` names this directory), so the
module is tested beside the core it extends and a core change that breaks it
fails the core's own suite — which is the point of keeping contrib in-repo
before the 1.0 freeze (spec 05 §4.3).

Deliberately *not* registering a hypothesis profile. The project's
property-test budget and its profile are declared once, in `tests/conftest.py`
(ADR-0060), and `settings.load_profile` is global state: a second profile
loaded from here would silently change the settings of the whole session. The
one property test in this suite sets `deadline=None` on itself instead, which is
the same individual exemption `test_any_query_text_is_safe` took (BUG-0021).
"""

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mycelium.modules import ModuleError, require_enabled
from mycelium_chats.settings import ChatsSettings

FIXTURES = Path(__file__).parent / "fixtures"

IMPORTED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
"""A fixed import clock, so a test that asserts a path or a header is not a test
about today. Real imports take custody's `first_seen`; tests pass this."""

CONFIG = """[project]
name = "fixture"
knowledge_dir = "knowledge"

[modules]
enabled = ["chats"]

[chats]
timezone = "UTC"
default_project = "research"
"""


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def settings() -> ChatsSettings:
    """The settings every test imports under: UTC, so paths are not machine-dependent."""
    return ChatsSettings(timezone="UTC", default_project="research")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository with the module enabled and one authored document.

    The seed document matters: it makes the corpus non-empty, so a test that
    finds chat content in a search has found it *among* other documents rather
    than by default.
    """
    root = tmp_path / "repo"
    (root / "knowledge" / "verified").mkdir(parents=True)
    with (root / "knowledge" / "verified" / "seed.md").open(
        "w", encoding="utf-8", newline="\n"
    ) as handle:
        handle.write("# Seed\n\nAn authored document, so the corpus is not only chats.\n")
    with (root / "mycelium.toml").open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(CONFIG)
    return root


@pytest.fixture
def read_fixture() -> Iterator[object]:
    """`read_fixture("chatgpt-export.json")` — one fixture's text."""

    def read(name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8")

    yield read


def enabled_in(root: Path) -> Mapping[str, object]:
    """Assert the module is enabled for `root`; used by the acceptance suite."""
    from mycelium.config import load_config

    config = load_config(root)
    require_enabled("chats", config.modules.enabled)
    return {"config": config}


__all__ = ["CONFIG", "FIXTURES", "IMPORTED_AT", "ModuleError", "enabled_in"]
