#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Re-bless the gate-G6 golden file after an intentional compiler change.

    python tools/update_determinism_golden.py

The gate fails whenever compiled output changes. That is the point: the diff this
tool produces is the change, and reviewing it is how a compiler change gets
approved rather than absorbed. Run it only when the difference is intended, and
put the reason in the PR.

The corpus is copied to a temporary directory before building, so the committed
fixtures are never touched — the same thing the gate does.
"""

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.determinism import observe_build, write_golden  # noqa: E402

CORPUS = ROOT / "tests" / "fixtures" / "determinism"
GOLDEN = CORPUS / "golden.json"


def main() -> int:
    with tempfile.TemporaryDirectory() as scratch:
        workspace = Path(scratch) / "corpus"
        shutil.copytree(CORPUS / "knowledge", workspace / "knowledge")
        observation = observe_build(workspace)

    before = GOLDEN.read_text(encoding="utf-8") if GOLDEN.exists() else ""
    write_golden(GOLDEN, observation)
    after = GOLDEN.read_text(encoding="utf-8")

    if before == after:
        print(f"golden unchanged: {GOLDEN.relative_to(ROOT)}")
        return 0
    print(f"golden updated: {GOLDEN.relative_to(ROOT)}")
    print("Review the diff — it is the compiler change, and it belongs in the PR body.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
