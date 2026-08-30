# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The build: orchestration, the single-writer lock, and snapshot publication.

- :mod:`mycelium.build.orchestrator` — the incremental pipeline
  (plan → dirty detection → parse → chunk → assemble → store → manifest → publish).
- :mod:`mycelium.build.dag` — build keys, stage versions, artifact envelopes
  (spec 02 §4.1, ADR-0015).
- :mod:`mycelium.build.cas` — the content-addressed artifact store under
  ``.mycelium/cas/``.
- :mod:`mycelium.build.lock` — the ``.mycelium/lock`` advisory single-writer lock
  (pid + host + heartbeat mtime, stale takeover; spec 02 §7).
- :mod:`mycelium.build.publish` — immutable manifests, the atomic ``CURRENT``
  pointer swap, and the diagnostic journal.

The publication and crash-safety semantics were fixed by v0 (ADR-0009) and are
inherited here unchanged; ADR-0015 adds the content-addressed incremental layer.
"""

from mycelium.build.lock import BuildLock, BuildLockedError, LockInfo
from mycelium.build.orchestrator import BuildResult, BuildStats, build
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
    "BuildStats",
    "LockInfo",
    "append_journal",
    "build",
    "read_current",
    "read_manifest",
    "swap_current",
    "write_manifest",
]
