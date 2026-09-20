# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The build: orchestration, the single-writer lock, and snapshot publication.

- :mod:`mycelium.build.orchestrator` — the incremental pipeline
  (plan → dirty detection → parse → chunk → assemble → store → manifest → publish).
- :mod:`mycelium.build.dag` — build keys, stage versions, artifact envelopes
  (spec 02 §4.1, ADR-0015).
- :mod:`mycelium.build.cas` — the content-addressed artifact store under
  ``.mycelium/cas/``.
- :mod:`mycelium.build.snapshots` — the snapshot lifecycle: list, rollback
  (restore then repoint), and garbage collection (ADR-0016).
- :mod:`mycelium.build.lock` — the ``.mycelium/lock`` advisory single-writer lock
  (pid + host + heartbeat mtime, stale takeover; spec 02 §7).
- :mod:`mycelium.build.publish` — immutable manifests, the atomic ``CURRENT``
  pointer swap, and the diagnostic journal.

The publication and crash-safety semantics were fixed by v0 (ADR-0009) and are
inherited here unchanged; ADR-0015 adds the content-addressed incremental layer.

## This façade is lazy, and the reason is the query path (roadmap 6.25, ADR-0140)

Every name below is resolved on **first access** rather than on import, through
the module ``__getattr__`` PEP 562 defines. The exported surface is unchanged: the
same names, from the same modules, with the same types.

The reason is that reading one pointer used to cost the whole compiler. The MCP
server, the CLI and the evaluation harness all need :func:`read_current` — six
lines that open ``.mycelium/CURRENT`` and return its contents — and
``from mycelium.build.publish import read_current`` runs *this* file first. When
this file imported the orchestrator eagerly, that pulled the build DAG, the
Markdown adapter and ``markdown_it`` behind it, the symbol extractors, the
embedding provider with ``urllib`` and ``ssl``, and the entire ingestion
subsystem: **367 modules and 1.9 s** for a read-only query path that can call
none of them (measured at roadmap 6.18, fixed here).

What this costs: the first caller of a build symbol pays that symbol's import
where it asks for it rather than at ``import mycelium.build``. `mycelium build`
pays exactly what it always paid, a few microseconds later. What it does not
cost is correctness — the names bind into this module's globals on first
resolution, so the second access is an ordinary attribute lookup.

Type checkers read the ``TYPE_CHECKING`` block below and see the real signatures;
laziness is a runtime property and deliberately not a typing one.
"""

import importlib
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from mycelium.build.lock import BuildLock, BuildLockedError, LockInfo
    from mycelium.build.orchestrator import BuildResult, BuildStats, build
    from mycelium.build.publish import (
        append_journal,
        read_current,
        read_manifest,
        swap_current,
        write_manifest,
    )
    from mycelium.build.snapshots import (
        GarbageCollection,
        RollbackResult,
        SnapshotError,
        SnapshotInfo,
        collect_garbage,
        list_snapshots,
        rollback,
    )

__all__ = [
    "BuildLock",
    "BuildLockedError",
    "BuildResult",
    "BuildStats",
    "GarbageCollection",
    "LockInfo",
    "RollbackResult",
    "SnapshotError",
    "SnapshotInfo",
    "append_journal",
    "build",
    "collect_garbage",
    "list_snapshots",
    "read_current",
    "read_manifest",
    "rollback",
    "swap_current",
    "write_manifest",
]

_ORIGIN: Final[dict[str, str]] = {
    "BuildLock": "mycelium.build.lock",
    "BuildLockedError": "mycelium.build.lock",
    "BuildResult": "mycelium.build.orchestrator",
    "BuildStats": "mycelium.build.orchestrator",
    "GarbageCollection": "mycelium.build.snapshots",
    "LockInfo": "mycelium.build.lock",
    "RollbackResult": "mycelium.build.snapshots",
    "SnapshotError": "mycelium.build.snapshots",
    "SnapshotInfo": "mycelium.build.snapshots",
    "append_journal": "mycelium.build.publish",
    "build": "mycelium.build.orchestrator",
    "collect_garbage": "mycelium.build.snapshots",
    "list_snapshots": "mycelium.build.snapshots",
    "read_current": "mycelium.build.publish",
    "read_manifest": "mycelium.build.publish",
    "rollback": "mycelium.build.snapshots",
    "swap_current": "mycelium.build.publish",
    "write_manifest": "mycelium.build.publish",
}
"""Which module each exported name comes from.

Kept beside ``__all__`` rather than derived from it, because a name that this
table and ``__all__`` disagree about is a broken export, and
``tests/test_build.py`` asserts they agree — the laziness must not be able to
drop a name quietly.
"""


if not TYPE_CHECKING:
    # Hidden from the type checker on purpose. A module-level `__getattr__` that
    # mypy can see answers *every* attribute, so `mycelium.build.compile_it_all`
    # would stop being an error and start being `object` - the laziness would buy
    # a faster import by giving up a check on every consumer. Behind this branch,
    # mypy reads only the `TYPE_CHECKING` imports above and still rejects a name
    # this package does not export; `tests/test_build.py` holds the runtime half,
    # which mypy no longer looks at.

    def __getattr__(name: str) -> object:
        """Resolve an exported name on first access (PEP 562)."""
        origin = _ORIGIN.get(name)
        if origin is None:
            msg = f"module {__name__!r} has no attribute {name!r}"
            raise AttributeError(msg)
        value = getattr(importlib.import_module(origin), name)
        globals()[name] = value  # bind it, so this path runs once per name
        return value

    def __dir__() -> list[str]:
        """`dir(mycelium.build)` lists what it exports, resolved or not."""
        return sorted(__all__)
