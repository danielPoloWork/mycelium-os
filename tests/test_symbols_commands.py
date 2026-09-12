# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Commands as symbols (roadmap 5.23, spec 03 §2, spec 04 §2, ADR-0094).

The claims under test:

**A command is what the corpus both demonstrates and names.** A prompt line
offers every prefix of its command run; a code span or a shell-word heading
names one; resolution keeps the intersection and nothing else, so
`uv add requests` (demonstrated, never named) and `uv cache prune` (named, never
demonstrated) are not symbols and `uv add` is.

**Both syntaxes are read where they are written.** KIR now carries a node's
inline code spans beside its flattened text, in the Markdown adapter and the
pandoc adapter alike, and a console fence is read by its prompt lines — or, for
a promptless script fence, by its lines.

**A command-shaped query is looked up whole and exactly**, in the `cli` language
alone — never by a prefix of itself; an identifier, a question and a casefolded
identifier are not looked up as commands at all.

**The sites are documentation.** `defined_in` is the first demonstration in
path order; `doc_refs` holds every chunk that demonstrates or names the command;
a document that only names it gets one `references` edge.
"""

from collections.abc import Mapping
from pathlib import Path

import pytest

from mycelium.build import build
from mycelium.chunking import ChunkingPolicy, chunk_document
from mycelium.markdown import parse_markdown
from mycelium.planner import STOPWORDS, plan_query
from mycelium.retrieval import (
    SYMBOL_PROMOTE_LANGUAGES,
    retrieval_identity,
    symbol_lookup_ids,
)
from mycelium.sdk.types import EdgeType, NodeKind
from mycelium.store import SqliteStore
from mycelium.symbols import (
    CLI_LANGUAGE,
    CODE_SPAN,
    COMMAND_KIND,
    CONSOLE_SESSION,
    HEADING,
    MAX_COMMAND_WORDS,
    command_phrase,
    command_prefixes,
    command_run,
    extract_symbols,
    named_command,
    named_heading,
    read_session,
    resolve_symbols,
    symbol_edges,
)

DOC_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


def extract(markdown: str, path: str = "a.md"):  # type: ignore[no-untyped-def]
    parsed = parse_markdown(markdown, doc_id=DOC_ID)
    chunks = chunk_document(parsed.kir, doc_path=path, policy=ChunkingPolicy())
    return extract_symbols(parsed.kir, chunks, doc_path=path)


def repo(tmp_path: Path, files: Mapping[str, str], name: str = "repo") -> Path:
    root = tmp_path / name
    for relative, text in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    return root


# ---------------------------------------------------------------------------
# The shell syntax
# ---------------------------------------------------------------------------


def test_a_console_fence_is_read_by_its_prompt_lines() -> None:
    fence = (
        "$ uv tool install ruff==0.5.0\n"
        "Resolved 1 package in 12ms\n"
        "$ uv tool install --with mkdocs-material mkdocs\n"
        "% uv lock --check\n"
        "PS C:\\> uv venv .venv\n"
        "> uv init example-app\n"
        "not a prompt line\n"
    )
    runs = [invocation.run for invocation in read_session(fence, "console")]
    # `example-app` is a shell word by rule, so the run keeps it: which prefix
    # is the command and which an argument is the corpus's call at resolution.
    assert runs == [
        ("uv", "tool", "install"),
        ("uv", "tool", "install"),
        ("uv", "lock"),
        ("uv", "venv"),
        ("uv", "init", "example-app"),
    ]
    rows = [invocation.row for invocation in read_session(fence, "console")]
    assert rows == [0, 2, 3, 4, 5]


def test_a_promptless_script_fence_is_read_line_by_line() -> None:
    script = (
        "# comment\n"
        "FOO=bar\n"
        "mycelium init              # scaffold knowledge/\n"
        "mycelium build --no-pin\n"
        "uv run pytest -q \\\n"
        "  tests/\n"
        "  indented continuation\n"
        "| piped\n"
    )
    runs = [invocation.run for invocation in read_session(script, "bash")]
    assert runs == [("mycelium", "init"), ("mycelium", "build"), ("uv", "run", "pytest")]


def test_a_prompt_inside_a_script_fence_makes_it_a_session() -> None:
    text = "$ mycelium build\npublished snapshot 01J\nmycelium doctor\n"
    assert [i.run for i in read_session(text, "bash")] == [("mycelium", "build")]


@pytest.mark.parametrize("lang", ["python", "toml", "yaml", "rust", "json"])
def test_a_fence_in_another_language_demonstrates_nothing(lang: str) -> None:
    assert read_session("$ uv sync\n", lang) == ()


def test_text_and_untagged_fences_count_only_with_a_prompt() -> None:
    assert [i.run for i in read_session("$ uv sync\n", "text")] == [("uv", "sync")]
    assert [i.run for i in read_session("$ uv sync\n", None)] == [("uv", "sync")]
    assert read_session("uv sync\n", "text") == ()


def test_a_command_run_stops_at_the_first_token_that_is_not_a_shell_word() -> None:
    assert command_run(["uv", "python", "pin", "3.11"]) == ("uv", "python", "pin")
    assert command_run(["uv", "export", "--format", "requirements.txt"]) == ("uv", "export")
    assert command_run(["uv", "add", "'httpx>0.1'"]) == ("uv", "add")
    assert command_run(["Get-ChildItem", "-Recurse"]) == ()
    assert command_run(["UV_INDEX=x", "uv", "sync"]) == ()
    assert command_run(["a", "b", "c", "d", "e", "f", "g"]) == ("a", "b", "c", "d", "e")
    assert len(command_run(["a"] * 9)) == MAX_COMMAND_WORDS


def test_every_prefix_of_a_run_is_offered() -> None:
    assert command_prefixes(("uv", "tool", "install")) == ("uv", "uv tool", "uv tool install")
    assert command_prefixes(()) == ()


@pytest.mark.parametrize(
    ("span", "run"),
    [
        ("uv tool install", ("uv", "tool", "install")),
        ("uv lock --check", ("uv", "lock")),
        ("uv tool install ruff", ("uv", "tool", "install", "ruff")),
        ("uvx", ("uvx",)),
        ("SqliteStore", ()),
        ("pyproject.toml", ()),
        ("--no-pin", ()),
        ("", ()),
    ],
)
def test_a_code_span_names_its_command_run(span: str, run: tuple[str, ...]) -> None:
    assert named_command(span) == run


@pytest.mark.parametrize(
    ("heading", "run"),
    [
        ("pip check", ("pip", "check")),
        ("uv tool install", ("uv", "tool", "install")),
        ("Installing tools", ()),
        ("uv.lock", ()),
        ("3.3 mycelium_neighbors", ()),
        ("", ()),
    ],
)
def test_a_heading_names_a_command_only_when_it_is_one(heading: str, run: tuple[str, ...]) -> None:
    assert named_heading(heading) == run


# ---------------------------------------------------------------------------
# The query side: spec 04 §2, amended for a language whose separator is a space
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "phrase"),
    [
        ("uv tool install", "uv tool install"),
        ("uv lock --check", "uv lock"),
        ("uv python pin 3.11", "uv python pin"),
        ("uvx", "uvx"),
        ("uv tool install?", "uv tool install"),
        ('"uv tool install"', "uv tool install"),
        ("`uv lock --check`", "uv lock"),
        ("how do I install a tool", None),
        ("what is in pyproject.toml", None),
        ("SqliteStore", None),
        ("UV tool install", None),
        ("uv lock the project", None),
        ("BEGIN IMMEDIATE transaction", None),
        ("", None),
    ],
)
def test_a_command_shaped_or_quoted_query_names_its_command_whole(
    query: str, phrase: str | None
) -> None:
    assert command_phrase(query, stopwords=STOPWORDS) == phrase


def test_a_function_word_makes_a_query_a_question_not_a_command() -> None:
    assert command_phrase("install a tool", stopwords=STOPWORDS) is None
    assert command_phrase("install tool", stopwords=STOPWORDS) == "install tool"
    assert command_phrase("install a tool", stopwords=()) == "install a tool"


def test_the_lookup_asks_for_the_whole_phrase_in_the_cli_language_alone() -> None:
    assert symbol_lookup_ids("uv tool install") == ("sym:cli:uv tool install",)
    # Never a prefix: the parent command is a different thing from the one asked about.
    assert "sym:cli:uv" not in symbol_lookup_ids("uv python pin")
    # An identifier-like token still crosses every language, and never `cli` by phrase.
    assert "sym:cli:pyproject.toml" not in symbol_lookup_ids("pyproject.toml")
    assert symbol_lookup_ids("how do I install a tool") == ()


@pytest.mark.parametrize(
    ("query", "rules"),
    [
        ("uv tool install", ("command",)),
        ("uv lock --check", ("command",)),
        ("uvx", ("command",)),
        ('"uv tool install"', ("identifier",)),
        ("SqliteStore", ("identifier",)),
        ("how do I install a tool", ("natural-language",)),
        ("what does uv sync depend on", ("relationship",)),
    ],
)
def test_the_planner_reports_the_command_rule_for_a_bare_command(
    query: str, rules: tuple[str, ...]
) -> None:
    plan = plan_query(query)
    assert plan.rules == rules
    if rules == ("command",):
        assert plan.asks_for("symbol")
        assert "command-shaped query" in plan.why


def test_promotion_ships_for_commands_only_and_is_fingerprinted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reading an operator gets on turning the leg on is the one that was
    measured to do something (ADR-0094) — and moving it moves the fingerprint."""
    assert SYMBOL_PROMOTE_LANGUAGES == (CLI_LANGUAGE,)
    before = retrieval_identity()
    monkeypatch.setattr("mycelium.retrieval.SYMBOL_PROMOTE_LANGUAGES", ())
    assert retrieval_identity() != before, "promotion by language decides a ranking"


# ---------------------------------------------------------------------------
# KIR carries the spans the flattening erased
# ---------------------------------------------------------------------------


def test_kir_nodes_carry_their_inline_code_spans_in_order() -> None:
    parsed = parse_markdown(
        "# Doc\n\nRun `uv tool install` or `uv lock --check`; see `pyproject.toml`.\n\n"
        "- item with `mycelium build`\n\n| a | b |\n|---|---|\n| `x y` | z |\n\n"
        "> [!note] Title\n> body `git status`\n\n## `pip check`\n",
        doc_id=DOC_ID,
    )
    by_kind = {}
    for node in parsed.kir.nodes:
        if node.spans:
            by_kind.setdefault(node.kind, []).append(node.spans)
    assert by_kind[NodeKind.PARAGRAPH][0] == (
        "uv tool install",
        "uv lock --check",
        "pyproject.toml",
    )
    assert by_kind[NodeKind.LIST_ITEM] == [("mycelium build",)]
    assert by_kind[NodeKind.TABLE_CELL] == [("x y",)]
    assert ("git status",) in by_kind[NodeKind.PARAGRAPH]
    assert by_kind[NodeKind.HEADING] == [("pip check",)]
    # The text is what it always was: flattened, backticks gone.
    heading = next(n for n in parsed.kir.nodes if n.kind is NodeKind.HEADING and n.level == 2)
    assert heading.text == "pip check"


# ---------------------------------------------------------------------------
# Extraction and resolution
# ---------------------------------------------------------------------------

GUIDE = """# Tools

## Installing tools

Tools can also be installed with `uv tool install`, in which case their executables
are available on the `PATH`. Use `uv add requests` to add a dependency instead.

```console
$ uv tool install ruff
$ uv add requests
Resolved 5 packages
```

## pip check

Compatibility notes.
"""

REFERENCE = """# Reference

`uv tool install` installs a tool user-wide; `uv cache prune` trims the cache.

```console
$ uv tool install httpie
```
"""


def test_a_prompt_line_demonstrates_every_prefix_and_a_span_names_one() -> None:
    extraction = extract(GUIDE, "guide.md")
    demonstrated = {
        (ref.name, ref.source) for ref in extraction.symbols if ref.language == CLI_LANGUAGE
    }
    assert demonstrated == {
        ("uv", CONSOLE_SESSION),
        ("uv tool", CONSOLE_SESSION),
        ("uv tool install", CONSOLE_SESSION),
        ("uv tool install ruff", CONSOLE_SESSION),
        ("uv add", CONSOLE_SESSION),
        ("uv add requests", CONSOLE_SESSION),
    }
    named = {
        (ref.name, ref.source) for ref in extraction.references if ref.language == CLI_LANGUAGE
    }
    assert named == {
        ("uv", CODE_SPAN),
        ("uv tool", CODE_SPAN),
        ("uv tool install", CODE_SPAN),
        ("uv add", CODE_SPAN),
        ("uv add requests", CODE_SPAN),
        ("pip", HEADING),
        ("pip check", HEADING),
    }
    assert all(
        ref.kind == COMMAND_KIND for ref in extraction.symbols if ref.language == CLI_LANGUAGE
    )
    # `PATH` is a span and not a shell word; it names nothing.
    assert not any(ref.name == "PATH" for ref in extraction.references)


def test_a_demonstration_line_is_where_the_command_is_defined() -> None:
    extraction = extract(GUIDE, "guide.md")
    install = next(
        ref
        for ref in extraction.symbols
        if ref.name == "uv tool install" and ref.source == CONSOLE_SESSION
    )
    assert install.line == 9  # the `$ uv tool install ruff` line of GUIDE
    assert install.anchor == "guide.md#installing-tools/0"
    assert install.direct


def pinned(text: str, suffix: str) -> str:
    """Give a document its identity up front, so no build pins one in and the line
    numbers `defined_in` reports are the ones written here."""
    return f"---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5F{suffix}\n---\n\n{text}"


def test_a_command_is_what_the_corpus_both_demonstrates_and_names(tmp_path: Path) -> None:
    root = repo(
        tmp_path,
        {
            "knowledge/guide.md": pinned(GUIDE, "D1"),
            "knowledge/reference.md": pinned(REFERENCE, "D2"),
        },
    )
    manifest = build(root).manifest
    with SqliteStore.open(root, read_only=True) as store:
        symbols = {s.symbol: s for s in store.all_symbols() if s.symbol.startswith("sym:cli:")}
        edges = store.all_edges()

    # Demonstrated and named: symbols. `uv add requests` is demonstrated (twice
    # over, in a fence and a span) and so named — a named invocation is a fact.
    assert set(symbols) == {
        "sym:cli:uv",
        "sym:cli:uv tool",
        "sym:cli:uv tool install",
        "sym:cli:uv add",
        "sym:cli:uv add requests",
    }
    # Demonstrated, never named: `uv tool install ruff`, `uv tool install httpie`.
    # Named, never demonstrated: `uv cache prune`, `pip check`. Neither is a symbol.
    install = symbols["sym:cli:uv tool install"]
    assert install.kind == COMMAND_KIND
    assert (
        install.defined_in == "knowledge/guide.md#L13"
    )  # GUIDE's line 9, below four frontmatter lines
    assert install.doc_refs == (
        "knowledge/guide.md#installing-tools/0",
        "knowledge/reference.md#/0",
    )
    assert manifest.counts.symbols == len(symbols)

    defines = {(e.from_, e.to) for e in edges if e.type is EdgeType.DEFINES}
    references = [e for e in edges if e.type is EdgeType.REFERENCES]
    assert ("doc:knowledge/guide.md", "sym:cli:uv tool install") in defines
    assert ("doc:knowledge/reference.md", "sym:cli:uv tool install") in defines
    # A document that both demonstrates and names gets `defines`, never `references`.
    assert not any(e.from_ == "doc:knowledge/guide.md" for e in references)


def test_a_document_that_only_names_a_command_references_it_once(tmp_path: Path) -> None:
    root = repo(
        tmp_path,
        {
            "knowledge/guide.md": GUIDE,
            "knowledge/notes.md": (
                "# Notes\n\n## First\n\nUse `uv tool install` here.\n\n"
                "## Second\n\nAnd `uv tool install` again, plus `uv add`.\n"
            ),
        },
    )
    build(root)
    with SqliteStore.open(root, read_only=True) as store:
        install = store.get_symbol("sym:cli:uv tool install")
        edges = [
            e
            for e in store.all_edges()
            if e.from_ == "doc:knowledge/notes.md" and e.type is EdgeType.REFERENCES
        ]
    assert install is not None
    # Both naming chunks are sites a reader can be sent to...
    assert "knowledge/notes.md#first/0" in install.doc_refs
    assert "knowledge/notes.md#second/0" in install.doc_refs
    # ...and the document references the command once, at its first naming.
    targets = sorted(e.to for e in edges)
    assert targets == ["sym:cli:uv", "sym:cli:uv add", "sym:cli:uv tool", "sym:cli:uv tool install"]
    first = next(e for e in edges if e.to == "sym:cli:uv tool install")
    assert first.provenance.kind == CODE_SPAN
    assert first.provenance.anchor == "knowledge/notes.md#first/0"


def test_resolution_keeps_only_confirmed_commands_from_the_states() -> None:
    from dataclasses import dataclass

    from mycelium.symbols import SymbolRef, encode_symbols

    @dataclass(frozen=True)
    class State:
        path: str
        symbols: tuple[Mapping[str, object], ...]
        symbol_uses: tuple[Mapping[str, object], ...] = ()
        symbol_gaps: tuple[str, ...] = ()

    demo = SymbolRef(CLI_LANGUAGE, "uv add", COMMAND_KIND, CONSOLE_SESSION, 4, "a.md#x/0")
    unnamed = SymbolRef(
        CLI_LANGUAGE, "uv add requests", COMMAND_KIND, CONSOLE_SESSION, 4, "a.md#x/0"
    )
    naming = SymbolRef(CLI_LANGUAGE, "uv add", COMMAND_KIND, CODE_SPAN, 2, "b.md#y/0")
    only_named = SymbolRef(CLI_LANGUAGE, "uv cache prune", COMMAND_KIND, CODE_SPAN, 3, "b.md#y/0")
    states = [
        State("a.md", tuple(encode_symbols([demo, unnamed]))),
        State("b.md", (), tuple(encode_symbols([naming, only_named]))),
    ]
    resolved = resolve_symbols(states)
    assert [s.symbol for s in resolved] == ["sym:cli:uv add"]
    assert resolved[0].defined_in == "a.md#L4"
    assert resolved[0].doc_refs == ("a.md#x/0", "b.md#y/0")
    edges = symbol_edges(states, resolved)
    assert [(e.from_, e.to, str(e.type)) for e in edges] == [
        ("doc:a.md", "sym:cli:uv add", "defines"),
        ("doc:b.md", "sym:cli:uv add", "references"),
    ]
