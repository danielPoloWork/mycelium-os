# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""CLI skeleton (roadmap 2.8): the conventions in spec 05 §1 hold — exit codes 0/1/2,
`--json` on every read command with nothing else on stdout, NO_COLOR honoured, and no
prompt anywhere that a CI run could block on."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mycelium.__about__ import __version__
from mycelium.build import build as run_build
from mycelium.build.lock import BuildLock
from mycelium.cli import app
from mycelium.cli.doctor import diagnose, worst_status
from mycelium.cli.output import ExitCode, use_color
from mycelium.store import SqliteStore
from mycelium.store.schema import META_CURRENT_SNAPSHOT, META_SCHEMA_VERSION

runner = CliRunner()

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
    invoke("init", str(tmp_path))
    assert text.count(".mycelium/") == 1


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
        "store",
        "snapshot",
        "manifest",
        "pointer",
        "lock",
    }


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
