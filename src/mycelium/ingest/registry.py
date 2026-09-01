# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Plugin resolution — pinned, ordered, and explainable (spec 05 §4.2).

The rule the whole module exists to enforce: **there is no "best available".**
A build must be reconstructible from its manifest alone, so the set of parsers is
whatever `[ingest] parsers` names, in the order it names them, and a name that
cannot be resolved is an error with a remedy in it — never a quiet fall-through
to the next one in the list. The difference shows up the day a machine without
pandoc produces a *different* corpus from CI and nobody can see why.

Ordering is how "docling first; pandoc fallback" (architecture §5) is expressed
without reintroducing negotiation: both declare DOCX, the first one listed wins,
and which one ran is recorded per document. An operator changes the answer by
changing the list, not by changing what is installed.

Three ids resolve to a built-in; anything else is looked up in the
``mycelium.plugins`` entry-point group, so a third-party parser is pinned and
loaded through exactly the same path. A plugin may not take a built-in's id:
shadowing would make two installations of the same configuration mean different
things, which is the failure this module is here to prevent.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path
from typing import Final, Self

from mycelium.ingest.connectors.file import FileConnector
from mycelium.ingest.errors import (
    PluginError,
    PluginUnavailableError,
    UnknownPluginError,
    UnsupportedMediaTypeError,
)
from mycelium.ingest.parsers import docling as docling_parser
from mycelium.ingest.parsers import markdown as markdown_parser
from mycelium.ingest.parsers import pandoc as pandoc_parser
from mycelium.ingest.parsers import pdf as pdf_parser
from mycelium.sdk.protocols import MYCELIUM_API_VERSION, Blob, Connector, Parser
from mycelium.sdk.types import KirDocument, Ulid

__all__ = [
    "BUILTIN_CONNECTORS",
    "BUILTIN_PARSERS",
    "ENTRY_POINT_GROUP",
    "PluginStatus",
    "Registry",
    "probe",
]

ENTRY_POINT_GROUP: Final = "mycelium.plugins"

BUILTIN_PARSERS: Final[Mapping[str, Callable[[], Parser]]] = {
    markdown_parser.PARSER_ID: markdown_parser.plugin,
    docling_parser.PARSER_ID: docling_parser.plugin,
    pandoc_parser.PARSER_ID: pandoc_parser.plugin,
    pdf_parser.PARSER_ID: pdf_parser.plugin,
}
"""Parser id → factory. A factory raises :class:`PluginUnavailableError` when its
engine is not installed here, which is what makes an unavailable parser a
*reportable* fact rather than an import-time crash."""

BUILTIN_CONNECTORS: Final = (FileConnector.meta.id,)
"""Connector ids the core provides. `file` needs roots, so it is constructed by
:meth:`Registry.resolve` rather than by a zero-argument factory."""


@dataclass(frozen=True, slots=True)
class PluginStatus:
    """Whether one pinned plugin can be used here, and what to do if not."""

    id: str
    available: bool
    detail: str

    def as_dict(self) -> dict[str, str | bool]:
        return {"id": self.id, "available": self.available, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class Registry:
    """The resolved, ordered plugin set a build or an ingest run uses."""

    parsers: tuple[Parser, ...]
    connectors: tuple[Connector, ...]

    @classmethod
    def resolve(
        cls,
        *,
        parsers: Sequence[str],
        connectors: Sequence[str],
        roots: Sequence[Path],
    ) -> Self:
        """Resolve the pinned ids, or raise the first failure with its remedy."""
        return cls(
            parsers=tuple(_load_parser(name) for name in _unique(parsers, "parsers")),
            connectors=tuple(
                _load_connector(name, roots) for name in _unique(connectors, "connectors")
            ),
        )

    def parser_for(self, media_type: str) -> Parser:
        """The first pinned parser declaring `media_type` — the order *is* the policy."""
        for parser in self.parsers:
            if media_type in parser.media_types:
                return parser
        pinned = ", ".join(parser.meta.id for parser in self.parsers) or "(none)"
        msg = (
            f"no pinned parser reads {media_type}; [ingest] parsers = [{pinned}]. "
            "Add a parser that declares it, or exclude the source."
        )
        raise UnsupportedMediaTypeError(msg)

    def connector_for(self, scheme: str) -> Connector:
        """The first pinned connector answering for `scheme`."""
        for connector in self.connectors:
            if scheme in connector.schemes:
                return connector
        pinned = ", ".join(connector.meta.id for connector in self.connectors) or "(none)"
        msg = f"no pinned connector answers for the {scheme or 'local path'!r} scheme ({pinned})"
        raise UnsupportedMediaTypeError(msg)

    def acquire(self, source: str, *, scheme: str = "") -> Blob:
        """Take `source` into custody through the connector pinned for its scheme."""
        return self.connector_for(scheme).acquire(source)

    def parse(self, blob: Blob, *, doc_id: Ulid) -> KirDocument:
        """Compile `blob` with the pinned parser for its media type.

        Acquisition warnings are folded into the KIR document here rather than in
        every parser: a custody problem and a fidelity problem end up in the same
        list, which is what a fidelity report needs, and no adapter can forget.
        """
        parser = self.parser_for(blob.media_type)
        document = parser.parse(blob, doc_id=doc_id)
        missing = tuple(item for item in blob.warnings if item not in document.warnings)
        if not missing:
            return document
        return document.model_copy(update={"warnings": (*missing, *document.warnings)})

    def describe(self) -> tuple[PluginStatus, ...]:
        """One line per resolved plugin — what `mycelium doctor` prints."""
        metas = [parser.meta for parser in self.parsers]
        metas.extend(connector.meta for connector in self.connectors)
        return tuple(
            PluginStatus(
                id=meta.id,
                available=True,
                detail=f"{meta.description} (engine {meta.version})",
            )
            for meta in metas
        )


def probe(parsers: Sequence[str]) -> tuple[PluginStatus, ...]:
    """Report each pinned parser's availability without raising.

    `mycelium doctor` needs to say "docling is pinned and not installed, here is
    the command" — which resolution cannot do, because resolution's contract is
    to refuse. Same ids, same factories, opposite failure mode.
    """
    statuses: list[PluginStatus] = []
    for name in parsers:
        try:
            parser = _load_parser(name)
        except PluginError as error:
            statuses.append(PluginStatus(id=name, available=False, detail=str(error)))
        else:
            statuses.append(
                PluginStatus(
                    id=name,
                    available=True,
                    detail=f"{parser.meta.description} (engine {parser.meta.version})",
                )
            )
    return tuple(statuses)


def _unique(names: Iterable[str], key: str) -> tuple[str, ...]:
    """The pinned list, refusing repeats — a duplicate makes the order ambiguous."""
    seen: list[str] = []
    for name in names:
        if name in seen:
            msg = f"[ingest] {key} names {name!r} twice; the order must be unambiguous"
            raise PluginError(msg)
        seen.append(name)
    return tuple(seen)


def _load_parser(name: str) -> Parser:
    """Resolve one parser id: built-in first, then the entry-point group."""
    factory = BUILTIN_PARSERS.get(name)
    if factory is not None:
        _refuse_shadowing(name)
        parser: Parser = factory()
    else:
        parser = _from_entry_point(name)
    if not parser.meta.supports(MYCELIUM_API_VERSION):
        msg = (
            f"plugin {name!r} declares Mycelium plugin API "
            f"[{parser.meta.api_min}, {parser.meta.api_max}) and this build speaks "
            f"{MYCELIUM_API_VERSION}"
        )
        raise PluginError(msg)
    return parser


def _load_connector(name: str, roots: Sequence[Path]) -> Connector:
    if name != FileConnector.meta.id:
        known = ", ".join(BUILTIN_CONNECTORS)
        msg = f"unknown connector {name!r}; v1 provides: {known}"
        raise UnknownPluginError(msg)
    return FileConnector(roots)


def _refuse_shadowing(name: str) -> None:
    """A plugin may not claim a built-in id.

    If it could, the same `mycelium.toml` would mean different things on two
    machines depending on what happened to be installed — the ambiguity pinned
    resolution exists to remove.
    """
    intruders = [point for point in entry_points(group=ENTRY_POINT_GROUP) if point.name == name]
    if intruders:
        providers = ", ".join(sorted(point.value for point in intruders))
        msg = (
            f"{providers} registers the id {name!r}, which is a built-in plugin; "
            "a plugin must choose an id of its own (D-026)"
        )
        raise PluginError(msg)


def _from_entry_point(name: str) -> Parser:
    """Load a third-party parser from the ``mycelium.plugins`` entry-point group."""
    matches = [point for point in entry_points(group=ENTRY_POINT_GROUP) if point.name == name]
    if not matches:
        known = ", ".join(sorted(BUILTIN_PARSERS))
        msg = (
            f"unknown parser {name!r}; built-in parsers are: {known}. A plugin must "
            f"register itself in the {ENTRY_POINT_GROUP!r} entry-point group."
        )
        raise UnknownPluginError(msg)
    if len(matches) > 1:
        providers = ", ".join(sorted(point.value for point in matches))
        msg = f"parser {name!r} is provided by more than one plugin ({providers})"
        raise PluginError(msg)
    try:
        loaded = matches[0].load()
    except Exception as error:  # noqa: BLE001 - third-party import, reported not propagated
        msg = f"parser {name!r} could not be loaded from {matches[0].value} - {error}"
        raise PluginUnavailableError(msg) from error
    built = loaded() if callable(loaded) else loaded
    if not isinstance(built, Parser):
        msg = f"the plugin registered as {name!r} does not satisfy the Parser protocol"
        raise PluginError(msg)
    return built
