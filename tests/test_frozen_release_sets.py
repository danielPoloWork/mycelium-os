# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The frozen-release-set guard (spec 04 §7.1, ADR-0027), and the two gaps it has closed.

`tools/check_frozen_release_sets.py` refuses one thing: a change that tunes retrieval and
re-judges a frozen release set at once. Roadmap 4.15 recorded that the guard *would not*
catch its own pairing — flipping `[chunking] pack_atomic` while re-judging — because the
shipped default lives in `src/mycelium/config.py` and that path was not in `TUNING_PATHS`.
PR #61 added it, and this file is what stops it being removed again by someone who reads
`config.py` as configuration plumbing rather than as the retriever's shipped defaults.

The second gap ran the other way: the rule was applied to a set in which **nothing is
judged**. A derived set's queries, grades and slices are copied verbatim from a frozen
source and only its anchor is computed (ADR-0039), so it is a function of the chunker and
a chunking change *must* move it — while the conjunction rule forbade exactly that. Roadmap
4.15 exempted the machinery; roadmap 4.26 retired the rest of the rule, because the same
deadlock reappeared from the judgement side and the byte-exact regeneration check says
everything the rule was a proxy for (ADR-0047, ADR-0056).

Every path list is checked against the filesystem for the same reason: a guard naming a
file that has since moved guards nothing, silently, and the failure mode is that a
conjunction it was written to refuse sails through.
"""

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import check_frozen_release_sets as guard  # noqa: E402


@pytest.fixture
def changed(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Drive the guard's decision without inventing a git history.

    `gated_default_only` is stubbed to "nothing gated" as well, because it reads a
    real diff: left live, a test's *scenario* would be decided by whatever the
    working branch happens to have changed in `config.py` (roadmap 6.8, ADR-0137).
    The tests that exercise the exemption set it themselves.
    """
    files: list[str] = []
    monkeypatch.setattr(guard, "changed_files", lambda base: list(files))
    monkeypatch.setattr(guard, "gated_default_only", lambda base, path: [])
    monkeypatch.setattr(sys, "argv", ["check_frozen_release_sets.py", "origin/main"])
    return files


@pytest.fixture
def gated(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Say which gated defaults the `config.py` diff binds, for the exemption's tests."""

    def _set(*names: str) -> None:
        monkeypatch.setattr(guard, "gated_default_only", lambda base, path: list(names))

    return _set


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


def test_a_gated_default_may_move_with_a_release_set(
    changed: list[str],
    gated: Callable[..., None],
) -> None:
    """The narrowing roadmap 6.8 needed, and the direct check it leans on (ADR-0137).

    `symbol_lookup` only flips when `tools/measure_symbol_leg.py --check` agrees,
    and that runner re-measures on the sets in the same tree — so a default cannot
    be chosen to flatter a set without the runner saying so. That is the same
    argument ADR-0056 used to retire the derived-set proxy: the direct check
    exists, and it is stronger than a rule about which commit two files arrived in.
    """
    gated("symbol_lookup")
    changed.extend(
        [
            "src/mycelium/config.py",
            "eval/corpora/uv-docs/eval/release.jsonl",
            "eval/release.jsonl",
        ]
    )
    assert guard.main() == 0


def test_a_gated_default_beside_another_binding_is_still_refused(
    changed: list[str],
    gated: Callable[..., None],
) -> None:
    """The exemption is for the flag alone, not for the file it lives in."""
    gated()  # the diff binds something the runner does not hold
    changed.extend(["src/mycelium/config.py", "eval/release.jsonl"])
    assert guard.main() == 1


def test_a_gated_default_beside_another_tuning_path_is_still_refused(
    changed: list[str],
    gated: Callable[..., None],
) -> None:
    """A flag the ablation holds says nothing about a ranker change riding with it."""
    gated("symbol_lookup")
    changed.extend(["src/mycelium/config.py", "src/mycelium/retrieval.py", "eval/release.jsonl"])
    assert guard.main() == 1


def test_every_gated_default_names_a_runner_that_exists() -> None:
    """A guard naming a runner that moved guards nothing, silently."""
    for flag, command in guard.GATED_DEFAULTS.items():
        script = ROOT / command.split()[0]
        assert script.is_file(), f"{flag} names {command}, which is not in the tree"


def test_the_gated_defaults_are_read_from_the_diff_not_the_file() -> None:
    """What the *change* did is the question, so the reader is line-based.

    Prose is ignored on purpose — a default flip carries its reasoning in the
    docstring beside it — and a line that binds any other name refuses.
    """
    assert guard._ASSIGNMENT.match("-    symbol_lookup: bool = True")
    assert guard._ASSIGNMENT.match("+    symbol_lookup: bool = False")
    assert guard._ASSIGNMENT.match("+    pack_atomic: bool = False")
    assert not guard._ASSIGNMENT.match("+    off because the ablation stopped earning it")
    assert not guard._ASSIGNMENT.match("+    # the flag follows the measurement")


def test_a_derived_set_may_move_with_the_machinery(changed: list[str]) -> None:
    """Roadmap 4.15 replaced the rule this used to assert, and the reason is a bind.

    A derived set is a function of the chunker, so a chunking change *must* move it —
    the `ingest / lanes` reproducibility check fails otherwise ([BUG-0018]) — while the
    conjunction rule *forbade* moving it. Both guards could not be satisfied, and no
    ordering of two PRs helped: the set only changes once the chunker does.

    So the conjunction rule no longer applies to a set in which nothing is judged
    (ADR-0039, ADR-0047). What replaces it is the test below, plus a byte-for-byte
    reproduction check on every CI run — a stronger guarantee than "nobody edited it".
    """
    changed.extend(["src/mycelium/chunking.py", "eval/corpora/uv-docs-ingested/eval/release.jsonl"])
    assert guard.main() == 0


def test_a_derived_set_may_now_move_with_its_source(changed: list[str]) -> None:
    """The rule roadmap 4.26 retired, and why it had to go (ADR-0056).

    It read: a carried set may not move in the same change as the judged set it is
    copied from, because then nothing distinguishes a carry from a re-fit. The
    intent was right and the control was a proxy — "this file was not
    hand-written" — and the direct check exists. `build_ingested_cases.py --check`
    regenerates the carry from its source and byte-compares it, in CI, whichever
    commit the file arrived in.

    What the proxy did do was make a source set unable to grow: the carry *must*
    follow its source, so the rule forbade exactly the change that was required.
    That deadlock was met from the chunking side at 4.15 and from the judgement
    side at 4.20, where eight drafted cases could not land.
    """
    changed.extend(
        [
            "eval/corpora/uv-docs-ingested/eval/release.jsonl",
            "eval/corpora/uv-docs/eval/release.jsonl",
        ]
    )
    assert guard.main() == 0


def test_the_derived_dev_set_may_move_with_its_source_too(changed: list[str]) -> None:
    changed.extend(
        [
            "eval/corpora/uv-docs-ingested/eval/dev.jsonl",
            "eval/corpora/uv-docs/eval/dev.jsonl",
        ]
    )
    assert guard.main() == 0


def test_growing_a_judged_set_still_refuses_a_retrieval_change_alongside(
    changed: list[str],
) -> None:
    """The rule that did *not* go, and the one the retirement leans on.

    Retiring the derived-set proxy widens what a judgement change may carry; it
    does not touch the conjunction that matters. A change that grows a judged set
    *and* moves the ranker still cannot be told apart from fitting the ranker to
    the set (spec 04 §7.1, ADR-0027).
    """
    changed.extend(
        [
            "eval/corpora/uv-docs/eval/release.jsonl",
            "eval/corpora/uv-docs-ingested/eval/release.jsonl",
            "src/mycelium/retrieval.py",
        ]
    )
    assert guard.main() == 1


def test_every_derived_set_names_a_source_that_exists() -> None:
    """A mapping naming a file that moved guards nothing, silently — the same reason
    the path lists are checked against the filesystem."""
    for derived, source in guard.DERIVED_SETS.items():
        assert (ROOT / derived).is_file(), derived
        assert (ROOT / source).is_file(), source


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
