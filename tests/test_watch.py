# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Watch mode (roadmap 3.5, spec 02 §7, ADR-0019).

Spec 02 §7 gives watch mode one sentence — *"debounced FS events → incremental
builds; identical guarantees"* — and the tests here are organised around its two
halves.

**Identical guarantees.** A watched rebuild is the ordinary incremental build, so
the snapshot a watch session publishes is the one a hand-run `mycelium build`
would publish from the same sources. That is asserted directly, by comparing
artifact digests.

**Everything around the build.** Debouncing a save burst into one build, never
watching the derived store (which would loop forever), surviving a document that
does not parse, and losing no change that arrives *while* a build is running.

The loop takes its events from a queue, so all of that is exercised without a
real filesystem watcher — which also means it is exercised on every CI platform,
where `watchdog` may not be installed. The watcher itself is one small adapter
with its own test, skipped when the optional dependency is absent.
"""

import queue
import threading
from pathlib import Path

import pytest

from mycelium.build import build
from mycelium.config import EmbeddingConfig, MyceliumConfig
from mycelium.watch import (
    STOP,
    WatchStats,
    collect_batch,
    is_relevant,
    run_watch,
    watched_paths,
)

# Pre-pinned, because the first build of an unpinned corpus writes `mycelium_id`
# back into the sources — a real change event, and one that would confound tests
# about which events the watcher reports. The convergence that pin-then-rebuild
# causes has its own test below.
CORPUS = {
    "knowledge/architecture.md": (
        "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FG1\n---\n\n"
        "# Architecture\n\nThe bus routes messages.\n"
    ),
    "knowledge/retries.md": (
        "---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5FG2\n---\n\n# Retries\n\nExponential backoff.\n"
    ),
}


class ScriptedSource(queue.Queue):  # type: ignore[type-arg]
    """A change source whose batch boundaries are declared, not timed.

    `QUIET` makes the next `get(timeout=...)` raise `Empty`, which is what ends a
    batch — so a test can say "these events, then a build, then those events"
    without sleeping and without depending on how long a build takes.
    """

    QUIET = object()

    def __init__(self, *script: object) -> None:
        super().__init__()
        for item in script:
            super().put(item)

    def get(self, block: bool = True, timeout: float | None = None) -> object:
        item = super().get(block=block, timeout=timeout)
        if item is ScriptedSource.QUIET:
            if timeout is None:  # a batch's first get: skip the marker and block
                return self.get(block, timeout)
            raise queue.Empty
        return item


LEXICAL = MyceliumConfig(embedding=EmbeddingConfig(provider="none"))
"""Watch tests build repeatedly; the vector stage is off so they measure the loop."""


def repo(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    root = tmp_path / "repo"
    for relative, text in (files or CORPUS).items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


def source(*items: object) -> "queue.Queue[object]":
    """A change source that yields `items` and then stops the loop."""
    events: queue.Queue[object] = queue.Queue()
    for item in items:
        events.put(item)
    events.put(STOP)
    return events


# ---------------------------------------------------------------------------
# What counts as a change
# ---------------------------------------------------------------------------


def test_the_derived_store_is_never_watched(tmp_path: Path) -> None:
    """The footgun this rule exists for: a build writes into `.mycelium/`, so
    treating those writes as changes is an infinite rebuild loop."""
    root = repo(tmp_path)
    for written in (
        root / ".mycelium" / "store.db",
        root / ".mycelium" / "CURRENT",
        root / ".mycelium" / "snapshots" / "01ARZ3NDEKTSV4RRFFQ69G5FAV.json",
        root / ".mycelium" / "cas" / "ab" / "cdef",
    ):
        assert is_relevant(written, root) is False


def test_documents_in_the_knowledge_tree_count(tmp_path: Path) -> None:
    root = repo(tmp_path)
    assert is_relevant(root / "knowledge" / "architecture.md", root) is True
    assert is_relevant(root / "knowledge" / "deep" / "nested.md", root) is True


def test_the_configuration_counts_because_it_changes_what_a_build_produces(
    tmp_path: Path,
) -> None:
    """`mycelium.toml` feeds the config digest (ADR-0014), so editing it is a
    change exactly as editing a document is."""
    root = repo(tmp_path)
    assert is_relevant(root / "mycelium.toml", root) is True


@pytest.mark.parametrize(
    "name",
    ["notes.txt", "image.png", "script.py", "README"],
)
def test_files_the_compiler_does_not_read_are_ignored(tmp_path: Path, name: str) -> None:
    root = repo(tmp_path)
    assert is_relevant(root / "knowledge" / name, root) is False


def test_documents_outside_the_knowledge_tree_are_ignored_when_it_exists(
    tmp_path: Path,
) -> None:
    """Watch mode and discovery must agree on what the corpus is (spec 02 §3)."""
    root = repo(tmp_path)
    assert is_relevant(root / "elsewhere" / "stray.md", root) is False

    bare = repo(tmp_path / "bare", {"notes.md": "# Notes\n"})
    assert is_relevant(bare / "notes.md", bare) is True  # no knowledge/: the root is the corpus


def test_a_path_outside_the_repository_is_ignored(tmp_path: Path) -> None:
    root = repo(tmp_path)
    assert is_relevant(tmp_path / "somewhere-else.md", root) is False


def test_watched_paths_reports_the_corpus(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root, config=LEXICAL)  # writes .mycelium/, which must not appear
    assert [path.name for path in watched_paths(root)] == ["architecture.md", "retries.md"]


# ---------------------------------------------------------------------------
# Debouncing
# ---------------------------------------------------------------------------


def test_a_burst_of_events_becomes_one_batch(tmp_path: Path) -> None:
    """One save is several events; five saves must not be five builds."""
    events = source(tmp_path / "a.md", tmp_path / "a.md", tmp_path / "b.md")
    batch = collect_batch(events, debounce_s=0.05)
    assert batch == {tmp_path / "a.md", tmp_path / "b.md"}


def test_the_batch_waits_for_quiet_not_for_a_fixed_delay(tmp_path: Path) -> None:
    """A change arriving inside the debounce window joins the same build."""
    events: queue.Queue[object] = queue.Queue()
    events.put(tmp_path / "a.md")

    def late() -> None:
        events.put(tmp_path / "b.md")

    timer = threading.Timer(0.05, late)
    timer.start()
    try:
        batch = collect_batch(events, debounce_s=0.25)
    finally:
        timer.cancel()
    assert batch == {tmp_path / "a.md", tmp_path / "b.md"}


def test_a_continuous_rewrite_still_builds_within_the_ceiling(tmp_path: Path) -> None:
    """A `git checkout` rewriting a tree must not postpone the build forever."""
    events: queue.Queue[object] = queue.Queue()
    stop = threading.Event()

    def flood() -> None:
        while not stop.is_set():
            events.put(tmp_path / "a.md")
            stop.wait(0.01)

    writer = threading.Thread(target=flood, daemon=True)
    writer.start()
    try:
        batch = collect_batch(events, debounce_s=0.2, max_wait_s=0.3)
    finally:
        stop.set()
        writer.join(timeout=2)
    assert batch == {tmp_path / "a.md"}


def test_stop_ends_the_batch_and_then_the_loop(tmp_path: Path) -> None:
    events = source()
    assert collect_batch(events, debounce_s=0.05) is None


def test_changes_before_a_stop_are_still_built(tmp_path: Path) -> None:
    """The last save must not be the one that gets dropped on shutdown."""
    events = source(tmp_path / "a.md")
    assert collect_batch(events, debounce_s=0.05) == {tmp_path / "a.md"}
    assert collect_batch(events, debounce_s=0.05) is None


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------


def test_a_change_triggers_exactly_one_build(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root, config=LEXICAL)
    (root / "knowledge" / "retries.md").write_text("# Retries\n\nRewritten.\n", encoding="utf-8")

    results = []
    stats = run_watch(
        root,
        source(root / "knowledge" / "retries.md"),
        config=LEXICAL,
        debounce_s=0.05,
        on_result=results.append,
    )

    assert stats == WatchStats(builds=1, failures=0, changes=1)
    assert results[0].stats.rebuilt == 1
    assert results[0].stats.reused == 1


def test_a_watched_build_publishes_what_a_manual_build_would(tmp_path: Path) -> None:
    """Spec 02 §7's "identical guarantees", asserted rather than assumed.

    The same repository is built both ways, because a *second* repository would
    differ on file mtimes alone — they become `created_at` on every document
    record (ADR-0009), so comparing two directories would be measuring the clock
    rather than the compiler.
    """
    root = repo(tmp_path)
    results = []
    run_watch(
        root,
        source(root / "knowledge" / "architecture.md"),
        config=LEXICAL,
        debounce_s=0.05,
        on_result=results.append,
    )
    watched = results[-1].manifest

    manual = build(root, config=LEXICAL).manifest

    assert watched.artifact_digests == manual.artifact_digests
    assert watched.counts == manual.counts
    assert watched.config_digest == manual.config_digest
    assert watched.snapshot_id != manual.snapshot_id  # two publications, one corpus


def test_a_failing_build_is_reported_and_the_loop_continues(tmp_path: Path) -> None:
    """A document mid-edit is routinely unparseable; that is not a reason to stop."""
    root = repo(tmp_path)
    build(root, config=LEXICAL)
    broken = root / "knowledge" / "broken.md"
    broken.write_text("---\nmycelium_id: not-a-ulid\n---\n\n# Broken\n", encoding="utf-8")

    results: list[object] = []
    failures: list[Exception] = []
    stats = run_watch(
        root,
        source(broken, root / "knowledge" / "retries.md"),
        config=LEXICAL,
        debounce_s=0.05,
        on_result=results.append,
        on_failure=failures.append,
    )

    # A quarantined document is not a failed build (the failure taxonomy); the
    # loop builds, reports the warning through the manifest, and carries on.
    assert stats.builds == 1
    assert failures == []
    assert results


def test_a_locked_repository_does_not_end_the_session(tmp_path: Path) -> None:
    from mycelium.build.lock import BuildLock

    root = repo(tmp_path)
    build(root, config=LEXICAL)

    failures: list[Exception] = []
    with BuildLock.acquire(root / ".mycelium"):
        stats = run_watch(
            root,
            source(root / "knowledge" / "retries.md"),
            config=LEXICAL,
            debounce_s=0.05,
            on_failure=failures.append,
        )

    assert stats.builds == 0
    assert stats.failures == 1
    assert "another build is running" in str(failures[0])


def test_the_loop_reports_what_changed(tmp_path: Path) -> None:
    root = repo(tmp_path)
    build(root, config=LEXICAL)

    seen: list[set[Path]] = []
    run_watch(
        root,
        source(root / "knowledge" / "retries.md"),
        config=LEXICAL,
        debounce_s=0.05,
        on_change=seen.append,
    )
    assert seen == [{root / "knowledge" / "retries.md"}]


def test_several_batches_build_several_times(tmp_path: Path) -> None:
    """Changes separated by quiet are separate builds — declared, not timed."""
    root = repo(tmp_path)
    build(root, config=LEXICAL)
    document = root / "knowledge" / "retries.md"

    events = ScriptedSource(
        document,
        ScriptedSource.QUIET,
        document,
        ScriptedSource.QUIET,
        document,
        ScriptedSource.QUIET,
        STOP,
    )
    stats = run_watch(root, events, config=LEXICAL, debounce_s=0.05)

    assert stats.builds == 3
    assert stats.failures == 0


def test_the_first_build_pins_identities_and_the_loop_converges(tmp_path: Path) -> None:
    """A build writes `mycelium_id` back into unpinned sources (ADR-0009), which
    the watcher rightly sees as a change. The rebuild it triggers pins nothing,
    so the loop settles instead of chasing its own tail."""
    root = repo(tmp_path / "unpinned", {"knowledge/fresh.md": "# Fresh\n\nNo identity yet.\n"})
    document = root / "knowledge" / "fresh.md"

    first = build(root, config=LEXICAL)
    assert first.pinned  # the build wrote to the corpus

    results = []
    run_watch(
        root,
        ScriptedSource(document, ScriptedSource.QUIET, STOP),
        config=LEXICAL,
        debounce_s=0.05,
        on_result=results.append,
    )

    assert results[-1].pinned == ()  # nothing left to pin: the loop has settled
    assert results[-1].stats.rebuilt == 0


def test_an_unreadable_config_is_reported_without_ending_the_session(tmp_path: Path) -> None:
    """`mycelium.toml` is watched, so it will be seen mid-edit."""
    root = repo(tmp_path)
    build(root, config=LEXICAL)
    (root / "mycelium.toml").write_text("[chunking\nmax_tokens = ", encoding="utf-8")

    failures: list[Exception] = []
    stats = run_watch(
        root,
        source(root / "mycelium.toml"),
        debounce_s=0.05,
        on_failure=failures.append,
        reload_config=True,
    )

    assert stats.builds == 0
    assert stats.failures == 1
    assert "mycelium.toml" in str(failures[0])


# ---------------------------------------------------------------------------
# The watcher adapter (skipped without the optional dependency)
# ---------------------------------------------------------------------------


watchdog = pytest.importorskip("watchdog", reason="the `watch` extra is not installed")


def test_the_observer_reports_a_real_edit(tmp_path: Path) -> None:
    """One end-to-end check that the adapter is wired to the real filesystem."""
    from mycelium.watch import _start_observer

    root = repo(tmp_path)
    events: queue.Queue[object] = queue.Queue()
    observer = _start_observer(root, events, "knowledge")
    try:
        target = root / "knowledge" / "retries.md"
        target.write_text("# Retries\n\nEdited on disk.\n", encoding="utf-8")
        # Filesystem events are asynchronous; wait for one rather than sleeping.
        changed = events.get(timeout=10)
    finally:
        observer.stop()
        observer.join(timeout=5)

    assert Path(str(changed)).name == "retries.md"


def test_the_observer_ignores_the_derived_store(tmp_path: Path) -> None:
    """The infinite-loop guard, over a real watcher this time."""
    from mycelium.watch import _start_observer

    root = repo(tmp_path)
    events: queue.Queue[object] = queue.Queue()
    observer = _start_observer(root, events, "knowledge")
    try:
        # The corpus is pre-pinned, so this build writes only into `.mycelium/`:
        # a store, a manifest, CURRENT, CAS blobs. None of it may come back as a
        # change, or the loop would rebuild forever.
        result = build(root, config=LEXICAL)
        assert result.pinned == ()
        with pytest.raises(queue.Empty):
            events.get(timeout=2)
    finally:
        observer.stop()
        observer.join(timeout=5)
