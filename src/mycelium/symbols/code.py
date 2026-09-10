# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Symbols from code fences, through tree-sitter (roadmap 5.1, ADR-0073).

Spec 03 §2 gives a symbol the identity ``sym:<language>:<qualified-name>`` and
says where it comes from: *"tree-sitter (code)"*. This module is that adapter,
and it owns nothing about parsing — every grammar is a wheel from the
tree-sitter organisation, and what a definition *is* in each language comes from
the grammar's own ``tags.scm``: the query GitHub's code navigation runs to
answer "where is this defined", shipped inside the grammar package as
``TAGS_QUERY``. Writing our own queries would have meant deciding, nine times,
what counts as a definition in a language we did not design; the grammar
authors already decided, and their answer is what every other tool agrees with.

Two things the tags queries leave to the caller, and this module adds:

**Qualification.** A tags query captures a *name* — ``delay`` — and the node it
belongs to; it does not say that the node sits inside ``class RetryPolicy``.
:func:`extract_definitions` walks each definition's ancestors and prepends the
names of the definitions and scopes it is nested in, so the symbol is
``RetryPolicy.delay`` in every language, joined with ``.`` whatever the language
spells its own paths with. Three constructs need a language-specific hint
because the tags query does not capture them as definitions: a Rust ``impl``
block (the scope is its ``type`` field), a C++ ``namespace`` (its ``name``), and
a Go method's receiver (``func (p *Policy) Deliver()`` defines ``Policy.Deliver``).
Those hints are data on the :class:`Grammar` row, not code paths.

**Availability.** The grammars are an optional extra — ``mycelium-os[symbols]``
— because a compiled wheel per language is a real price to charge someone who
only wants lexical search, and the definition syntax for documentation
(:mod:`mycelium.symbols.docs`) needs none of them. A build without the extra
compiles; every fence whose grammar is absent is reported as a *gap*, and the
snapshot says it is degraded and why (spec 02 §4.3), exactly as it does when the
embedding model is missing (ADR-0017). Which grammars are installed, and at
which versions, is part of the build environment digest, so installing the extra
recompiles the documents that need it and nothing else.

Fences are untrusted input like everything else in a document (D-017). The
parser is a C library with error recovery — a fence full of ``...`` placeholders
still yields its definitions — bounded by a byte ceiling per fence
(:data:`MAX_FENCE_BYTES`), and a failure inside it is a warning on the document,
never a quarantine: the prose is fine, one fence was not read.
"""

import importlib
import importlib.metadata
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cache
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    import tree_sitter

__all__ = [
    "CORE_DISTRIBUTION",
    "EXTRA",
    "FENCE_ALIASES",
    "GRAMMARS",
    "MAX_FENCE_BYTES",
    "CodeDefinition",
    "CodeReference",
    "FenceContents",
    "Grammar",
    "GrammarStatus",
    "LoadedGrammar",
    "extract_definitions",
    "extract_references",
    "grammar_fingerprint",
    "grammar_for",
    "grammar_statuses",
    "load_grammar",
    "missing_grammars",
]

MAX_FENCE_BYTES: Final = 256 * 1024
"""The largest fence a build will hand to a grammar.

tree-sitter is linear in the input and recovers from errors, so the bound is
not a guard against a known pathology — it is the statement that a quarter of a
megabyte of code inside a *documentation* fence is not documentation, and that
the build's time belongs to the prose (threat model B14)."""

CORE_DISTRIBUTION: Final = "tree-sitter"
"""The Python binding every grammar wheel is loaded through."""

EXTRA: Final = "mycelium-os[symbols]"
"""What to install when a gap is reported. Named once, here, so every message agrees."""


@dataclass(frozen=True, slots=True)
class Grammar:
    """One supported fence language, and how its wheel is used.

    ``name`` is the registry key and the canonical fence tag; ``language`` is the
    segment that goes into the symbol id, which is why ``tsx`` is a grammar of
    its own but its symbols are ``sym:typescript:…`` — a TSX file is TypeScript
    with markup, not another language.
    """

    name: str
    language: str
    distribution: str
    module: str
    attribute: str = "language"
    """The module attribute returning the grammar's language pointer."""
    queries: tuple[tuple[str, str], ...] = ()
    """``(module, attribute)`` pairs naming the tags queries to run, in order.
    Empty means the grammar's own ``TAGS_QUERY``. TypeScript needs two: its own
    query covers only what TypeScript adds (interfaces, abstract members,
    signatures) and relies on the JavaScript query for classes and functions —
    the same arrangement the grammar's upstream tooling uses."""
    scopes: Mapping[str, str] = field(default_factory=dict)
    """Node types that enclose definitions without being one, mapped to the
    field holding the scope's name: ``impl_item → type`` in Rust,
    ``namespace_definition → name`` in C++."""
    receiver: str | None = None
    """For languages whose methods name their type in a receiver rather than by
    nesting (Go): the field of a method node that holds it."""

    def query_sources(self) -> tuple[tuple[str, str], ...]:
        return self.queries or ((self.module, "TAGS_QUERY"),)


_TYPESCRIPT_QUERIES: Final = (
    ("tree_sitter_typescript", "TAGS_QUERY"),
    ("tree_sitter_javascript", "TAGS_QUERY"),
)

GRAMMARS: Final[tuple[Grammar, ...]] = (
    Grammar("python", "python", "tree-sitter-python", "tree_sitter_python"),
    Grammar("javascript", "javascript", "tree-sitter-javascript", "tree_sitter_javascript"),
    Grammar(
        "typescript",
        "typescript",
        "tree-sitter-typescript",
        "tree_sitter_typescript",
        attribute="language_typescript",
        queries=_TYPESCRIPT_QUERIES,
        scopes={"internal_module": "name"},
    ),
    Grammar(
        "tsx",
        "typescript",
        "tree-sitter-typescript",
        "tree_sitter_typescript",
        attribute="language_tsx",
        queries=_TYPESCRIPT_QUERIES,
        scopes={"internal_module": "name"},
    ),
    Grammar("rust", "rust", "tree-sitter-rust", "tree_sitter_rust", scopes={"impl_item": "type"}),
    Grammar("go", "go", "tree-sitter-go", "tree_sitter_go", receiver="receiver"),
    Grammar("java", "java", "tree-sitter-java", "tree_sitter_java"),
    Grammar("c", "c", "tree-sitter-c", "tree_sitter_c"),
    Grammar(
        "cpp", "cpp", "tree-sitter-cpp", "tree_sitter_cpp", scopes={"namespace_definition": "name"}
    ),
    Grammar("ruby", "ruby", "tree-sitter-ruby", "tree_sitter_ruby"),
)
"""The supported fence languages, in the order `doctor` reports them.

C# is deliberately absent: its wheel (0.23.5) ships no ``tags.scm``, and writing
one here would be the decision this module exists not to make. It joins when
upstream publishes one."""

_BY_NAME: Final[Mapping[str, Grammar]] = {grammar.name: grammar for grammar in GRAMMARS}

FENCE_ALIASES: Final[Mapping[str, str]] = {
    "python": "python",
    "py": "python",
    "python3": "python",
    "py3": "python",
    "javascript": "javascript",
    "js": "javascript",
    "jsx": "javascript",
    "mjs": "javascript",
    "cjs": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "mts": "typescript",
    "cts": "typescript",
    "tsx": "tsx",
    "rust": "rust",
    "rs": "rust",
    "go": "go",
    "golang": "go",
    "java": "java",
    "c": "c",
    "h": "c",
    "cpp": "cpp",
    "c++": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    "hpp": "cpp",
    "hh": "cpp",
    "hxx": "cpp",
    "ruby": "ruby",
    "rb": "ruby",
}
"""Fence info strings, as authors actually write them, to a grammar name.

Case-insensitive; the first word of the info string is what counts, so
``python title="x.py"`` and ``py`` both reach the Python grammar. A tag not
listed here is a fence this build does not read for symbols — ``console``,
``toml``, ``yaml`` and ``text`` are the common ones, and none of them defines
anything."""


def grammar_for(lang: str | None) -> Grammar | None:
    """The grammar a fence's info string selects, or ``None`` for one not read."""
    if not lang:
        return None
    words = lang.strip().split()
    if not words:
        return None
    name = FENCE_ALIASES.get(words[0].casefold())
    return None if name is None else _BY_NAME[name]


@dataclass(frozen=True, slots=True)
class LoadedGrammar:
    """A grammar the running interpreter can use: its language, queries, and version."""

    grammar: Grammar
    version: str
    language: "tree_sitter.Language"
    queries: tuple["tree_sitter.Query", ...]


@dataclass(frozen=True, slots=True)
class GrammarStatus:
    """What `doctor` reports per grammar: available at a version, or why not."""

    name: str
    available: bool
    detail: str


@dataclass(frozen=True, slots=True)
class _Load:
    loaded: LoadedGrammar | None
    detail: str


def _import(module: str) -> Any:
    """One seam for every import this module makes, so a test can make a wheel vanish."""
    return importlib.import_module(module)


@cache
def _load(name: str) -> _Load:
    grammar = _BY_NAME.get(name)
    if grammar is None:
        return _Load(None, f"{name} is not a supported fence language")
    try:
        tree_sitter = _import("tree_sitter")
        module = _import(grammar.module)
        language = tree_sitter.Language(getattr(module, grammar.attribute)())
        queries = tuple(
            tree_sitter.Query(language, getattr(_import(source_module), attribute))
            for source_module, attribute in grammar.query_sources()
        )
        version = importlib.metadata.version(grammar.distribution)
    except ImportError as error:
        return _Load(None, f"not installed ({error.name or error}); install {EXTRA}")
    except Exception as error:  # noqa: BLE001 - a broken wheel is reported, never guessed at
        return _Load(None, f"unusable ({type(error).__name__}: {error})")
    return _Load(LoadedGrammar(grammar, version, language, queries), version)


def load_grammar(name: str) -> LoadedGrammar | None:
    """The loaded grammar named `name`, or ``None`` when this interpreter lacks it.

    Cached for the life of the process: loading compiles the tags queries, and a
    build asks for the same grammar once per fence.
    """
    return _load(name).loaded


def grammar_statuses() -> tuple[GrammarStatus, ...]:
    """Every supported grammar, available or not, in registry order."""
    statuses = []
    for grammar in GRAMMARS:
        load = _load(grammar.name)
        statuses.append(GrammarStatus(grammar.name, load.loaded is not None, load.detail))
    return tuple(statuses)


def missing_grammars() -> tuple[GrammarStatus, ...]:
    """The grammars this interpreter cannot load — empty when the extra is installed."""
    return tuple(status for status in grammar_statuses() if not status.available)


def grammar_fingerprint() -> dict[str, str]:
    """What the extract stage's build key sees of the environment.

    The binding's version and each *available* grammar's version, keyed by
    grammar name. A grammar that is absent contributes nothing, so installing it
    changes the fingerprint — which is what makes the documents that need it
    dirty on the next build (ADR-0015's rule: an input that changes the output
    is part of the key). The versions are there for the same reason: a grammar
    release can change what its tags query captures for unchanged input.
    """
    fingerprint: dict[str, str] = {}
    try:
        fingerprint[CORE_DISTRIBUTION] = importlib.metadata.version(CORE_DISTRIBUTION)
    except importlib.metadata.PackageNotFoundError:
        return fingerprint
    for grammar in GRAMMARS:
        loaded = load_grammar(grammar.name)
        if loaded is not None:
            fingerprint[grammar.name] = loaded.version
    return fingerprint


# ---------------------------------------------------------------------------
# Definitions: one fence -> what it defines, qualified
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CodeDefinition:
    """One definition a tags query found in a fence."""

    kind: str
    """The tags query's own word: `class`, `function`, `method`, `interface`,
    `module`, `type`, `constant`, `macro` — a function nested directly in a
    class or interface is reported as a `method` whatever the query called it,
    so Python and Rust agree with JavaScript and Java."""
    name: str
    """The qualified name, nesting joined with `.`."""
    row: int
    """0-based line of the definition within the fence."""


@dataclass(frozen=True, slots=True)
class CodeReference:
    """One *use* a tags query found in a fence — the other half of spec 03 §6.

    Deliberately **not** qualified. A definition's identity is its place in the
    tree, so nesting belongs in its name; a use is a call site, and where the
    call sits says nothing about what it calls. The name is what the grammar
    captured — ``delay`` for ``policy.delay(2)``, since every tags query captures
    an attribute call's last segment — and resolving that to a qualified symbol
    is the corpus's job, not the fence's (:func:`mycelium.symbols.symbol_edges`).
    """

    kind: str
    """The tags query's own word: `call`, `class`, `type`, `implementation`."""
    name: str
    """The name as captured, unqualified."""
    row: int
    """0-based line of the reference within the fence."""


@dataclass(frozen=True, slots=True)
class FenceContents:
    """What one parse of one fence yields: what it defines, and what it uses.

    Both come from the same tree, because parsing a fence twice to ask two
    questions of it would double the only real cost in this module.
    """

    definitions: tuple[CodeDefinition, ...]
    references: tuple[CodeReference, ...]


@dataclass(frozen=True, slots=True)
class _Scope:
    name: str
    kind: str


@dataclass(frozen=True, slots=True)
class _Match:
    node: "tree_sitter.Node"
    name_node: "tree_sitter.Node"
    kind: str


_KIND_RANK: Final[Mapping[str, int]] = {"method": 2, "function": 1}
"""When two patterns capture one node — Rust tags every `impl` function as both
`method` and `function` — the more specific word wins."""

_METHOD_SCOPES: Final = frozenset({"class", "interface", "implementation"})
"""Enclosing definition kinds that make a nested `function` a `method`."""

_NON_SCOPE_KINDS: Final = frozenset({"type", "constant", "macro"})
"""Definitions nothing is qualified by. A C ``typedef struct policy {…} policy_t``
nests the struct inside the type definition syntactically, and ``policy_t.policy``
would be a name no reader recognises; a constant or a macro encloses nothing."""

_CONSTANT_NAME: Final = re.compile(r"^[A-Z][A-Z0-9_]*$")
"""What a `constant` must be called to be kept.

Python's tags query captures *every* module-level assignment as a constant —
``policy = build_policy()`` as readily as ``MAX_ATTEMPTS = 5`` — because the
grammar cannot know which the author meant. In a documentation fence the first
kind is example glue and would swamp the table; the second is a definition. The
name is the only signal available, and SCREAMING_CASE is the one every style
guide gives it, so the capture is honoured exactly when the name says so."""

_QUALIFIED_NODE_TYPES: Final = frozenset(
    {
        "qualified_identifier",
        "scoped_identifier",
        "scoped_type_identifier",
        "nested_identifier",
        "nested_type_identifier",
    }
)
"""Name nodes that carry their own path (`RetryPolicy::attempts`): the whole
path is the local name, so an out-of-class C++ definition and the declaration
inside the class body produce the same symbol."""


def _text(node: "tree_sitter.Node | None") -> str:
    if node is None or node.text is None:
        return ""
    return " ".join(node.text.decode("utf-8", errors="replace").split())


def _scope_name(node: "tree_sitter.Node | None") -> str:
    """A scope's name as a path segment: generics dropped, `::` spelled `.`."""
    text = _text(node)
    text = text.split("<", 1)[0].strip()
    return text.replace("::", ".")


def _local_name(name_node: "tree_sitter.Node") -> str:
    node = name_node
    while node.parent is not None and node.parent.type in _QUALIFIED_NODE_TYPES:
        node = node.parent
    return _text(node).replace("::", ".")


def _receiver_type(node: "tree_sitter.Node", grammar: Grammar) -> str:
    if grammar.receiver is None:
        return ""
    receiver = node.child_by_field_name(grammar.receiver)
    if receiver is None:
        return ""
    pending = list(receiver.children)
    while pending:
        current = pending.pop(0)
        if current.type == "type_identifier":
            return _scope_name(current)
        pending.extend(current.children)
    return ""


def _enclosing_scopes(
    node: "tree_sitter.Node", found: Mapping[int, _Match], grammar: Grammar
) -> tuple[_Scope, ...]:
    """Outermost first: every definition or named scope `node` sits inside."""
    scopes: list[_Scope] = []
    receiver = _receiver_type(node, grammar)
    if receiver:
        scopes.append(_Scope(receiver, "class"))
    current = node.parent
    while current is not None:
        match = found.get(current.id)
        if match is not None and match.kind not in _NON_SCOPE_KINDS:
            scopes.append(_Scope(_local_name(match.name_node), match.kind))
        else:
            field_name = grammar.scopes.get(current.type)
            if field_name is not None:
                name = _scope_name(current.child_by_field_name(field_name))
                if name:
                    scopes.append(_Scope(name, "scope"))
        current = current.parent
    return tuple(reversed(scopes))


def extract_definitions(loaded: LoadedGrammar, source: bytes) -> tuple[CodeDefinition, ...]:
    """Every definition the grammar's tags queries find in `source`, qualified."""
    return read_fence(loaded, source).definitions


def extract_references(loaded: LoadedGrammar, source: bytes) -> tuple[CodeReference, ...]:
    """Every use the grammar's tags queries find in `source`, unqualified."""
    return read_fence(loaded, source).references


def read_fence(loaded: LoadedGrammar, source: bytes) -> FenceContents:
    """Parse one fence once and answer both questions of it.

    Deterministic: each list is ordered by position, then name, and the parse is
    a pure function of the bytes and the grammar version — which is why that
    version sits in the build key (:func:`grammar_fingerprint`).
    """
    import tree_sitter

    tree = tree_sitter.Parser(loaded.language).parse(source)
    root = tree.root_node

    # Keyed by node identity, not by byte span: a Python `expression_statement`
    # and the `assignment` it holds cover the same bytes, and a span key would
    # make the assignment its own enclosing scope (`CONSTANT.CONSTANT`).
    found: dict[int, _Match] = {}
    uses: dict[int, _Match] = {}
    for query in loaded.queries:
        for _, captures in tree_sitter.QueryCursor(query).matches(root):
            names = captures.get("name")
            if not names:
                continue
            for capture, nodes in captures.items():
                if capture.startswith("definition."):
                    target, prefix = found, "definition."
                elif capture.startswith("reference."):
                    target, prefix = uses, "reference."
                else:
                    continue
                kind = capture.removeprefix(prefix)
                for node in nodes:
                    current = target.get(node.id)
                    if current is None or _KIND_RANK.get(kind, 0) > _KIND_RANK.get(current.kind, 0):
                        target[node.id] = _Match(node, names[0], kind)

    definitions: list[CodeDefinition] = []
    for match in found.values():
        local = _local_name(match.name_node)
        if not local:
            continue
        kind = match.kind
        if kind == "constant" and not _CONSTANT_NAME.match(local.rsplit(".", 1)[-1]):
            continue
        scopes = _enclosing_scopes(match.node, found, loaded.grammar)
        if kind == "function" and scopes and scopes[-1].kind in _METHOD_SCOPES:
            kind = "method"
        name = ".".join([*(scope.name for scope in scopes), local])
        definitions.append(CodeDefinition(kind=kind, name=name, row=match.node.start_point.row))

    references: list[CodeReference] = []
    for match in uses.values():
        # The captured token, not `_local_name`: a use is resolved by name and
        # `RetryPolicy::new` in a call position should reach the same symbol as
        # `new` does, through the corpus index rather than through the fence.
        local = _text(match.name_node).replace("::", ".")
        if not local:
            continue
        references.append(
            CodeReference(kind=match.kind, name=local, row=match.node.start_point.row)
        )

    return FenceContents(
        definitions=tuple(sorted(definitions, key=lambda item: (item.row, item.name, item.kind))),
        references=tuple(sorted(references, key=lambda item: (item.row, item.name, item.kind))),
    )
