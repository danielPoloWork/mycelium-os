# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The element-inventory gate (roadmap 4.7): zero *silent* element loss.

The M4 exit gate's words are "every element represented / opaque /
dropped-by-policy / failed-and-reported", and roadmap 4.3 built the accounting for
it. The accounting alone cannot close the gate: a fidelity report is computed from
the KIR, so a parser that drops a table before emitting anything produces a report
saying 100 % represented. The report can only account for what it can see.

So the corpus carries a **declaration** — what a person counted in a source they
can read — and this module compares it with what each engine produced. Every
difference is either recorded in the file with a reason a reviewer approved, or
it fails the gate. There is no third outcome; that is what makes it a gate rather
than a report.

Two checks run against the same committed file, and they catch different things:

- the *declaration* check catches an element that vanished, which is the exit
  gate's own words;
- the *observation* check catches any other change in what a parser produces —
  the golden discipline (ADR-0012), so a change in behaviour is reviewed rather
  than absorbed.
"""

import json
import shutil
from pathlib import Path

import pytest

from mycelium.ingest import Registry, probe
from mycelium.ingest.inventory import (
    INVENTORY_SCHEMA_VERSION,
    ElementInventory,
    compare,
    observe,
    read_inventory,
    stale_reasons,
    unexplained,
    write_inventory,
)
from mycelium.ingest.parsers import pandoc as pandoc_parser
from mycelium.sdk.types import KirDocument, KirNode, NodeKind, OpaqueDisposition

FIXTURES = Path(__file__).parent / "fixtures" / "ingest"
INVENTORY = FIXTURES / "inventory.json"
DOC_ID = "01J1ZC8Q4R6XKQ3F0V9T8B2M7N"

HAVE_PANDOC = shutil.which(pandoc_parser.DEFAULT_EXECUTABLE) is not None
needs_pandoc = pytest.mark.skipif(not HAVE_PANDOC, reason="the pandoc binary is not on PATH")


@pytest.fixture(scope="module")
def registry() -> Registry:
    statuses = probe(("markdown", "docling", "pandoc", "pdf"))
    available = [status.id for status in statuses if status.available]
    return Registry.resolve(parsers=available, connectors=["file"], roots=[FIXTURES])


def observed(registry: Registry, path: str) -> tuple[str, ElementInventory]:
    blob = registry.acquire(str(FIXTURES / path))
    parser = registry.parser_for(blob.media_type)
    return parser.meta.id, observe(registry.parse(blob, doc_id=DOC_ID))


def corpus() -> list[str]:
    return [entry.path for entry in read_inventory(INVENTORY).fixtures]


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


@pytest.mark.inventory
@needs_pandoc
@pytest.mark.parametrize("path", corpus())
def test_no_element_is_lost_without_a_recorded_reason(registry: Registry, path: str) -> None:
    """The M4 exit gate, per fixture.

    A parser that stops emitting an element fails here with the kind named — and
    it fails whether or not the loss shows up in the fidelity report, which is the
    whole reason the declaration exists.
    """
    committed = read_inventory(INVENTORY)
    entry = next(item for item in committed.fixtures if item.path == path)
    family = committed.family_of(entry)
    _, inventory = observed(registry, path)

    differences = compare(family.declared, inventory.kinds, deviations=entry.deviations)
    missing = unexplained(differences)
    assert not missing, (
        f"{path}: element(s) unaccounted for against {family.source}:\n  "
        + "\n  ".join(item.render() for item in missing)
        + "\n\nEither the parser lost something, or the difference is legitimate and "
        "belongs in this fixture's `deviations` with the reason."
    )


@pytest.mark.inventory
@needs_pandoc
@pytest.mark.parametrize("path", corpus())
def test_no_recorded_reason_outlives_the_difference_it_explains(
    registry: Registry, path: str
) -> None:
    """A stale excuse is a reviewer's approval left standing over changed behaviour."""
    committed = read_inventory(INVENTORY)
    entry = next(item for item in committed.fixtures if item.path == path)
    family = committed.family_of(entry)
    _, inventory = observed(registry, path)

    stale = stale_reasons(entry, compare(family.declared, inventory.kinds))
    assert not stale, (
        f"{path}: deviations record a reason for {list(stale)}, which now agree with "
        f"{family.source}. Delete the entry: the difference it explains is gone."
    )


@pytest.mark.inventory
@needs_pandoc
@pytest.mark.parametrize("path", corpus())
def test_each_fixture_produces_what_the_inventory_records(registry: Registry, path: str) -> None:
    """The golden half: any change in what a parser produces is reviewed, not absorbed."""
    committed = read_inventory(INVENTORY)
    entry = next(item for item in committed.fixtures if item.path == path)
    parser, inventory = observed(registry, path)

    assert entry.parser == parser, (
        f"{path} is now read by {parser!r} rather than {entry.parser!r}. If the pinned "
        "order changed on purpose, run `python tools/update_ingest_inventories.py`."
    )
    assert entry.inventory is not None, f"{path} has no committed inventory yet"
    assert entry.inventory.as_dict() == inventory.as_dict(), (
        f"{path}: the parser produces different elements than the committed inventory. "
        "If that is intended, run `python tools/update_ingest_inventories.py` and put the "
        "diff in the PR."
    )


@pytest.mark.inventory
def test_every_corpus_fixture_is_in_the_inventory() -> None:
    """A fixture nobody declared is a fixture nobody checks.

    Without this, adding a file to the corpus directory and forgetting to declare
    it would leave it silently untested — which is the same failure mode, one
    level up, that the gate itself exists to catch.
    """
    declared = {entry.path for entry in read_inventory(INVENTORY).fixtures}
    on_disk = {
        path.relative_to(FIXTURES).as_posix()
        for path in FIXTURES.rglob("*")
        if path.is_file() and path.suffix not in {".py", ".json", ".png"}
    }
    # The hostile suite is the *other* half of the M4 exit gate: those files are
    # declared by `test_ingest_hostile.py`, which asserts each one is refused
    # rather than parsed, so an inventory of their elements would be a category error.
    on_disk = {path for path in on_disk if not path.startswith("hostile/")}
    assert on_disk == declared, (
        "the corpus directory and inventory.json disagree; "
        f"undeclared: {sorted(on_disk - declared)}, missing: {sorted(declared - on_disk)}"
    )


# ---------------------------------------------------------------------------
# The gate can fail — proved, not assumed (the ADR-0012 discipline)
# ---------------------------------------------------------------------------


def kir_of(*kinds: NodeKind) -> KirDocument:
    return KirDocument(
        doc_id=DOC_ID,
        source_digest="sha256:" + "0" * 64,
        nodes=tuple(
            KirNode(
                id=f"n{index + 1}",
                kind=kind,
                ord=index,
                text="x",
                level=1 if kind is NodeKind.HEADING else None,
            )
            for index, kind in enumerate(kinds)
        ),
    )


def test_a_vanished_element_is_an_unexplained_difference() -> None:
    # The mutation the gate exists for: a parser that stops emitting tables.
    declared = {"heading": 1, "table": 1}
    inventory = observe(kir_of(NodeKind.HEADING))
    missing = unexplained(compare(declared, inventory.kinds))
    assert [item.kind for item in missing] == ["table"]
    assert "declared 1, observed 0" in missing[0].render()


def test_a_recorded_reason_turns_a_difference_into_an_approval() -> None:
    declared = {"heading": 1, "table": 1}
    inventory = observe(kir_of(NodeKind.HEADING))
    reason = "this format has no tables"
    differences = compare(declared, inventory.kinds, deviations={"table": reason})
    assert not unexplained(differences)
    assert reason in differences[0].render()


def test_an_element_that_appeared_from_nowhere_also_fails() -> None:
    # Symmetry matters: a parser inventing elements is as much a defect as one
    # losing them, and a one-sided check would call the invention a pass.
    inventory = observe(kir_of(NodeKind.HEADING, NodeKind.TABLE))
    missing = unexplained(compare({"heading": 1}, inventory.kinds))
    assert [item.kind for item in missing] == ["table"]


# ---------------------------------------------------------------------------
# The observation itself
# ---------------------------------------------------------------------------


def test_reference_nodes_count_as_kinds_but_not_as_elements() -> None:
    """A vanished link is a vanished edge, and the loss ratio cannot see it.

    The fidelity report excludes reference nodes from its denominator (ADR-0034)
    because their text lives in their parent block. The inventory counts them
    anyway — in `kinds`, never in `dispositions` — so the two artifacts agree on
    how many elements a parse had while the gate still notices a lost link.
    """
    inventory = observe(kir_of(NodeKind.PARAGRAPH, NodeKind.LINK, NodeKind.IMAGE))
    assert inventory.kinds == {"image": 1, "link": 1, "paragraph": 1}
    assert inventory.dispositions == {"represented": 1, "degraded": 0, "lost": 0}


def test_an_opaque_node_is_counted_under_its_own_disposition() -> None:
    document = KirDocument(
        doc_id=DOC_ID,
        source_digest="sha256:" + "0" * 64,
        nodes=(
            KirNode(id="n1", kind=NodeKind.PARAGRAPH, ord=0, text="kept"),
            KirNode(
                id="n2",
                kind=NodeKind.OPAQUE,
                ord=1,
                note="a scanned page",
                variant=OpaqueDisposition.LOST.value,
            ),
            KirNode(
                id="n3",
                kind=NodeKind.OPAQUE,
                ord=2,
                text="raw",
                note="a raw block",
                variant=OpaqueDisposition.DEGRADED.value,
            ),
        ),
        warnings=("a policy this parser declares",),
    )
    inventory = observe(document)
    assert inventory.dispositions == {"represented": 1, "degraded": 1, "lost": 1}
    assert inventory.opaque == ("a raw block (degraded)", "a scanned page (lost)")
    assert inventory.policies == ("a policy this parser declares",)


def test_the_inventory_file_round_trips(tmp_path: Path) -> None:
    original = read_inventory(INVENTORY)
    path = tmp_path / "inventory.json"
    write_inventory(path, original)
    assert read_inventory(path) == original
    assert path.read_text(encoding="utf-8").endswith("}\n")


def test_a_foreign_schema_version_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps({"schema_version": "other/v9"}), encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        read_inventory(path)


def test_the_committed_file_declares_this_schema() -> None:
    data = json.loads(INVENTORY.read_text(encoding="utf-8"))
    assert data["schema_version"] == INVENTORY_SCHEMA_VERSION


def test_re_blessing_never_rewrites_the_human_half() -> None:
    """The asymmetry the whole design rests on.

    A tool that could rewrite a declaration would let a regression re-bless
    itself: the parser drops a table, the tool records that it drops a table, and
    the gate agrees with the defect.
    """
    committed = read_inventory(INVENTORY)
    entry = committed.fixtures[0]
    replaced = committed.refreshed(
        {entry.path: ("someone-else", observe(kir_of(NodeKind.PARAGRAPH)))}
    )
    assert replaced.families == committed.families
    assert replaced.fixtures[0].deviations == entry.deviations
    assert replaced.fixtures[0].parser == "someone-else"


def test_a_fixture_the_tool_could_not_observe_keeps_nothing_it_did_not_measure() -> None:
    committed = read_inventory(INVENTORY)
    refreshed = committed.refreshed({})
    assert all(entry.inventory is None for entry in refreshed.fixtures)
    assert refreshed.families == committed.families
