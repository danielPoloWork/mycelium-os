#!/usr/bin/env python3
"""Tests for pr_review (M8 8.3) — the inbound-PR evaluator core, on in-memory PR fixtures against
the real shipped specs (contribution / authority / risk). Exercises trust classification, the
owned-path escalation, the risk lens, and the disposition policy: a non-owner's commits are NEVER
merged — a wanted change is adopted via re-implement-in-house (its co-author/rationale/thank ritual),
declined via close-with-thanks, or escalated via needs-maintainer; no auto-accept; always thank. The
`gh` shell is not touched. Dependency-free.

    python .eados-core/tools/tests/test_pr_review.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import pr_review as pr           # noqa: E402  (the module under test)
import authority_check as ac     # noqa: E402
import risk_score as rs          # noqa: E402


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    policy, auth, risk = pr.load_policy(), ac.load_authority(), rs.load_risk()

    def ev(**kw):
        base = {"number": 1, "author": "ext", "author_association": "NONE", "is_fork": True,
                "files": ["README.md"], "additions": 5, "deletions": 1, "checks_passing": True}
        base.update(kw)
        return pr.evaluate(base, policy, auth, risk)

    # --- trust classification (the change is judged, not the person — but unknown gets most scrutiny) ---
    check("OWNER -> owner", pr.classify_tier("OWNER", False) == "owner", failures)
    check("COLLABORATOR -> collaborator", pr.classify_tier("COLLABORATOR", False) == "collaborator", failures)
    check("FIRST_TIME_CONTRIBUTOR -> external-fork",
          pr.classify_tier("FIRST_TIME_CONTRIBUTOR", True) == "external-fork", failures)
    check("unknown association -> external-fork (strict default)",
          pr.classify_tier(None, True) == "external-fork", failures)

    # --- the load-bearing rule: external fork touching an owned path escalates, never auto-disposed ---
    esc = ev(files=["src/main/x.cpp"])
    check("external fork touching an owned path escalates", esc["escalated"], failures)
    check("escalation -> needs-maintainer", esc["disposition"]["id"] == "needs-maintainer", failures)
    check("the owned path is reported", esc["owned_paths_touched"] == ["src/main/x.cpp"], failures)
    check("an owner touching the same owned path does NOT escalate",
          not ev(author_association="OWNER", is_fork=False, files=["src/main/x.cpp"])["escalated"], failures)

    # --- the risk lens: a high-risk change routes to the human decider ---
    hi = ev(author_association="COLLABORATOR", is_fork=False,
            files=[".github/workflows/ci.yml"], additions=600)
    check("a high-risk change requires the security gate", hi["risk"]["security_gate"], failures)
    check("a security-gated change -> needs-maintainer", hi["disposition"]["id"] == "needs-maintainer", failures)

    # --- a non-owner's commits are NEVER merged: adopt via re-implement-in-house, decline via close ---
    clean = ev()
    check("a clean non-owner PR -> re-implement-in-house (never merge their commits)",
          clean["disposition"]["id"] == "re-implement-in-house", failures)
    check("the adopt disposition carries its courtesy ritual (co-author-credit)",
          "co-author-credit" in (clean["disposition"].get("requires") or []), failures)
    check("close-with-thanks is offered as the decline alternative",
          (clean["alternative"] or {}).get("id") == "close-with-thanks", failures)
    check("no disposition takes the commits as-is (no conditional_on)",
          not clean["disposition"].get("conditional_on"), failures)
    check("every non-owner disposition thanks the contributor",
          any("thank" in n for n in clean["notes"]), failures)
    check("no auto-accept is stated", any("auto-accept" in n for n in clean["notes"]), failures)
    check("never-merge-their-commits is stated",
          any("never merge" in n for n in clean["notes"]), failures)

    # --- a failing CI does not change the model — we re-implement regardless (it is a note) ---
    red = ev(checks_passing=False)
    check("a failing-CI non-owner PR still -> re-implement-in-house",
          red["disposition"]["id"] == "re-implement-in-house", failures)

    # --- an owner's own PR is not an inbound contribution — nothing to triage ---
    own = ev(author_association="OWNER", is_fork=False)
    check("an owner's PR has no inbound disposition", own["disposition"]["id"] is None, failures)
    check("an owner's PR carries no thank-the-contributor note",
          not any("thank" in n for n in own["notes"]), failures)

    # --- the report renders (for a non-owner adopt and for an owner no-op) ---
    report = pr.format_report(clean)
    check("format_report renders a non-empty review string",
          isinstance(report, str) and "recommended disposition" in report, failures)
    check("format_report renders an owner no-op without crashing",
          isinstance(pr.format_report(own), str), failures)

    if failures:
        print("test-pr-review: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-pr-review: OK — classification, escalation, risk, and the never-merge disposition hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
