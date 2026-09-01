# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""``mycelium doctor`` — environment, store integrity, lock state (spec 05 §1).

The checks are a pure function of the repository on disk, returning records
rather than printing, so the command renders them and the tests assert them.

One check exists because [ADR-0009](../../../docs/adr/0009-adopt-build-publication-semantics.md)
promised it: a build can be interrupted between its COMMIT and the ``CURRENT``
swap, leaving the store's own ``meta[current_snapshot]`` ahead of the ``CURRENT``
file. That window cannot be closed with a single mutable store — so it is
detected here, and healed by the next build.
"""

import platform
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from mycelium.__about__ import __version__
from mycelium.build.lock import DEFAULT_STALE_AFTER_S, LOCK_FILENAME, BuildLock
from mycelium.build.publish import manifest_path, read_current
from mycelium.config import CONFIG_FILENAME, ConfigError, load_config
from mycelium.ingest import Custody, CustodyError, probe
from mycelium.store import STORE_DIRNAME, STORE_FILENAME, SqliteStore, StoreError
from mycelium.store.schema import META_CURRENT_SNAPSHOT

__all__ = ["Check", "Status", "diagnose", "worst_status"]

type Status = Literal["ok", "warn", "fail"]


@dataclass(frozen=True, slots=True)
class Check:
    """One diagnostic result."""

    name: str
    status: Status
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def worst_status(checks: list[Check]) -> Status:
    """The most severe status present — what the exit code is derived from."""
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "warn" for check in checks):
        return "warn"
    return "ok"


def _check_lock(mycelium_dir: Path, stale_after_s: float) -> Check:
    lock_file = mycelium_dir / LOCK_FILENAME
    if not lock_file.exists():
        return Check("lock", "ok", "no build lock held")
    lock = BuildLock(lock_file)
    holder = lock.read_holder()
    who = f"pid {holder.pid} on {holder.host}" if holder else "an unidentified process"
    age = max(0.0, datetime.now(tz=UTC).timestamp() - lock_file.stat().st_mtime)
    if age > stale_after_s:
        return Check(
            "lock",
            "warn",
            f"stale lock from {who} ({age:.0f}s without a heartbeat); "
            "the next build will take it over",
        )
    return Check("lock", "warn", f"a build is running ({who}, heartbeat {age:.0f}s ago)")


def _check_snapshot(root: Path, mycelium_dir: Path, store: SqliteStore | None) -> list[Check]:
    current = read_current(mycelium_dir)
    if current is None:
        return [Check("snapshot", "warn", "nothing published yet; run `mycelium build`")]

    checks = [Check("snapshot", "ok", f"CURRENT -> {current}")]
    if not manifest_path(mycelium_dir, current).exists():
        checks.append(
            Check(
                "manifest",
                "fail",
                f"CURRENT names {current} but its manifest file is missing; run `mycelium build`",
            )
        )
    else:
        checks.append(Check("manifest", "ok", f"snapshots/{current}.json present"))

    if store is not None:
        pointer = store.get_meta(META_CURRENT_SNAPSHOT)
        if pointer is None:
            checks.append(
                Check("pointer", "fail", "the store records no snapshot; run `mycelium build`")
            )
        elif pointer != current:
            # The ADR-0009 window: a build committed but was interrupted before
            # the CURRENT swap.
            checks.append(
                Check(
                    "pointer",
                    "fail",
                    f"the store is at {pointer} but CURRENT names {current}: a build was "
                    "interrupted between commit and publish; run `mycelium build` to heal",
                )
            )
        else:
            checks.append(Check("pointer", "ok", "the store and CURRENT agree"))
    return checks


def _check_config(root: Path) -> Check:
    """Validate `mycelium.toml` and say what it does not yet control (spec 05 §2)."""
    if not (root / CONFIG_FILENAME).exists():
        return Check("config", "ok", f"no {CONFIG_FILENAME}; built-in defaults apply")
    try:
        config = load_config(root)
    except ConfigError as error:
        return Check("config", "fail", str(error).replace("\n", "; "))
    detail = f"{CONFIG_FILENAME} valid; knowledge_dir={config.project.knowledge_dir}"
    pending = [*config.unhonoured_sections, *config.unhonoured_keys]
    if pending:
        # An operator who tuned a knob deserves to hear that it does nothing yet.
        return Check(
            "config",
            "warn",
            f"{detail}; not honoured yet: {', '.join(pending)}",
        )
    return Check("config", "ok", detail)


def _check_parsers(root: Path) -> Check:
    """Report whether every pinned ingestion plugin can actually run here.

    Resolution refuses an unavailable plugin (spec 05 §4.2), so without this check
    an operator meets that refusal for the first time in the middle of a build.
    `probe` asks the same factories the registry asks and reports instead of
    raising, which is the whole reason `doctor` exists.
    """
    try:
        config = load_config(root)
    except ConfigError:
        return Check("parsers", "warn", "not checked: the configuration is invalid")
    statuses = probe(config.ingest.parsers)
    missing = [status for status in statuses if not status.available]
    if missing:
        return Check(
            "parsers",
            "fail",
            "; ".join(f"{status.id}: {status.detail}" for status in missing),
        )
    return Check(
        "parsers",
        "ok",
        "pinned: " + ", ".join(f"{status.id} ({status.detail})" for status in statuses),
    )


def _check_custody(mycelium_dir: Path) -> Check:
    """Re-hash tier-1 evidence and report what no longer holds (ADR-0033).

    The build cache heals itself by discarding a blob that fails its own digest;
    custody must not, because a corrupt original is the loss of the only copy of
    something a citation quotes. So it is reported here, loudly, and the operator
    decides — re-ingest from the source, or accept that the evidence is gone.
    """
    custody = Custody(mycelium_dir)
    if not custody.root.is_dir():
        return Check("custody", "ok", "nothing ingested yet")
    try:
        integrity = custody.verify()
    except CustodyError as error:
        return Check("custody", "fail", str(error))
    summary = f"{integrity.blobs} tier-1 blob(s), {integrity.bytes} bytes"
    if integrity.healthy:
        return Check("custody", "ok", f"{summary}; every digest verifies")
    problems = []
    if integrity.corrupt:
        problems.append(f"{len(integrity.corrupt)} blob(s) no longer match their own digest")
    if integrity.orphaned_records:
        problems.append(f"{len(integrity.orphaned_records)} record(s) whose blob is gone")
    return Check("custody", "fail", f"{summary}; " + ", ".join(problems))


def diagnose(root: Path, *, stale_after_s: float = DEFAULT_STALE_AFTER_S) -> list[Check]:
    """Run every diagnostic against the repository at `root`."""
    mycelium_dir = root / STORE_DIRNAME
    checks = [
        Check(
            "toolchain",
            "ok",
            f"mycelium {__version__} on CPython {platform.python_version()}",
        ),
        _check_config(root),
        _check_parsers(root),
        _check_custody(mycelium_dir),
    ]

    if not (mycelium_dir / STORE_FILENAME).exists():
        checks.append(Check("store", "warn", "no store yet; run `mycelium build`"))
        checks.append(_check_lock(mycelium_dir, stale_after_s))
        return checks

    store: SqliteStore | None = None
    try:
        store = SqliteStore.open(root, read_only=True)
        counts = store.counts()
        checks.append(
            Check(
                "store",
                "ok",
                f"{counts['documents']} documents, {counts['chunks']} chunks, "
                f"{counts['vectors']} vectors",
            )
        )
    except StoreError as error:
        checks.append(Check("store", "fail", str(error)))

    try:
        checks.extend(_check_snapshot(root, mycelium_dir, store))
        checks.append(_check_lock(mycelium_dir, stale_after_s))
    finally:
        if store is not None:
            store.close()
    return checks
