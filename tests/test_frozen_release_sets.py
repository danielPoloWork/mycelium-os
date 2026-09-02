# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The frozen-release-set guard (spec 04 §7.1, ADR-0027), and the gap 4.13 keeps closed.

`tools/check_frozen_release_sets.py` refuses one thing: a change that tunes retrieval and
re-judges a frozen release set at once. Roadmap 4.15 recorded that the guard *would not*
catch its own pairing — flipping `[chunking] pack_atomic` while re-judging — because the
shipped default lives in `src/mycelium/config.py` and that path was not in `TUNING_PATHS`.
PR #61 added it, and this file is what stops it being removed again by someone who reads
`config.py` as configuration plumbing rather than as the retriever's shipped defaults.

The two path lists are checked against the filesystem for the same reason: a guard naming
a file that has since moved guards nothing, silently, and the failure mode is that a
conjunction it was written to refuse sails through.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import check_frozen_release_sets as guard  # noqa: E402


@pytest.fixture
def changed(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Drive the guard's decision without inventing a git history."""
    files: list[str] = []
    monkeypatch.setattr(guard, "changed_files", lambda base: list(files))
    monkeypatch.setattr(sys, "argv", ["check_frozen_release_sets.py", "origin/main"])
    return files


def test_a_change_that_tunes_and_re_judges_is_refused(changed: list[str]) -> None:
    changed.extend(["src/mycelium/retrieval.py", "eval/release.jsonl"])
    assert guard.main() == 1


def test_re_judging_alone_is_allowed(changed: list[str]) -> None:
    # A release set may grow; that is not what the rule forbids.
    changed.extend(["eval/release.jsonl", "docs/adr/0043-judge.md"])
    assert guard.main() == 0


def test_tuning_alone_is_allowed(changed: list[str]) -> None:
    changed.extend(["src/mycelium/chunking.py", "src/mycelium/config.py"])
    assert guard.main() == 0


def test_flipping_a_shipped_default_counts_as_tuning(changed: list[str]) -> None:
    """The pairing roadmap 4.15 named, and the reason `config.py` is a tuning path.

    `[chunking] pack_atomic` moves every chunk boundary in every corpus, and its
    default lives in `ChunkingConfig` rather than in the chunker (ADR-0042). A
    change that flips it *and* re-judges the set it is measured on cannot be told
    apart from fitting the set to the result — which is the whole point of the
    guard, whatever file the switch happens to live in.
    """
    changed.extend(["src/mycelium/config.py", "eval/corpora/uv-docs/eval/release.jsonl"])
    assert guard.main() == 1


def test_every_derived_release_set_is_guarded_too(changed: list[str]) -> None:
    """The ingested twin's judgments are carried, not written — but they are still a set
    a retrieval change may not move in the same breath (roadmap 4.10)."""
    changed.extend(
        ["src/mycelium/eval/metrics.py", "eval/corpora/uv-docs-ingested/eval/release.jsonl"]
    )
    assert guard.main() == 1


def test_an_unrelated_change_is_not_refused(changed: list[str]) -> None:
    changed.extend(["README.md", "src/mycelium/cli/app.py"])
    assert guard.main() == 0


@pytest.mark.parametrize("relative", guard.RELEASE_SETS)
def test_every_guarded_release_set_exists(relative: str) -> None:
    assert (ROOT / relative).is_file(), (
        f"{relative} is guarded but absent: a guard naming a file that moved guards nothing"
    )


@pytest.mark.parametrize("relative", guard.TUNING_PATHS)
def test_every_tuning_path_exists(relative: str) -> None:
    target = ROOT / relative
    assert target.exists(), (
        f"{relative} is listed as a tuning path but is absent - the guard silently "
        "stopped watching it"
    )


def test_the_shipped_defaults_are_a_tuning_path() -> None:
    """Named explicitly, not merely present, because this is the entry 4.15 lost."""
    assert "src/mycelium/config.py" in guard.TUNING_PATHS
