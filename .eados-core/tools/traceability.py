#!/usr/bin/env python3
"""EADOS traceability — the lineage graph and the `roadmap-covers-rfcs` + `traceability-lint` gates
(roadmap 3.3 / 3.4 / 4.3; RFC-0001 §7).

Builds the `RFC → milestone` edges from a roadmap (`roadmap-covers-rfcs`: every RFC is addressed by
a milestone), and — given the Git-side cross-link edges (`milestone → PR → commit → release`, from
the `git` spec) — detects **dangling edges** (`traceability-lint`: an RFC with no PR, a PR missing
its RFC/milestone, a release not tracing to a PR + commit). Dependency-free.

    python .eados-core/tools/traceability.py <roadmap.md> <RFC-id> [<RFC-id> ...]
    python .eados-core/tools/traceability.py <roadmap.md> <RFC-id> ... --links links.yaml
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render  # noqa: E402  — the hand-rolled YAML loader (for the --links edge file)


def parse_milestones(text):
    """Ordered list of (number, title, body) for each `## Milestone N — ...` section."""
    out = []
    matches = list(re.finditer(r"(?m)^##\s+Milestone\s+(\d+)\s*[—:-]?\s*(.*)$", text))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out.append((m.group(1), m.group(2).strip(), text[start:end]))
    return out


def covering_milestones(text, rfc_id):
    """The milestone numbers whose section mentions `rfc_id` (the RFC → milestone edges).

    Matched on a word boundary, NOT as a raw substring: a longer id (`RFC-00021`) must not
    falsely satisfy a shorter one (`RFC-0002`), or `roadmap-covers-rfcs` would report false
    coverage and pass when it should fail."""
    pattern = re.compile(rf"\b{re.escape(rfc_id)}\b")
    return [num for num, _title, body in parse_milestones(text) if pattern.search(body)]


def uncovered_rfcs(text, rfc_ids):
    """RFC ids no milestone references — the roadmap-covers-rfcs violations."""
    return [r for r in rfc_ids if not covering_milestones(text, r)]


def traceability_lint(roadmap_text, rfc_ids, links):
    """Detect dangling edges in the `RFC → milestone → PR → commit → release` graph. `links` is a
    list of `{pr, rfc, milestone, commit, release}` edge records (from the PR cross-links the
    `git` spec mandates). Returns a list of `(kind, detail)` problems — empty means the graph is
    whole."""
    problems = []
    for rfc in uncovered_rfcs(roadmap_text, rfc_ids):
        problems.append(("rfc-no-milestone", rfc))
    linked_rfcs = {l.get("rfc") for l in links if isinstance(l, dict) and l.get("rfc")}
    for rfc in rfc_ids:
        if rfc not in linked_rfcs:
            problems.append(("rfc-no-pr", rfc))
    for l in links:
        if not isinstance(l, dict):
            continue
        pr = l.get("pr")
        if not l.get("rfc"):
            problems.append(("pr-no-rfc", f"PR {pr}"))
        if not l.get("milestone"):
            problems.append(("pr-no-milestone", f"PR {pr}"))
        if l.get("release") and not (l.get("pr") and l.get("commit")):
            problems.append(("release-no-pr-commit", str(l.get("release"))))
    return problems


def _load_links(path):
    """Read the edge file — a mapping with a top-level `links:` list of edge records."""
    with open(path, encoding="utf-8") as handle:
        data = render.load_yaml(handle.read())
    return (data or {}).get("links") or []


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    import argparse
    ap = argparse.ArgumentParser(description="EADOS traceability — coverage + dangling-edge lint.")
    ap.add_argument("roadmap", help="path to ROADMAP.md")
    ap.add_argument("rfcs", nargs="*", help="the RFC ids to trace")
    ap.add_argument("--links", help="YAML edge file: {links: [{pr,rfc,milestone,commit,release}]}")
    args = ap.parse_args(argv)
    try:
        with open(args.roadmap, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        print(f"traceability: cannot read roadmap {args.roadmap!r}: {exc}", file=sys.stderr)
        return 2

    if args.links:
        problems = traceability_lint(text, args.rfcs, _load_links(args.links))
        if problems:
            print("traceability-lint: FAIL — dangling edges:")
            for kind, detail in problems:
                print(f"  [{kind}] {detail}")
            return 1
        print("traceability-lint: OK -- the RFC->milestone->PR->commit->release graph is whole.")
        return 0

    milestones = parse_milestones(text)
    print(f"roadmap: {len(milestones)} milestone(s); RFCs to cover: {len(args.rfcs)}")
    for rfc in args.rfcs:
        cov = covering_milestones(text, rfc)
        where = ", ".join(f"M{n}" for n in cov) if cov else "—"
        print(f"  {rfc} -> {where}")
    missing = uncovered_rfcs(text, args.rfcs)
    if missing:
        print("roadmap-covers-rfcs: FAIL — no milestone addresses:")
        for r in missing:
            print(f"  {r}")
        return 1
    if args.rfcs:
        print("roadmap-covers-rfcs: OK — every RFC is addressed by a milestone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
