#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""How far each judged slice is from a bar that means more than one case.

    python tools/measure_slice_power.py

Roadmap 6.8 exists because gate G3's per-slice condition — no slice may regress
more than 2 % — is a statement about a *category* of question, and at four to
seven cases a slice it is a statement about one question. This reports, for every
committed baseline, the count each slice would need before that stops being true,
and how many cases short it is.

The arithmetic is `mycelium.eval.harness.enforceable_at`, which is also what gate
G3 reads, so this tool and the gate cannot disagree (ADR-0123). A slice of `n`
cases at blessed mean `m` trips when its total gain falls by more than
`0.02 · n · m`; the smallest real thing that happens to a case is that it stops
being answered, costing the slice that case's whole score; so the bar needs more
than one case exactly when `n ≥ q / (0.02 · m)`, with `q` the median blessed
non-zero per-case score.

**It is a target, not a verdict.** Nothing here says a slice is wrong — it says
how many judged cases it would take for its gate to be a gate. Run it while
authoring cases (roadmap 6.8's remaining half) to see the shortfall close.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.eval.harness import G3_REPORTED_SLICES, enforceable_at  # noqa: E402

BASELINES: tuple[Path, ...] = (
    ROOT / "eval" / "baselines",
    ROOT / "eval" / "corpora" / "uv-docs" / "eval" / "baselines",
    ROOT / "eval" / "corpora" / "uv-docs-ingested" / "eval" / "baselines",
)
"""Every committed baseline directory — the frozen numbers G3 compares against."""


def rows(path: Path, arm: str = "mycelium") -> list[tuple[str, int, float, float, int]]:
    """One row per slice: name, cases held, blessed mean, typical case, cases needed."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    blessed = payload.get(arm)
    if not isinstance(blessed, dict):
        return []
    means = blessed.get("per_slice") or {}
    per_case = blessed.get("per_case") or {}

    found: list[tuple[str, int, float, float, int]] = []
    for name, mean in sorted(means.items()):
        if name in G3_REPORTED_SLICES or not isinstance(mean, int | float) or mean <= 0:
            continue  # gated elsewhere, or with nothing to lose (ADR-0052)
        scores = [float(v) for v in (per_case.get(name) or {}).values()]
        answered = sorted(score for score in scores if score > 0.0)
        typical = answered[len(answered) // 2] if answered else 0.0
        found.append((name, len(scores), float(mean), typical, enforceable_at(float(mean), scores)))
    return found


def report(directory: Path) -> int:
    """Print one baseline directory's table. Returns the number of unarmed slices."""
    unarmed = 0
    for path in sorted(directory.glob("*.json")):
        found = rows(path)
        if not found:
            continue
        label = path.relative_to(ROOT).as_posix()
        print(f"\n{label}")
        print(f"  {'slice':14}{'cases':>6}{'blessed':>9}{'typical':>9}{'needs':>7}{'short':>7}")
        for name, cases, mean, typical, needs in found:
            short = max(0, needs - cases)
            unarmed += 1 if short else 0
            print(f"  {name:14}{cases:6}{mean:9.3f}{typical:9.3f}{needs:7}{short:7}")
    return unarmed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--baselines", type=Path, action="append", help="a baseline directory to read"
    )
    args = parser.parse_args(argv)

    directories = args.baselines or list(BASELINES)
    unarmed = sum(report(directory) for directory in directories if directory.exists())
    print(
        f"\n{unarmed} slice(s) hold fewer cases than their own bar needs. G3 reports those "
        "rows and enforces the rest; authoring cases is what arms them (roadmap 6.8)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
