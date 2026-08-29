#!/usr/bin/env python3
"""lesson_sweep — harvest review-time `Lesson:` fields from merged PRs into draft ledger entries
(#174, M13).

The lessons ledger stayed nearly empty because the capture point was wrong: end-of-run
recollection instead of review time, when the knowledge is hot and the human gate is already
open. The PR template now carries an optional `Lesson:` field; because squash-merge makes the PR
body the permanent `main` commit (`os/git/git.yaml` `commit.squash_body`), a merged lesson is
owner-approved by construction. This tool sweeps merged PR bodies for that field and drafts
`learning/lessons.yaml` entries for the owner to approve — it **prints** drafts and never writes
the ledger (lessons stay human-approved; the tool never self-approves).

    python .eados-core/tools/lesson_sweep.py [--limit N] [--repo OWNER/REPO]

Like `derive_links.py`: the parser (`extract_lesson` / `draft_entries`) is pure and tested
without `gh`; only the fetch shells out and degrades cleanly (clear message, exit 2) when `gh` is
absent, unauthenticated, or offline — CI never depends on the network.
"""

import os
import re
import subprocess
import sys

# Subprocess budgets (#321). `subprocess.run` without one waits FOREVER: a `gh` call that
# stalls on a TLS handshake, a rate-limit backoff, or an auth prompt with no stdin does not
# fail — it blocks until the CI job times out, and then reports as a generic job timeout
# rather than as "the network call hung". A timeout turns an unattributable stall into a
# clean, named degradation on the path this tool already has for `gh` being unavailable.
GH_TIMEOUT = 30    # network-bound

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # .eados-core/
LESSONS_PATH = os.path.join(ROOT, "learning", "lessons.yaml")

# The gh fields the parser needs (gh pr list --json <these>).
GH_FIELDS = "number,title,body,mergedAt"
# A `Lesson:` line at the start of a (stripped) body line; the value is the rest of the line.
_LESSON_RE = re.compile(r"(?im)^\s*Lesson:\s*(.+?)\s*$")
_ID_RE = re.compile(r"(?m)^-\s+id:\s*(L-(\d{4}))\s*$")
# Values that mean "no durable lesson" — the template default, blanks, and an unfilled placeholder.
_EMPTY = {"", "none", "n/a", "na", "-"}


# ---------------------------------------------------------------------------
# Pure core — no I/O, fixture-testable.
# ---------------------------------------------------------------------------
def extract_lesson(body):
    """The one-line lesson a PR body declares, or None. Reads the first `Lesson:` line; treats
    the template default ("none"), blanks, and an unfilled `<placeholder>` as no lesson."""
    for match in _LESSON_RE.finditer(body or ""):
        value = " ".join(match.group(1).split())
        if value.lower() in _EMPTY or value.startswith("<"):
            continue
        return value
    return None


def known_ids(ledger_text):
    """The lesson ids already in the ledger (textual — the ledger's root is a YAML sequence)."""
    return {m.group(1) for m in _ID_RE.finditer(ledger_text or "")}


def _next_num(ledger_text):
    nums = [int(m.group(2)) for m in _ID_RE.finditer(ledger_text or "")]
    return (max(nums) + 1) if nums else 1


def draft_entries(records, ledger_text, today):
    """Draft ledger entries for merged PRs that declared a lesson not already captured. Ids
    continue the ledger's sequence; scope defaults to `global` and context points at the PR
    (both are the owner's to refine — this is a draft, not an approval). A lesson whose text
    already appears in the ledger is skipped so re-running the sweep does not duplicate."""
    existing_text = (ledger_text or "").lower()
    num = _next_num(ledger_text)
    drafts = []
    for rec in records or []:
        if not isinstance(rec, dict):
            continue
        lesson = extract_lesson(rec.get("body") or "")
        if not lesson or lesson.lower() in existing_text:
            continue
        pr = rec.get("number")
        title = " ".join(str(rec.get("title") or "").split())
        merged = str(rec.get("mergedAt") or "")
        date = merged[:10] if re.match(r"\d{4}-\d{2}-\d{2}", merged) else today
        drafts.append({
            "id": f"L-{num:04d}",
            "date": date,
            "scope": "global",
            "context": f"From PR #{pr}" + (f" ({title})" if title else "") + " — review the scope "
                       "and context before approving.",
            "rule": lesson,
            "source": f"PR #{pr}" + (f" — {title}" if title else ""),
        })
        existing_text += "\n" + lesson.lower()   # dedupe within this same sweep too
        num += 1
    return drafts


def emit_drafts_yaml(drafts):
    """The drafts as ledger-shaped YAML the owner can review and paste into learning/lessons.yaml
    after refining scope/context. A header marks them as unapproved drafts."""
    if not drafts:
        return "# lesson-sweep: no new lessons found in the swept PRs.\n"
    out = ["# lesson-sweep DRAFTS — review scope/context, then paste approved entries into",
           "# learning/lessons.yaml. Nothing here is approved; the tool never writes the ledger."]
    for d in drafts:
        out.append("")
        out.append(f"- id: {d['id']}")
        out.append(f"  date: {d['date']}")
        out.append(f"  scope: {d['scope']}")
        out.append(f"  context: {d['context']}")
        out.append(f"  rule: {d['rule']}")
        out.append(f"  source: {d['source']}")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Thin gh shell — the only I/O; degrades cleanly when gh/network is unavailable.
# ---------------------------------------------------------------------------
def fetch_records(limit=100, repo=None):
    """Merged-PR records via `gh`. Raises RuntimeError (not a crash) when gh is missing,
    unauthenticated, or offline — the caller degrades cleanly."""
    import json
    cmd = ["gh", "pr", "list", "--state", "merged", "--limit", str(limit), "--json", GH_FIELDS]
    if repo:
        cmd += ["--repo", repo]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              timeout=GH_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"`gh` timed out after {GH_TIMEOUT}s — the network stalled, the API is "
                           "rate-limiting, or it is waiting on an auth prompt that will never be "
                           "answered")
    except (FileNotFoundError, OSError) as exc:
        raise RuntimeError(f"could not run `gh` (is the GitHub CLI installed and on PATH?): {exc}")
    if proc.returncode != 0:
        raise RuntimeError(f"`gh pr list` failed (authenticated? online?): "
                           f"{(proc.stderr or proc.stdout or '').strip()}")
    try:
        return json.loads(proc.stdout or "[]")
    except ValueError as exc:
        raise RuntimeError(f"could not parse `gh` JSON output: {exc}")


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    import argparse
    import datetime
    ap = argparse.ArgumentParser(
        description="Draft learning/lessons.yaml entries from merged PRs' `Lesson:` fields.")
    ap.add_argument("--limit", type=int, default=100, help="max merged PRs to scan (default 100)")
    ap.add_argument("--repo", help="OWNER/REPO (default: the current repo gh infers)")
    args = ap.parse_args(argv)

    try:
        records = fetch_records(limit=args.limit, repo=args.repo)
    except RuntimeError as exc:
        print(f"lesson-sweep: SKIP — {exc}", file=sys.stderr)
        return 2
    ledger_text = ""
    if os.path.exists(LESSONS_PATH):
        with open(LESSONS_PATH, encoding="utf-8") as handle:
            ledger_text = handle.read()
    drafts = draft_entries(records, ledger_text, datetime.date.today().isoformat())
    sys.stdout.write(emit_drafts_yaml(drafts))
    print(f"\nlesson-sweep: {len(drafts)} draft(s) from {len(records)} merged PR(s) — "
          "approve and paste into learning/lessons.yaml (nothing was written).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
