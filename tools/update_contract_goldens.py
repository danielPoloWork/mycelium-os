#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Re-bless the compatibility goldens after an intended change to a stable contract.

    python tools/update_contract_goldens.py

`tests/test_contracts.py` fails whenever one of the five stable contracts
(architecture §10) no longer matches its golden under `tests/fixtures/contracts/`.
That is the point: the diff this tool produces is the contract change, and reviewing
it is how such a change gets approved rather than absorbed (roadmap 6.1, ADR-0114).

A changed golden is never just a re-bless. Spec 06 §4 makes a change to a stable
contract an RFC, spec 05 §5 makes it a CHANGELOG migration note, and an
*incompatible* change bumps the contract's version token first — the golden file is
named after it, so the bump renames the file and the old shape stays in history.
Run this only when the difference is intended, and put all three in the PR.

The history fixtures beside the goldens (`tests/fixtures/contracts/history/`) are
records earlier releases wrote and are never regenerated: they exist to prove a
reader still accepts them.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.contracts import CONTRACTS, golden_name, project, write_golden  # noqa: E402

GOLDENS = ROOT / "tests" / "fixtures" / "contracts"

# ASCII only: this reaches a Windows console that may not be UTF-8 (BUG-0009).
REMINDER = """\
A golden moved, so a stable contract moved. Before this lands:
  - an RFC under docs/rfc/ says why (spec 06 section 4), and an ADR records the decision;
  - CHANGELOG.md carries a migration note under [Unreleased];
  - if a consumer of the old shape can no longer read the new one, the contract's
    version token is bumped first (schema_version, or MYCELIUM_API_VERSION) and the
    golden is renamed with it;
  - the golden diff is in the PR body - it is the change."""


def main() -> int:
    GOLDENS.mkdir(parents=True, exist_ok=True)
    expected = {golden_name(item.name) for item in CONTRACTS}
    changed = False
    for item in CONTRACTS:
        path = GOLDENS / golden_name(item.name)
        before = path.read_text(encoding="utf-8") if path.exists() else None
        write_golden(path, project(item.name))
        after = path.read_text(encoding="utf-8")
        if before is None:
            status = "written"
        elif before == after:
            status = "unchanged"
        else:
            status = "updated"
        changed = changed or before != after
        print(f"{status}: {path.relative_to(ROOT).as_posix()}")

    strays = sorted(p.name for p in GOLDENS.glob("*.json") if p.name not in expected)
    for name in strays:
        print(
            f"stray golden: {name} names a token no contract carries any more - remove it "
            "(the old shape is in history) or restore the token"
        )

    if changed:
        print()
        print(REMINDER)
    return 1 if strays else 0


if __name__ == "__main__":
    raise SystemExit(main())
