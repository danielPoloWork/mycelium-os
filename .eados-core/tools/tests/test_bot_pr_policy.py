#!/usr/bin/env python3
"""A generated repo must not violate its own git policy the moment a bot wakes up (#350).

The factory shipped a `dependabot.yml` that opens PRs and a policy allowing **one open PR at a
time**. Minutes after the bootstrap PR merged on a real scaffold, Dependabot had opened three and
the repo was permanently in violation — with nobody having done anything. The same collision hit
`pr.metadata`: a bot cannot assign, cannot set a milestone, and the label it requests is dropped
until the repo's labels are imported, so every required field reported MISSING on every bot PR.

Both halves matter, and the second is the reason to care: **a check that is routinely ignored has
stopped being a check.** Two policies that cannot be satisfied teach a maintainer to skip the
output — the same failure #313 was closed for, in a different surface.

Fixes A + B + C from the issue, asserted here: the count is scoped by author **type** (never a login
denylist), the bot's queue is bounded in the template, and the metadata contract reports `n/a`
rather than a failure nobody can fix. Driven against a **real render**, per #359.

    python .eados-core/tools/tests/test_bot_pr_policy.py
"""

import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
REPO_ROOT = os.path.dirname(ROOT)
REFERENCE = os.path.join(ROOT, "orchestrator", "examples", "reference.yaml")
sys.path.insert(0, TOOLS)
import git_check           # noqa: E402
import pr_metadata_check   # noqa: E402
import render              # noqa: E402

# The scaffold's actual state minutes after bootstrap: three bot PRs, no authored PR at all.
THE_INCIDENT = [{"number": 12, "author": {"login": "app/dependabot", "is_bot": True}},
                {"number": 11, "author": {"login": "app/dependabot", "is_bot": True}},
                {"number": 10, "author": {"login": "app/dependabot", "is_bot": True}}]


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []

    # --- A. the one-PR count is scoped by author TYPE ---------------------------------------
    check(f"THE INCIDENT: three bot PRs and no authored one count as 0 "
          f"({git_check.count_open_prs(THE_INCIDENT)})",
          git_check.count_open_prs(THE_INCIDENT) == 0, failures)
    check("...and `all` still counts them, for a repo that wants the literal reading",
          git_check.count_open_prs(THE_INCIDENT, "all") == 3, failures)

    mixed = THE_INCIDENT + [{"number": 13, "author": {"login": "danielPoloWork", "is_bot": False}}]
    check("an authored PR among bots still counts as one",
          git_check.count_open_prs(mixed) == 1, failures)
    check("two authored PRs are still a violation — the rule itself is not weakened",
          git_check.count_open_prs(
              mixed + [{"number": 14, "author": {"login": "x", "is_bot": False}}]) == 2, failures)

    # A future bot is covered on the day it arrives: this matches the PROPERTY, not a name list.
    check("an unknown bot is excluded without anyone updating a denylist",
          git_check.count_open_prs(
              [{"number": 1, "author": {"login": "app/some-future-bot", "is_bot": True}}]) == 0,
          failures)
    check("a missing author field is counted, not silently dropped — an unknown author is not "
          "evidence of a bot", git_check.count_open_prs([{"number": 1}]) == 1, failures)
    check("garbage yields None (SKIP), never a confident 0",
          git_check.count_open_prs(None) is None, failures)

    # --- C. the metadata contract does not fail a PR nobody can fix --------------------------
    bot_pr = {"number": 11, "assignees": [], "labels": [], "milestone": None, "is_bot": True}
    report = pr_metadata_check.evaluate_metadata(bot_pr)
    check("a bot PR is complete-by-n/a, not INCOMPLETE", report["complete"]
          and report.get("bot") and report["missing_required"] == [], failures)
    text = pr_metadata_check.format_report(report)
    check(f"...and the readout says WHY rather than just going quiet\n{text}",
          "bot-authored" in text and "n/a" in text, failures)
    literal = pr_metadata_check.evaluate_metadata(bot_pr, applies_to="all")
    check("`all` restores the literal reading",
          not literal["complete"] and len(literal["missing_required"]) == 3, failures)
    human = pr_metadata_check.evaluate_metadata(
        {"number": 12, "assignees": [], "labels": [], "milestone": None})
    check("an AUTHORED PR with no metadata still fails — the fix must not blanket-excuse",
          not human["complete"] and len(human["missing_required"]) == 3, failures)

    # --- B. the bot's queue is bounded, in the template AND in the factory itself -------------
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "rendered")
        rc = subprocess.run([sys.executable, os.path.join(TOOLS, "render.py"), REFERENCE,
                             "--out", out], capture_output=True, text=True, timeout=180)
        check(f"the reference manifest renders ({rc.stderr[-200:] if rc.returncode else ''})",
              rc.returncode == 0, failures)
        if rc.returncode != 0:
            print("test-bot-pr-policy: FAIL\n  render failed")
            return 1

        for label, path in (("a generated repo", os.path.join(out, ".github", "dependabot.yml")),
                            ("the factory itself (dogfood — a rule EADOS breaks in its own repo "
                             "is not a rule)",
                             os.path.join(REPO_ROOT, ".github", "dependabot.yml"))):
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            spec = render.load_yaml(text) or {}
            updates = spec.get("updates") or []
            check(f"{label}: dependabot declares ecosystems ({len(updates)})", updates, failures)
            for eco in updates:
                name = (eco or {}).get("package-ecosystem")
                check(f"{label}: '{name}' caps its open PRs (default is 5 per ecosystem)",
                      eco.get("open-pull-requests-limit") == 1, failures)
                check(f"{label}: '{name}' groups its bumps into one PR",
                      isinstance(eco.get("groups"), dict) and eco["groups"], failures)
            # The loader every gate runs on must agree with PyYAML about the new nested block —
            # `groups:` is a mapping of mappings, a shape #316's key rule only just made safe.
            try:
                import yaml
                check(f"{label}: both parsers agree on the grouped config",
                      yaml.safe_load(text) == spec, failures)
            except ImportError:
                pass

        # --- the rendered policy carries both scopings, so a consumer inherits the fix --------
        policy = git_check.load_policy(os.path.join(out, git_check.PROJECT_POLICY))
        check("a generated repo's policy scopes the one-PR count",
              (policy.get("commit") or {}).get("one_pr_counts") == "authored", failures)
        check("...and the metadata contract",
              (policy.get("pr") or {}).get("metadata_applies_to") == "authored", failures)

        # End to end through the real CLI: the incident's readout, with a stubbed gh.
        gh = os.path.join(tmp, "bin")
        os.makedirs(gh)
        stub = os.path.join(gh, "gh.py")
        with open(stub, "w", encoding="utf-8") as fh:
            fh.write("import json,sys\nprint(json.dumps(%r))\n" % (THE_INCIDENT,))
        real = git_check.open_pr_count

        def stubbed(repo, counts="authored"):
            proc = subprocess.run([sys.executable, stub], capture_output=True, text=True,
                                  timeout=60)
            import json
            return git_check.count_open_prs(json.loads(proc.stdout), counts)
        git_check.open_pr_count = stubbed
        try:
            check("the incident's three bot PRs raise no violation end to end",
                  stubbed(out) == 0, failures)
        finally:
            git_check.open_pr_count = real

    # --- the factory's own spec agrees with what the tools default to ------------------------
    factory = git_check.load_policy()
    check("os/git/git.yaml declares the count scoping",
          (factory.get("commit") or {}).get("one_pr_counts") == "authored", failures)
    check("os/git/git.yaml declares the metadata scoping",
          (factory.get("pr") or {}).get("metadata_applies_to") == "authored", failures)

    if failures:
        print("test-bot-pr-policy: FAIL\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("test-bot-pr-policy: OK — the incident's three bot PRs raise no violation, an authored "
          "PR still counts and an authored PR with no metadata still fails, the bot's queue is "
          "bounded in both the template and the factory, and the scoping is data a generated repo "
          "inherits.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
