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
  references into one :class:`~mycelium.sdk.types.Symbol` record per id, and
  derives the ``defines`` and ``references`` edges over it (roadmap 5.2).

Extraction is per-document and resolution is global, on the seam ADR-0018 cut
for the link graph, and for the same reason: a symbol is one row, and two
documents may define it.
"""

from mycelium.symbols.code import (
    EXTRA,
    GRAMMARS,
    MAX_FENCE_BYTES,
    CodeReference,
    FenceContents,
    Grammar,
    GrammarStatus,
    LoadedGrammar,
    extract_definitions,
    extract_references,
    grammar_fingerprint,
    grammar_for,
    grammar_statuses,
    load_grammar,
    missing_grammars,
    read_fence,
)
from mycelium.symbols.docs import (
    DOC_LANGUAGE,
    MAX_HEADING_WORDS,
    TERM_KIND,
    definition_terms,
    heading_subject,
    identifier_like,
)
from mycelium.symbols.extract import (
    CODE_FENCE,
    CODE_SPAN,
    CONSOLE_SESSION,
    DEFINITION_LIST,
    HEADING,
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
    symbol_edges,
    symbols_digest,
)
from mycelium.symbols.shell import (
    CLI_LANGUAGE,
    COMMAND_KIND,
    MAX_COMMAND_WORDS,
    SCRIPT_FENCES,
    SESSION_FENCES,
    Invocation,
    command_phrase,
    command_prefixes,
    command_run,
    named_command,
    named_heading,
    read_session,
    shell_word,
)

__all__ = [
    "CLI_LANGUAGE",
    "CODE_FENCE",
    "CODE_SPAN",
    "COMMAND_KIND",
    "CONSOLE_SESSION",
    "DEFINITION_LIST",
    "DOC_LANGUAGE",
    "EXTRA",
    "GRAMMARS",
    "HEADING",
    "MAX_COMMAND_WORDS",
    "MAX_FENCE_BYTES",
    "MAX_HEADING_WORDS",
    "SCRIPT_FENCES",
    "SESSION_FENCES",
    "TERM_KIND",
    "CodeReference",
    "Extraction",
    "FenceContents",
    "Grammar",
    "GrammarStatus",
    "Invocation",
    "LoadedGrammar",
    "SymbolRef",
    "SymbolState",
    "command_phrase",
    "command_prefixes",
    "command_run",
    "decode_symbols",
    "definition_terms",
    "describe_gaps",
    "encode_symbols",
    "extract_definitions",
    "extract_references",
    "extract_symbols",
    "grammar_fingerprint",
    "grammar_for",
    "grammar_statuses",
    "heading_subject",
    "identifier_like",
    "load_grammar",
    "missing_grammars",
    "named_command",
    "named_heading",
    "read_fence",
    "read_session",
    "resolve_symbols",
    "shell_word",
    "symbol_edges",
    "symbols_digest",
]
