# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The Markdown parser, behind the ingestion protocol.

This adapter adds no parsing: :mod:`mycelium.markdown.adapter` has compiled the
authored corpus since roadmap 2.4. What it adds is the *proof that the protocol
fits* — a parser that predates the protocol by four milestones satisfies it with
a decode and a call, which is the check that :class:`~mycelium.sdk.protocols.Parser`
describes ingestion rather than describing the two engines that arrived with it.

It is also the only parser with no optional runtime, so it is the one every CI
cell exercises on every platform.

Decoding is strict UTF-8. Markdown is text, the corpus is authored, and silently
replacing undecodable bytes would put mojibake into a citation that claims to be
verbatim — a `ParseError` and a quarantine is the honest outcome (spec 02 §5).
"""

from importlib.metadata import PackageNotFoundError, version
from typing import Final

from mycelium.ingest.errors import ParseError
from mycelium.ingest.media import MARKDOWN
from mycelium.markdown.adapter import MarkdownError, parse_markdown
from mycelium.markdown.frontmatter import FrontmatterError
from mycelium.sdk.protocols import Blob, PluginMeta
from mycelium.sdk.types import KirDocument, Ulid

__all__ = ["PARSER_ID", "MarkdownParser", "plugin"]

PARSER_ID: Final = "markdown"


def _engine_version() -> str:
    """markdown-it-py's version — the number that explains this parser's output."""
    try:
        return version("markdown-it-py")
    except PackageNotFoundError:  # pragma: no cover - a runtime dependency, always present
        return "unknown"


class MarkdownParser:
    """Compiles Mycelium Markdown Profile v1 into KIR (ADR-0006)."""

    meta = PluginMeta(
        id=PARSER_ID,
        version=_engine_version(),
        description="CommonMark plus the Mycelium Markdown Profile, via markdown-it-py.",
    )

    media_types: tuple[str, ...] = (MARKDOWN,)

    def parse(self, blob: Blob, *, doc_id: Ulid) -> KirDocument:
        try:
            text = blob.data.decode("utf-8")
        except UnicodeDecodeError as error:
            msg = f"{blob.source_uri}: not valid UTF-8 - {error}"
            raise ParseError(msg) from error
        try:
            return parse_markdown(text, doc_id=doc_id).kir
        except (MarkdownError, FrontmatterError) as error:
            msg = f"{blob.source_uri}: {error}"
            raise ParseError(msg) from error


def plugin() -> MarkdownParser:
    """Build the parser. Always available: markdown-it-py is a runtime dependency."""
    return MarkdownParser()
