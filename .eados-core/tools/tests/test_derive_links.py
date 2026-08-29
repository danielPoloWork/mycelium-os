#!/usr/bin/env python3
"""Tests for derive_links — PR-body -> traceability-link derivation (roadmap 6.6 / F2).
Dependency-free and **gh-free**: the parser is exercised with fixture PR records; the gh fetch is
never invoked (CI has no network).

    python .eados-core/tools/tests/test_derive_links.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import derive_links as dl  # noqa: E402  (the module under test)
import render  # noqa: E402  (round-trip the emitted YAML)
import traceability  # noqa: E402  (feed the derived links to the gate)

# gh `pr list --json number,title,body,mergeCommit,milestone` shaped records.
RECORDS = [
    {"number": 81, "title": "feat(refactor): single-artifact render (closes #63)",
     "body": "Roadmap M6 item 6.3 per RFC-0001.", "mergeCommit": {"oid": "5c34109abc"},
     "milestone": {"title": "M6 - hardening & UX", "number": 6}},
    {"number": 70, "title": "chore(release): v2.0.0 - the pivot",
     "body": "Release rolling up RFC-0001.", "mergeCommit": {"oid": "b626522def"},
     "milestone": None},
    {"number": 99, "title": "docs: fix a typo", "body": "no crosslinks here",
     "mergeCommit": {"oid": "deadbeef"}, "milestone": None},
]

ROADMAP = (
    "# Roadmap\n## Milestone 1 — Bootstrap\n- [ ] 1.1 implement per RFC-0001\n"
)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def by_pr(links, pr):
    return next((l for l in links if l.get("pr") == pr), None)


def main():
    failures = []

    links = dl.parse_links(RECORDS)
    check("a non-delivery PR (no rfc/milestone) is skipped by default", by_pr(links, 99) is None,
          failures)
    check("delivery PRs (81, 70) are emitted", len(links) == 2, failures)

    e81 = by_pr(links, 81)
    check("PR 81 rfc parsed from the body", e81 and e81["rfc"] == "RFC-0001", failures)
    check("PR 81 milestone from gh metadata (title preferred over body 'M6')",
          e81 and e81["milestone"] == "M6 - hardening & UX", failures)
    check("PR 81 commit from mergeCommit.oid", e81 and e81["commit"] == "5c34109abc", failures)
    check("PR 81 has no release (no vX.Y.Z in title)", e81 and "release" not in e81, failures)

    e70 = by_pr(links, 70)
    check("PR 70 release parsed from the title", e70 and e70.get("release") == "v2.0.0", failures)
    check("PR 70 milestone is None (no metadata, none in body)", e70 and e70["milestone"] is None,
          failures)
    check("PR 70 rfc still parsed", e70 and e70["rfc"] == "RFC-0001", failures)

    # --include-all emits the non-delivery PR too (with null crosslinks)
    all_links = dl.parse_links(RECORDS, include_all=True)
    check("--all emits every PR", len(all_links) == 3, failures)
    e99 = by_pr(all_links, 99)
    check("the docs PR has null rfc + milestone under --all",
          e99 and e99["rfc"] is None and e99["milestone"] is None, failures)

    # emitted YAML round-trips through the hand-rolled loader and feeds the gate
    text = dl.emit_links_yaml(links)
    reloaded = (render.load_yaml(text) or {}).get("links") or []
    check("emitted YAML round-trips to the same edge count", len(reloaded) == 2, failures)
    r81 = by_pr(reloaded, 81)
    check("round-tripped PR 81 keeps its rfc/commit",
          r81 and r81.get("rfc") == "RFC-0001" and r81.get("commit") == "5c34109abc", failures)
    r70 = by_pr(reloaded, 70)
    check("round-tripped PR 70 milestone is null (None)", r70 and r70.get("milestone") is None,
          failures)

    # the derived links drive traceability_lint: PR 70's missing milestone -> pr-no-milestone
    kinds = [k for k, _ in traceability.traceability_lint(ROADMAP, ["RFC-0001"], reloaded)]
    check("traceability-lint flags PR 70's missing milestone", "pr-no-milestone" in kinds, failures)
    check("a release with pr+commit does not trip release-no-pr-commit",
          "release-no-pr-commit" not in kinds, failures)

    # empty input -> a valid, empty links document
    check("no records -> 'links: []'", "links: []" in dl.emit_links_yaml([]), failures)
    check("empty links doc round-trips to an empty list",
          ((render.load_yaml(dl.emit_links_yaml([])) or {}).get("links") or []) == [], failures)

    if failures:
        print("test-derive-links: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-derive-links: OK -- PR records parse to edges; delivery filter, --all, YAML "
          "round-trip, and the gate all hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
