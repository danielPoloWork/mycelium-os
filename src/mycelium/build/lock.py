# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The single-writer build lock (spec 02 §7, D-015).

One advisory file, ``.mycelium/lock``, carrying who holds it (pid + host +
acquisition time) and proving liveness through its mtime, which the holder
refreshes as a heartbeat. A lock whose heartbeat is older than the staleness
threshold belongs to a dead build and may be taken over safely.

Why a file and not an OS lock: ``fcntl``/``msvcrt`` locks are process-scoped and
evaporate with their holder — which sounds right until a crashed build leaves no
trace of *why* the store is half-written — and they cannot be inspected by
`mycelium doctor` or a human. A JSON file with a heartbeat is diagnosable,
portable, and exactly what the spec names.

Creation uses ``O_CREAT | O_EXCL``, the one primitive that is atomic on every
platform and filesystem this project supports: of N processes racing to create
the file, exactly one wins. Takeover of a stale lock is unlink-then-create, so
racing takeover attempts collapse back into that same create race.
"""

import json
import os
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Final, Self

__all__ = ["BuildLock", "BuildLockedError", "LOCK_FILENAME", "LockInfo"]

LOCK_FILENAME: Final = "lock"
DEFAULT_STALE_AFTER_S: Final = 600.0
"""Ten minutes without a heartbeat marks a lock stale (spec: 'stale after N minutes')."""


class BuildLockedError(RuntimeError):
    """Another live build holds the writer lock."""


@dataclass(frozen=True, slots=True)
class LockInfo:
    """What the lock file says about its holder."""

    pid: int
    host: str
    acquired_at: str


class BuildLock:
    """Holds the single-writer lock for the duration of a build.

    Usage::

        with BuildLock.acquire(mycelium_dir) as lock:
            ...            # the build
            lock.heartbeat()  # refresh liveness at stage boundaries
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._held = False

    @property
    def path(self) -> Path:
        return self._path

    @classmethod
    def acquire(cls, mycelium_dir: Path, *, stale_after_s: float = DEFAULT_STALE_AFTER_S) -> Self:
        """Take the lock, or raise :class:`BuildLockedError` naming the live holder.

        A stale lock (heartbeat older than `stale_after_s`) is taken over: its
        file is removed and the create race is re-run, so if two processes
        attempt takeover simultaneously, exactly one wins.
        """
        mycelium_dir.mkdir(parents=True, exist_ok=True)
        lock = cls(mycelium_dir / LOCK_FILENAME)
        for _ in range(2):  # first attempt, then once more after a stale takeover
            if lock._try_create():
                return lock
            holder = lock.read_holder()
            age = lock._heartbeat_age_s()
            if age is None:
                continue  # the lock vanished between attempts; race again
            if age <= stale_after_s:
                who = f"pid {holder.pid} on {holder.host}" if holder else "an unknown process"
                msg = (
                    f"another build is running ({who}, heartbeat {age:.0f}s ago); "
                    f"if it is dead, it becomes stale after {stale_after_s:.0f}s"
                )
                raise BuildLockedError(msg)
            # Stale: remove and re-race. Losing the create race after this unlink
            # just means someone else took over first — that is a live lock.
            lock._path.unlink(missing_ok=True)
        msg = "could not acquire the build lock after a stale takeover"
        raise BuildLockedError(msg)

    def _try_create(self) -> bool:
        payload = {
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "acquired_at": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        }
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
        try:
            descriptor = os.open(self._path, flags)
        except FileExistsError:
            return False
        try:
            os.write(descriptor, (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8"))
        finally:
            os.close(descriptor)
        self._held = True
        return True

    def _heartbeat_age_s(self) -> float | None:
        try:
            mtime = self._path.stat().st_mtime
        except OSError:
            return None
        return max(0.0, datetime.now(tz=UTC).timestamp() - mtime)

    def read_holder(self) -> LockInfo | None:
        """Best-effort read of the holder's identity (diagnostics; may be None)."""
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return LockInfo(
                pid=int(data["pid"]),
                host=str(data["host"]),
                acquired_at=str(data["acquired_at"]),
            )
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def heartbeat(self) -> None:
        """Refresh the lock's mtime to prove this build is still alive."""
        if not self._held:
            msg = "heartbeat on a lock this process does not hold"
            raise BuildLockedError(msg)
        os.utime(self._path)

    def release(self) -> None:
        """Give the lock back. Safe to call twice."""
        if self._held:
            self._path.unlink(missing_ok=True)
            self._held = False

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()
