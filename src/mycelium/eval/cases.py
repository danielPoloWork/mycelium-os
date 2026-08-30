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

from mycelium.sdk.types import EvalCase

__all__ = ["load_cases", "write_cases"]


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
