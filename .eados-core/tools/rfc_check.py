#!/usr/bin/env python3
"""EADOS RFC check — verify an RFC against the review protocol (orchestrator/os/rfc/rfc.yaml).

Mechanically enforces the **`rfc-approved`** gate: the RFC carries every required section (as a
heading) and a well-formed **Approval record** by the approver role. The approval encodes a
*human* decision — this verifies the record exists and is by the right role, nothing more
(`AGENTS.md` §6). Dependency-free (stdlib + the sibling renderer's YAML loader).

Scope: this targets **generated-project** RFCs that follow `orchestrator/os/rfc/template.md`. A
repo's own meta-design RFC (e.g. EADOS's `docs/rfc/0001-eados-delivery-os.md`) may use a richer
structure and is intentionally out of scope — a FAIL there is by design, not a defect. See
`orchestrator/os/rfc/review-protocol.md` §Scope.

    python .eados-core/tools/rfc_check.py <rfc.md>
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # .eados-core/
sys.path.insert(0, HERE)
import render  # noqa: E402  — the hand-rolled, dependency-free YAML loader

RFC_SPEC = os.path.join(ROOT, "orchestrator", "os", "rfc", "rfc.yaml")


def load_protocol(path=RFC_SPEC):
    with open(path, encoding="utf-8") as handle:
        return render.load_yaml(handle.read())


def check_rfc(text, protocol):
    """Return a list of protocol violations (empty == the RFC satisfies rfc-approved)."""
    problems = []
    for sec in protocol.get("required_sections") or []:
        # A markdown heading containing the section name as a word — tolerant of numbering
        # ("## 3. Decision") and trailing words ("## Approval record").
        if not re.search(r"(?mi)^#{1,6}\s.*\b" + re.escape(sec) + r"\b", text):
            problems.append(f"missing required section heading: '{sec}'")
    approval = protocol.get("approval") or {}
    marker = approval.get("marker", "approved-by:")
    approver = protocol.get("approver_role", "")
    m = re.search(re.escape(marker) + r"\s*([A-Za-z][\w-]*)", text)
    if not m:
        problems.append(f"no approval record (expected '{marker} {approver} (YYYY-MM-DD)')")
    elif approver and m.group(1) != approver:
        problems.append(f"approved-by '{m.group(1)}' but the rfc-approved gate requires "
                        f"'{approver}'")
    return problems


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: rfc_check.py <rfc.md>", file=sys.stderr)
        return 2
    try:
        with open(argv[0], encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        print(f"rfc-check: cannot read {argv[0]!r}: {exc}", file=sys.stderr)
        return 2
    problems = check_rfc(text, load_protocol())
    if problems:
        print(f"rfc-check: FAIL — {argv[0]}")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"rfc-check: OK — {argv[0]} satisfies the rfc-approved gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
