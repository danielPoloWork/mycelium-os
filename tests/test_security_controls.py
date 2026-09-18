# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The controls the 6.3 security review added, each at the scale that found it (ADR-0119).

The review measured what a hostile document could make the compiler *spend*, and found
four shapes with no bound: a nine-line YAML alias bomb in frontmatter that took a build
past ninety seconds (BUG-0027); a private-key secret rule whose lazy body scanned to the
end of the text once per header, so twenty thousand headers in 640 KB did not finish in a
minute (BUG-0028); forty kilobytes of asterisks that recursed past the interpreter's
limit, quarantined by a catch-all in the build and a traceback out of `mycelium ingest`
(BUG-0029); and an authored document of any size read whole before anything asked how
big it was. It also found one claimed control with no test behind it: the pandoc
subprocess's `--sandbox` and timeout (B9).

These tests hold each bound at the size that used to break it. `tests/test_injection.py`
holds the same shapes at fixture size, inside the corpus; this file holds the megabytes.
"""

import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

from mycelium.build import build, orchestrator
from mycelium.ingest import Quarantine, Registry, ingest_source, redact_text, scan_text
from mycelium.ingest.errors import ParseError
from mycelium.ingest.media import HTML
from mycelium.ingest.parsers.pandoc import PandocParser
from mycelium.markdown import MarkdownError, parse_markdown
from mycelium.markdown.adapter import MAX_NESTING
from mycelium.markdown.frontmatter import MAX_FRONTMATTER_BYTES, FrontmatterError, parse_frontmatter
from mycelium.retrieval import MAX_QUERY_TERMS, search
from mycelium.sdk.protocols import Blob
from mycelium.store import SqliteStore

pytestmark = [
    pytest.mark.boundary("B4"),
    pytest.mark.boundary("B9"),
    pytest.mark.boundary("B6"),
]
"""The threat-model boundaries these tests hold (docs/security/threat-model.md §4).

B6 joined at roadmap 6.17 with the bound on the question — the one cost on the serving
path that the review left open (register F11), held here at the size that found it."""

DOC_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"
BUDGET_S = 5.0
"""How long any single refusal below may take. The shapes it bounds took 90 s, 60 s+ and
13 s before the controls existed; five seconds is generous to a slow CI runner and still
an order of magnitude inside what a stall looks like."""


def _alias_bomb(levels: int = 9) -> str:
    lines = ["a0: &a0 [x, x, x, x, x, x, x, x, x]"]
    for level in range(1, levels):
        previous = f"*a{level - 1}"
        lines.append(f"a{level}: &a{level} [{', '.join([previous] * 9)}]")
    lines.append(f"tags: *a{levels - 1}")
    return "\n".join(lines)


EMPHASIS = "# Emphasis\n\n" + "*" * 20_000 + "a" + "*" * 20_000 + "\n"


# ---------------------------------------------------------------------------
# Frontmatter: a block's cost to read is bounded before a field is read
# ---------------------------------------------------------------------------


def test_a_yaml_alias_bomb_is_refused_by_name_in_milliseconds() -> None:
    started = time.perf_counter()
    with pytest.raises(FrontmatterError, match="alias"):
        parse_frontmatter("---\n" + _alias_bomb() + "\n---\n\n# Bomb\n\nprose\n")
    assert time.perf_counter() - started < BUDGET_S


def test_a_single_harmless_alias_is_refused_too_because_the_rule_is_the_shape() -> None:
    """Refusing only *bombs* would mean recognising one, and the profile has no use for
    aliases at all — a property is a scalar or a short list."""
    with pytest.raises(FrontmatterError, match=r"\*base"):
        parse_frontmatter("---\nbase: &base [a, b]\ntags: *base\n---\n\nbody\n")


def test_an_anchor_without_an_alias_is_still_valid_yaml() -> None:
    """An anchor by itself expands nothing; the loader refuses the *use*, not the mark."""
    result = parse_frontmatter("---\ntags: &tags [a, b]\n---\n\nbody\n")
    assert result.frontmatter.tags == ("a", "b")


def test_a_frontmatter_block_over_the_ceiling_is_refused_and_one_under_it_is_read() -> None:
    padding = "x" * (MAX_FRONTMATTER_BYTES + 1)
    with pytest.raises(FrontmatterError, match="ceiling"):
        parse_frontmatter(f"---\nnote: {padding}\n---\n\nbody\n")
    fits = "x" * (MAX_FRONTMATTER_BYTES - 64)
    result = parse_frontmatter(f"---\ntitle: T\nnote: {fits}\n---\n\nbody\n")
    assert result.frontmatter.title == "T"
    assert result.frontmatter.properties["note"] == fits


def test_the_ceiling_is_two_orders_above_any_real_frontmatter() -> None:
    assert MAX_FRONTMATTER_BYTES == 64 * 1024


# ---------------------------------------------------------------------------
# The adapter: a document's nesting is bounded before the tree is built
# ---------------------------------------------------------------------------


def test_an_emphasis_run_past_the_nesting_ceiling_is_a_typed_refusal() -> None:
    started = time.perf_counter()
    with pytest.raises(MarkdownError, match="nests"):
        parse_markdown(EMPHASIS, doc_id=DOC_ID)
    assert time.perf_counter() - started < BUDGET_S


def test_the_ceiling_is_the_parsers_own_and_real_documents_sit_far_below_it() -> None:
    """One hundred is markdown-it's `maxNesting`; the deepest document in the three
    corpora nests six. A list ten deep with emphasis inside parses without complaint."""
    assert MAX_NESTING == 100
    nested = "".join("  " * depth + "- *item*\n" for depth in range(10))
    document = parse_markdown("# Deep\n\n" + nested, doc_id=DOC_ID)
    assert document.kir.nodes


def test_the_build_quarantines_the_emphasis_run_by_its_contract_not_by_the_interpreter(
    tmp_path: Path,
) -> None:
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "emphasis.md").write_text(EMPHASIS, encoding="utf-8")
    (tmp_path / "knowledge" / "fine.md").write_text("# Fine\n\nprose\n", encoding="utf-8")
    started = time.perf_counter()
    result = build(tmp_path)
    assert time.perf_counter() - started < BUDGET_S * 3
    assert result.manifest.counts.quarantined == 1
    (warning,) = [w for w in result.manifest.warnings if "emphasis.md" in w]
    assert "MarkdownError" in warning and "RecursionError" not in warning


def test_ingest_quarantines_the_emphasis_run_instead_of_dying_on_it(tmp_path: Path) -> None:
    """BUG-0029's second half: the evidence lane catches `IngestError` only, and a
    `RecursionError` was not one. Now the adapter refuses first, as a `ParseError`,
    and the refusal is written down."""
    source = tmp_path / "sources" / "emphasis.md"
    source.parent.mkdir()
    source.write_text(EMPHASIS, encoding="utf-8")
    registry = Registry.resolve(parsers=["markdown"], connectors=["file"], roots=[source.parent])
    mycelium_dir = tmp_path / ".mycelium"
    with pytest.raises(ParseError, match="nests"):
        ingest_source(mycelium_dir, registry, str(source), doc_id=DOC_ID)
    quarantine = Quarantine(mycelium_dir)
    assert quarantine.count() == 1
    (record,) = list(quarantine.records())
    assert record.reason == "ParseError"


# ---------------------------------------------------------------------------
# Authored documents share the ingest lane's byte ceiling
# ---------------------------------------------------------------------------


def test_an_authored_document_over_the_byte_ceiling_is_quarantined_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orchestrator, "MAX_SOURCE_BYTES", 1024)
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "huge.md").write_text(
        "# Huge\n\n" + "x" * 2048 + "\n", encoding="utf-8"
    )
    (tmp_path / "knowledge" / "fine.md").write_text("# Fine\n\nprose\n", encoding="utf-8")
    result = build(tmp_path)
    assert result.manifest.counts.documents == 1
    assert result.manifest.counts.quarantined == 1
    (warning,) = [w for w in result.manifest.warnings if "huge.md" in w]
    assert "ceiling" in warning and "1024" in warning


def test_the_authored_ceiling_is_the_connectors() -> None:
    from mycelium.ingest.connectors.file import DEFAULT_MAX_BYTES

    assert orchestrator.MAX_SOURCE_BYTES == DEFAULT_MAX_BYTES == 64 * 1024 * 1024


# ---------------------------------------------------------------------------
# The question is bounded too (B6, register F11, roadmap 6.17)
# ---------------------------------------------------------------------------


def test_a_document_pasted_as_a_query_is_answered_in_milliseconds(tmp_path: Path) -> None:
    """The finding the review left open, at the size that found it.

    F11 measured twenty thousand terms holding the single-threaded stdio server for
    57 s. Re-measured through the whole `search` path at 6.17 it was worse: this
    repository's own README — 62 KB, 7 384 terms, an agent pasting a document and
    nothing hostile at all — held it for **146 s**. Bounded, the same query is
    answered in ~94 ms.
    """
    (tmp_path / "knowledge").mkdir()
    (tmp_path / "knowledge" / "retries.md").write_text(
        "# Retries\n\nFailed deliveries retry with exponential backoff.\n", encoding="utf-8"
    )
    build(tmp_path)

    pasted = "exponential backoff " + " ".join(
        f"word{index % 977} filler prose" for index in range(2500)
    )
    assert len(pasted.split()) > 7000

    with SqliteStore.open(tmp_path, read_only=True) as store:
        started = time.perf_counter()
        outcome = search(store, pasted)
        elapsed = time.perf_counter() - started

    assert elapsed < BUDGET_S, f"a pasted document took {elapsed:.1f} s"
    assert outcome.hits, "the bounded question is still answered, not refused"
    assert any("bounded" in note for note in outcome.notes)


def test_the_bound_is_the_only_unbounded_cost_the_review_found_still_open() -> None:
    """The other three costs on this path were already bounded, and the bound is
    sized against a question rather than against a document (ADR-0129)."""
    assert MAX_QUERY_TERMS == 64
    # Seven times the longest query anything in this project measures itself on.
    assert MAX_QUERY_TERMS > 9 * 7


# ---------------------------------------------------------------------------
# The secret scan is linear, block rules included
# ---------------------------------------------------------------------------

HEADER = "-----BEGIN RSA PRIVATE KEY-----"
FOOTER = "-----END RSA PRIVATE KEY-----"


def test_twenty_thousand_truncated_keys_scan_in_seconds_and_each_is_a_finding() -> None:
    block = HEADER + "\nMIIBOgIBAAJBAK\n"
    text = block * 20_000
    started = time.perf_counter()
    findings = scan_text(text)
    assert time.perf_counter() - started < BUDGET_S
    assert len(findings) == 20_000
    assert all(text[f.start : f.end] == block.rstrip("\n") for f in findings)


def test_twenty_thousand_lone_headers_scan_in_seconds_and_none_is_a_key() -> None:
    """The shape that hung the old rule. A header with nothing under it is
    documentation of a key — this repository's own bug ledger quotes one — and the
    doctrine is precision, so none flags; what matters is that it costs nothing."""
    text = (HEADER + "\n") * 20_000
    started = time.perf_counter()
    findings = scan_text(text)
    assert time.perf_counter() - started < BUDGET_S
    assert findings == []


def test_a_well_formed_key_is_one_finding_from_header_to_footer() -> None:
    key = f"{HEADER}\nMIIBOgIBAAJBAK\nAAAAB3NzaC1yc2E=\n{FOOTER}"
    text = f"before\n{key}\nafter\n"
    (finding,) = scan_text(text)
    assert text[finding.start : finding.end] == key
    redacted = redact_text(text, [finding])
    assert redacted == "before\n[redacted: private-key-block]\nafter\n"


def test_a_truncated_key_still_flags_and_its_body_is_still_redacted() -> None:
    """The old regex needed the footer to match at all, so a truncated key went through
    unflagged and unredacted — the worse outcome, from the rule meant to catch it."""
    text = f"{HEADER}\nMIIBOgIBAAJBAK\nAAAAB3NzaC1yc2E=\n\nThe prose that follows.\n"
    (finding,) = scan_text(text)
    assert text[finding.start : finding.end].startswith(HEADER)
    assert "AAAAB3NzaC1yc2E=" in text[finding.start : finding.end]
    assert "The prose that follows" not in text[finding.start : finding.end]
    assert "AAAAB3NzaC1yc2E=" not in redact_text(text, [finding])


def test_an_encrypted_legacy_key_keeps_its_own_headers_inside_the_block() -> None:
    headers = "Proc-Type: 4,ENCRYPTED\nDEK-Info: AES-128-CBC,ABCDEF"
    key = f"{HEADER}\n{headers}\n\nMIIBOgIBAAJBAK\n{FOOTER}"
    (finding,) = scan_text(key)
    assert key[finding.start : finding.end] == key


def test_a_header_quoted_in_prose_is_not_a_key() -> None:
    assert scan_text(f"{HEADER} is how a PEM key starts.\nMIIBOg\n") == []
    assert scan_text(f"The armour line reads:\n\n{HEADER}\n\nand then base64 follows.\n") == []


def test_a_header_inside_a_block_is_not_a_second_block() -> None:
    text = f"{HEADER}\nMIIBOg\n{HEADER}\nAAAA\n{FOOTER}\n"
    findings = scan_text(text)
    assert len(findings) == 2
    assert text[findings[0].start : findings[0].end] == f"{HEADER}\nMIIBOg"
    assert text[findings[1].start : findings[1].end] == f"{HEADER}\nAAAA\n{FOOTER}"


# ---------------------------------------------------------------------------
# B9: the pandoc subprocess is sandboxed, bounded, and never handed a path
# ---------------------------------------------------------------------------


def test_pandoc_runs_sandboxed_over_stdin_with_a_timeout_and_no_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The threat model claimed these four controls since 4.1 and no test held them."""
    captured: dict[str, Any] = {}

    def fake_run(argv: list[str], **kwargs: Any) -> Any:
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        raise subprocess.TimeoutExpired(argv, kwargs.get("timeout", 0))

    monkeypatch.setattr(subprocess, "run", fake_run)
    parser = PandocParser(executable="pandoc", version="3.6", timeout_s=7.0)
    blob = Blob.of(b"<p>hostile</p>", media_type=HTML, source_uri="hostile.html")
    with pytest.raises(ParseError, match="did not finish within 7s"):
        parser.parse(blob, doc_id=DOC_ID)
    argv = captured["argv"]
    assert argv[0] == "pandoc" and "--sandbox" in argv
    assert isinstance(argv, list), "a fixed argument vector, never a shell string"
    assert "hostile.html" not in " ".join(argv), "the bytes travel over stdin; no path is passed"
    assert captured["kwargs"]["input"] == b"<p>hostile</p>"
    assert captured["kwargs"]["timeout"] == 7.0
    assert not captured["kwargs"].get("shell")
