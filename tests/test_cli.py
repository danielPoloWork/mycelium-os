# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""CLI skeleton (roadmap 2.8): the conventions in spec 05 §1 hold — exit codes 0/1/2,
`--json` on every read command with nothing else on stdout, NO_COLOR honoured, and no
prompt anywhere that a CI run could block on."""

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

import mycelium.cli.app  # noqa: F401 - imported so `sys.modules` has the module below
from mycelium.__about__ import __version__
from mycelium.build import build as run_build
from mycelium.build.lock import BuildLock
from mycelium.cli import app
from mycelium.cli.doctor import diagnose, worst_status
from mycelium.cli.output import ExitCode, use_color
from mycelium.sdk.types import ProvenanceOrigin, TrustClass, VerificationStatus
from mycelium.store import SqliteStore
from mycelium.store.schema import META_CURRENT_SNAPSHOT, META_SCHEMA_VERSION

runner = CliRunner()

cli_app = sys.modules["mycelium.cli.app"]
"""The command *module*, not the Typer object `mycelium.cli` re-exports under the
same name. Tests that replace a collaborator have to patch the module."""

DOC = """# Retry Policy

Failed deliveries retry with exponential backoff. See [[api]].

## Limits

At most five attempts.
"""


def seeded(tmp_path: Path, name: str = "knowledge/verified/retries.md", text: str = DOC) -> Path:
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return tmp_path


def invoke(*args: str, env: dict[str, str] | None = None):  # type: ignore[no-untyped-def]
    return runner.invoke(app, list(args), env=env)


# ---------------------------------------------------------------------------
# Conventions (spec 05 §1)
# ---------------------------------------------------------------------------


def test_version_and_help_exit_zero() -> None:
    version = invoke("--version")
    assert version.exit_code == ExitCode.OK
    assert __version__ in version.stdout
    assert invoke("--help").exit_code == ExitCode.OK


def test_no_arguments_shows_help_without_hanging() -> None:
    result = invoke()
    assert result.exit_code != ExitCode.OK
    assert "Usage" in result.stdout


def test_unknown_command_and_bad_option_are_usage_errors() -> None:
    assert invoke("frobnicate").exit_code == ExitCode.USAGE
    assert invoke("search", "q", "--nonsense").exit_code == ExitCode.USAGE


def test_search_without_a_store_fails_with_guidance(tmp_path: Path) -> None:
    result = invoke("search", "anything", "--path", str(tmp_path))
    assert result.exit_code == ExitCode.FAILED
    assert "mycelium build" in result.stderr
    assert result.stdout == ""  # the failure is commentary, not an answer


@pytest.mark.parametrize("command", [("init",), ("build",), ("doctor",)])
def test_json_stdout_is_exactly_one_document(tmp_path: Path, command: tuple[str, ...]) -> None:
    seeded(tmp_path)
    result = invoke(*command, str(tmp_path), "--json")
    assert result.exit_code == ExitCode.OK
    json.loads(result.stdout)  # parses whole: no progress lines, no prose


def test_no_color_disables_styling(tmp_path: Path) -> None:
    seeded(tmp_path)
    coloured = invoke("build", str(tmp_path), env={"NO_COLOR": "1"})
    assert coloured.exit_code == ExitCode.OK
    assert "\x1b[" not in coloured.stdout


def test_use_color_respects_no_color_and_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "")
    assert use_color() is False  # any value counts, including empty
    monkeypatch.delenv("NO_COLOR", raising=False)

    class Tty:
        @staticmethod
        def isatty() -> bool:
            return True

    class Pipe:
        @staticmethod
        def isatty() -> bool:
            return False

    assert use_color(Tty()) is True
    assert use_color(Pipe()) is False


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


def test_init_scaffolds_and_is_idempotent(tmp_path: Path) -> None:
    first = invoke("init", str(tmp_path), "--json")
    assert first.exit_code == ExitCode.OK
    created = json.loads(first.stdout)["created"]
    assert "mycelium.toml" in created
    assert ".gitignore" in created

    for lane in ("verified", "candidate", "evidence"):
        assert (tmp_path / "knowledge" / lane / ".gitkeep").exists()
    assert ".mycelium/" in (tmp_path / ".gitignore").read_text(encoding="utf-8")

    second = invoke("init", str(tmp_path), "--json")
    assert json.loads(second.stdout)["created"] == []


def test_init_appends_to_an_existing_gitignore_without_clobbering(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
    invoke("init", str(tmp_path))
    text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "*.pyc" in text
    assert ".mycelium/" in text
    assert "export/" in text  # D-006: bundles are regenerable, not committed by default
    invoke("init", str(tmp_path))
    again = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert again == text
    assert again.count(".mycelium/") == 1
    assert again.count("export/") == 1


def test_init_adds_an_entry_a_repository_predates(tmp_path: Path) -> None:
    """Idempotent per entry, not all-or-nothing: a repository initialised before
    `export/` existed must gain it rather than be judged already complete."""
    (tmp_path / ".gitignore").write_text(".mycelium/\n", encoding="utf-8")

    invoke("init", str(tmp_path))

    text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert text.count(".mycelium/") == 1
    assert "export/" in text


def test_init_does_not_overwrite_an_edited_config(tmp_path: Path) -> None:
    invoke("init", str(tmp_path))
    config = tmp_path / "mycelium.toml"
    config.write_text('[project]\nname = "edited"\n', encoding="utf-8")
    invoke("init", str(tmp_path))
    assert config.read_text(encoding="utf-8") == '[project]\nname = "edited"\n'


def test_init_then_build_is_the_documented_first_run(tmp_path: Path) -> None:
    invoke("init", str(tmp_path))
    (tmp_path / "knowledge" / "verified" / "doc.md").write_text(DOC, encoding="utf-8")
    result = invoke("build", str(tmp_path), "--json")
    assert result.exit_code == ExitCode.OK
    assert json.loads(result.stdout)["counts"]["documents"] == 1


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------


def test_build_reports_pinned_files_to_commit(tmp_path: Path) -> None:
    seeded(tmp_path)
    result = invoke("build", str(tmp_path))
    assert result.exit_code == ExitCode.OK
    assert "commit them" in result.stdout
    assert "knowledge/verified/retries.md" in result.stdout

    payload = json.loads(invoke("build", str(tmp_path), "--json").stdout)
    assert payload["pinned"] == []  # already pinned; a second build touches nothing


def test_build_surfaces_quarantine_warnings_on_stderr(tmp_path: Path) -> None:
    seeded(tmp_path)
    (tmp_path / "knowledge" / "broken.md").write_text(
        '---\ntitle: "unterminated\n---\nbody\n', encoding="utf-8"
    )
    result = invoke("build", str(tmp_path))
    assert result.exit_code == ExitCode.OK  # a quarantined document is not a failed build
    assert "1 quarantined" in result.stdout
    assert "warning:" in result.stderr


def test_build_refuses_while_another_writer_holds_the_lock(tmp_path: Path) -> None:
    seeded(tmp_path)
    with BuildLock.acquire(tmp_path / ".mycelium"):
        result = invoke("build", str(tmp_path))
    assert result.exit_code == ExitCode.FAILED
    assert "another build is running" in result.stderr


# ---------------------------------------------------------------------------
# snapshots / rollback / gc (roadmap 3.2)
# ---------------------------------------------------------------------------


def test_snapshots_lists_and_marks_the_served_one(tmp_path: Path) -> None:
    seeded(tmp_path)
    first = run_build(tmp_path).manifest
    (tmp_path / "knowledge" / "extra.md").write_text("# Extra\n\nMore.\n", encoding="utf-8")
    second = run_build(tmp_path).manifest

    result = invoke("snapshots", str(tmp_path))
    assert result.exit_code == ExitCode.OK
    assert f"* {second.snapshot_id}" in result.stdout
    assert f"  {first.snapshot_id}" in result.stdout

    payload = json.loads(invoke("snapshots", str(tmp_path), "--json").stdout)
    assert payload["current"] == second.snapshot_id
    assert [item["snapshot_id"] for item in payload["snapshots"]] == [
        second.snapshot_id,
        first.snapshot_id,
    ]


def test_snapshots_on_a_fresh_repository_says_so(tmp_path: Path) -> None:
    result = invoke("snapshots", str(tmp_path))
    assert result.exit_code == ExitCode.OK
    assert "mycelium build" in result.stdout


def test_rollback_restores_and_reports(tmp_path: Path) -> None:
    seeded(tmp_path)
    first = run_build(tmp_path).manifest
    (tmp_path / "knowledge" / "extra.md").write_text("# Extra\n\nMore.\n", encoding="utf-8")
    run_build(tmp_path)

    result = invoke("rollback", first.snapshot_id, "--path", str(tmp_path))
    assert result.exit_code == ExitCode.OK
    assert first.snapshot_id in result.stdout
    payload = json.loads(
        invoke("rollback", first.snapshot_id, "--path", str(tmp_path), "--json").stdout
    )
    assert payload["snapshot_id"] == first.snapshot_id


def test_rollback_of_an_unknown_snapshot_fails_with_guidance(tmp_path: Path) -> None:
    seeded(tmp_path)
    run_build(tmp_path)
    result = invoke("rollback", "01ARZ3NDEKTSV4RRFFQ69G5FZZ", "--path", str(tmp_path))
    assert result.exit_code == ExitCode.FAILED
    assert "mycelium snapshots" in result.stderr
    assert result.stdout == ""


def test_gc_dry_run_reports_and_changes_nothing(tmp_path: Path) -> None:
    seeded(tmp_path)
    for index in range(3):
        (tmp_path / "knowledge" / "extra.md").write_text(f"# Extra {index}\n", encoding="utf-8")
        run_build(tmp_path)

    dry = json.loads(
        invoke(
            "gc", str(tmp_path), "--keep", "1", "--cache-max-age", "0", "--dry-run", "--json"
        ).stdout
    )
    assert dry["dry_run"] is True
    assert dry["removed_blobs"] > 0

    applied = invoke("gc", str(tmp_path), "--keep", "1", "--cache-max-age", "0")
    assert applied.exit_code == ExitCode.OK
    assert "removed" in applied.stdout


def test_gc_rejects_negative_retention_as_usage(tmp_path: Path) -> None:
    seeded(tmp_path)
    run_build(tmp_path)
    # Typer's own `min=0` catches it before the library does; either way the
    # contract is exit 2, because nothing was attempted.
    assert invoke("gc", str(tmp_path), "--keep", "-1").exit_code == ExitCode.USAGE


# ---------------------------------------------------------------------------
# neighbors (roadmap 3.4)
# ---------------------------------------------------------------------------


def test_neighbors_shows_both_directions_with_provenance(tmp_path: Path) -> None:
    seeded(tmp_path, "knowledge/verified/retries.md", DOC + "\nSee [[api]].\n")
    seeded(tmp_path, "knowledge/verified/api.md", "# API\n\nEndpoints.\n")
    run_build(tmp_path)

    outgoing = invoke("neighbors", "knowledge/verified/retries.md", "--path", str(tmp_path))
    assert outgoing.exit_code == ExitCode.OK
    assert "-> doc:knowledge/verified/api.md" in outgoing.stdout
    assert "links_to, authored" in outgoing.stdout
    assert "via wikilink" in outgoing.stdout

    incoming = invoke("neighbors", "knowledge/verified/api.md", "--path", str(tmp_path))
    assert "<- doc:knowledge/verified/retries.md" in incoming.stdout

    payload = json.loads(
        invoke("neighbors", "knowledge/verified/api.md", "--path", str(tmp_path), "--json").stdout
    )
    assert payload["origin"] == "doc:knowledge/verified/api.md"
    assert payload["neighbors"][0]["direction"] == "in"


def test_neighbors_of_a_document_with_no_links_says_so(tmp_path: Path) -> None:
    seeded(tmp_path)
    run_build(tmp_path)
    result = invoke("neighbors", "knowledge/verified/retries.md", "--path", str(tmp_path))
    assert result.exit_code == ExitCode.OK
    assert "No neighbors" in result.stdout


def test_neighbors_of_an_unknown_document_fails_with_guidance(tmp_path: Path) -> None:
    seeded(tmp_path)
    run_build(tmp_path)
    result = invoke("neighbors", "knowledge/nowhere.md", "--path", str(tmp_path))
    assert result.exit_code == ExitCode.FAILED
    assert "no document at" in result.stderr
    assert result.stdout == ""


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


def test_search_returns_ranked_hits_with_citation_uris(tmp_path: Path) -> None:
    seeded(tmp_path)
    run_build(tmp_path)
    result = invoke("search", "exponential backoff", "--path", str(tmp_path), "--json")
    assert result.exit_code == ExitCode.OK
    payload = json.loads(result.stdout)
    assert payload["snapshot_id"]
    (hit,) = payload["results"]
    assert hit["uri"].startswith("mycelium://")
    assert "?lines=" in hit["uri"]
    assert hit["path"] == "knowledge/verified/retries.md"
    assert hit["trust_class"] == "authored"
    assert hit["verification_status"] == "verified"


def test_search_honours_limit_and_filters(tmp_path: Path) -> None:
    seeded(tmp_path)
    run_build(tmp_path)
    assert (
        len(
            json.loads(
                invoke("search", "retry", "--path", str(tmp_path), "-k", "1", "--json").stdout
            )["results"]
        )
        <= 1
    )

    filtered = invoke("search", "retry", "--path", str(tmp_path), "--trust", "external", "--json")
    assert json.loads(filtered.stdout)["results"] == []


def test_search_with_no_hits_is_success_not_failure(tmp_path: Path) -> None:
    seeded(tmp_path)
    run_build(tmp_path)
    result = invoke("search", "nonexistentterm", "--path", str(tmp_path))
    assert result.exit_code == ExitCode.OK
    assert "No results" in result.stdout


def test_search_query_syntax_is_data(tmp_path: Path) -> None:
    seeded(tmp_path)
    run_build(tmp_path)
    result = invoke("search", '"; DROP TABLE chunks; --', "--path", str(tmp_path))
    assert result.exit_code == ExitCode.OK
    with SqliteStore.open(tmp_path, read_only=True) as store:
        assert store.counts()["chunks"] > 0


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------


def first_hit_uri(root: Path) -> str:
    payload = json.loads(invoke("search", "retry", "--path", str(root), "--json").stdout)
    return str(payload["results"][0]["uri"])


def test_show_resolves_a_citation_uri_with_provenance(tmp_path: Path) -> None:
    seeded(tmp_path)
    run_build(tmp_path)
    result = invoke("show", first_hit_uri(tmp_path), "--path", str(tmp_path), "--json")
    assert result.exit_code == ExitCode.OK
    payload = json.loads(result.stdout)
    assert payload["path"] == "knowledge/verified/retries.md"
    assert payload["verification_status"] == "verified"
    assert payload["provenance"]["origin"] == "authored"
    assert len(payload["chunks"]) == 1


def test_show_resolves_a_bare_anchor_and_widening_contexts(tmp_path: Path) -> None:
    seeded(tmp_path)
    run_build(tmp_path)
    with SqliteStore.open(tmp_path, read_only=True) as store:
        document = store.get_document_by_path("knowledge/verified/retries.md")
        assert document is not None
        anchors = [chunk.anchor for chunk in store.chunks_of(document.doc_id)]

    chunk_view = json.loads(invoke("show", anchors[0], "--path", str(tmp_path), "--json").stdout)
    document_view = json.loads(
        invoke(
            "show", anchors[0], "--path", str(tmp_path), "--context", "document", "--json"
        ).stdout
    )
    assert len(chunk_view["chunks"]) == 1
    assert len(document_view["chunks"]) == len(anchors)


def test_show_survives_a_folder_move_because_uris_key_on_doc_id(tmp_path: Path) -> None:
    """D-021: promotion moves the file; the citation keeps resolving."""
    seeded(tmp_path, name="knowledge/candidate/draft.md")
    run_build(tmp_path)
    uri = first_hit_uri(tmp_path)

    moved = tmp_path / "knowledge" / "verified" / "draft.md"
    moved.parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "knowledge" / "candidate" / "draft.md").rename(moved)
    run_build(tmp_path)

    result = invoke("show", uri, "--path", str(tmp_path), "--json")
    assert result.exit_code == ExitCode.OK
    assert json.loads(result.stdout)["path"] == "knowledge/verified/draft.md"


def test_show_rejects_nonsense_targets_as_usage_errors(tmp_path: Path) -> None:
    seeded(tmp_path)
    run_build(tmp_path)
    assert invoke("show", "not-a-target", "--path", str(tmp_path)).exit_code == ExitCode.USAGE
    assert (
        invoke("show", "a.md#x/0", "--path", str(tmp_path), "--context", "galaxy").exit_code
        == ExitCode.USAGE
    )


def test_show_explains_a_dead_anchor_and_names_survivors(tmp_path: Path) -> None:
    seeded(tmp_path)
    run_build(tmp_path)
    result = invoke("show", "knowledge/verified/retries.md#gone/0", "--path", str(tmp_path))
    assert result.exit_code == ExitCode.FAILED
    assert "is gone" in result.stderr
    assert "#limits/0" in result.stderr  # the survivors are listed


def test_show_reports_an_unknown_document(tmp_path: Path) -> None:
    seeded(tmp_path)
    run_build(tmp_path)
    result = invoke("show", "knowledge/verified/absent.md#x/0", "--path", str(tmp_path))
    assert result.exit_code == ExitCode.FAILED
    assert "no document" in result.stderr


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# `mycelium ingest` (roadmap 4.3)
# ---------------------------------------------------------------------------

INGEST_FIXTURES = Path(__file__).parent / "fixtures" / "ingest"
INGEST_CONFIG = '[ingest]\nparsers = ["markdown", "docling", "pdf"]\n'


def _ingestable(tmp_path: Path, name: str, *, subdir: str = "") -> Path:
    """Copy a fixture into the repository, because acquisition is root-bounded."""
    sources = tmp_path / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    origin = INGEST_FIXTURES / subdir / name if subdir else INGEST_FIXTURES / name
    target = sources / name
    target.write_bytes(origin.read_bytes())
    (tmp_path / "mycelium.toml").write_text(INGEST_CONFIG, encoding="utf-8")
    return target


def test_ingest_projects_a_source_and_reports_its_fidelity(tmp_path: Path) -> None:
    seeded(tmp_path)
    source = _ingestable(tmp_path, "source.docx")

    result = invoke("ingest", str(source), "--root", str(tmp_path), "--json")
    assert result.exit_code == ExitCode.OK
    (entry,) = json.loads(result.stdout)["sources"]
    assert entry["ok"] is True
    assert entry["parser"] == "docling"
    assert entry["lost"] == 0
    assert entry["written"] is True

    projected = tmp_path / entry["document"]
    assert projected.is_file()
    assert projected.parent.name == "evidence"
    assert "origin: ingested" in projected.read_text(encoding="utf-8")


def test_ingest_dry_run_takes_custody_but_writes_no_document(tmp_path: Path) -> None:
    seeded(tmp_path)
    source = _ingestable(tmp_path, "source.docx")

    result = invoke("ingest", str(source), "--root", str(tmp_path), "--dry-run", "--json")
    assert result.exit_code == ExitCode.OK
    (entry,) = json.loads(result.stdout)["sources"]
    assert entry["written"] is False
    assert not (tmp_path / entry["document"]).exists()
    # The evidence is kept anyway: custody is not conditional on projection.
    assert (tmp_path / ".mycelium" / "cas" / "originals").is_dir()


def test_ingest_reports_a_failure_per_source_and_carries_on(tmp_path: Path) -> None:
    seeded(tmp_path)
    good = _ingestable(tmp_path, "source.docx")
    hostile = _ingestable(tmp_path, "no-text-layer.pdf", subdir="hostile")

    result = invoke("ingest", str(hostile), str(good), "--root", str(tmp_path), "--json")
    # Exit 1 because something failed, and a script needs to know without parsing.
    assert result.exit_code == ExitCode.FAILED
    entries = {Path(item["source"]).name: item for item in json.loads(result.stdout)["sources"]}
    assert entries["no-text-layer.pdf"]["ok"] is False
    assert "did not survive parsing" in entries["no-text-layer.pdf"]["error"]
    assert entries["source.docx"]["ok"] is True, "the good source was still ingested"


def test_ingest_refuses_a_source_outside_the_repository(tmp_path: Path) -> None:
    seeded(tmp_path)
    (tmp_path / "mycelium.toml").write_text(INGEST_CONFIG, encoding="utf-8")
    outside = tmp_path.parent / f"outside-{tmp_path.name}.md"
    outside.write_text("# nope\n", encoding="utf-8")
    try:
        result = invoke("ingest", str(outside), "--root", str(tmp_path), "--json")
        assert result.exit_code == ExitCode.FAILED
        (entry,) = json.loads(result.stdout)["sources"]
        assert "outside the declared root" in entry["error"]
    finally:
        outside.unlink(missing_ok=True)


def test_a_projected_document_compiles_as_ingested_evidence(tmp_path: Path) -> None:
    """The point of the whole lane (spec 02 §5, ADR-0034).

    The projector writes Markdown only; the compiler does everything else. So an
    ingested PDF has to arrive in the store as a document with `ingested` trust,
    `evidence` status, and the provenance the custody record holds — none of which
    the projection itself writes.
    """
    seeded(tmp_path)
    source = _ingestable(tmp_path, "text-layer.pdf")
    ingested = invoke("ingest", str(source), "--root", str(tmp_path), "--json")
    assert ingested.exit_code == ExitCode.OK
    (entry,) = json.loads(ingested.stdout)["sources"]

    assert invoke("build", str(tmp_path)).exit_code == ExitCode.OK
    with SqliteStore.open(tmp_path, read_only=True) as store:
        document = store.get_document_by_path(str(entry["document"]).replace("\\", "/"))
    assert document is not None
    assert document.trust_class is TrustClass.INGESTED
    assert document.verification_status is VerificationStatus.EVIDENCE
    assert document.provenance.origin is ProvenanceOrigin.INGESTED
    assert document.provenance.source_digest == entry["source_digest"]
    # Filled from tier-1 custody, not from frontmatter: one key carries the link
    # and the record carries the facts (ADR-0034).
    assert document.provenance.connector == "file"
    assert document.provenance.ingested_at is not None
    assert document.fidelity_report == entry["fidelity_report"]


def test_doctor_is_clean_after_a_build(tmp_path: Path) -> None:
    seeded(tmp_path)
    run_build(tmp_path)
    result = invoke("doctor", str(tmp_path), "--json")
    assert result.exit_code == ExitCode.OK
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert {check["name"] for check in payload["checks"]} == {
        "toolchain",
        "config",
        "parsers",
        "custody",
        "store",
        "snapshot",
        "manifest",
        "pointer",
        "lock",
    }


def test_doctor_fails_when_a_pinned_parser_is_not_installed(tmp_path: Path) -> None:
    """The point of the check (roadmap 4.1).

    Resolution refuses an unavailable plugin rather than falling through to the
    next one, so without this an operator meets that refusal in the middle of a
    build. `doctor` asks the same question first, and prints the remedy.
    """
    seeded(tmp_path)
    (tmp_path / "mycelium.toml").write_text(
        '[ingest]\nparsers = ["markdown", "nonexistent-parser"]\n', encoding="utf-8"
    )
    result = invoke("doctor", str(tmp_path), "--json")
    payload = json.loads(result.stdout)
    parsers = next(check for check in payload["checks"] if check["name"] == "parsers")
    assert parsers["status"] == "fail"
    assert "nonexistent-parser" in parsers["detail"]


def test_doctor_lists_the_pinned_parsers_when_they_all_resolve(tmp_path: Path) -> None:
    seeded(tmp_path)
    result = invoke("doctor", str(tmp_path), "--json")
    payload = json.loads(result.stdout)
    parsers = next(check for check in payload["checks"] if check["name"] == "parsers")
    assert parsers["status"] == "ok"
    assert "markdown" in parsers["detail"]


def test_doctor_reports_tier_one_evidence_that_went_bad(tmp_path: Path) -> None:
    """Custody does not heal itself, and that is the point (ADR-0033).

    The build cache discards a blob that fails its own digest, because losing it
    costs a recompile. A corrupt original is the loss of the only copy of
    something a citation quotes, so it is reported and left where it is.
    """
    from mycelium.ingest import Custody
    from mycelium.sdk.types import CustodyKind

    seeded(tmp_path)
    custody = Custody(tmp_path / ".mycelium")
    record = custody.put(b"acquired bytes", kind=CustodyKind.ORIGINAL, media_type="text/plain")
    custody.blob_path(record.digest).write_bytes(b"tampered with")

    result = invoke("doctor", str(tmp_path), "--json")
    payload = json.loads(result.stdout)
    check = next(item for item in payload["checks"] if item["name"] == "custody")
    assert check["status"] == "fail"
    assert "no longer match their own digest" in check["detail"]
    assert custody.blob_path(record.digest).is_file(), "reported, not tidied away"


def test_doctor_warns_but_succeeds_on_a_fresh_repository(tmp_path: Path) -> None:
    result = invoke("doctor", str(tmp_path), "--json")
    assert result.exit_code == ExitCode.OK
    payload = json.loads(result.stdout)
    assert payload["status"] == "warn"
    assert any("mycelium build" in check["detail"] for check in payload["checks"])


def test_doctor_detects_the_commit_to_swap_window(tmp_path: Path) -> None:
    """The window ADR-0009 documents: the store committed, the swap did not happen."""
    seeded(tmp_path)
    run_build(tmp_path)
    with SqliteStore.open(tmp_path) as store, store.transaction():
        store.set_meta(META_CURRENT_SNAPSHOT, "01J1ZF8Q4R6XKQ3F0V9T8B2M7N")

    checks = diagnose(tmp_path)
    pointer = next(check for check in checks if check.name == "pointer")
    assert pointer.status == "fail"
    assert "interrupted between commit and publish" in pointer.detail
    assert worst_status(checks) == "fail"
    assert invoke("doctor", str(tmp_path)).exit_code == ExitCode.FAILED


def test_doctor_fails_on_a_missing_manifest(tmp_path: Path) -> None:
    seeded(tmp_path)
    result = run_build(tmp_path)
    result.manifest_path.unlink()
    checks = diagnose(tmp_path)
    manifest = next(check for check in checks if check.name == "manifest")
    assert manifest.status == "fail"
    assert invoke("doctor", str(tmp_path)).exit_code == ExitCode.FAILED


def test_doctor_reports_an_unreadable_store(tmp_path: Path) -> None:
    seeded(tmp_path)
    run_build(tmp_path)
    with SqliteStore.open(tmp_path) as store, store.transaction():
        store.set_meta(META_SCHEMA_VERSION, "mycelium/store/v99")
    checks = diagnose(tmp_path)
    store_check = next(check for check in checks if check.name == "store")
    assert store_check.status == "fail"
    assert "mycelium build" in store_check.detail


def test_doctor_reports_lock_state(tmp_path: Path) -> None:
    seeded(tmp_path)
    run_build(tmp_path)
    with BuildLock.acquire(tmp_path / ".mycelium"):
        live = next(check for check in diagnose(tmp_path) if check.name == "lock")
        assert live.status == "warn"
        assert f"pid {os.getpid()}" in live.detail

        ancient = datetime.now(tz=UTC).timestamp() - 3600
        os.utime(tmp_path / ".mycelium" / "lock", (ancient, ancient))
        stale = next(check for check in diagnose(tmp_path) if check.name == "lock")
        assert stale.status == "warn"
        assert "stale lock" in stale.detail


# ---------------------------------------------------------------------------
# export (roadmap 3.6)
# ---------------------------------------------------------------------------


def test_export_writes_a_bundle_and_reports_it(tmp_path: Path) -> None:
    seeded(tmp_path)
    run_build(tmp_path)

    result = invoke("export", str(tmp_path))
    assert result.exit_code == ExitCode.OK

    payload = json.loads(invoke("export", str(tmp_path), "--json").stdout)
    bundle = Path(str(payload["bundle"]))
    assert bundle.is_dir()
    assert bundle.parent == tmp_path / "export"
    assert bundle.name == payload["snapshot_id"]
    assert payload["records"]["documents"] == 1
    assert payload["markdown_files"] == 0


def test_export_honours_an_explicit_out_directory(tmp_path: Path) -> None:
    seeded(tmp_path)
    run_build(tmp_path)
    elsewhere = tmp_path / "bundles"

    payload = json.loads(invoke("export", str(tmp_path), "--out", str(elsewhere), "--json").stdout)

    assert Path(str(payload["bundle"])).parent == elsewhere


def test_export_with_markdown_reports_the_copies(tmp_path: Path) -> None:
    seeded(tmp_path)
    run_build(tmp_path)

    payload = json.loads(invoke("export", str(tmp_path), "--with-markdown", "--json").stdout)

    assert payload["markdown_files"] == 1
    copied = Path(str(payload["bundle"])) / "markdown" / "knowledge/verified/retries.md"
    assert copied.is_file()


def test_export_before_a_build_fails_with_guidance(tmp_path: Path) -> None:
    result = invoke("export", str(tmp_path))
    assert result.exit_code == ExitCode.FAILED
    assert "mycelium build" in result.stderr
    assert result.stdout == ""  # a failure is commentary, not an answer


# ---------------------------------------------------------------------------
# The synthesis lane, through the command (roadmap 4.4)
# ---------------------------------------------------------------------------


SYNTHESIZED = """\
# Retry Behaviour

Webhook deliveries are retried up to five times [[retry-policy-md-{digest}#Retry Policy]].
"""


def _evidence_source(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    source = root / "retry-policy.md"
    source.write_text(
        "# Retry Policy\n\nWebhook deliveries are retried five times.\n",
        encoding="utf-8",
        newline="\n",
    )
    return source


def test_ingest_writes_a_candidate_when_a_provider_is_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fakes import ScriptedProvider
    from mycelium.synthesis import WikiSynthesizer

    source = _evidence_source(tmp_path / "sources")
    (tmp_path / "mycelium.toml").write_text(
        '[synthesis]\nprovider = "anthropic"\n', encoding="utf-8"
    )

    # The evidence document's name carries the source digest (ADR-0034), so the
    # citation the scripted model writes has to be built from the real one.
    from mycelium.ingest.projection import evidence_path
    from mycelium.sdk.identity import digest_bytes

    stem = evidence_path(source.as_uri(), digest=digest_bytes(source.read_bytes())).stem
    answer = f"# Retry Behaviour\n\nDeliveries are retried five times [[{stem}#Retry Policy]].\n"

    monkeypatch.setattr(
        cli_app, "build_synthesizer", lambda settings: WikiSynthesizer(ScriptedProvider(answer))
    )
    result = invoke("ingest", str(source), "--root", str(tmp_path), "--json")
    assert result.exit_code == ExitCode.OK
    payload = json.loads(result.stdout)
    synthesis = payload["sources"][0]["synthesis"]
    assert synthesis["ok"] is True
    assert synthesis["coverage"] == 1.0
    assert synthesis["provider"] == "scripted"
    assert (tmp_path / synthesis["document"]).exists()


def test_no_synthesize_skips_the_lane_without_touching_the_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _evidence_source(tmp_path / "sources")
    (tmp_path / "mycelium.toml").write_text(
        '[synthesis]\nprovider = "anthropic"\n', encoding="utf-8"
    )

    def refuse(settings: object) -> object:
        raise AssertionError("the synthesizer must not be built")

    monkeypatch.setattr(cli_app, "build_synthesizer", refuse)
    result = invoke("ingest", str(source), "--root", str(tmp_path), "--json", "--no-synthesize")
    assert result.exit_code == ExitCode.OK
    payload = json.loads(result.stdout)
    assert "synthesis" not in payload["sources"][0]
    assert payload["sources"][0]["ok"] is True


def test_an_unavailable_provider_warns_and_the_evidence_lane_still_delivers(
    tmp_path: Path,
) -> None:
    """D-020's asymmetry, enforced: synthesis is the *additional* lane."""
    source = _evidence_source(tmp_path / "sources")
    (tmp_path / "mycelium.toml").write_text('[synthesis]\nprovider = "nowhere"\n', encoding="utf-8")
    result = invoke("ingest", str(source), "--root", str(tmp_path))
    assert result.exit_code == ExitCode.OK
    assert "synthesis lane off" in result.stderr
    assert (tmp_path / "knowledge" / "evidence").exists()


def test_doctor_reports_the_lane_only_once_it_is_configured(tmp_path: Path) -> None:
    seeded(tmp_path)
    names = {
        check["name"]
        for check in json.loads(invoke("doctor", str(tmp_path), "--json").stdout)["checks"]
    }
    assert "synthesis" not in names, "off by default is the posture, not a finding"

    (tmp_path / "mycelium.toml").write_text('[synthesis]\nprovider = "nowhere"\n', encoding="utf-8")
    payload = json.loads(invoke("doctor", str(tmp_path), "--json").stdout)
    check = next(item for item in payload["checks"] if item["name"] == "synthesis")
    assert check["status"] == "warn"
    assert "nowhere" in check["detail"]


# ---------------------------------------------------------------------------
# verify / promote / demote (roadmap 4.5, gate G7)
# ---------------------------------------------------------------------------

_VERIFY_EVIDENCE = """\
---
title: Retry Policy
origin: ingested
source: https://docs.example.com/retries
source_trust: high
---

# Retry Policy

## Backoff

Deliveries are retried five times, and backoff doubles after every failed attempt.
"""

_VERIFY_CANDIDATE = """\
---
title: Webhook Retries
origin: synthesized
generated_by: scripted/scripted-1
---

# Webhook Retries

Deliveries are retried up to five times before the system gives up ([[retry-policy#Backoff]]).
"""


def _verifiable(tmp_path: Path, *, candidate: str = _VERIFY_CANDIDATE) -> Path:
    knowledge = tmp_path / "knowledge"
    (knowledge / "evidence").mkdir(parents=True, exist_ok=True)
    (knowledge / "candidate").mkdir(parents=True, exist_ok=True)
    (knowledge / "evidence" / "retry-policy.md").write_text(
        _VERIFY_EVIDENCE, encoding="utf-8", newline=""
    )
    (knowledge / "candidate" / "webhook-retries.md").write_text(
        candidate, encoding="utf-8", newline=""
    )
    return tmp_path


def _with_judge(monkeypatch: pytest.MonkeyPatch, *, entailed: bool = True) -> None:
    """Point the CLI at a judge that answers without a network."""

    class Judge:
        identity = "scripted/judge-1"

        def judge(self, claim: str, evidence: str) -> tuple[bool, str]:
            return entailed, "the test decided"

    monkeypatch.setattr(cli_app, "build_judge", lambda *_: (Judge(), False, ""))


def test_verify_reports_coverage_and_says_entailment_was_not_measured(tmp_path: Path) -> None:
    _verifiable(tmp_path)
    result = invoke("verify", "--root", str(tmp_path), "--json")
    assert result.exit_code == ExitCode.OK
    payload = json.loads(result.stdout)
    document = payload["documents"][0]
    assert document["coverage"] == 1.0
    assert document["entailment"] is None, "not measured is not zero"
    assert document["blockers"][0]["code"] == "entailment-not-measured"
    assert payload["thresholds"] == {"coverage": 0.95, "entailment": 0.9}


def test_verify_gate_passes_offline_on_measured_coverage(tmp_path: Path) -> None:
    # A gate that were red on every offline checkout is a gate everyone ignores.
    _verifiable(tmp_path)
    assert invoke("verify", "--root", str(tmp_path), "--gate").exit_code == ExitCode.OK


def test_verify_gate_fails_on_a_measured_shortfall(tmp_path: Path) -> None:
    broken = _VERIFY_CANDIDATE.replace("([[retry-policy#Backoff]])", "")
    _verifiable(tmp_path, candidate=broken)
    result = invoke("verify", "--root", str(tmp_path), "--gate")
    assert result.exit_code == ExitCode.FAILED
    assert "gate G7" in result.stderr


def test_verify_writes_the_score_into_the_document(tmp_path: Path) -> None:
    from mycelium.markdown.frontmatter import parse_frontmatter

    _verifiable(tmp_path)
    invoke("verify", "--root", str(tmp_path))
    text = (tmp_path / "knowledge/candidate/webhook-retries.md").read_text(encoding="utf-8")
    assert parse_frontmatter(text).frontmatter.grounding == 1.0


def test_verify_dry_run_writes_nothing(tmp_path: Path) -> None:
    _verifiable(tmp_path)
    before = (tmp_path / "knowledge/candidate/webhook-retries.md").read_text(encoding="utf-8")
    invoke("verify", "--root", str(tmp_path), "--dry-run")
    after = (tmp_path / "knowledge/candidate/webhook-retries.md").read_text(encoding="utf-8")
    assert after == before


def test_verify_measures_entailment_when_a_judge_is_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _verifiable(tmp_path)
    _with_judge(monkeypatch)
    payload = json.loads(invoke("verify", "--root", str(tmp_path), "--json").stdout)
    document = payload["documents"][0]
    assert document["entailment"] == 1.0
    assert document["judge"] == "scripted/judge-1"
    assert document["passes"] is True


def test_no_entailment_skips_the_judge_entirely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _verifiable(tmp_path)

    def refuse(*_: object) -> object:
        raise AssertionError("no judge must be built")

    monkeypatch.setattr(cli_app, "build_judge", refuse)
    result = invoke("verify", "--root", str(tmp_path), "--no-entailment", "--json")
    assert result.exit_code == ExitCode.OK
    assert json.loads(result.stdout)["documents"][0]["entailment"] is None


def test_verify_says_when_a_document_has_nothing_to_verify(tmp_path: Path) -> None:
    seeded(tmp_path)
    result = invoke("verify", "--root", str(tmp_path))
    assert result.exit_code == ExitCode.OK
    assert "no synthesized documents" in result.stdout


def test_promote_refuses_below_the_gate_and_points_at_force(tmp_path: Path) -> None:
    _verifiable(tmp_path)
    result = invoke("promote", "knowledge/candidate/webhook-retries.md", "--root", str(tmp_path))
    assert result.exit_code == ExitCode.FAILED
    assert "--force" in result.stderr
    assert (tmp_path / "knowledge/candidate/webhook-retries.md").is_file()


def test_promote_moves_the_document_when_the_gate_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _verifiable(tmp_path)
    _with_judge(monkeypatch)
    result = invoke(
        "promote", "knowledge/candidate/webhook-retries.md", "--root", str(tmp_path), "--json"
    )
    assert result.exit_code == ExitCode.OK
    promoted = json.loads(result.stdout)["promoted"]
    assert promoted["to"] == "knowledge/verified/webhook-retries.md"
    assert promoted["forced"] is False
    assert "entailment via scripted/judge-1" in promoted["verified_by"]
    assert (tmp_path / "knowledge/verified/webhook-retries.md").is_file()


def test_promote_refuses_when_entailment_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _verifiable(tmp_path)
    _with_judge(monkeypatch, entailed=False)
    result = invoke("promote", "knowledge/candidate/webhook-retries.md", "--root", str(tmp_path))
    assert result.exit_code == ExitCode.FAILED
    assert "entailment-below-threshold" in result.stdout


def test_force_promotion_records_the_human_and_the_reason(tmp_path: Path) -> None:
    _verifiable(tmp_path)
    result = invoke(
        "promote",
        "knowledge/candidate/webhook-retries.md",
        "--root",
        str(tmp_path),
        "--force",
        "--by",
        "Daniel Polo",
        "--json",
    )
    assert result.exit_code == ExitCode.OK
    promoted = json.loads(result.stdout)["promoted"]
    assert promoted["forced"] is True
    assert promoted["verified_by"] == "Daniel Polo (forced: entailment-not-measured)"
    # In the document, so the override survives in Git rather than in scrollback.
    text = (tmp_path / "knowledge/verified/webhook-retries.md").read_text(encoding="utf-8")
    assert "forced: entailment-not-measured" in text


def test_promoting_something_that_is_not_synthesized_is_a_usage_error(tmp_path: Path) -> None:
    seeded(tmp_path, name="knowledge/candidate/hand-written.md", text="# Notes\n\nBy hand.\n")
    result = invoke("promote", "knowledge/candidate/hand-written.md", "--root", str(tmp_path))
    assert result.exit_code == ExitCode.USAGE
    assert "not a synthesized document" in result.stderr


def test_demote_moves_back_and_strips_the_verification(tmp_path: Path) -> None:
    from mycelium.markdown.frontmatter import parse_frontmatter

    _verifiable(tmp_path)
    invoke("promote", "knowledge/candidate/webhook-retries.md", "--root", str(tmp_path), "--force")
    result = invoke(
        "demote", "knowledge/verified/webhook-retries.md", "--root", str(tmp_path), "--json"
    )
    assert result.exit_code == ExitCode.OK
    assert json.loads(result.stdout)["demoted"]["to"] == "knowledge/candidate/webhook-retries.md"
    text = (tmp_path / "knowledge/candidate/webhook-retries.md").read_text(encoding="utf-8")
    assert parse_frontmatter(text).frontmatter.verified_by is None


def test_demoting_a_candidate_fails_rather_than_moving_it_sideways(tmp_path: Path) -> None:
    _verifiable(tmp_path)
    result = invoke("demote", "knowledge/candidate/webhook-retries.md", "--root", str(tmp_path))
    assert result.exit_code == ExitCode.FAILED
    assert "not under a verified/ folder" in result.stderr


def test_verify_refuses_a_document_outside_the_repository(tmp_path: Path) -> None:
    _verifiable(tmp_path)
    outside = tmp_path.parent / "elsewhere.md"
    outside.write_text("# Elsewhere\n", encoding="utf-8")
    result = invoke("verify", str(outside), "--root", str(tmp_path))
    assert result.exit_code == ExitCode.USAGE
    assert "outside" in result.stderr


def test_a_promoted_document_compiles_as_verified(tmp_path: Path) -> None:
    """The end of the workflow: the store learns the new status from a build.

    Nothing in verification writes an index (D-021), so this is what proves the
    move actually reaches the served snapshot.
    """
    _verifiable(tmp_path)
    invoke("promote", "knowledge/candidate/webhook-retries.md", "--root", str(tmp_path), "--force")
    assert invoke("build", str(tmp_path)).exit_code == ExitCode.OK
    store = SqliteStore.open(tmp_path, read_only=True)
    try:
        document = store.get_document_by_path("knowledge/verified/webhook-retries.md")
    finally:
        store.close()
    assert document is not None, "the promoted document is in the published snapshot"
    assert document.verification_status is VerificationStatus.VERIFIED
    assert document.provenance.origin is ProvenanceOrigin.SYNTHESIZED
    assert document.verification is not None, "and it carries the evidence it was promoted on"
    assert document.verification.grounding == 1.0


def test_doctor_says_nothing_about_verification_until_a_provider_exists(tmp_path: Path) -> None:
    # With no provider there are no candidate documents, so a line about their
    # grounding would be noise on every offline install.
    seeded(tmp_path)
    payload = json.loads(invoke("doctor", str(tmp_path), "--json").stdout)
    assert not any(item["name"] == "verification" for item in payload["checks"])


def test_doctor_names_the_judge_and_the_promotion_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeded(tmp_path)
    (tmp_path / "mycelium.toml").write_text(
        '[synthesis]\nprovider = "anthropic"\n\n[verification]\nsample_size = 4\n',
        encoding="utf-8",
    )

    class Judge:
        identity = "anthropic/some-model"

    from mycelium.cli import doctor as doctor_module

    monkeypatch.setattr(doctor_module, "build_judge", lambda *_: (Judge(), True, ""))
    payload = json.loads(invoke("doctor", str(tmp_path), "--json").stdout)
    check = next(item for item in payload["checks"] if item["name"] == "verification")
    assert check["status"] == "ok"
    assert "anthropic/some-model (self-judged)" in check["detail"]
    assert "4 sampled claims" in check["detail"]
    assert "promotion is human" in check["detail"]


def test_doctor_warns_when_the_gate_has_no_judge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeded(tmp_path)
    (tmp_path / "mycelium.toml").write_text(
        '[synthesis]\nprovider = "anthropic"\n', encoding="utf-8"
    )
    from mycelium.cli import doctor as doctor_module

    monkeypatch.setattr(
        doctor_module, "build_judge", lambda *_: (None, False, "no credential here")
    )
    payload = json.loads(invoke("doctor", str(tmp_path), "--json").stdout)
    check = next(item for item in payload["checks"] if item["name"] == "verification")
    assert check["status"] == "warn"
    assert "no credential here" in check["detail"]
