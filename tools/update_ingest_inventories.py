#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Re-bless the ingestion corpus's element inventories after an intended change.

    python tools/update_ingest_inventories.py

The gate fails whenever a parser produces a different set of elements than the
committed inventory records. That is the point: the diff this tool produces *is*
the behaviour change, and reviewing it is how a parser change gets approved
rather than absorbed.

The tool regenerates only the machine's half of the file — which parser ran, and
what it produced. `families[*].declared` (what a person counted in the source)
and `fixtures[*].deviations` (which route differences a person approved, and why)
are never touched. That asymmetry is the whole design: a tool that could rewrite
the claim would let a regression re-bless itself.

A fixture whose parser is unavailable here is left exactly as it was, and named
in the output, so running this without pandoc cannot silently blank half the
corpus.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.ingest import Registry  # noqa: E402
from mycelium.ingest.errors import IngestError  # noqa: E402
from mycelium.ingest.inventory import (  # noqa: E402
    ElementInventory,
    observe,
    read_inventory,
    write_inventory,
)

FIXTURES = ROOT / "tests" / "fixtures" / "ingest"
INVENTORY = FIXTURES / "inventory.json"
PARSERS = ("markdown", "docling", "pandoc", "pdf")
DOC_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"
"""A fixed document id: identity belongs to the caller (ADR-0032), and a fresh
ULID per run would put a different digest in the file on every re-bless."""


def main() -> int:
    committed = read_inventory(INVENTORY)
    registry, missing = _resolve()
    if missing:
        print(f"parsers unavailable here, their fixtures left untouched: {', '.join(missing)}")

    # Start from what is already committed. Keeping the previous observation for
    # a fixture that cannot run here is the safe answer: blanking it would turn
    # "I could not run this on this machine" into "this fixture now produces
    # nothing", which is a claim nobody made.
    observations: dict[str, tuple[str, ElementInventory]] = {
        entry.path: (entry.parser, entry.inventory)
        for entry in committed.fixtures
        if entry.parser is not None and entry.inventory is not None
    }
    skipped: list[str] = []
    for entry in committed.fixtures:
        try:
            blob = registry.acquire(str(FIXTURES / entry.path))
            parser = registry.parser_for(blob.media_type)
            observations[entry.path] = (
                parser.meta.id,
                observe(registry.parse(blob, doc_id=DOC_ID)),
            )
        except IngestError as error:
            skipped.append(f"{entry.path} ({error})")

    refreshed = committed.refreshed(observations)
    if skipped:
        print("not re-observed: " + "; ".join(skipped))

    before = INVENTORY.read_text(encoding="utf-8")
    write_inventory(INVENTORY, refreshed)
    after = INVENTORY.read_text(encoding="utf-8")
    if before == after:
        print(f"inventories unchanged: {INVENTORY.relative_to(ROOT)}")
        return 0
    print(f"inventories updated: {INVENTORY.relative_to(ROOT)}")
    print("Review the diff — it is the parser change, and it belongs in the PR body.")
    return 0


def _resolve() -> tuple[Registry, list[str]]:
    """Resolve every parser that can run here, and name the ones that cannot."""
    from mycelium.ingest import probe

    statuses = probe(PARSERS)
    available = [status.id for status in statuses if status.available]
    missing = [status.id for status in statuses if not status.available]
    return (
        Registry.resolve(parsers=available, connectors=["file"], roots=[FIXTURES]),
        missing,
    )


if __name__ == "__main__":
    raise SystemExit(main())
