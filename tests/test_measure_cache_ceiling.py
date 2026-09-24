# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The remote-cache instrument measures what it names (roadmap 7.4, ADR-0154).

`tools/measure_cache_ceiling.py` prices a remote build cache before anybody builds
one, by building fresh checkouts of one corpus with different things in their
`.mycelium/`. A number from it is only evidence if each arm did what its name says —
the seeded arm hit every stage, the cold arm hit none, and no arm changed the output —
so that is what this pins, on a corpus small enough to build six times in a test.

It also pins the two properties any remote cache would stand on, because this is the
first place that measures them: two checkouts of one tree at different paths, with
different mtimes and different line endings, **mint the same build keys and agree on
every artifact those keys name**.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import adoption_report  # noqa: E402 - the tools are not a package
import benchmark_reference_profile as profile  # noqa: E402
import measure_cache_ceiling as ceiling  # noqa: E402

from mycelium.store import STORE_DIRNAME  # noqa: E402

DOCUMENTS = {
    "knowledge/guide.md": (
        "# Guide\n\nHow the compiler turns [[reference]] pages into chunks.\n\n"
        "## Install\n\n```bash\nuv sync --all-extras --dev\n```\n\n"
        "## Build\n\nRun `mycelium build --no-pin` from the repository root.\n"
    ),
    "knowledge/reference.md": (
        "# Reference\n\nEvery command, with its flags.\n\n"
        "## search\n\nReturns cited chunks; see [[guide]].\n\n"
        "```python\ndef search(query: str) -> list[str]:\n    return []\n```\n"
    ),
    "knowledge/notes/decisions.md": (
        "# Decisions\n\n| Decision | Why |\n|---|---|\n| SQLite | one file |\n\n"
        "## Deferred\n\nA remote cache waits for a team that needs it.\n"
    ),
    "knowledge/notes/glossary.md": (
        "# Glossary\n\n## Chunk\n\nA heading-bounded passage.\n\n"
        "## Snapshot\n\nOne published build of the corpus.\n"
    ),
}

CONFIG = '[project]\nname = "ceiling-fixture"\n\n[embedding]\nprovider = "none"\n'


def _template(root: Path) -> Path:
    for relative, text in DOCUMENTS.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    (root / "mycelium.toml").write_text(CONFIG, encoding="utf-8", newline="\n")
    return root


@pytest.fixture(scope="module")
def measured(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    """One run of every arm, shared: six builds are the expensive part of this file."""
    root = tmp_path_factory.mktemp("ceiling")
    return ceiling.measure(_template(root / "template"), root / "work", rounds=1, label="fixture")


def _by_arm(block: dict[str, object]) -> dict[str, dict[str, object]]:
    measurements = block["measurements"]
    assert isinstance(measurements, list)
    return {str(item["arm"]): item for item in measurements}


def test_each_arm_measured_what_it_names(measured: dict[str, object]) -> None:
    block = measured
    arms = _by_arm(block)
    documents = len(DOCUMENTS)
    assert block["documents"] == documents
    # A cold build hits nothing; a seeded or restored one hits every stage it runs.
    assert arms["cold"]["parse_hits"] == [0]
    assert arms["cold"]["chunk_hits"] == [0]
    for arm in ("seeded", "restored"):
        assert arms[arm]["rebuilt"] == [documents], arm
        assert arms[arm]["parse_hits"] == [documents], arm
        assert arms[arm]["chunk_hits"] == [documents], arm
    # Two stage artifacts per document, each with the row that names it.
    assert arms["seeding"]["rows"] == [2 * documents]

    result = block["ceiling"]
    assert isinstance(result, dict)
    assert result["outputs_identical"] is True
    # A document record carries its file's mtime, and a fresh checkout's are new:
    # expected, and the reason a cached checkout still re-assembles every document.
    assert result["documents_digest_varies_by_checkout"] is True


def test_the_mtime_is_the_whole_reason_a_restored_checkout_recompiles(
    measured: dict[str, object],
) -> None:
    """Give the restored checkout its cache's mtimes and nothing is rebuilt at all.

    The same `.mycelium/`, the same bytes: the only difference between this arm and
    `restored` is the mtime of each document, and it is the difference between every
    document re-assembled and re-stored and none. The published documents digest comes
    back identical, because the records now carry the timestamps they were built with.
    """
    arms = _by_arm(measured)
    assert arms["restored-mtimes"]["rebuilt"] == [0]
    assert arms["restored-mtimes"]["parse_hits"] == [0]
    result = measured["ceiling"]
    assert isinstance(result, dict)
    assert result["documents_digest_kept_with_mtimes"] is True


def test_keys_are_portable_across_paths_mtimes_and_line_endings(
    measured: dict[str, object],
) -> None:
    """The precondition of any shared cache, measured rather than assumed.

    The seeded arm already builds at a different path with new mtimes; the CRLF
    checkout is a Windows clone under `core.autocrlf`, seeded from the LF build.
    Every key it asks for is one the LF build minted, and nothing it serves differs.
    """
    portability = measured["portability"]
    assert isinstance(portability, dict)
    assert portability["parse_hits"] == len(DOCUMENTS)
    assert portability["chunk_hits"] == len(DOCUMENTS)
    assert portability["outputs_identical"] is True


def test_the_manifest_block_is_evidence_the_reference_profile_accepts(
    measured: dict[str, object],
) -> None:
    block = measured
    assert "cache_profile" in profile.MEASUREMENT_SECTIONS
    blocks = profile._measurement_blocks([block])
    assert blocks, "a cache_profile block must carry measurements"
    assert all("p95" in measurement for measurement in blocks[0])
    names = [str(measurement["name"]) for measurement in blocks[0]]
    assert len(names) == len(set(names)), "two measurements share a name"


def test_the_report_is_what_the_trigger_reads_and_carries_no_path(
    measured: dict[str, object], tmp_path: Path
) -> None:
    """One schema, two readers: what the instrument prints, the gate parses.

    And it is meant for a public issue, so no string in it may name a file or a
    directory of the corpus it measured.

    The report is built from real timings of a four-document corpus, and on a fast
    disk the seeded build can come out *slower* than the cold one — the saving is
    then negative. That report must still parse: the round trip is a property of
    the schema, not of this machine's clock, and the first version of this test
    failed on one CI cell for exactly that reason (BUG-0036).
    """
    report = ceiling.pain_report(measured, people=4, cold_builds_per_week=30)

    assert report["schema"] == adoption_report.CACHE_REPORT_SCHEMA
    body = "Our numbers:\n\n```json\n" + json.dumps(report, indent=2) + "\n```\n"
    parsed = adoption_report.reports_in(body, login="someone", issue=7)
    assert len(parsed) == 1, "a report parses whatever its saving's sign"
    assert parsed[0].people == 4
    assert parsed[0].documents == len(DOCUMENTS)
    assert parsed[0].cold_builds_per_week == 30

    strings = [value for value in report.values() if isinstance(value, str)]
    assert strings, "the report carries at least its schema tag"
    for value in strings:
        assert str(tmp_path.parent) not in value
        assert not any(Path(name).stem in value for name in DOCUMENTS)


def test_copying_a_corpus_writes_nothing_into_the_repository(tmp_path: Path) -> None:
    repository = _template(tmp_path / "repository")
    (repository / "README.md").write_text("# Not in the corpus\n", encoding="utf-8")
    before = sorted(path.relative_to(repository) for path in repository.rglob("*"))

    copied = ceiling.copy_corpus(repository, tmp_path / "copy")

    assert copied == len(DOCUMENTS)
    after = sorted(path.relative_to(repository) for path in repository.rglob("*"))
    assert after == before
    assert not (repository / STORE_DIRNAME).exists()
    assert (tmp_path / "copy" / "mycelium.toml").is_file()
    assert not (tmp_path / "copy" / "README.md").exists()


def test_a_crlf_checkout_differs_in_bytes_and_not_in_content(tmp_path: Path) -> None:
    template = _template(tmp_path / "template")
    lf = ceiling.checkout(template, tmp_path / "lf")
    crlf = ceiling.checkout(template, tmp_path / "crlf", crlf=True)

    for relative in DOCUMENTS:
        lf_bytes = (lf / relative).read_bytes()
        crlf_bytes = (crlf / relative).read_bytes()
        assert b"\r\n" in crlf_bytes and b"\r\n" not in lf_bytes
        assert crlf_bytes.replace(b"\r\n", b"\n") == lf_bytes
    assert ceiling.corpus_digest(lf) == ceiling.corpus_digest(template)
    assert ceiling.corpus_digest(crlf) != ceiling.corpus_digest(template)
