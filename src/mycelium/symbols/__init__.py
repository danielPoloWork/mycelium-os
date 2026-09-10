# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Symbol extraction: what the documents define, and where (roadmap 5.1, ADR-0073).

The ``extract`` stage of spec 02 §4.1's DAG, for the ``symbols`` artifact:

- :mod:`mycelium.symbols.code` — code fences, through each grammar's own
  tree-sitter tags query, qualified by nesting;
- :mod:`mycelium.symbols.docs` — the definition syntax documentation uses:
  definition lists, and headings whose text is an identifier;
- :mod:`mycelium.symbols.extract` — the per-document stage, cached with the
  document;
- :mod:`mycelium.symbols.resolve` — the global pass that folds every document's
  references into one :class:`~mycelium.sdk.types.Symbol` record per id.

Extraction is per-document and resolution is global, on the seam ADR-0018 cut
for the link graph, and for the same reason: a symbol is one row, and two
documents may define it.
"""

from mycelium.symbols.code import (
    EXTRA,
    GRAMMARS,
    MAX_FENCE_BYTES,
    Grammar,
    GrammarStatus,
    LoadedGrammar,
    extract_definitions,
    grammar_fingerprint,
    grammar_for,
    grammar_statuses,
    load_grammar,
    missing_grammars,
)
from mycelium.symbols.docs import DOC_LANGUAGE, TERM_KIND, definition_terms, heading_term
from mycelium.symbols.extract import (
    Extraction,
    SymbolRef,
    decode_symbols,
    encode_symbols,
    extract_symbols,
)
from mycelium.symbols.resolve import (
    SymbolState,
    describe_gaps,
    resolve_symbols,
    symbols_digest,
)

__all__ = [
    "DOC_LANGUAGE",
    "EXTRA",
    "GRAMMARS",
    "MAX_FENCE_BYTES",
    "TERM_KIND",
    "Extraction",
    "Grammar",
    "GrammarStatus",
    "LoadedGrammar",
    "SymbolRef",
    "SymbolState",
    "decode_symbols",
    "definition_terms",
    "describe_gaps",
    "encode_symbols",
    "extract_definitions",
    "extract_symbols",
    "grammar_fingerprint",
    "grammar_for",
    "grammar_statuses",
    "heading_term",
    "load_grammar",
    "missing_grammars",
    "resolve_symbols",
    "symbols_digest",
]
