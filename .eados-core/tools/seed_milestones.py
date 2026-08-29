#!/usr/bin/env python3
"""EADOS milestone seeder (roadmap M11 #143) — read `ROADMAP.md` and seed EVERY roadmap milestone on
GitHub as `MN — <name>` (em-dash) with a professional description derived from the milestone's Goal.
Run it once, right after the roadmap is finalized, so milestone-scoped PR delivery can begin against
a complete board — matching EADOS's own `M1 … MN` milestones (the dogfood).

By DEFAULT it PRINTS the exact `gh api …/milestones` commands (safe — copy-paste, or pipe to a
shell); `--run` executes them via `gh`, degrading cleanly (clear message, exit 2) when gh is
missing/offline. Creating a milestone that already exists returns HTTP 422 — safe to ignore, so the
seeder is re-runnable. Parsing is markdown-only and dependency-free.

    python .eados-core/tools/seed_milestones.py [ROADMAP.md] [--run] [--repo OWNER/REPO] [--json]
"""

import os
import re
import shlex
import subprocess
import sys

# Subprocess budgets (#321). `subprocess.run` without one waits FOREVER: a `gh` call that
# stalls on a TLS handshake, a rate-limit backoff, or an auth prompt with no stdin does not
# fail — it blocks until the CI job times out, and then reports as a generic job timeout
# rather than as "the network call hung". A timeout turns an unattributable stall into a
# clean, named degradation on the path this tool already has for `gh` being unavailable.
GH_TIMEOUT = 30    # network-bound

HERE = os.path.dirname(os.path.abspath(__file__))

# `## Milestone <N> — <title>` (em-dash; a hyphen is tolerated). The title runs to end-of-line.
HEADER = re.compile(r"^##\s+Milestone\s+(\d+)\s+[—-]\s+(.+?)\s*$")
ITEM = re.compile(r"^- \[[ xX]\]\s+(\d+\.\d+)\b")
GOAL_MARK = re.compile(r"^\*\*Goal[.:]\*\*\s*")


# --- the pure parser ------------------------------------------------------
def parse_roadmap(text):
    """Return `[{number, title, goal, items[]}]` from a ROADMAP.md, in document order. `goal` is the
    first paragraph after the header (a leading `**Goal.**` marker stripped); `items` are the `N.M`
    ids under the milestone. Pure (string in, list out)."""
    lines = text.splitlines()
    heads = [i for i, ln in enumerate(lines) if HEADER.match(ln)]
    milestones = []
    for k, start in enumerate(heads):
        end = heads[k + 1] if k + 1 < len(heads) else len(lines)
        h = HEADER.match(lines[start])
        block = lines[start + 1:end]
        goal_parts = []
        for ln in block:
            s = ln.strip()
            if not s:
                if goal_parts:
                    break                       # blank line ends the first paragraph
                continue
            if s == "---" or s.startswith("#") or s.startswith(("- ", "* ", "|", "{{")):
                break                           # divider / sub-heading / list / template marker
            goal_parts.append(GOAL_MARK.sub("", s))
        items = [m.group(1) for ln in block for m in (ITEM.match(ln),) if m]
        milestones.append({
            "number": int(h.group(1)),
            "title": h.group(2).strip(),
            "goal": " ".join(goal_parts).strip(),
            "items": items,
        })
    return milestones


def milestone_title(m):
    """The GitHub milestone title: `MN — <name>` (matching this repo's own M1 … MN)."""
    return f"M{m['number']} — {m['title']}"


def milestone_description(m):
    """A professional one-paragraph description: the Goal, plus a short item summary."""
    goal = m.get("goal") or f"Milestone {m['number']} of the delivery roadmap."
    items = m.get("items") or []
    if items:
        span = items[0] if len(items) == 1 else f"{items[0]}–{items[-1]}"
        return f"{goal} Roadmap items: {span} ({len(items)} total)."
    return goal


def gh_argv(m, repo=None):
    """The `gh api` argv that creates one milestone (no shell — safe for subprocess)."""
    repo_path = repo or ":owner/:repo"
    return ["gh", "api", "-X", "POST", f"repos/{repo_path}/milestones",
            "-f", f"title={milestone_title(m)}",
            "-f", "state=open",
            "-f", f"description={milestone_description(m)}"]


def gh_command(m, repo=None):
    """The same call as a copy-pasteable, properly shell-quoted one-liner."""
    return " ".join(shlex.quote(a) for a in gh_argv(m, repo))


# --- the thin `gh` shell (only on --run; degrades cleanly) ----------------
def run_one(m, repo=None):
    """Create one milestone via `gh`. Returns (ok, message). RuntimeError only when gh is
    missing/unreachable; an existing milestone (422) is reported as a benign skip."""
    try:
        proc = subprocess.run(gh_argv(m, repo), capture_output=True, text=True,
                              encoding="utf-8", timeout=GH_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"`gh` timed out after {GH_TIMEOUT}s — the network stalled, the API is "
                           "rate-limiting, or it is waiting on an auth prompt that will never be "
                           "answered")
    except (FileNotFoundError, OSError) as exc:
        raise RuntimeError(f"could not run `gh` (is the GitHub CLI installed and on PATH?): {exc}")
    if proc.returncode == 0:
        return (True, f"created {milestone_title(m)!r}")
    err = (proc.stderr or proc.stdout or "").strip()
    if "already_exists" in err or "HTTP 422" in err:
        return (True, f"exists (skipped) {milestone_title(m)!r}")
    return (False, f"FAILED {milestone_title(m)!r}: {err}")


def main(argv=None):
    # issue #128: force UTF-8 stdio so the em-dash titles won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    import argparse
    import json
    ap = argparse.ArgumentParser(description="Seed every roadmap milestone (MN — name) on GitHub "
                                             "from ROADMAP.md, with a goal-derived description.")
    ap.add_argument("roadmap", nargs="?", default="ROADMAP.md", help="path to ROADMAP.md")
    ap.add_argument("--run", action="store_true", help="execute the gh calls (default: print them)")
    ap.add_argument("--repo", help="OWNER/REPO (default: the repo gh infers)")
    ap.add_argument("--json", action="store_true", help="emit the parsed milestones as JSON")
    args = ap.parse_args(argv)

    try:
        text = open(args.roadmap, encoding="utf-8").read()
    except OSError as exc:
        print(f"seed-milestones: could not read {args.roadmap}: {exc}", file=sys.stderr)
        return 2
    milestones = parse_roadmap(text)
    if not milestones:
        print(f"seed-milestones: no `## Milestone N — name` headers found in {args.roadmap}",
              file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps([{"title": milestone_title(m),
                           "description": milestone_description(m)} for m in milestones], indent=2))
        return 0
    if args.run:
        try:
            results = [run_one(m, repo=args.repo) for m in milestones]
        except RuntimeError as exc:
            print(f"seed-milestones: SKIP — {exc}", file=sys.stderr)
            return 2
        for ok, msg in results:
            print(f"  {'[OK]  ' if ok else '[FAIL]'} {msg}")
        return 0 if all(ok for ok, _ in results) else 1
    # default: print the exact gh commands (safe to copy-paste or pipe to a shell)
    print(f"# {len(milestones)} roadmap milestone(s) from {args.roadmap} — pipe to a shell, or add --run:")
    for m in milestones:
        print(gh_command(m, repo=args.repo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
