# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The build: orchestration, the single-writer lock, and snapshot publication.

- :mod:`mycelium.build.orchestrator` — the v0 sequential pipeline
  (discover → pin identity → parse → chunk → store → manifest → publish).
- :mod:`mycelium.build.lock` — the ``.mycelium/lock`` advisory single-writer lock
  (pid + host + heartbeat mtime, stale takeover; spec 02 §7).
- :mod:`mycelium.build.publish` — immutable manifests, the atomic ``CURRENT``
  pointer swap, and the diagnostic journal.

The publication and crash-safety semantics set here are inherited unchanged by
the incremental compiler (roadmap 3.1) — see ADR-0009.
"""

from mycelium.build.lock import BuildLock, BuildLockedError, LockInfo
from mycelium.build.orchestrator import BuildResult, build
from mycelium.build.publish import (
    append_journal,
    read_current,
    read_manifest,
    swap_current,
    write_manifest,
)

__all__ = [
    "BuildLock",
    "BuildLockedError",
    "BuildResult",
    "LockInfo",
    "append_journal",
    "build",
    "read_current",
    "read_manifest",
    "swap_current",
    "write_manifest",
]
