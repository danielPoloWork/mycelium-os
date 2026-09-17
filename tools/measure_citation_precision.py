#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""What this project's citations actually name, per corpus and per source format.

    python tools/measure_citation_precision.py            # every built corpus
    python tools/measure_citation_precision.py --root .   # one of them

Roadmap 6.7 added `citation_precision` to the harness: the share of returned
anchors that name a heading path rather than only a position in this product's own
chunking (ADR-0122). `mycelium eval` reports it for a *run*. This reports it for a
*corpus*, over every chunk the snapshot holds, broken down by the format each
document was ingested from — which is the breakdown that makes the number
actionable, because locatedness is produced by the compiler and spent by the
retriever.

It exists because the finding it produced is one nobody would have predicted from
the aggregate: the three lanes that keep headings — authored Markdown, DOCX and
HTML — sit at 0.998-1.000, and the PDF lane sits at **0.000**, with passages three
to five times the size. That is not a ranking problem and no ranking metric can
see it (ADR-0040 said exactly this and could not put a number on it).

Nothing here writes. It reads published snapshots, so a corpus must have been
built: `mycelium build <root> --no-pin`.
"""

import argparse
import collections
import re
import statistics
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.store import STORE_DIRNAME, SqliteStore  # noqa: E402

CORPORA: tuple[Path, ...] = (
    ROOT,
    ROOT / "eval" / "corpora" / "uv-docs",
    ROOT / "eval" / "corpora" / "uv-docs-ingested",
)
"""The three corpora the gates run on (ADR-0027, ADR-0053)."""

_PROJECTED = re.compile(r"-(pdf|docx|html|md)-[0-9a-f]{8}\.md$")
"""The evidence lane names a projection `<stem>-<format>-<digest>.md` (ADR-0034),
so the format a document was ingested from is readable from its path. A document
that does not match was authored, not ingested."""


def source_format(path: str) -> str:
    """Which lane produced this document: a source format, or `authored`."""
    found = _PROJECTED.search(path)
    return found.group(1) if found else "authored"


def measure(root: Path) -> dict[str, dict[str, float]]:
    """Locatedness and passage size for every chunk in `root`'s snapshot, by format."""
    anchors: dict[str, list[tuple[bool, int]]] = collections.defaultdict(list)
    with SqliteStore.open(root, read_only=True) as store:
        for doc_id in store.document_ids():
            document = store.get_document(doc_id)
            if document is None:  # pragma: no cover - ids come from the store
                continue
            lane = source_format(document.path)
            for chunk in store.chunks_of(doc_id):
                anchors[lane].append((bool(chunk.heading_path), chunk.tokens))

    rows: dict[str, dict[str, float]] = {}
    for lane, seen in sorted(anchors.items()):
        sizes = [tokens for _, tokens in seen]
        rows[lane] = {
            "chunks": len(seen),
            "located": sum(1 for is_located, _ in seen if is_located) / len(seen),
            "median_tokens": statistics.median(sizes),
            "mean_tokens": statistics.fmean(sizes),
        }
    return rows


def report(root: Path) -> int:
    """Print one corpus's table. Returns 1 when it has no snapshot to read."""
    if not (root / STORE_DIRNAME / "CURRENT").exists():
        print(f"{_name(root)}: not built - run `mycelium build {root} --no-pin` first")
        return 1

    rows = measure(root)
    print(f"\n{_name(root)}")
    print(f"  {'lane':10} {'chunks':>7} {'located':>9} {'median':>8} {'mean':>8}")
    for lane, row in rows.items():
        print(
            f"  {lane:10} {int(row['chunks']):7} {row['located']:9.3f} "
            f"{row['median_tokens']:8.0f} {row['mean_tokens']:8.0f}"
        )
    total = sum(int(row["chunks"]) for row in rows.values())
    weighted = sum(row["located"] * int(row["chunks"]) for row in rows.values())
    print(f"  {'all':10} {total:7} {weighted / total:9.3f}")
    return 0


def _name(root: Path) -> str:
    try:
        relative = root.resolve().relative_to(ROOT)
    except ValueError:  # pragma: no cover - a corpus outside the repository
        return str(root)
    return str(relative).replace("\\", "/") if str(relative) != "." else "(this repository)"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", type=Path, help="measure one corpus instead of all three")
    args = parser.parse_args(argv)

    roots = [args.root] if args.root else list(CORPORA)
    missing = sum(report(root) for root in roots)
    if missing:
        print(f"\n{missing} corpus/corpora unbuilt; the rest are reported above")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
