# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Symbol extraction (roadmap 5.1, spec 03 §§2, 6, ADR-0073).

The claims under test, in the order they matter:

**A fence yields what its grammar's tags query finds, qualified by nesting.**
Every supported language is read from a sample and the qualified names are
asserted, so a grammar release that changes a capture fails here, by name.

**Documentation defines terms through its own syntax** — a definition list, or
a heading whose text *is* an identifier — and a title defines nothing.

**Extraction is per document; resolution is global and deterministic.** One
record per symbol id, `defined_in` is the first site in path order, `doc_refs`
collects every site, and an untouched document keeps its symbols through an
incremental build.

**A missing grammar is a gap, not a failure.** The document compiles, the
snapshot says it is degraded and names the extra, and installing the extra is a
change the build sees without anyone editing a file.
"""

import json
import shutil
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mycelium.build import build, rollback
from mycelium.build.snapshots import decode_snapshot_state
from mycelium.chunking import ChunkingPolicy, chunk_document
from mycelium.cli.doctor import diagnose
from mycelium.determinism import observe_build
from mycelium.export import RECORDS_DIRNAME, export_bundle
from mycelium.markdown import parse_markdown
from mycelium.sdk.identity import symbol_id
from mycelium.sdk.types import Symbol
from mycelium.store import SqliteStore
from mycelium.symbols import (
    CODE_FENCE,
    EXTRA,
    GRAMMARS,
    MAX_FENCE_BYTES,
    LoadedGrammar,
    SymbolRef,
    code,
    definition_terms,
    describe_gaps,
    encode_symbols,
    extract_definitions,
    extract_symbols,
    grammar_fingerprint,
    grammar_for,
    heading_term,
    load_grammar,
    resolve_symbols,
    symbols_digest,
)

DOC_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"

REFERENCE = """# Reference

## RetryPolicy

The policy.

```python
class RetryPolicy:
    def delay(self, attempt):
        return attempt


def build_policy():
    return RetryPolicy()
```

## Terms

snapshot
: An immutable build.

anchor
: Where a chunk lives.

## Worked example

```python
policy = build_policy()
```
"""


def parsed_and_chunks(markdown: str, path: str = "a.md") -> tuple[object, tuple[object, ...]]:
    parsed = parse_markdown(markdown, doc_id=DOC_ID)
    chunks = chunk_document(parsed.kir, doc_path=path, policy=ChunkingPolicy())
    return parsed, chunks


def extract(markdown: str, path: str = "a.md") -> tuple[SymbolRef, ...]:
    parsed = parse_markdown(markdown, doc_id=DOC_ID)
    chunks = chunk_document(parsed.kir, doc_path=path, policy=ChunkingPolicy())
    return extract_symbols(parsed.kir, chunks, doc_path=path).symbols


def repo(tmp_path: Path, files: Mapping[str, str], name: str = "repo") -> Path:
    root = tmp_path / name
    for relative, text in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    return root


def stored_symbols(root: Path) -> tuple[Symbol, ...]:
    with SqliteStore.open(root, read_only=True) as store:
        return store.all_symbols()


@pytest.fixture
def python_grammar() -> LoadedGrammar:
    loaded = load_grammar("python")
    if loaded is None:
        pytest.skip(f"the symbols extra is not installed ({EXTRA})")
    return loaded


@pytest.fixture
def without_python(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A process in which the Python grammar wheel is not installed."""
    real = code._import

    def missing(module: str) -> object:
        if module == "tree_sitter_python":
            raise ImportError("No module named 'tree_sitter_python'", name="tree_sitter_python")
        return real(module)

    monkeypatch.setattr(code, "_import", missing)
    code._load.cache_clear()
    yield
    code._load.cache_clear()


# ---------------------------------------------------------------------------
# Code fences: the grammar's tags query, qualified
# ---------------------------------------------------------------------------

SAMPLES: dict[str, tuple[str, set[tuple[str, str]]]] = {
    "python": (
        """import os

CONSTANT = 1
lowercase = 2

def helper(x):
    return x

class RetryPolicy:
    attempts = 5
    def __init__(self, attempts):
        self.attempts = attempts
    @property
    def delay(self):
        return 1
    class Inner:
        def method(self): ...

async def fetch(): ...
""",
        {
            ("CONSTANT", "constant"),
            ("helper", "function"),
            ("RetryPolicy", "class"),
            ("RetryPolicy.__init__", "method"),
            ("RetryPolicy.delay", "method"),
            ("RetryPolicy.Inner", "class"),
            ("RetryPolicy.Inner.method", "method"),
            ("fetch", "function"),
        },
    ),
    "javascript": (
        """import x from "y";
const value = 1;
function helper(a) { return a; }
const arrow = (a) => a;
class Bus extends Base {
  constructor() { super(); }
  publish(msg) {}
  static create() {}
  get size() { return 0; }
}
export default function main() {}
""",
        {
            ("helper", "function"),
            ("arrow", "function"),
            ("Bus", "class"),
            ("Bus.publish", "method"),
            ("Bus.create", "method"),
            ("Bus.size", "method"),
            ("main", "function"),
        },
    ),
    "typescript": (
        """interface Policy { attempts: number }
type Id = string;
namespace NS { export function f() {} }
abstract class Base<T> { abstract run(): void; protected helper(): T { return null as T; } }
class Impl extends Base<number> { run(): void {} static make() {} }
function top(): void {}
const arrow = (): void => {};
""",
        {
            ("Policy", "interface"),
            ("NS.f", "function"),
            ("Base", "class"),
            ("Base.helper", "method"),
            ("Base.run", "method"),
            ("Impl", "class"),
            ("Impl.make", "method"),
            ("Impl.run", "method"),
            ("top", "function"),
            ("arrow", "function"),
        },
    ),
    "tsx": (
        """interface Props { name: string }
export function Greeting({ name }: Props) { return <p>{name}</p>; }
class Widget { render() { return <div />; } }
""",
        {
            ("Props", "interface"),
            ("Greeting", "function"),
            ("Widget", "class"),
            ("Widget.render", "method"),
        },
    ),
    "rust": (
        """use std::fmt;
pub const MAX: u32 = 5;
pub struct RetryPolicy { attempts: u32 }
impl RetryPolicy {
    pub fn new(attempts: u32) -> Self { Self { attempts } }
    fn private(&self) {}
}
pub trait Deliver { fn deliver(&self); }
impl Deliver for RetryPolicy { fn deliver(&self) {} }
pub enum State { On, Off }
pub fn top() {}
mod inner { pub fn nested() {} }
macro_rules! say { () => {} }
type Alias = u32;
""",
        {
            ("RetryPolicy", "class"),
            ("RetryPolicy.new", "method"),
            ("RetryPolicy.private", "method"),
            ("Deliver", "interface"),
            ("RetryPolicy.deliver", "method"),
            ("State", "class"),
            ("top", "function"),
            ("inner", "module"),
            ("inner.nested", "method"),
            ("say", "macro"),
            ("Alias", "class"),
        },
    ),
    "go": (
        """package main
import "fmt"
type Policy struct { Attempts int }
type Deliverer interface { Deliver() error }
func (p *Policy) Deliver() error { return nil }
func (p Policy) Name() string { return "" }
func helper() {}
func main() { fmt.Println(helper) }
""",
        {
            ("Policy", "type"),
            ("Deliverer", "type"),
            ("Policy.Deliver", "method"),
            ("Policy.Name", "method"),
            ("helper", "function"),
            ("main", "function"),
        },
    ),
    "java": (
        """package com.example;
public class RetryPolicy {
    private static final int MAX = 5;
    public RetryPolicy(int attempts) {}
    public int attempts() { return 5; }
    static class Inner { void run() {} }
    interface Deliver { void deliver(); }
}
""",
        {
            ("RetryPolicy", "class"),
            ("RetryPolicy.attempts", "method"),
            ("RetryPolicy.Inner", "class"),
            ("RetryPolicy.Inner.run", "method"),
            ("RetryPolicy.Deliver", "interface"),
            ("RetryPolicy.Deliver.deliver", "method"),
        },
    ),
    "c": (
        """#include <stdio.h>
typedef struct policy { int attempts; } policy_t;
struct node { int v; };
enum state { ON, OFF };
static int helper(int x) { return x; }
int main(void) { return helper(1); }
""",
        {
            ("policy", "class"),
            ("policy_t", "type"),
            ("node", "class"),
            ("state", "type"),
            ("helper", "function"),
            ("main", "function"),
        },
    ),
    "cpp": (
        """namespace bus {
class RetryPolicy {
public:
    RetryPolicy(int attempts);
    int attempts() const;
};
RetryPolicy::RetryPolicy(int attempts) {}
int RetryPolicy::attempts() const { return 1; }
struct Node { int v; };
template <typename T> T identity(T v) { return v; }
enum class State { On, Off };
}
int main() { return 0; }
""",
        {
            ("bus.RetryPolicy", "class"),
            ("bus.RetryPolicy.RetryPolicy", "method"),
            ("bus.RetryPolicy.attempts", "method"),
            ("bus.Node", "class"),
            ("bus.identity", "function"),
            ("bus.State", "type"),
            ("main", "function"),
        },
    ),
    "ruby": (
        """require 'json'
module Bus
  class RetryPolicy < Base
    def initialize(attempts)
      @attempts = attempts
    end
    def self.create
      new(5)
    end
    def deliver; end
  end
  def self.helper; end
end
def top_level; end
""",
        {
            ("Bus", "module"),
            ("Bus.RetryPolicy", "class"),
            ("Bus.RetryPolicy.initialize", "method"),
            ("Bus.RetryPolicy.create", "method"),
            ("Bus.RetryPolicy.deliver", "method"),
            ("Bus.helper", "method"),
            ("top_level", "method"),
        },
    ),
}


def test_every_supported_grammar_has_a_sample() -> None:
    assert {grammar.name for grammar in GRAMMARS} == set(SAMPLES)


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_a_fence_yields_its_definitions_qualified_by_nesting(name: str) -> None:
    loaded = load_grammar(name)
    if loaded is None:
        pytest.skip(f"the {name} grammar is not installed ({EXTRA})")
    source, expected = SAMPLES[name]
    definitions = extract_definitions(loaded, source.encode("utf-8"))
    assert {(item.name, item.kind) for item in definitions} == expected
    # Ordered by position, so the output is a function of the fence alone.
    assert [item.row for item in definitions] == sorted(item.row for item in definitions)


def test_an_out_of_class_definition_and_its_declaration_are_one_symbol() -> None:
    """C++ spells the method twice; the symbol id must not (ADR-0073)."""
    loaded = load_grammar("cpp")
    if loaded is None:
        pytest.skip(f"the cpp grammar is not installed ({EXTRA})")
    definitions = extract_definitions(loaded, SAMPLES["cpp"][0].encode("utf-8"))
    attempts = [item for item in definitions if item.name == "bus.RetryPolicy.attempts"]
    assert len(attempts) == 2 and {item.kind for item in attempts} == {"method"}


def test_fence_info_strings_reach_their_grammar() -> None:
    assert grammar_for("python") is grammar_for("py") is grammar_for("Python3")
    assert grammar_for('python title="x.py"') is grammar_for("python")
    assert grammar_for("rs") is not None and grammar_for("rs").language == "rust"
    assert grammar_for("tsx") is not None and grammar_for("tsx").language == "typescript"
    assert grammar_for("c++") is not None and grammar_for("c++").name == "cpp"
    for unread in ("console", "toml", "yaml", "text", "", "   ", None):
        assert grammar_for(unread) is None


def test_lowercase_assignments_and_calls_define_nothing(python_grammar: LoadedGrammar) -> None:
    """The grammar tags every module-level assignment as a constant; a documentation
    fence is mostly example glue, so the capture is honoured only for names that
    say they are constants."""
    source = b"retry_policy = RetryPolicy(attempts=5)\nsnapshot = build(root)\nMAX_ATTEMPTS = 5\n"
    definitions = extract_definitions(python_grammar, source)
    assert [(item.name, item.kind) for item in definitions] == [("MAX_ATTEMPTS", "constant")]


@given(st.text(alphabet=st.characters(exclude_categories=("Cs",)), max_size=2000))
def test_any_python_fence_is_read_without_error_and_deterministically(text: str) -> None:
    loaded = load_grammar("python")
    if loaded is None:
        pytest.skip(f"the symbols extra is not installed ({EXTRA})")
    source = text.encode("utf-8")
    first = extract_definitions(loaded, source)
    assert first == extract_definitions(loaded, source)
    for item in first:
        # Every name the extractor emits is a legal symbol id and record.
        Symbol(symbol=symbol_id("python", item.name), kind=item.kind, defined_in="a.md#L1")


# ---------------------------------------------------------------------------
# Documentation: the definition syntax
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("heading", "term"),
    [
        ("RetryPolicy", "RetryPolicy"),
        ("3.3 mycelium_neighbors", "mycelium_neighbors"),
        ("uv.lock", "uv.lock"),
        (".python-version", ".python-version"),
        ("AGENTS.md", "AGENTS.md"),
        ("helper()", "helper"),
        ("RetryPolicy:", "RetryPolicy"),
        ("docs/adr", "docs/adr"),
        ("std::fmt", "std::fmt"),
        ("Retries", None),
        ("Event Bus", None),
        ("The RetryPolicy class", None),
        ("API", None),
        ("v0.4.0", None),
        ("4.2", None),
        ("...", None),
        ("Größenordnung", None),
        ("C++", None),
        ("", None),
    ],
)
def test_a_heading_defines_a_term_only_when_it_is_an_identifier(
    heading: str, term: str | None
) -> None:
    assert heading_term(heading) == term


def test_definition_lists_define_their_terms() -> None:
    assert definition_terms("snapshot\n: An immutable build.") == ((0, "snapshot"),)
    assert definition_terms("Term one\nTerm two\n: Shared definition\n: continued.") == (
        (0, "Term one"),
        (1, "Term two"),
    )
    # Prose with a colon-led line somewhere inside it is prose.
    assert definition_terms("A sentence.\n: not a definition\nMore prose.") == ()
    assert definition_terms(": leads with the colon") == ()
    assert definition_terms("One line only") == ()
    assert definition_terms("x" * 81 + "\n: too long to be a term") == ()


def test_extraction_reads_docs_and_code_in_document_order(python_grammar: LoadedGrammar) -> None:
    symbols = extract(REFERENCE)
    assert [(item.language, item.name, item.kind, item.line) for item in symbols] == [
        ("doc", "RetryPolicy", "term", 3),
        ("python", "RetryPolicy", "class", 8),
        ("python", "RetryPolicy.delay", "method", 9),
        ("python", "build_policy", "function", 13),
        ("doc", "snapshot", "term", 19),
        ("doc", "anchor", "term", 22),
    ]
    # Each definition knows the chunk a reader would find it in.
    assert {item.anchor for item in symbols[:4]} == {"a.md#retrypolicy/0"}
    assert {item.anchor for item in symbols[4:]} == {"a.md#terms/0"}


def test_symbol_references_round_trip_through_their_encoding(
    python_grammar: LoadedGrammar,
) -> None:
    from mycelium.symbols import decode_symbols

    symbols = extract(REFERENCE)
    assert decode_symbols(encode_symbols(symbols)) == symbols


def test_an_oversized_fence_is_a_warning_on_the_document_not_a_lost_document(
    tmp_path: Path, python_grammar: LoadedGrammar
) -> None:
    huge = "x = 1\n" * (MAX_FENCE_BYTES // 6 + 1000)
    text = f"# Big\n\n## Section\n\n```python\n{huge}```\n"
    parsed, chunks = parsed_and_chunks(text)
    extraction = extract_symbols(parsed.kir, chunks, doc_path="big.md")  # type: ignore[arg-type]
    assert extraction.symbols == ()
    assert len(extraction.warnings) == 1
    assert "exceeds" in extraction.warnings[0] and "line 5" in extraction.warnings[0]

    root = repo(tmp_path, {"knowledge/big.md": text})
    manifest = build(root).manifest
    assert manifest.counts.documents == 1 and manifest.counts.quarantined == 0
    assert any("exceeds" in warning for warning in manifest.warnings)


# ---------------------------------------------------------------------------
# Resolution: one record per symbol, across the corpus
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _State:
    path: str
    symbols: tuple[Mapping[str, object], ...]
    symbol_uses: tuple[Mapping[str, object], ...] = ()
    symbol_gaps: tuple[str, ...] = ()
    origin: str = "authored"


def _refs(*items: tuple[str, str, str, int, str]) -> tuple[Mapping[str, object], ...]:
    """(language, name, kind, line, anchor) -> the stored form, read from a fence."""
    return tuple(
        encode_symbols(
            [
                SymbolRef(language, name, kind, CODE_FENCE, line, anchor)
                for language, name, kind, line, anchor in items
            ]
        )
    )


def test_resolution_merges_definitions_across_documents_in_path_order() -> None:
    states = [
        _State(
            "knowledge/b.md",
            _refs(("python", "Shared", "class", 40, "knowledge/b.md#api/0")),
        ),
        _State(
            "knowledge/a.md",
            _refs(
                ("python", "Shared", "class", 12, "knowledge/a.md#intro/0"),
                ("doc", "Shared", "term", 3, "knowledge/a.md#intro/0"),
            ),
        ),
    ]
    resolved = resolve_symbols(states)
    assert [symbol.symbol for symbol in resolved] == ["sym:doc:Shared", "sym:python:Shared"]
    shared = resolved[1]
    assert shared.defined_in == "knowledge/a.md#L12"  # a.md before b.md, whatever the input order
    assert shared.doc_refs == ("knowledge/a.md#intro/0", "knowledge/b.md#api/0")
    assert shared.kind == "class"
    # Order of the input never reaches the output.
    assert resolve_symbols(list(reversed(states))) == resolved
    assert symbols_digest(resolved) == symbols_digest(resolve_symbols(list(reversed(states))))


def test_a_reference_without_a_source_line_falls_back_to_its_anchor() -> None:
    (symbol,) = resolve_symbols([_State("a.md", _refs(("doc", "Term", "term", 0, "a.md#x/0")))])
    assert symbol.defined_in == "a.md#x/0"


def test_gaps_are_described_from_the_documents_not_the_environment() -> None:
    assert describe_gaps([_State("a.md", ())]) is None
    reason = describe_gaps(
        [
            _State("a.md", (), symbol_gaps=("python",)),
            _State("b.md", (), symbol_gaps=("rust", "python")),
            _State("c.md", ()),
        ]
    )
    assert reason is not None
    assert "2 document(s)" in reason and "python, rust" in reason and EXTRA in reason


def test_state_written_before_the_symbol_stage_decodes_with_no_symbols() -> None:
    blob = json.dumps(
        [
            {
                "doc_id": DOC_ID,
                "path": "knowledge/a.md",
                "source_digest": "sha256:aa",
                "source_mtime": "2026-01-01T00:00:00+00:00",
                "env_digest": "sha256:bb",
                "document": "sha256:cc",
                "chunks": "sha256:dd",
                "warnings": [],
            }
        ]
    )
    (state,) = decode_snapshot_state(blob)
    assert state.symbols == () and state.symbol_gaps == ()


# ---------------------------------------------------------------------------
# The build: published, exported, restored, incremental
# ---------------------------------------------------------------------------


def pinned(text: str, suffix: str) -> str:
    """Give a corpus document its identity up front, so no build pins one in and
    the line numbers `defined_in` reports are the ones written here."""
    return f"---\nmycelium_id: 01ARZ3NDEKTSV4RRFFQ69G5F{suffix}\n---\n\n{text}"


GUIDE = (
    "# Guide\n\n## Configuration\n\n```rust\npub struct Config { pub attempts: u32 }\n"
    "impl Config {\n    pub fn new() -> Self { Self { attempts: 5 } }\n}\n```\n\n"
    "## RetryPolicy\n\nDiscussed again here, defined in the API reference.\n"
)

CORPUS = {
    "knowledge/api.md": pinned(REFERENCE, "C1"),  # the heading `RetryPolicy` sits on line 7
    "knowledge/guide.md": pinned(GUIDE, "C2"),  # `Config.new` on line 12, the heading on 16
}


def test_the_build_publishes_the_symbol_table_and_digests_it(
    tmp_path: Path, python_grammar: LoadedGrammar
) -> None:
    root = repo(tmp_path, CORPUS)
    manifest = build(root).manifest
    symbols = stored_symbols(root)

    assert manifest.counts.symbols == len(symbols) == 8
    assert manifest.artifact_digests["symbols"] == symbols_digest(symbols)
    assert manifest.schema_versions["symbol"] == "v0"
    assert "symbols" not in manifest.degraded
    by_id = {symbol.symbol: symbol for symbol in symbols}
    # The heading in the guide *mentions* RetryPolicy and the API defines it: two
    # documentation sites, one term, defined where it appears first in path order.
    assert by_id["sym:doc:RetryPolicy"].defined_in == "knowledge/api.md#L7"
    assert by_id["sym:doc:RetryPolicy"].doc_refs == (
        "knowledge/api.md#retrypolicy/0",
        "knowledge/guide.md#retrypolicy/0",
    )
    assert by_id["sym:rust:Config.new"].kind == "method"
    assert by_id["sym:rust:Config.new"].defined_in == "knowledge/guide.md#L12"


def test_export_writes_the_symbols_the_snapshot_holds(
    tmp_path: Path, python_grammar: LoadedGrammar
) -> None:
    root = repo(tmp_path, CORPUS)
    build(root)
    result = export_bundle(root)
    lines = (result.bundle / RECORDS_DIRNAME / "symbols.jsonl").read_text("utf-8").splitlines()
    exported = [Symbol.model_validate_json(line) for line in lines]
    assert result.counts["symbols"] == len(exported) == 8
    assert exported == list(stored_symbols(root))


def test_an_untouched_document_keeps_its_symbols_through_an_incremental_build(
    tmp_path: Path, python_grammar: LoadedGrammar
) -> None:
    root = repo(tmp_path, CORPUS)
    build(root)
    guide = root / "knowledge" / "guide.md"
    with guide.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\nA sentence that changes nothing structural.\n")
    result = build(root)

    assert result.stats.reused == 1 and result.stats.rebuilt == 1
    ids = {symbol.symbol for symbol in stored_symbols(root)}
    assert {"sym:python:RetryPolicy", "sym:python:build_policy", "sym:rust:Config"} <= ids

    # The exit-gate property: the incremental result equals a from-scratch build.
    fresh = tmp_path / "fresh"
    for path in root.rglob("*.md"):
        if ".mycelium" in path.parts:
            continue
        target = fresh / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    assert observe_build(root, pin=False) == observe_build(fresh, pin=False)


def test_rollback_restores_the_symbols_the_snapshot_published(
    tmp_path: Path, python_grammar: LoadedGrammar
) -> None:
    root = repo(tmp_path, CORPUS)
    first = build(root).manifest
    before = stored_symbols(root)
    guide = root / "knowledge" / "guide.md"
    with guide.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\n## Extra\n\n```python\ndef later(): ...\n```\n")
    build(root)
    assert "sym:python:later" in {symbol.symbol for symbol in stored_symbols(root)}

    rollback(root, first.snapshot_id)

    assert stored_symbols(root) == before
    assert first.artifact_digests["symbols"] == symbols_digest(before)


def test_removing_the_first_definer_hands_defined_in_to_the_next(
    tmp_path: Path, python_grammar: LoadedGrammar
) -> None:
    """Resolution is global: a document this build never recompiled can become
    the definition site when the one before it in path order goes away."""
    root = repo(tmp_path, CORPUS)
    build(root)
    by_id = {symbol.symbol: symbol for symbol in stored_symbols(root)}
    assert by_id["sym:doc:RetryPolicy"].defined_in == "knowledge/api.md#L7"

    (root / "knowledge" / "api.md").unlink()
    result = build(root)

    assert result.stats.rebuilt == 0 and result.stats.reused == 1
    by_id = {symbol.symbol: symbol for symbol in stored_symbols(root)}
    assert by_id["sym:doc:RetryPolicy"].defined_in == "knowledge/guide.md#L16"
    assert "sym:python:RetryPolicy" not in by_id


# ---------------------------------------------------------------------------
# Availability: a missing grammar is a gap the snapshot reports
# ---------------------------------------------------------------------------


def test_a_missing_grammar_degrades_the_snapshot_and_names_the_extra(
    tmp_path: Path, without_python: None
) -> None:
    root = repo(tmp_path, CORPUS)
    result = build(root)
    manifest = result.manifest

    assert "symbols" in manifest.degraded
    assert any("python" in reason and EXTRA in reason for reason in result.degraded_reasons)
    ids = {symbol.symbol for symbol in stored_symbols(root)}
    # Documentation terms and the Rust fence are unaffected; the Python fence is a gap.
    assert "sym:doc:RetryPolicy" in ids and "sym:rust:Config" in ids
    assert not any(identity.startswith("sym:python:") for identity in ids)
    assert manifest.counts.documents == 2 and manifest.counts.quarantined == 0
    assert "python" not in grammar_fingerprint()


def test_a_corpus_without_fences_is_never_degraded_by_a_missing_grammar(
    tmp_path: Path, without_python: None
) -> None:
    root = repo(tmp_path, {"knowledge/prose.md": "# Prose\n\nNo code here.\n"})
    manifest = build(root).manifest
    assert "symbols" not in manifest.degraded


def test_installing_the_grammar_is_a_change_the_next_build_sees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if load_grammar("python") is None:
        pytest.skip(f"the symbols extra is not installed ({EXTRA})")
    real = code._import

    def missing(module: str) -> object:
        if module == "tree_sitter_python":
            raise ImportError("No module named 'tree_sitter_python'", name="tree_sitter_python")
        return real(module)

    monkeypatch.setattr(code, "_import", missing)
    code._load.cache_clear()
    root = repo(tmp_path, CORPUS)
    degraded = build(root).manifest
    assert "symbols" in degraded.degraded

    monkeypatch.undo()  # the wheel appears
    code._load.cache_clear()
    result = build(root)  # no file changed

    assert result.stats.rebuilt == 2, "the grammar fingerprint is a build input"
    assert result.stats.parse_hits == 2, "and the parse cache still serves"
    assert "symbols" not in result.manifest.degraded
    assert "sym:python:RetryPolicy" in {symbol.symbol for symbol in stored_symbols(root)}


def test_doctor_names_the_grammars_it_can_load(tmp_path: Path) -> None:
    if load_grammar("python") is None:
        pytest.skip(f"the symbols extra is not installed ({EXTRA})")
    root = repo(tmp_path, {"knowledge/prose.md": "# Prose\n"})
    (check,) = [check for check in diagnose(root) if check.name == "symbols"]
    assert check.status == "ok"
    assert "python (" in check.detail and "rust (" in check.detail


def test_doctor_warns_about_a_grammar_it_cannot_load(tmp_path: Path, without_python: None) -> None:
    root = repo(tmp_path, {"knowledge/prose.md": "# Prose\n"})
    (check,) = [check for check in diagnose(root) if check.name == "symbols"]
    assert check.status == "warn"
    assert "python" in check.detail and EXTRA in check.detail
