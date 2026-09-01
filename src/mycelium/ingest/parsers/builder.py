# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The KIR shape every ingestion adapter must produce.

Three parsers in this package walk three different engines' outputs, and all
three have to hand the chunker the same thing the Markdown adapter hands it
(ADR-0006), or a DOCX would chunk differently from the Markdown that describes
it. The invariants are small enough to state and too easy to get subtly wrong to
leave to three implementations:

- Nodes are emitted in document order; ``ord`` is the 0-based position in that
  order and ``id`` is ``n<ord+1>`` — the spec's own naming (§4).
- Headings parent the content that follows them, and a deeper heading parents to
  the nearest shallower one. This is the nesting the chunker reads as a heading
  path; without it every ingested document would be one flat section.
- Text is normalized on the way in (spec 03 §1), because a digest over
  unnormalized text is a digest of the engine's line-ending habits.

The builder owns the ordinal, the id, and the heading stack. An adapter decides
only *what* a node is.
"""

from dataclasses import dataclass, field

from mycelium.ingest.errors import ParseError
from mycelium.ingest.safety import DEFAULT_LIMITS, Limits
from mycelium.sdk.identity import normalize_text
from mycelium.sdk.types import KirNode, NodeKind, OpaqueDisposition, SrcLocator

__all__ = ["KirBuilder"]


@dataclass
class KirBuilder:
    """Accumulates KIR nodes in document order, threading the heading stack.

    The builder is also the last line of the hostile-input defence (ADR-0033).
    :mod:`mycelium.ingest.safety` bounds what an *engine* is asked to read; those
    bounds are shape-specific and a new format arrives without them. What every
    adapter shares is this class, so the two limits that apply to any document at
    all — how many nodes it may produce and how much text they may hold — are
    enforced here, where no adapter can forget them and a new one inherits them.
    """

    limits: Limits = DEFAULT_LIMITS
    nodes: list[KirNode] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    _text_bytes: int = 0
    _headings: list[tuple[int, str]] = field(default_factory=list)

    def add(
        self,
        kind: NodeKind,
        *,
        parent: str | None = None,
        text: str | None = None,
        src: SrcLocator | None = None,
        **fields: object,
    ) -> str:
        """Append a node under `parent` (or the open heading) and return its id."""
        ordinal = len(self.nodes)
        if ordinal >= self.limits.max_nodes:
            msg = (
                f"document produces more than {self.limits.max_nodes} KIR nodes; "
                "it is refused rather than compiled (ADR-0033)"
            )
            raise ParseError(msg)
        if text is not None:
            self._text_bytes += len(text)
            if self._text_bytes > self.limits.max_text_bytes:
                msg = (
                    f"document carries more than {self.limits.max_text_bytes} bytes of node "
                    "text; it is refused rather than compiled (ADR-0033)"
                )
                raise ParseError(msg)
        node_id = f"n{ordinal + 1}"
        self.nodes.append(
            KirNode(
                id=node_id,
                kind=kind,
                text=normalize_text(text) if text is not None else None,
                parent=parent if parent is not None else self.open_heading,
                ord=ordinal,
                src=src,
                **fields,  # type: ignore[arg-type]
            )
        )
        return node_id

    def add_heading(self, level: int, text: str, *, src: SrcLocator | None = None) -> str:
        """Append a heading, closing every open heading at or below `level`."""
        while self._headings and self._headings[-1][0] >= level:
            self._headings.pop()
        node_id = self.add(NodeKind.HEADING, text=text, level=level, src=src)
        self._headings.append((level, node_id))
        return node_id

    def opaque(
        self,
        note: str,
        *,
        disposition: OpaqueDisposition,
        parent: str | None = None,
        text: str | None = None,
        media_type: str | None = None,
        src: SrcLocator | None = None,
    ) -> str:
        """Record an element KIR cannot model, with what became of it (ADR-0034).

        Shared rather than per-adapter because the fidelity report reads
        `variant` back out of these nodes: an adapter that invented its own
        spelling would silently drop out of the loss accounting, which is the one
        thing the M4 exit gate forbids.
        """
        node_id = self.add(
            NodeKind.OPAQUE,
            parent=parent,
            text=text,
            src=src,
            media_type=media_type,
            note=note,
            variant=disposition.value,
        )
        self.warn(f"{note} kept as an opaque node ({disposition.value})")
        return node_id

    @property
    def open_heading(self) -> str | None:
        """The innermost open heading, which parents the next block."""
        return self._headings[-1][1] if self._headings else None

    def warn(self, message: str) -> None:
        """Record a fidelity warning, once — repeats say nothing new."""
        if message not in self.warnings:
            self.warnings.append(message)
