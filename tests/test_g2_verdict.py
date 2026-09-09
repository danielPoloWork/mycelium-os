# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Gate G2 has a runner, and the runner refuses a stale verdict (roadmap 4.40).

G2 decides the product's default retrieval profile, and it can only be *measured*
where the embedding model is — which is not CI (D-013). So the verdict is
committed, and what runs everywhere is the question CI can answer: does the
recorded verdict still describe this product? These tests are that question's
falsification, one criterion at a time.

The load-bearing one is
:func:`test_the_retrieval_identity_moves_when_a_field_weight_moves`. Every other
check here rests on that digest actually being a fingerprint: it is what would
have caught the four lexical changes that moved G2's verdict underneath itself
while the recorded verdict stayed put (ADR-0064, ADR-0068).
"""

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from mycelium.eval.harness import G2_OVERALL_MIN, G2_SLICE_FLOOR
from mycelium.retrieval import STOPWORDS, retrieval_identity
from mycelium.store import STORE_DIRNAME, STORE_FILENAME, describe_field_weights
from mycelium.store import sqlite as store_sqlite

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
import measure_hybrid_gate as g2  # noqa: E402

ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def committed() -> dict[str, Any]:
    """The verdict this repository ships."""
    record = g2.read_record()
    assert record is not None, "eval/g2-verdict.json is missing"
    return record


def current(record: dict[str, Any]) -> dict[str, Any]:
    """A deep-enough copy for one test to spoil one field."""
    return json.loads(json.dumps(record))


# ---------------------------------------------------------------------------
# The fingerprint everything else rests on
# ---------------------------------------------------------------------------


def test_the_retrieval_identity_moves_when_a_field_weight_moves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one guarantee that makes the currency check a check.

    The weights were a hand-typed string in two places until roadmap 4.40, so a
    change to the ranking's arithmetic did not have to move anything that claimed
    to describe it. Read from the store at call time, it must.
    """
    before = retrieval_identity()
    monkeypatch.setattr(store_sqlite, "_SURFACE_WEIGHTS", (0.0, 1.0, 4.0, 2.0, 0.5))
    assert retrieval_identity() != before
    assert describe_field_weights() == "title=4.0,heading=2.0,body=1.0,ancestors=0.5"


def test_the_retrieval_identity_moves_when_the_stem_weight_moves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = retrieval_identity()
    monkeypatch.setattr(store_sqlite, "STEM_WEIGHT", 0.09)
    monkeypatch.setattr("mycelium.retrieval.STEM_WEIGHT", 0.09)
    assert retrieval_identity() != before


def test_the_retrieval_identity_moves_on_a_stopword_swap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Membership, not size — a count would have missed this entirely."""
    swapped = (STOPWORDS - {"the"}) | {"thee"}
    assert len(swapped) == len(STOPWORDS), "the same size, a different list"
    before = retrieval_identity()
    monkeypatch.setattr("mycelium.retrieval.STOPWORDS", frozenset(swapped))
    assert retrieval_identity() != before


def test_the_retrieval_identity_is_stable_across_calls() -> None:
    assert retrieval_identity() == retrieval_identity()


# ---------------------------------------------------------------------------
# The committed record
# ---------------------------------------------------------------------------


def test_the_committed_verdict_is_current(committed: dict[str, Any]) -> None:
    """The record ships describing the product it ships with."""
    failures, _ = g2.check_currency(committed)
    assert failures == []


def test_the_committed_verdict_records_what_it_was_measured_under(
    committed: dict[str, Any],
) -> None:
    assert committed["schema_version"] == g2.VERDICT_SCHEMA
    assert committed["retrieval_identity"] == retrieval_identity()
    assert committed["recorded_at"].count("-") == 2, "a date a reader can act on"
    assert committed["model_id"]
    # Every judged set the repository carries is in the record: a verdict that
    # covered four of six sets would be a verdict about the four it liked.
    assert set(committed["sets"]) == {
        f"{label}/{name}"
        for label, root in g2.CORPORA
        for name in g2.SETS
        if (root / "eval" / f"{name}.jsonl").is_file()
    }


def test_a_tripped_slice_in_the_record_names_its_cases(committed: dict[str, Any]) -> None:
    """Roadmap 4.41: a percentage over four cases cannot tell a reader whether it is
    noise or a destroyed answer, and the item was filed believing the wrong one.

    Model-free, so it runs in CI: the record is the one place a tripped slice's
    cases are readable without re-measuring (ADR-0069).
    """
    tripped = [
        regression for row in committed["sets"].values() for regression in row["regressions"]
    ]
    assert tripped, "every set passing would make this test vacuous - check the record"
    assert all("->" in regression for regression in tripped), (
        f"a slice trips without naming a case: {tripped}"
    )


def test_the_recorded_decision_is_the_shipped_default(committed: dict[str, Any]) -> None:
    """A decision the product does not follow is not a decision."""
    assert committed["decision"] == committed["shipped_profile"]


def test_the_record_is_byte_stable(committed: dict[str, Any], tmp_path: Path) -> None:
    """Re-serialising the committed record reproduces it exactly.

    A record whose formatting drifts produces a diff on every re-measurement and
    hides the one line that actually moved.
    """
    written = tmp_path / "g2-verdict.json"
    written.write_text(
        json.dumps(committed, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    assert written.read_bytes() == g2.VERDICT_PATH.read_bytes()


def test_the_record_restates_the_gate_it_measures(committed: dict[str, Any]) -> None:
    """The thresholds come from the harness, so the tool cannot drift from the gate."""
    assert (G2_OVERALL_MIN, G2_SLICE_FLOOR) == (0.05, -0.02)
    assert f"needs {G2_OVERALL_MIN:+.0%}" in committed["sets"]["uv/release"]["detail"]


# ---------------------------------------------------------------------------
# Staleness, one criterion at a time
# ---------------------------------------------------------------------------


def test_a_missing_record_names_the_command_that_writes_one() -> None:
    failures, _ = g2.check_currency(None)
    assert len(failures) == 1
    assert "--record" in failures[0]


def test_an_unknown_schema_version_stops_before_guessing() -> None:
    failures, _ = g2.check_currency({"schema_version": "mycelium/g2-verdict/v99"})
    assert len(failures) == 1, "one failure, not a cascade of misread fields"
    assert "v99" in failures[0]


def test_a_changed_retrieval_configuration_fails(committed: dict[str, Any]) -> None:
    """The failure the item was filed about: four lexical changes, none noticed."""
    stale = current(committed)
    stale["retrieval_identity"] = "sha256:" + "0" * 64
    failures, _ = g2.check_currency(stale)
    assert any("retrieval configuration changed" in failure for failure in failures)


def test_a_flipped_default_fails_even_with_everything_else_current(
    committed: dict[str, Any],
) -> None:
    stale = current(committed)
    stale["shipped_profile"] = "hybrid"
    failures, _ = g2.check_currency(stale)
    assert any("shipped default is now" in failure for failure in failures)


def test_a_decision_the_product_does_not_follow_fails(committed: dict[str, Any]) -> None:
    stale = current(committed)
    stale["decision"] = "hybrid"
    failures, _ = g2.check_currency(stale)
    assert any("flip the default or re-measure" in failure for failure in failures)


def test_moved_judgements_fail_on_a_dated_corpus(committed: dict[str, Any]) -> None:
    stale = current(committed)
    stale["sets"]["uv/release"]["cases_digest"] = "sha256:" + "1" * 64
    failures, _ = g2.check_currency(stale)
    assert any("uv/release's judgements changed" in failure for failure in failures)


def test_moved_judgements_are_only_noted_on_our_own_corpus(
    committed: dict[str, Any],
) -> None:
    """`ours` is reported, never gated — every pull request moves this repository."""
    stale = current(committed)
    stale["sets"]["ours/release"]["cases_digest"] = "sha256:" + "1" * 64
    failures, notes = g2.check_currency(stale)
    assert failures == []
    assert any("ours/release" in note for note in notes)


def test_a_missing_set_in_the_record_fails(committed: dict[str, Any]) -> None:
    stale = current(committed)
    del stale["sets"]["uv/dev"]
    failures, _ = g2.check_currency(stale)
    assert any("uv/dev" in failure for failure in failures)


def test_a_moved_dated_corpus_fails(
    committed: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The corpus check, exercised without depending on a built store.

    The suite runs where the corpora are not compiled, so the fingerprint is
    injected: what is under test is the *rule* — a moved dated corpus fails, a
    moved undated one is noted.
    """
    built = tmp_path / "corpus"
    (built / STORE_DIRNAME).mkdir(parents=True)
    (built / STORE_DIRNAME / STORE_FILENAME).write_bytes(b"")
    monkeypatch.setattr(g2, "CORPORA", (("uv", built),))
    monkeypatch.setattr(
        g2, "corpus_fingerprint_of", lambda root: _Fingerprint("sha256:moved", "sha256:recut")
    )
    notes: list[str] = []
    failures = g2._check_corpora(committed, notes)
    assert any("'uv' corpus changed" in failure for failure in failures)
    assert any("chunk boundaries moved" in note for note in notes)


def test_a_moved_undated_corpus_is_only_noted(
    committed: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built = tmp_path / "corpus"
    (built / STORE_DIRNAME).mkdir(parents=True)
    (built / STORE_DIRNAME / STORE_FILENAME).write_bytes(b"")
    monkeypatch.setattr(g2, "CORPORA", (("ours", built),))
    monkeypatch.setattr(
        g2, "corpus_fingerprint_of", lambda root: _Fingerprint("sha256:moved", "sha256:recut")
    )
    notes: list[str] = []
    assert g2._check_corpora(committed, notes) == []
    assert any("never gated" in note for note in notes)


def test_an_unbuilt_corpus_says_it_was_not_compared(
    committed: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Silence would read as agreement; the runner has to name what it skipped."""
    monkeypatch.setattr(g2, "CORPORA", (("uv", tmp_path),))
    notes: list[str] = []
    assert g2._check_corpora(committed, notes) == []
    assert any("not built here" in note for note in notes)


def compare(
    record: dict[str, Any], measured: list[g2.SetVerdict], notes: list[str] | None = None
) -> list[str]:
    return g2.compare_measurement(record, measured, notes)


def _verdict(name: str, *, passed: bool) -> g2.SetVerdict:
    """A measured verdict for one set, carrying only what the comparison reads."""
    return g2.SetVerdict(
        name=name,
        lexical=0.5,
        hybrid=0.4 if not passed else 0.9,
        passed=passed,
        detail="",
        regressions=(),
        cases=4,
        cases_digest="sha256:" + "0" * 64,
        per_slice={},
    )


def test_a_flipped_verdict_fails_on_a_dated_corpus(committed: dict[str, Any]) -> None:
    """A frozen corpus that changes its mind means something the fingerprints missed."""
    recorded = str(committed["sets"]["uv/release"]["verdict"])
    measured = [_verdict("uv/release", passed=recorded != "pass")]
    failures = compare(committed, measured)
    assert any("uv/release: recorded" in failure for failure in failures)


def test_a_flipped_verdict_is_only_noted_on_our_own_corpus(committed: dict[str, Any]) -> None:
    """The carve-out roadmap 4.42 found missing (ADR-0070).

    `ours` is this repository, so a pull request that writes an ADR moves the
    corpus the verdict was measured on — and the flip that follows is *expected*.
    Gating it fails `verify.py` for a contributor who has the embedding model,
    while CI, which has none and never re-measures, sees nothing: the
    local-versus-CI divergence ADR-0059 exists to remove.
    """
    recorded = str(committed["sets"]["ours/release"]["verdict"])
    measured = [_verdict("ours/release", passed=recorded != "pass")]
    notes: list[str] = []
    assert compare(committed, measured, notes) == []
    assert any("ours/release: recorded" in note for note in notes)
    assert any("undated corpus" in note for note in notes)


def test_a_flipped_verdict_without_a_notes_list_is_still_not_a_failure(
    committed: dict[str, Any],
) -> None:
    """`notes` is optional, and dropping it must not re-arm the gate."""
    recorded = str(committed["sets"]["ours/release"]["verdict"])
    assert compare(committed, [_verdict("ours/release", passed=recorded != "pass")]) == []


def test_a_moved_decision_fails_wherever_the_drift_came_from(
    committed: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one thing the carve-out does not excuse.

    An undated corpus may flip a *set*; it may not quietly change which retrieval
    profile the measurement supports. That is checked over every set at once, so
    it survives the note above.
    """
    monkeypatch.setattr(g2, "decision_of", lambda verdicts: "hybrid")
    measured = [_verdict(name, passed=True) for name in committed["sets"]]
    failures = compare(committed, measured)
    assert any("now supports 'hybrid'" in failure for failure in failures)


class _Fingerprint:
    """The two folds `corpus_fingerprint_of` returns, without a store to fold."""

    def __init__(self, content: str, chunks: str) -> None:
        self.content = content
        self.chunks = chunks


# ---------------------------------------------------------------------------
# What the release rows decide
# ---------------------------------------------------------------------------


def test_the_release_rows_decide_and_the_dev_rows_do_not() -> None:
    passing = {"verdict": "pass"}
    failing = {"verdict": "fail"}
    assert g2.decision_of({"uv/release": passing, "ours/release": passing}) == "hybrid"
    assert g2.decision_of({"uv/release": passing, "ours/release": failing}) == "lexical"
    # Two dev sets clearing the bar cannot flip the default; that is the split
    # (ADR-0027), and hybrid gains +23 % on the dev sets it must not be judged on.
    assert g2.decision_of({"uv/dev": passing, "ours/dev": passing}) == "lexical"


def test_no_release_row_at_all_leaves_the_default_alone() -> None:
    """The burden is on hybrid, so absence of evidence is not evidence."""
    assert g2.decision_of({}) == "lexical"


def test_the_committed_release_rows_support_the_recorded_decision(
    committed: dict[str, Any],
) -> None:
    assert g2.decision_of(committed["sets"]) == committed["decision"]


# ---------------------------------------------------------------------------
# Comparing a fresh measurement, where one is possible
# ---------------------------------------------------------------------------


def measured(name: str, *, passed: bool) -> g2.SetVerdict:
    return g2.SetVerdict(
        name=name,
        lexical=0.5,
        hybrid=0.6 if passed else 0.4,
        passed=passed,
        detail="stub",
        regressions=(),
        cases=4,
        cases_digest="sha256:" + "2" * 64,
        per_slice={},
    )


def test_a_verdict_that_flipped_since_the_record_is_reported(
    committed: dict[str, Any],
) -> None:
    was = committed["sets"]["uv/release"]["verdict"]
    flipped = measured("uv/release", passed=was != "pass")
    failures = g2.compare_measurement(committed, [flipped])
    assert any("uv/release: recorded" in failure for failure in failures)


def test_a_verdict_that_reproduced_is_silent(committed: dict[str, Any]) -> None:
    same = measured("uv/release", passed=committed["sets"]["uv/release"]["verdict"] == "pass")
    assert g2.compare_measurement(committed, [same]) == []


def test_a_set_measured_here_and_absent_from_the_record_is_reported(
    committed: dict[str, Any],
) -> None:
    failures = g2.compare_measurement(committed, [measured("acme/release", passed=True)])
    assert any("absent from the record" in failure for failure in failures)


def test_comparison_is_on_verdicts_not_on_floats(committed: dict[str, Any]) -> None:
    """ONNX is not promised identical across machines (ADR-0017), so a float
    comparison would fail on a second machine for a reason that is not retrieval."""
    row = committed["sets"]["uv/release"]
    drifted = measured("uv/release", passed=row["verdict"] == "pass")
    assert drifted.lexical != row["lexical_ndcg_at_10"]
    assert g2.compare_measurement(committed, [drifted]) == []
