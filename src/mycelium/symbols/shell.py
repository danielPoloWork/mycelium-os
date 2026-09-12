# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Commands: what a documentation corpus demonstrates at a prompt and names in prose (roadmap 5.23).

Spec 03 §2's identity has a language segment and two sources — tree-sitter for
code, definition syntax for docs — and neither reaches a *command*. Sixteen of
the nineteen judged `symbol` case-instances ask for one (`uv tool install`,
`uv lock --check`, `uv python pin`), spec 04 §2's identifier test rejects every
one of them on whitespace alone, and the pages that document them head their
sections *Installing tools* and *Checking the lockfile* — never with the command.
So a command needed a source of its own, and this module is it: language
``cli``, kind ``command``, identity ``sym:cli:uv tool install`` with the words
kept as a shell would read them.

**A command is what the corpus both demonstrates and names.** Measured on the
uv documentation before the rule was chosen (2026-09-12): 509 prompt lines in
388 console fences yield 176 distinct multi-word invocation prefixes, of which
the prose names 45 in inline code — and those 45 are, almost exactly, the
CLI's command list (`uv add`, `uv lock`, `uv pip install`, `uv python pin`,
`uv tool install`, `uv self update`, …). The 131 demonstrated and never named
are arguments and one-offs: `uv add httpx`, `uv init example-bare`,
`aws lambda create-function`. The named and never demonstrated are mentions of
things the corpus talks about but does not show (`uv cache prune`, `pip check`).
Neither half is a definition on its own; the intersection is.

The two halves are two syntaxes, and both are read where they are written:

- **A prompt line** — ``$ uv tool install ruff`` inside a console fence — is a
  *demonstration*. Its leading run of shell words (``uv tool install``) and every
  prefix of that run (``uv``, ``uv tool``) are candidate commands; ``ruff``, a
  version, a path or a flag ends the run. Which prefix is the command and which
  is an argument is exactly what one line cannot know — ``uv add requests`` and
  ``uv tool install`` have the same shape — and the corpus decides at resolution
  (:mod:`mycelium.symbols.resolve`), which is why every prefix is offered.
- **A code span** — ``` `uv tool install` ``` in a paragraph — is a *naming*.
  Documentation names a command in backticks and, unlike a prompt line, names it
  *without its arguments* nearly every time: the span's own word run is the
  phrase the author meant. A heading that is a run of shell words (``## pip
  check``, the convention CLI reference pages use) names one the same way.

Reading a prompt line uses no grammar and no dependency: shells have one
tokenizer worth agreeing with (``shlex``), and a command is a run of *shell
words* — lowercase, starting with a letter, made of letters, digits and hyphens.
The rule is stated once here and shared with the query side
(:func:`command_phrase`), for the reason ADR-0080 gave for `identifier_like`: a
query that names a command and an extractor that mints one must agree on what a
command looks like, or the leg misses precisely the symbols the table holds.
"""

import re
import shlex
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

__all__ = [
    "CLI_LANGUAGE",
    "COMMAND_KIND",
    "MAX_COMMAND_WORDS",
    "SCRIPT_FENCES",
    "SESSION_FENCES",
    "Invocation",
    "command_phrase",
    "command_prefixes",
    "command_run",
    "named_command",
    "named_heading",
    "read_session",
    "shell_word",
]

CLI_LANGUAGE: Final = "cli"
"""The `<language>` segment of a command symbol (spec 03 §2). Not a grammar in
the tree-sitter registry — a shell is not one language, and the corpora that
document commands write them for whichever shell the reader has."""

COMMAND_KIND: Final = "command"
"""The `kind` of every command symbol, program and subcommand alike: `uv` is the
root of the same tree `uv tool install` is a leaf of."""

MAX_COMMAND_WORDS: Final = 5
"""How many shell words a command may run to.

`uv tool install` is three, `gh auth login` three, `aws lambda create-function`
three; the deepest real command tree in either measured corpus is four
(`uv pip compile` under a program is three — the bound is one more than the
deepest observed, so it is a ceiling rather than a fit). Beyond it the words are
arguments, and every prefix up to the bound is still offered."""

SESSION_FENCES: Final = frozenset(
    {
        "",
        "bash",
        "console",
        "fish",
        "sh",
        "shell",
        "shell-session",
        "shellsession",
        "terminal",
        "text",
        "zsh",
    }
)
"""Fence tags whose *prompt lines* are demonstrations.

`console` and `shell-session` are the tags written for the purpose. `bash`,
`sh`, `shell` and `zsh` are how authors tag a session as often as a script, and
a prompt inside one is unambiguous. `text` and the untagged fence are included
because a ``$ `` prompt at the start of a line in a documentation fence is a
shell session whatever the author called it — measured: four of this
repository's own `text` fences hold prompt lines, and nothing else does."""

SCRIPT_FENCES: Final = frozenset({"bash", "fish", "sh", "shell", "zsh"})
"""Fence tags whose lines are commands *without* a prompt.

A `bash` fence with no prompt in it is a script, and a script's lines are
invocations by definition — this repository's README documents every
`mycelium` command that way. Comments, assignments and continuation lines are
skipped; a keyword such as `if` is a shell word and is offered, and the corpus
will not name it, so it never becomes a symbol."""

_PROMPT: Final = re.compile(r"^\s*(?:\$|%|>|PS(?:\s+\S+)?>|❯)\s+(?P<command>\S.*)$")
"""The prompts a session line may open with: `$ ` and `% ` (POSIX shells),
`> ` and `PS C:\\> ` (Windows), `❯ ` (the prompt several modern shells draw)."""

_WORD: Final = re.compile(r"^[a-z][a-z0-9-]*$")
"""A shell word: what a program or a subcommand is spelled like. Lowercase by
rule rather than by observation of one CLI — `Get-ChildItem` is a PowerShell
cmdlet and is not read, and that limit is stated in ADR-0094."""

_ASSIGNMENT: Final = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
"""A script line that sets a variable rather than running anything."""

_QUERY_PUNCTUATION: Final = "`\"'.,;:!?()[]{}"


@dataclass(frozen=True, slots=True)
class Invocation:
    """One command line a fence demonstrates."""

    run: tuple[str, ...]
    """The leading shell words — the command and any subcommands — up to
    :data:`MAX_COMMAND_WORDS`. Never empty."""
    row: int
    """0-based line of the invocation within the fence."""


def shell_word(token: str) -> bool:
    """Whether `token` is spelled the way a program or subcommand is."""
    return _WORD.match(token) is not None


def command_run(tokens: Sequence[str]) -> tuple[str, ...]:
    """The leading run of shell words in a tokenised command line, bounded."""
    run: list[str] = []
    for token in tokens:
        if not shell_word(token) or len(run) >= MAX_COMMAND_WORDS:
            break
        run.append(token)
    return tuple(run)


def command_prefixes(run: Sequence[str]) -> tuple[str, ...]:
    """Every command a run may be spelling: `uv`, `uv tool`, `uv tool install`."""
    return tuple(" ".join(run[:length]) for length in range(1, len(run) + 1))


def _tokens(line: str) -> list[str]:
    try:
        return shlex.split(line, posix=True)
    except ValueError:
        # An unbalanced quote is the author's problem, not a reason to lose the
        # line: whitespace is the tokenizer every shell agrees on first.
        return line.split()


def read_session(text: str, lang: str | None) -> tuple[Invocation, ...]:
    """The invocations one fence demonstrates, in order.

    A fence in :data:`SESSION_FENCES` contributes its prompt lines; a fence in
    :data:`SCRIPT_FENCES` with *no* prompt line contributes every line that is a
    command — not a comment, an assignment, a continuation of the line above, or
    output. A fence tagged for another language contributes nothing, whatever it
    holds: a ``$`` at the start of a line of Python is Python.
    """
    tag = (lang or "").strip().split()[0].casefold() if (lang or "").strip() else ""
    if tag not in SESSION_FENCES:
        return ()
    lines = text.split("\n")
    prompted = [
        (row, match.group("command"))
        for row, line in enumerate(lines)
        if (match := _PROMPT.match(line))
    ]
    if prompted:
        candidates = prompted
    elif tag in SCRIPT_FENCES:
        candidates = []
        continued = False
        for row, line in enumerate(lines):
            stripped = line.strip()
            starts = bool(stripped) and not line[0].isspace() and not continued
            continued = stripped.endswith("\\")
            if not starts or stripped.startswith("#") or _ASSIGNMENT.match(stripped):
                continue
            candidates.append((row, stripped))
    else:
        return ()

    invocations: list[Invocation] = []
    for row, command in candidates:
        run = command_run(_tokens(command.rstrip("\\").strip()))
        if run:
            invocations.append(Invocation(run=run, row=row))
    return tuple(invocations)


def named_command(span: str) -> tuple[str, ...]:
    """The command a code span names, as a run of shell words; empty for none.

    ``uv tool install`` names three words; ``uv lock --check`` names ``uv lock``
    (the flag ends the run, and the section that shows the flag is documenting
    the command); ``uv tool install ruff`` names its whole run, and whether that
    is a command or a named invocation is the corpus's call at resolution.
    ``SqliteStore``, ``pyproject.toml`` and ``--no-pin`` name no command: the
    first word must be a shell word.
    """
    return command_run(span.strip().split())


def named_heading(text: str) -> tuple[str, ...]:
    """The command a heading names, when the heading *is* a run of shell words.

    The convention of a CLI reference page — ``### uv tool install``,
    ``## pip check`` — and nothing looser: every word must be a shell word, or
    *Installing tools* would name ``installing tools``.
    """
    words = text.strip().split()
    if not words or len(words) > MAX_COMMAND_WORDS or not all(shell_word(word) for word in words):
        return ()
    return tuple(words)


def command_phrase(query: str, *, stopwords: Iterable[str] = ()) -> str | None:
    """The command a *query* names, for an exact lookup (spec 04 §2), or ``None``.

    Two shapes qualify, and both are the whole of what the user typed rather
    than a window slid over it:

    - **a quoted phrase** — ``"uv tool install"``, or the same in backticks —
      which is spec 04 §2's own signal for an exact lookup, applied to the `cli`
      language;
    - **a command-shaped query** — one whose tokens are a leading run of shell
      words followed by nothing but flags and arguments (``uv lock --check``,
      ``uv python pin 3.11``, ``uvx``), holding at most
      :data:`MAX_COMMAND_WORDS` words and **no function word**. The last
      condition is what separates ``uv tool install`` from ``how do i install``:
      a command has no *how*, *do*, *the* or *with* in it, and a question does.
      `stopwords` is that list, supplied by the caller because the planner owns
      it (ADR-0057, roadmap 5.23) and one list must serve both.

    A sentence that happens to contain a command unquoted — *how do I use uv
    tool install* — is routed nowhere by this rule, on purpose: the alternative
    is looking every window of every question up as a command, which reports
    ``how do`` as a command phrase in every plan and finds nothing.

    **The answer is the run, whole, and never a prefix of it.** A corpus that
    holds ``uv python`` and not ``uv python pin`` does not answer a query about
    ``uv python pin`` with the parent's sites: that is ADR-0080's tail-matching
    refusal from the other end — the parent is a different thing from the one
    asked about — and it was measured to bury the judged section under every
    page that runs the parent (ADR-0094). The words are read as written, not
    casefolded: a command is lowercase, and casefolding would turn
    ``SqliteStore`` into a shell word.
    """
    stripped = query.strip()
    if not stripped:
        return None
    quoted = re.fullmatch(r"[\"'`](.+)[\"'`]", stripped)
    if quoted:
        stripped = quoted.group(1).strip()
    words = [token.strip(_QUERY_PUNCTUATION) for token in stripped.split()]
    words = [word for word in words if word]
    if not words:
        return None
    run = command_run(words)
    if not run:
        return None
    if not quoted:
        rest = words[len(run) :]
        # Command-shaped: what follows the run is flags and arguments, never
        # another word — `uv lock --check`, not `uv lock the project`.
        if any(shell_word(token) for token in rest):
            return None
        banned = set(stopwords)
        if any(word in banned for word in run):
            return None
    return " ".join(run)
