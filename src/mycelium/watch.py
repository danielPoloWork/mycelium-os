# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Watch mode: debounced filesystem events drive incremental builds (spec 02 §7).

The spec's own sentence fixes the design: *"debounced FS events → incremental
builds; **identical guarantees**"*. So events decide **when** to build and never
**what** to build. Each rebuild is the ordinary incremental build — the same
conservative, digest-based dirty detection ADR-0015 argued for — so a watched
repository and a hand-built one publish the same snapshot from the same sources,
and there is no second correctness story to reason about.

That is a deliberate refusal of the obvious optimisation. An event stream looks
like a perfect dirty-set, and it is not: watchers drop events under load, editors
save through temp-file-and-rename, `git checkout` rewrites a tree without anyone
watching the right directory, and a watcher started after an edit never hears
about it. A build that trusted the event set would inherit every one of those as
a *silently stale snapshot* — the one failure ADR-0015 says a determinism product
cannot afford. What events are trusted for here is the cheap half of the problem:
noticing that something probably happened.

What the loop must get right instead is everything around the build:

- **Debounce.** One save is a burst of events, so the loop waits for quiet before
  building; a burst becomes one build rather than five.
- **Never watch the derived store.** `.mycelium/` is where a build *writes*, so
  watching it is an infinite rebuild loop wearing a plausible disguise. The same
  dot-directory rule discovery uses (spec 02 §3) excludes it.
- **Survive a failed build.** A syntax error in a document, or another process
  holding the writer lock, must leave the loop watching. Exiting on the first
  failure would make watch mode useless exactly when it is most useful.
- **Lose nothing.** Events that arrive *during* a build are collected and trigger
  the next one, so the last save is never the one that gets dropped.
"""

import queue
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from mycelium.build import BuildResult
from mycelium.build import build as run_build
from mycelium.build.lock import BuildLockedError
from mycelium.config import CONFIG_FILENAME, MyceliumConfig, load_config
from mycelium.sdk.identity import digest_text
from mycelium.store import STORE_DIRNAME

__all__ = [
    "CHANGE_EVENT_TYPES",
    "DEFAULT_DEBOUNCE_S",
    "STOP",
    "WATCH_EXTRA",
    "WatchStats",
    "WatcherUnavailableError",
    "collect_batch",
    "has_real_change",
    "is_change_event",
    "is_relevant",
    "run_watch",
    "watch",
    "watched_paths",
]

DEFAULT_DEBOUNCE_S: Final = 0.3
"""Quiet period before a build. Long enough to coalesce an editor's save burst,
short enough that the rebuild still feels like part of pressing Ctrl-S."""

MAX_BATCH_WAIT_S: Final = 5.0
"""Ceiling on debouncing. A directory being rewritten continuously (a `git
checkout`, an rsync) would otherwise postpone the build for as long as it runs."""

WATCH_EXTRA: Final = "watch"

STOP: Final = object()
"""Sentinel that ends the loop. The observer pushes it on shutdown; tests use it
to run a bounded session without a test-only parameter in the production loop."""

CHANGE_EVENT_TYPES: Final = frozenset({"created", "deleted", "modified", "moved", "closed"})
"""Event types that mean the content changed — and **Linux is why this exists**.

inotify reports reads as well as writes, so a build's own plan scan (which opens
every document) produces a burst of `opened` / `closed_no_write` events on the
corpus it just read. A watcher that accepted those would rebuild forever *on
Linux only*: Windows and macOS never emit them, so the platform that needs the
filter is not the one a developer is likely to be testing on.

`closed` is kept because inotify's ``IN_CLOSE_WRITE`` is a *completed write* —
the most reliable "this file is now fully saved" signal there is. The values are
watchdog's own ``EVENT_TYPE_*`` strings; a test pins them against the library so
a rename upstream fails loudly instead of silently reopening the loop.
"""


def is_change_event(event_type: str) -> bool:
    """Whether a filesystem event type means content changed rather than was read."""
    return event_type in CHANGE_EVENT_TYPES


class WatcherUnavailableError(RuntimeError):
    """Watch mode was asked for and the filesystem watcher is not installed."""


@dataclass(frozen=True, slots=True)
class WatchStats:
    """What one watch session did, for the summary line when it ends."""

    builds: int
    failures: int
    changes: int


def is_relevant(path: Path, root: Path, knowledge_dir: str = "knowledge") -> bool:
    """Whether a changed path could change what the next build produces.

    Three rules, and the first is the one that matters: **never the derived
    store**. A build writes into `.mycelium/`, so treating those writes as
    changes is an infinite loop. The dot-directory rule that excludes it is the
    same one discovery uses, so watch mode and the compiler agree on what the
    corpus is (spec 02 §3).

    `mycelium.toml` counts too: it feeds the config digest, so editing it changes
    what a build produces exactly as editing a document does (ADR-0014).
    """
    try:
        relative = path.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return False  # outside the repository, or gone before we could look

    parts = relative.parts
    if not parts or any(part.startswith(".") for part in parts):
        return False
    if relative.as_posix() == CONFIG_FILENAME:
        return True
    if path.suffix.lower() != ".md":
        return False
    base = root / knowledge_dir
    if base.is_dir():
        return parts[0] == knowledge_dir
    return True


def has_real_change(root: Path, batch: Iterable[Path], knowledge_dir: str = "knowledge") -> bool:
    """Whether anything in `batch` actually differs from what the store indexed.

    **Every platform reports a build's own reads as events, by a different
    route.** Linux inotify emits `opened`/`closed_no_write`, which an event-type
    filter can drop; macOS FSEvents reports a read's atime update as inode
    metadata modification, which arrives indistinguishable from a write. Without
    a check, each build's plan scan would trigger the next build, forever, and
    every one of them would publish a snapshot.

    So the loop asks the same question the build asks, against the same
    ``doc_state`` truth: is this file's content — and its mtime, which becomes
    ``created_at`` (ADR-0009) — different from what is indexed? A read changes
    neither. This reads only the batch's own files, so it costs one digest per
    changed document rather than a scan.

    Conservative in every direction: an unreadable file, a missing store, a path
    with no row, or anything unexpected answers **yes, build**. The guard may
    only ever suppress a build it can prove would publish the same corpus.
    """
    paths = list(batch)
    if not paths:
        return False

    store_path = root / STORE_DIRNAME / "store.db"
    if not store_path.exists():
        return True  # nothing indexed yet: the first build decides everything

    try:
        from mycelium.store import SqliteStore

        with SqliteStore.open(root, read_only=True) as store:
            indexed = {state.path: state for state in store.doc_states()}
    except Exception:  # noqa: BLE001 - an unreadable store is a reason to build, not to stop
        return True

    for path in paths:
        try:
            relative = path.resolve().relative_to(root.resolve()).as_posix()
        except (ValueError, OSError):
            return True
        if relative == CONFIG_FILENAME:
            return True  # the config reaches every stage; never worth proving otherwise

        state = indexed.get(relative)
        exists = path.is_file()
        if state is None or not exists:
            return True  # appeared, or disappeared

        try:
            raw = path.read_bytes().decode("utf-8")
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
        except (OSError, UnicodeDecodeError):
            return True
        if digest_text(raw) != state.source_digest or mtime != state.source_mtime:
            return True

    return False


def collect_batch(
    source: "queue.Queue[Any]",
    *,
    debounce_s: float = DEFAULT_DEBOUNCE_S,
    max_wait_s: float = MAX_BATCH_WAIT_S,
) -> set[Path] | None:
    """Block for the first change, then drain until the filesystem goes quiet.

    Returns the coalesced set of changed paths, or ``None`` when the source asks
    the loop to stop. The `max_wait_s` ceiling stops a continuously-rewritten
    tree from postponing the build forever: at that point the batch is built with
    what it has, and whatever arrives next simply triggers the following build.

    A stop that arrives *while* a batch is being drained is put back before the
    batch is returned. The last save must still be built, and the next call must
    still stop — swallowing the sentinel would leave the loop blocked on an
    empty queue with no way out.
    """
    first = source.get()
    if first is STOP:
        return None

    batch: set[Path] = {first}
    deadline = time.monotonic() + max_wait_s
    while True:
        remaining = min(debounce_s, max(0.0, deadline - time.monotonic()))
        if remaining <= 0.0:
            return batch
        try:
            item = source.get(timeout=remaining)
        except queue.Empty:
            return batch  # quiet for a full debounce window: build it
        if item is STOP:
            source.put(STOP)  # build what we have; stop on the next call
            return batch
        batch.add(item)


def run_watch(
    root: Path,
    source: "queue.Queue[Any]",
    *,
    config: MyceliumConfig | None = None,
    debounce_s: float = DEFAULT_DEBOUNCE_S,
    on_change: Callable[[set[Path]], None] | None = None,
    on_result: Callable[[BuildResult], None] | None = None,
    on_failure: Callable[[Exception], None] | None = None,
    reload_config: bool = True,
    knowledge_dir: str = "knowledge",
) -> WatchStats:
    """Build whenever `source` reports a *real* change, until it reports :data:`STOP`.

    The build is the ordinary incremental one, so a watched repository publishes
    exactly what a hand-built one would (spec 02 §7's "identical guarantees").

    A failed build is reported and the loop continues: a document mid-edit is
    routinely unparseable, and another process may hold the writer lock. Neither
    is a reason to stop watching — which is precisely when the operator needs the
    next successful build most.

    `reload_config` re-reads `mycelium.toml` before each build, because it is one
    of the files being watched; a caller that passed an explicit `config` gets
    that config every time instead.
    """
    builds = failures = changes = 0

    while True:
        batch = collect_batch(source, debounce_s=debounce_s)
        if batch is None:
            return WatchStats(builds=builds, failures=failures, changes=changes)

        changes += len(batch)
        # Prove something actually changed before building. Every platform
        # reports a build's own reads as events by some route, so without this
        # each build would trigger the next one and publish a snapshot for it.
        if not has_real_change(root, batch, knowledge_dir):
            continue
        if on_change is not None:
            on_change(batch)

        settings = config
        if settings is None and reload_config:
            try:
                settings = load_config(root)
            except Exception as error:  # noqa: BLE001 - a broken config is a reportable event
                failures += 1
                if on_failure is not None:
                    on_failure(error)
                continue

        try:
            result = run_build(root, config=settings)
        except (BuildLockedError, Exception) as error:  # noqa: BLE001 - the loop outlives one build
            failures += 1
            if on_failure is not None:
                on_failure(error)
            continue

        builds += 1
        if on_result is not None:
            on_result(result)


def watch(
    root: Path,
    *,
    config: MyceliumConfig | None = None,
    debounce_s: float = DEFAULT_DEBOUNCE_S,
    on_change: Callable[[set[Path]], None] | None = None,
    on_result: Callable[[BuildResult], None] | None = None,
    on_failure: Callable[[Exception], None] | None = None,
    build_first: bool = True,
) -> WatchStats:
    """Watch `root` and rebuild on change, until interrupted.

    Blocks. Raises :class:`WatcherUnavailableError` when the optional watcher is
    not installed — watch mode is a development convenience, and charging every
    install for it would be the wrong trade (D-017's minimal closure).

    `build_first` compiles once before waiting, because a watcher started after
    an edit hears nothing about it: without that first build, the session would
    begin by serving a stale snapshot and look like it was working.
    """
    settings = config if config is not None else load_config(root)
    knowledge_dir = settings.project.knowledge_dir

    if build_first:
        try:
            result = run_build(root, config=config)
        except Exception as error:  # noqa: BLE001 - reported, and the session still starts
            if on_failure is not None:
                on_failure(error)
        else:
            if on_result is not None:
                on_result(result)

    events: queue.Queue[Any] = queue.Queue()
    observer = _start_observer(root, events, knowledge_dir)
    try:
        return run_watch(
            root,
            events,
            config=config,
            debounce_s=debounce_s,
            on_change=on_change,
            on_result=on_result,
            on_failure=on_failure,
            knowledge_dir=knowledge_dir,
        )
    except KeyboardInterrupt:
        return WatchStats(builds=0, failures=0, changes=0)
    finally:
        observer.stop()
        observer.join(timeout=5.0)


def _start_observer(root: Path, events: "queue.Queue[Any]", knowledge_dir: str) -> Any:
    """Start a filesystem observer that pushes relevant paths onto `events`.

    Imported here rather than at module import, so `mycelium.watch` stays
    importable — and its error stays *explainable* — in an install that never
    asked for watch mode.
    """
    try:
        from watchdog.events import FileSystemEvent, FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError as error:
        msg = (
            "watch mode needs the optional watcher; install `mycelium-os[watch]` "
            f"(watchdog), or re-run `mycelium build` by hand after each edit ({error})"
        )
        raise WatcherUnavailableError(msg) from error

    class _Handler(FileSystemEventHandler):
        def on_any_event(self, event: FileSystemEvent) -> None:
            if event.is_directory or not is_change_event(event.event_type):
                return
            # A rename reports both ends; both matter, because a document can
            # arrive or leave by being moved.
            for raw in (event.src_path, getattr(event, "dest_path", None)):
                if not raw:
                    continue
                path = Path(raw if isinstance(raw, str) else raw.decode())
                if is_relevant(path, root, knowledge_dir):
                    events.put(path)

    observer = Observer()
    scope = root / knowledge_dir if (root / knowledge_dir).is_dir() else root
    observer.schedule(_Handler(), str(scope), recursive=True)
    if scope != root and (root / CONFIG_FILENAME).exists():
        # The configuration lives outside the knowledge tree but changes what a
        # build produces, so it gets its own non-recursive watch.
        observer.schedule(_Handler(), str(root), recursive=False)
    observer.start()
    return observer


def watched_paths(root: Path, knowledge_dir: str = "knowledge") -> Iterable[Path]:
    """The corpus a watch session covers — what `--watch` reports on startup."""
    base = root / knowledge_dir
    scope = base if base.is_dir() else root
    return (
        path
        for path in sorted(scope.rglob("*.md"))
        if is_relevant(path, root, knowledge_dir) and STORE_DIRNAME not in path.parts
    )
