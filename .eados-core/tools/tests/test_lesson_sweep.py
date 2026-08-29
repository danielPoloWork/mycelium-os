#!/usr/bin/env python3
"""Tests for lesson_sweep (#174) — the review-time lesson harvester behind the PR `Lesson:` field.

Pure-core fixtures: `extract_lesson` reads the field and treats none/blank/placeholder as no
lesson; `draft_entries` continues the ledger's id sequence, dates from `mergedAt`, skips PRs
whose lesson text is already captured, and dedupes within one sweep; the emitted drafts parse
back as ledger-shaped YAML entries. The `gh` fetch is not exercised (network-free), mirroring
derive_links's test posture. Dependency-free.

    python .eados-core/tools/tests/test_lesson_sweep.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import lesson_sweep as ls  # noqa: E402  (the module under test)

REAL_LESSONS = os.path.join(ROOT, "learning", "lessons.yaml")

LEDGER = ("- id: L-0001\n  scope: global\n  rule: an existing captured rule about indentation.\n"
          "- id: L-0002\n  scope: global\n  rule: another existing rule.\n")


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    # --- extract_lesson: the field, and the not-a-lesson values ---
    check("a real lesson line is extracted",
          ls.extract_lesson("## Lesson\n\nLesson: always pin the reference parser")
          == "always pin the reference parser", failures)
    check("the template default 'none' is not a lesson",
          ls.extract_lesson("Lesson: none") is None, failures)
    check("a blank field is not a lesson", ls.extract_lesson("Lesson:   ") is None, failures)
    check("an unfilled <placeholder> is not a lesson",
          ls.extract_lesson("Lesson: <one-line generalizable rule>") is None, failures)
    check("case/indentation tolerated, whitespace collapsed",
          ls.extract_lesson("   lesson:   keep   it    tidy  ") == "keep it tidy", failures)
    check("no field at all -> None", ls.extract_lesson("## Summary\nchanges") is None, failures)
    check("the HTML guidance comment does not count as a lesson",
          ls.extract_lesson("<!-- write Lesson: none if nothing durable -->\nLesson: none")
          is None, failures)

    # --- known_ids / id sequencing ---
    check("known_ids reads the ledger ids", ls.known_ids(LEDGER) == {"L-0001", "L-0002"}, failures)

    # --- draft_entries: sequence continues, dates from mergedAt, dedupe, skip captured ---
    records = [
        {"number": 201, "title": "feat: thing", "body": "Lesson: reject unsupported YAML loudly",
         "mergedAt": "2026-07-03T10:00:00Z"},
        {"number": 202, "title": "docs: nope", "body": "Lesson: none", "mergedAt": "2026-07-04T09:00:00Z"},
        {"number": 203, "title": "fix: dup", "body": "Lesson: reject unsupported YAML loudly",
         "mergedAt": "2026-07-05T09:00:00Z"},
        {"number": 204, "title": "chore: known", "body": "Lesson: an existing captured rule about "
         "indentation.", "mergedAt": "2026-07-05T11:00:00Z"},
    ]
    drafts = ls.draft_entries(records, LEDGER, "2026-07-06")
    check("only the one novel lesson is drafted (none/dup/already-captured dropped)",
          len(drafts) == 1, failures)
    d = drafts[0] if drafts else {}
    check("the draft continues the id sequence (L-0003)", d.get("id") == "L-0003", failures)
    check("the draft dates from mergedAt", d.get("date") == "2026-07-03", failures)
    check("the draft carries the lesson as its rule",
          d.get("rule") == "reject unsupported YAML loudly", failures)
    check("the draft cites the source PR", "#201" in (d.get("source") or ""), failures)
    check("the draft defaults scope to global", d.get("scope") == "global", failures)

    # two novel distinct lessons across two PRs get sequential ids
    two = ls.draft_entries(
        [{"number": 1, "title": "a", "body": "Lesson: first new rule", "mergedAt": "2026-07-01T0:0:0Z"},
         {"number": 2, "title": "b", "body": "Lesson: second new rule", "mergedAt": "2026-07-02T0:0:0Z"}],
        LEDGER, "2026-07-06")
    check("two novel lessons get sequential ids L-0003/L-0004",
          [x["id"] for x in two] == ["L-0003", "L-0004"], failures)

    # empty ledger -> ids start at L-0001; bad mergedAt -> today fallback
    fresh = ls.draft_entries([{"number": 9, "title": "t", "body": "Lesson: bootstrap rule",
                               "mergedAt": ""}], "", "2026-07-06")
    check("an empty ledger seeds L-0001", fresh and fresh[0]["id"] == "L-0001", failures)
    check("a missing mergedAt falls back to today", fresh[0]["date"] == "2026-07-06", failures)

    # --- emission: drafts parse back as ledger entries; empty is a clear no-op note ---
    text = ls.emit_drafts_yaml(drafts)
    check("emitted drafts carry the id/rule as ledger YAML",
          "- id: L-0003" in text and "rule: reject unsupported YAML loudly" in text, failures)
    check("emitted drafts are marked unapproved", "never writes the ledger" in text, failures)
    check("no drafts emits a clear no-op line",
          "no new lessons" in ls.emit_drafts_yaml([]), failures)

    # --- the emitter output satisfies the real ledger's required-field shape ---
    for key in ("id:", "date:", "scope:", "context:", "rule:", "source:"):
        check(f"a draft entry has the required field {key!r}", key in text, failures)

    # --- the sweep does not choke on the REAL ledger (id continuation is live) ---
    with open(REAL_LESSONS, encoding="utf-8") as fh:
        real = fh.read()
    check("known_ids finds the backfilled L-0003..L-0006 in the real ledger",
          {"L-0003", "L-0004", "L-0005", "L-0006"} <= ls.known_ids(real), failures)
    live = ls.draft_entries([{"number": 300, "title": "x", "body": "Lesson: a brand new maxim",
                              "mergedAt": "2026-07-05T00:00:00Z"}], real, "2026-07-06")
    # Derived, not pinned: the ledger legitimately grows (every append would break a literal —
    # the same enumeration-drift class the #168 discovery runner killed).
    next_id = "L-%04d" % (max(int(i.split("-")[1]) for i in ls.known_ids(real)) + 1)
    check("a new lesson continues after the real ledger's highest id",
          live and live[0]["id"] == next_id, failures)

    if failures:
        print("test-lesson-sweep: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-lesson-sweep: OK — the field parses, drafts continue the ledger sequence, "
          "duplicates are skipped, and nothing is auto-approved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
