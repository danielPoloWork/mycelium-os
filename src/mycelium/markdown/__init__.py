# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The authored-Markdown lane: Mycelium Markdown Profile v1 → KIR (D-022).

- :mod:`mycelium.markdown.frontmatter` — the closed frontmatter contract and its
  ownership rules (spec 03 §3).
- :mod:`mycelium.markdown.profile` — the Obsidian-flavored syntax extensions
  CommonMark lacks: wikilinks, embeds, tags, callouts (spec 03 §3.1).
- :mod:`mycelium.markdown.adapter` — the token stream → KIR mapping (spec 03 §4).
"""

from mycelium.markdown.adapter import MarkdownDocument, MarkdownError, parse_markdown
from mycelium.markdown.frontmatter import (
    FIELD_OWNERS,
    Frontmatter,
    FrontmatterError,
    FrontmatterResult,
    parse_frontmatter,
    split_frontmatter,
)
from mycelium.markdown.profile import Callout, match_callout, profile_markdown_it

__all__ = [
    "FIELD_OWNERS",
    "Callout",
    "Frontmatter",
    "FrontmatterError",
    "FrontmatterResult",
    "MarkdownDocument",
    "MarkdownError",
    "match_callout",
    "parse_frontmatter",
    "parse_markdown",
    "profile_markdown_it",
    "split_frontmatter",
]
