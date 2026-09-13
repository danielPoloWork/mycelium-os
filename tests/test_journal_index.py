# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The journal index is generated, and generation cannot drift (roadmap 5.32).

`docs/journal/README.md` had fallen 24 checkpoints behind `docs/journal/2026/**` because
the index was a hand-copied row and nothing read the two against each other. The fix
observed that every checkpoint's own first line already states the row its index wants —
`# <date> — <title>` — so the index is generated wholesale from the tree instead, and
`tools/consistency_lint.py`'s `journal-index` check holds the committed file to what a
fresh run would produce.

What is asserted here: the render is a pure, deterministic function of the checkpoints on
disk (same input, same bytes, every time); newest-first ordering, including the tie-break
by filename when two checkpoints share a date; a checkpoint whose heading cannot be read is
refused rather than silently skipped, because a row generation cannot see is a row the
index would otherwise just lose; and `--check` never writes, `main()` does and is
idempotent the second time.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import update_journal_index as generator  # noqa: E402 - the tool is not an installed package

PREAMBLE = """# Session Journal

Some hand-written instructions live here.

## Index

_(stale content a real run must replace)_
"""


@pytest.fixture
def journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A synthetic `docs/journal/` tree, wired in place of the real one."""
    root = tmp_path / "journal"
    root.mkdir()
    (root / "README.md").write_text(PREAMBLE, encoding="utf-8", newline="\n")
    monkeypatch.setattr(generator, "JOURNAL", root)
    monkeypatch.setattr(generator, "INDEX", root / "README.md")
    return root


def write(journal: Path, path: str, first_line: str, body: str = "content\n") -> None:
    target = journal / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"{first_line}\n\n{body}", encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# checkpoints(): what a file must say to be read at all
# ---------------------------------------------------------------------------


def test_a_well_formed_checkpoint_is_read(journal: Path) -> None:
    write(journal, "2026/08/2026-08-29-first.md", "# 2026-08-29 — the first session")
    (relative, date, title) = generator.checkpoints()[0]
    assert relative == "2026/08/2026-08-29-first.md"
    assert date == "2026-08-29"
    assert title == "the first session"


def test_a_heading_with_no_date_is_refused(journal: Path) -> None:
    write(journal, "2026/08/2026-08-29-bad.md", "# Not a dated heading at all")
    with pytest.raises(SystemExit, match="first line is not"):
        generator.checkpoints()


def test_a_heading_naming_a_different_date_than_its_filename_is_refused(journal: Path) -> None:
    write(journal, "2026/08/2026-08-29-mismatch.md", "# 2026-08-30 — wrong date")
    with pytest.raises(SystemExit, match="different date"):
        generator.checkpoints()


def test_an_em_dash_is_required_not_a_hyphen(journal: Path) -> None:
    """The separator every checkpoint actually uses (roadmap 5.32's own preamble)."""
    write(journal, "2026/08/2026-08-29-hyphen.md", "# 2026-08-29 - hyphen, not em dash")
    with pytest.raises(SystemExit, match="first line is not"):
        generator.checkpoints()


# ---------------------------------------------------------------------------
# render(): ordering, and the tie-break the tree can actually support
# ---------------------------------------------------------------------------


def test_render_orders_newest_year_and_month_first() -> None:
    entries = [
        ("2025/12/2025-12-01-old.md", "2025-12-01", "an older session"),
        ("2026/01/2026-01-05-new.md", "2026-01-05", "a newer session"),
        ("2026/01/2026-01-01-earlier.md", "2026-01-01", "earlier the same month"),
    ]
    rendered = generator.render(entries)
    assert rendered.index("### 2026") < rendered.index("### 2025")
    assert rendered.index("#### January") < rendered.index("#### December")
    assert rendered.index("2026-01-05") < rendered.index("2026-01-01")
    assert rendered.startswith(generator.MARKER)


def test_render_breaks_a_same_date_tie_by_filename_descending() -> None:
    """Nothing on disk orders two sessions opened the same day; the rule is stated,
    not hidden, and it is the tree's own filename order."""
    entries = [
        ("2026/09/2026-09-13-alpha.md", "2026-09-13", "alpha session"),
        ("2026/09/2026-09-13-zulu.md", "2026-09-13", "zulu session"),
    ]
    rendered = generator.render(entries)
    assert rendered.index("zulu.md") < rendered.index("alpha.md")


def test_render_is_a_pure_function_of_its_input() -> None:
    entries = [("2026/08/2026-08-29-a.md", "2026-08-29", "a session")]
    assert generator.render(entries) == generator.render(list(entries))


def test_an_empty_journal_renders_just_the_banner() -> None:
    rendered = generator.render([])
    assert rendered == (
        f"{generator.MARKER}\n\n"
        "_(newest first, generated by `tools/update_journal_index.py` — "
        "do not edit by hand)_\n"
    )


# ---------------------------------------------------------------------------
# main(): the preamble survives, --check never writes, and it is idempotent
# ---------------------------------------------------------------------------


def test_main_regenerates_the_index_and_keeps_the_preamble(journal: Path) -> None:
    write(journal, "2026/08/2026-08-29-first.md", "# 2026-08-29 — the first session")
    assert generator.main() == 0

    text = generator.INDEX.read_text(encoding="utf-8")
    assert "Some hand-written instructions live here." in text
    assert "the first session" in text
    assert "stale content a real run must replace" not in text


def test_check_reports_stale_and_never_writes(
    journal: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write(journal, "2026/08/2026-08-29-first.md", "# 2026-08-29 — the first session")
    before = generator.INDEX.read_text(encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["update_journal_index.py", "--check"])
    assert generator.main() == 1

    assert generator.INDEX.read_text(encoding="utf-8") == before


def test_a_second_run_is_a_no_op(journal: Path) -> None:
    write(journal, "2026/08/2026-08-29-first.md", "# 2026-08-29 — the first session")
    generator.main()
    once = generator.INDEX.read_text(encoding="utf-8")
    assert generator.main() == 0
    assert generator.INDEX.read_text(encoding="utf-8") == once


def test_missing_index_heading_refuses_rather_than_guessing(journal: Path) -> None:
    generator.INDEX.write_text("# No index heading here\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="no '## Index' heading"):
        generator.main()


# ---------------------------------------------------------------------------
# The live repository: the check this was all for
# ---------------------------------------------------------------------------


def test_the_committed_journal_index_is_current(monkeypatch: pytest.MonkeyPatch) -> None:
    """The generator's own opinion of the committed file must be 'nothing to do' —
    the same property `tools/consistency_lint.py`'s `journal-index` check holds
    every PR to."""
    monkeypatch.setattr(sys, "argv", ["update_journal_index.py", "--check"])
    assert generator.main() == 0
