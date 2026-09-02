# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Element inventories — the check the fidelity report cannot perform on itself.

The M4 exit gate is *zero silent element loss on the fixture corpus*, and roadmap
4.3 built the accounting for it: :mod:`mycelium.ingest.fidelity` counts every KIR
node as represented, degraded or lost. That report is honest about everything it
can see, and **it cannot see an element that never became a node**. A parser that
drops a table before emitting anything produces a report saying 100 % represented.
The report is computed from the KIR, so it can only ever account for what the KIR
already contains; asking it to prove nothing was lost is asking a witness to
corroborate itself.

The missing half is a **declaration**: a statement, written by a person against a
source they can read, of what that source contains. This module supplies the
other half — the observation — and the comparison between them. A difference is
either recorded with a reason or it is a defect; there is no third outcome, which
is what makes the gate mean something.

Two things are observed, and they answer different questions:

``kinds``
    How many nodes of each KIR kind the document produced. This is what a
    declaration is compared against, and it deliberately **includes reference
    nodes** (links, images, wikilinks, embeds, tags) which the fidelity report
    excludes from its denominator (ADR-0034). A vanished link is a vanished edge
    even though its text survives inside its parent block, and the loss ratio is
    the wrong instrument for noticing it.

``dispositions``
    The fidelity report's three buckets, recorded here too. Not redundant: the
    declaration says a table should exist, and the disposition says whether the
    table that exists carried its content. Either alone lets a real regression
    through.

The parser's *declared policies* travel as the KIR warnings, verbatim. They are
properties of a parser rather than per-element counts (ADR-0034), and a change to
them is exactly the kind of quiet behaviour change a committed observation exists
to surface.
"""

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Self

from mycelium.sdk.types import KirDocument, NodeKind, OpaqueDisposition

__all__ = [
    "INVENTORY_SCHEMA_VERSION",
    "ElementInventory",
    "Family",
    "FixtureEntry",
    "InventoryDifference",
    "InventoryFile",
    "compare",
    "observe",
    "read_inventory",
    "stale_reasons",
    "unexplained",
    "write_inventory",
]

INVENTORY_SCHEMA_VERSION: Final = "mycelium/ingest-inventory/v0"


@dataclass(frozen=True, slots=True)
class ElementInventory:
    """What one parse produced, in the form a reviewer reads in a diff."""

    kinds: Mapping[str, int]
    """KIR node kind → count, references included, zero-count kinds omitted."""

    dispositions: Mapping[str, int]
    """``represented`` / ``degraded`` / ``lost``, the fidelity buckets (ADR-0034)."""

    opaque: tuple[str, ...]
    """Each opaque node's note with its disposition, deduplicated and sorted.

    The note is what an element became when KIR could not model it. Sorted and
    deduplicated because the interesting fact is *which* constructs went opaque,
    not how many times; the count is already in ``kinds``.
    """

    policies: tuple[str, ...]
    """The KIR document's warnings — the parser's declared policies, verbatim."""

    def as_dict(self) -> dict[str, Any]:
        return {
            "kinds": dict(self.kinds),
            "dispositions": dict(self.dispositions),
            "opaque": list(self.opaque),
            "policies": list(self.policies),
        }


def observe(kir: KirDocument) -> ElementInventory:
    """Take the inventory of a parsed document."""
    kinds: Counter[str] = Counter()
    dispositions: Counter[str] = Counter()
    opaque: set[str] = set()

    for node in kir.nodes:
        kinds[node.kind.value] += 1
        if node.kind is not NodeKind.OPAQUE:
            continue
        disposition = node.variant or OpaqueDisposition.DEGRADED.value
        dispositions[disposition] += 1
        opaque.add(f"{node.note or 'unnamed'} ({disposition})")

    # `represented` is derived rather than counted so the three buckets always
    # sum to the fidelity report's denominator: references are not elements
    # (ADR-0034), and this module counts them in `kinds` but must not let them
    # into the disposition totals, or two artifacts describing the same parse
    # would disagree about how many elements it had.
    elements = sum(count for kind, count in kinds.items() if kind not in _REFERENCE_KIND_VALUES)
    dispositions["represented"] = (
        elements - dispositions.get("degraded", 0) - dispositions.get("lost", 0)
    )

    return ElementInventory(
        kinds=dict(sorted(kinds.items())),
        dispositions={
            name: dispositions.get(name, 0) for name in ("represented", "degraded", "lost")
        },
        opaque=tuple(sorted(opaque)),
        policies=kir.warnings,
    )


_REFERENCE_KIND_VALUES = frozenset(
    kind.value
    for kind in (
        NodeKind.LINK,
        NodeKind.IMAGE,
        NodeKind.WIKILINK,
        NodeKind.EMBED,
        NodeKind.TAG_REF,
    )
)
"""Mirrors :data:`mycelium.ingest.fidelity.REFERENCE_KINDS`, as strings.

Kept as values rather than imported as members because this module speaks the
inventory file's vocabulary, which is JSON: one conversion, at the boundary, so a
kind name means the same thing in the file and in the comparison.
"""


@dataclass(frozen=True, slots=True)
class InventoryDifference:
    """One kind on which an observation and a declaration disagree."""

    kind: str
    declared: int
    observed: int
    reason: str | None

    @property
    def explained(self) -> bool:
        """Whether a human recorded why this route differs."""
        return self.reason is not None

    def render(self) -> str:
        detail = f"declared {self.declared}, observed {self.observed}"
        if self.reason is None:
            return f"{self.kind}: {detail} — no reason recorded"
        return f"{self.kind}: {detail} — {self.reason}"


def compare(
    declared: Mapping[str, int],
    observed: Mapping[str, int],
    *,
    deviations: Mapping[str, str] | None = None,
) -> tuple[InventoryDifference, ...]:
    """Every kind on which `observed` differs from `declared`, explained or not.

    `deviations` maps a kind to the reason a particular route legitimately differs
    on it — docling nesting a DOCX table inside the preceding list, a format that
    cannot express footnotes. Recording the reason is the whole mechanism: it
    turns a difference from something a test tolerates into something a reviewer
    approved, and a difference nobody approved fails the gate.

    Returns differences in kind order, explained and unexplained alike; the caller
    decides which are fatal. Both are worth returning: an *explained* deviation
    that has since disappeared is also news — the reason is stale and the file
    should stop claiming it.
    """
    excuses = deviations or {}
    kinds = sorted(set(declared) | set(observed))
    return tuple(
        InventoryDifference(
            kind=kind,
            declared=declared.get(kind, 0),
            observed=observed.get(kind, 0),
            reason=excuses.get(kind),
        )
        for kind in kinds
        if declared.get(kind, 0) != observed.get(kind, 0)
    )


# ---------------------------------------------------------------------------
# The committed corpus file
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Family:
    """One source document and the human's count of what is in it.

    A family exists because the same document reaches several parsers: one
    Markdown source, rendered by pandoc into DOCX, HTML and reStructuredText, is
    four fixtures and **one** declaration. Declaring per route would multiply the
    hand-authored numbers by four and turn the reviewer's job into checking a
    generator instead of reading a document.
    """

    source: str
    """Path of the readable source, relative to the fixture root — what a reviewer opens."""

    note: str
    """One line on how the numbers were arrived at, for the reviewer who checks them."""

    declared: Mapping[str, int]
    """KIR node kind → how many the source contains. Hand-authored; never generated."""

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "note": self.note,
            "declared": dict(sorted(self.declared.items())),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        return cls(
            source=str(data["source"]),
            note=str(data["note"]),
            declared={str(k): int(v) for k, v in dict(data.get("declared") or {}).items()},
        )


@dataclass(frozen=True, slots=True)
class FixtureEntry:
    """One file in the corpus: what it belongs to, and what came out of it."""

    path: str
    family: str
    deviations: Mapping[str, str] = field(default_factory=dict)
    """Kinds on which *this route* legitimately differs from its family's
    declaration, each with the reason. Hand-authored: a deviation is an approval,
    and a generator cannot approve anything."""

    parser: str | None = None
    """Which parser actually ran — generated, and asserted, so a change to the pinned
    order shows up here rather than silently changing what the corpus tests."""

    inventory: ElementInventory | None = None
    """The observation. Generated."""

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "family": self.family,
            "deviations": dict(sorted(self.deviations.items())),
            "parser": self.parser,
            "inventory": self.inventory.as_dict() if self.inventory is not None else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        raw = data.get("inventory")
        inventory = None
        if raw is not None:
            inventory = ElementInventory(
                kinds={str(k): int(v) for k, v in dict(raw.get("kinds") or {}).items()},
                dispositions={
                    str(k): int(v) for k, v in dict(raw.get("dispositions") or {}).items()
                },
                opaque=tuple(str(item) for item in raw.get("opaque") or ()),
                policies=tuple(str(item) for item in raw.get("policies") or ()),
            )
        return cls(
            path=str(data["path"]),
            family=str(data["family"]),
            deviations={str(k): str(v) for k, v in dict(data.get("deviations") or {}).items()},
            parser=None if data.get("parser") is None else str(data["parser"]),
            inventory=inventory,
        )


@dataclass(frozen=True, slots=True)
class InventoryFile:
    """The corpus's committed inventory: the declarations, and the last observation.

    Half of this file is written by a person and half by a tool, and the split is
    load-bearing. ``families[*].declared`` and ``fixtures[*].deviations`` are the
    human's statement — what the source contains, and which route differences are
    approved. ``fixtures[*].parser`` and ``fixtures[*].inventory`` are the
    machine's. :meth:`refreshed` regenerates the second half and **never touches
    the first**, so re-blessing after an intentional parser change cannot quietly
    rewrite the claim that change is being checked against.
    """

    families: Mapping[str, Family]
    fixtures: tuple[FixtureEntry, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": INVENTORY_SCHEMA_VERSION,
            "families": {name: family.as_dict() for name, family in sorted(self.families.items())},
            "fixtures": [entry.as_dict() for entry in self.fixtures],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        version = data.get("schema_version")
        if version != INVENTORY_SCHEMA_VERSION:
            msg = (
                f"inventory file declares schema {version!r}; this build reads "
                f"{INVENTORY_SCHEMA_VERSION!r}"
            )
            raise ValueError(msg)
        return cls(
            families={
                str(name): Family.from_dict(body)
                for name, body in dict(data.get("families") or {}).items()
            },
            fixtures=tuple(FixtureEntry.from_dict(entry) for entry in data.get("fixtures") or ()),
        )

    def refreshed(self, observations: Mapping[str, tuple[str, ElementInventory]]) -> Self:
        """A copy carrying fresh observations, with every human field preserved."""
        return type(self)(
            families=self.families,
            fixtures=tuple(
                FixtureEntry(
                    path=entry.path,
                    family=entry.family,
                    deviations=entry.deviations,
                    parser=observations[entry.path][0] if entry.path in observations else None,
                    inventory=observations[entry.path][1] if entry.path in observations else None,
                )
                for entry in self.fixtures
            ),
        )

    def family_of(self, entry: FixtureEntry) -> Family:
        """The declaration `entry` is measured against."""
        family = self.families.get(entry.family)
        if family is None:
            msg = f"fixture {entry.path!r} names family {entry.family!r}, which is not declared"
            raise ValueError(msg)
        return family


def read_inventory(path: Path) -> InventoryFile:
    """Read the committed inventory."""
    return InventoryFile.from_dict(json.loads(path.read_text(encoding="utf-8")))


def write_inventory(path: Path, inventory: InventoryFile) -> None:
    """Write it back: sorted keys, LF, trailing newline — reviewable in a diff.

    Fixture order is the file's own rather than sorted: the corpus reads as a list
    a person curated, and reordering it on every re-bless would put churn in the
    diff this gate exists to make readable.
    """
    text = json.dumps(inventory.as_dict(), indent=2, sort_keys=True, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def unexplained(differences: Sequence[InventoryDifference]) -> tuple[InventoryDifference, ...]:
    """The differences nobody approved — the ones that fail the gate."""
    return tuple(item for item in differences if not item.explained)


def stale_reasons(
    entry: FixtureEntry, differences: Sequence[InventoryDifference]
) -> tuple[str, ...]:
    """Deviation reasons the file still records for kinds that now agree.

    A stale excuse is not harmless. It is a reviewer's approval left standing over
    behaviour that has since changed, which is how a gate's exception list grows
    until the gate means nothing.
    """
    differing = {item.kind for item in differences}
    return tuple(sorted(kind for kind in entry.deviations if kind not in differing))
