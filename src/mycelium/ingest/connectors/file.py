# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The local-filesystem connector — acquisition with custody (spec 02 §5, §8).

Reading a file is one line; taking it into *custody* is this module. Three rules,
all of them from the security posture rather than from convenience (D-017):

**Roots are declared, and resolution happens before the check.** A connector
resolves paths within declared roots and no symlink escapes them (spec 02 §8).
Both halves matter: `roots/../../etc/passwd` is caught by resolving first, and a
symlink inside the tree pointing out of it is caught because resolution follows
links. The check is on the *resolved real path*, so there is no textual prefix
comparison to defeat.

**Size is bounded.** Acquisition reads into memory and the input is untrusted; a
build must be able to *quarantine* a hostile file rather than be taken down by
it. The ceiling is checked against the file's stat before any read, so an
oversized file costs a stat rather than a gigabyte.

**Directories, devices and dangling links are refused by name.** The message says
which rule was broken and which path broke it, because an operator meeting this
error is usually one typo away from a working `sources_dir`.

The URI form is `file://` — accepted with or without the scheme, because an
operator types a path and a manifest stores a URI, and both reach here.
"""

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Final
from urllib.parse import unquote, urlparse

from mycelium.ingest.errors import ConnectorError, SourceTooLargeError
from mycelium.ingest.media import EXTENSIONS, classify
from mycelium.sdk.protocols import Blob, PluginMeta

__all__ = ["CONNECTOR_ID", "DEFAULT_MAX_BYTES", "FileConnector"]

CONNECTOR_ID: Final = "file"

DEFAULT_MAX_BYTES: Final = 64 * 1024 * 1024
"""64 MiB — comfortably above any document a human wrote, far below a memory
exhaustion. It is a *default*, not a policy: the ceiling belongs in
``[ingest]`` once the loss-budget keys it sits beside are honoured (roadmap 4.3)."""


class FileConnector:
    """Acquires files from declared roots on the local filesystem."""

    meta = PluginMeta(
        id=CONNECTOR_ID,
        version="1",
        description="Local filesystem, restricted to the declared roots.",
    )

    schemes: tuple[str, ...] = ("file", "")

    def __init__(self, roots: Sequence[Path], *, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        if not roots:
            msg = "the file connector needs at least one declared root"
            raise ConnectorError(msg)
        self._roots = tuple(_resolve_root(root) for root in roots)
        self._max_bytes = max_bytes

    @property
    def roots(self) -> tuple[Path, ...]:
        """The resolved roots this connector will read inside, and nowhere else."""
        return self._roots

    def acquire(self, source: str) -> Blob:
        """Read `source` and return its bytes under custody."""
        path = self._locate(source)
        size = path.stat().st_size
        if size > self._max_bytes:
            msg = (
                f"{path} is {size} bytes, above the connector's {self._max_bytes}-byte "
                "ceiling; raise the ceiling deliberately or exclude the file"
            )
            raise SourceTooLargeError(msg)
        try:
            data = path.read_bytes()
        except OSError as error:
            msg = f"{path} cannot be read - {error}"
            raise ConnectorError(msg) from error

        claim = classify(path.name, data)
        if claim.declared is None:
            suffix = path.suffix or "(none)"
            known = ", ".join(sorted(EXTENSIONS))
            msg = f"{path}: extension {suffix} is not one Mycelium ingests ({known})"
            raise ConnectorError(msg)
        mismatch = claim.mismatch
        return Blob.of(
            data,
            media_type=claim.declared,
            source_uri=path.as_uri(),
            warnings=(mismatch,) if mismatch else (),
        )

    def _locate(self, source: str) -> Path:
        """Resolve `source` to a real path inside a declared root, or refuse it."""
        candidate = _as_path(source)
        if not candidate.is_absolute():
            candidate = self._roots[0] / candidate
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as error:
            msg = f"{candidate} cannot be resolved - {error}"
            raise ConnectorError(msg) from error

        if not any(_within(resolved, root) for root in self._roots):
            declared = ", ".join(str(root) for root in self._roots)
            msg = (
                f"{resolved} is outside the declared root(s) [{declared}]; "
                "acquisition never leaves them, symlinks included"
            )
            raise ConnectorError(msg)
        if not resolved.is_file():
            msg = f"{resolved} is not a regular file"
            raise ConnectorError(msg)
        return resolved


def _as_path(source: str) -> Path:
    """Accept both a plain path and a ``file://`` URI.

    The scheme test deliberately does not go through :func:`urlparse` alone:
    ``urlparse("D:/docs/a.md")`` reports the scheme ``"d"``, so a Windows drive
    letter would be refused as an unsupported protocol. A single-character scheme
    is a drive, and only a real ``file:`` URI is unwrapped.
    """
    if source[:5].lower() == "file:":
        parsed = urlparse(source)
        if parsed.netloc:
            msg = f"{source!r} names a host; this connector reads the local filesystem only"
            raise ConnectorError(msg)
        # `file:///C:/x` parses with a leading slash Windows must not keep.
        local = unquote(parsed.path)
        return Path(local[1:] if os.name == "nt" and local[2:3] == ":" else local)
    scheme = urlparse(source).scheme
    if len(scheme) > 1:
        msg = f"{source!r} uses the {scheme!r} scheme; this connector serves file:// only"
        raise ConnectorError(msg)
    return Path(source)


def _resolve_root(root: Path) -> Path:
    try:
        return root.resolve(strict=True)
    except OSError as error:
        msg = f"declared root {root} does not exist - {error}"
        raise ConnectorError(msg) from error


def _within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents
