# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Judged case sets, as versioned JSONL (spec 04 §7.1).

One case per line, so a case set diffs cleanly, and adding or re-judging a query
shows up in review as exactly that. The format is the interchange format the rest
of the project already uses (D-006): JSONL for exchange, records for meaning.
"""

import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Final

from mycelium.sdk.types import EvalCase

if TYPE_CHECKING:
    from mycelium.store import SqliteStore

__all__ = ["HEADING_STUB_TOKENS", "load_cases", "validate_judged_set", "write_cases"]


def load_cases(path: Path) -> tuple[EvalCase, ...]:
    """Read a JSONL case set, refusing duplicates and malformed lines by line number."""
    cases: list[EvalCase] = []
    seen: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("//"):
            continue
        try:
            case = EvalCase.model_validate_json(line)
        except ValueError as error:
            msg = f"{path}:{number}: {error}"
            raise ValueError(msg) from error
        if case.case_id in seen:
            msg = f"{path}:{number}: duplicate case_id {case.case_id!r}"
            raise ValueError(msg)
        seen.add(case.case_id)
        cases.append(case)
    return tuple(cases)


def write_cases(path: Path, cases: Iterable[EvalCase]) -> None:
    """Write a case set: one compact record per line, sorted keys, LF."""
    lines = [
        json.dumps(case.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        for case in cases
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def slices_of(cases: Sequence[EvalCase]) -> tuple[str, ...]:
    """Every slice represented in a case set, sorted."""
    return tuple(sorted({slice_.value for case in cases for slice_ in case.slices}))


HEADING_STUB_TOKENS: Final = 30
"""Below this, a chunk is a heading and little else — too small to *be* an answer."""


def validate_judged_set(
    cases: Sequence[EvalCase], store: "SqliteStore"
) -> tuple[list[str], list[str]]:
    """Check a judged set against the corpus it judges: ``(errors, warnings)``.

    Three lints, and each of them exists because this project shipped the mistake
    it catches (ADR-0021, ADR-0027):

    **A judged anchor must exist.** A case citing an anchor the corpus does not
    contain is broken, and headings move. A *section* judgment (ADR-0029) resolves
    against the set of heading paths rather than against a chunk, since not
    depending on the chunk count is the whole point of writing one.

    **An `unanswerable` case must be unanswerable by *every* retriever.** The
    corpus keeps growing, including into a query's vocabulary — writing up a bug
    report once put an unanswerable query's own words into the corpus and turned
    gate G4 red. `grep` is checked too, because it matches word *prefixes*: a case
    that separates the two retrievers is measuring tokenisation, not abstention.

    **A grade-3 anchor should carry the answer.** A heading-stub chunk cited as
    *the* evidence is usually a skim-judgment: it reads as the right section and
    answers nothing. This one **warns**, because short is only a proxy for empty —
    ``## License`` followed by one line naming the licence is 24 tokens and is a
    complete answer to "what licence is this". A rule that cannot tell those apart
    is a reviewer's prompt, not a gate (ADR-0027).
    """
    from mycelium.eval.metrics import SECTION_MARKER, section_of
    from mycelium.eval.retrievers import build_retriever

    sections = {
        section_of(chunk.anchor)
        for doc_id in store.document_ids()
        for chunk in store.chunks_of(doc_id)
    }

    errors: list[str] = []
    warnings: list[str] = []
    for case in cases:
        for relevant in case.relevant:
            if relevant.anchor.endswith(SECTION_MARKER):
                # A section judgment resolves when the corpus holds a section by
                # that heading path; how many chunks it was split into is exactly
                # what the judgment declined to depend on (ADR-0029).
                if relevant.anchor not in sections:
                    errors.append(
                        f"{case.case_id}: judged section {relevant.anchor} is not in the "
                        "corpus - a heading probably moved; re-judge against the current text"
                    )
                continue
            chunk = store.get_chunk(relevant.anchor)
            if chunk is None:
                errors.append(
                    f"{case.case_id}: judged anchor {relevant.anchor} is not in the corpus "
                    "- a heading probably moved; re-judge against the current text"
                )
            elif relevant.grade == 3 and chunk.tokens < HEADING_STUB_TOKENS:
                warnings.append(
                    f"{case.case_id}: grade-3 anchor {relevant.anchor} is a heading stub "
                    f"({chunk.tokens} tokens) - check that it carries the answer"
                )

    retrievers = [(name, build_retriever(name, store)) for name in ("mycelium", "grep")]
    for case in cases:
        if case.answerable:
            continue
        for name, retriever in retrievers:
            found = retriever.search(case.query, 3)
            if found:
                errors.append(
                    f"{case.case_id}: `unanswerable` but {name} answers it with {found[0]} "
                    "- the corpus grew into the query's vocabulary. Re-draw the query from a "
                    "domain this corpus will never cover, and never quote it verbatim in "
                    "prose, or documenting the case will answer it"
                )
    return errors, warnings
