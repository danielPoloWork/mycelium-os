#!/usr/bin/env python3
"""git_check — the deterministic evaluator for the `os/git/git.yaml` policy (#250).

`git.yaml` declares the branch / commit / one-PR policy as data, but until now NO tool evaluated
it: branch naming, Conventional-Commit shape, and one-PR-at-a-time were advisory prose — the
honor system this issue closes. This tool reads the policy AS DATA (never hardcoded) and checks:

  * **branch**  — the current branch matches `<type>/<short-kebab>` with a declared type
                  (the default branch itself is exempt: the human lives there; agents branch);
  * **commit**  — HEAD's subject is a Conventional Commit: `type(scope): subject`, declared
                  type, declared scope when present, subject <= 72 chars (merge commits and the
                  bootstrap root are exempt — they are not authored change subjects);
  * **one-PR**  — at most one open PR (git.yaml `commit.one_pr_at_a_time`), via `gh`; no `gh`
                  (or no network) degrades to SKIP — offline work must not fail on a courtesy
                  check it cannot perform.

PR *metadata* (assignee / one type label / milestone) stays `pr_metadata_check.py`'s job — this
tool checks what is knowable from git alone plus the one-PR count. Registered in workflow.yaml
as the cross-cutting `git-policy` gate (`wired: external`, like `traceability-lint`): the agent
runs it pre-PR, CI may gate on it; `--advisory` reports without failing the exit code (the
"advisory locally, gating in CI" split is the caller's flag, not two tools).

**Whose policy?** (#358) The policy is *discovered*, not hardcoded. In a **generated** repo it is
that repo's own `docs/workflow/git-policy.yaml`, rendered from its manifest; in **EADOS itself** it
is `os/git/git.yaml`; in a repo that has neither, the check narrows to what is identical in every
EADOS contract and **says so** rather than borrowing someone else's scope list. This tool used to
read the factory spec unconditionally, so after `scaffold` it judged a project's commits against
EADOS's own scopes — rejecting the project's valid ones and, more quietly, accepting scopes it had
never declared.

    python .eados-core/tools/git_check.py [--repo DIR] [--advisory] [--policy PATH]
        [--branch NAME] [--message SUBJECT]     # overrides for testing / CI contexts

Pure helpers (branch_problems / commit_problems) + a thin CLI shell, per the pr_review.py
pattern. Dependency-free (stdlib + the sibling YAML loader).
"""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # .eados-core/
sys.path.insert(0, HERE)
import render  # noqa: E402  — the dependency-free YAML loader

# Subprocess budgets (#321). `subprocess.run` without one waits FOREVER: a `gh` call that
# stalls on a TLS handshake, a rate-limit backoff, or an auth prompt with no stdin does not
# fail — it blocks until the CI job times out, and then reports as a generic job timeout
# rather than as "the network call hung". A timeout turns an unattributable stall into a
# clean, named degradation on the path this tool already has for `gh` being unavailable.
GH_TIMEOUT = 30    # network-bound
GIT_TIMEOUT = 15   # local, but git can block on a credential helper or a remote

GIT_POLICY = os.path.join(ROOT, "orchestrator", "os", "git", "git.yaml")
# Where a GENERATED repo keeps its own policy (rendered from its manifest — #358). Relative to the
# repo root, next to the prose it makes machine-readable.
PROJECT_POLICY = os.path.join("docs", "workflow", "git-policy.yaml")
# The factory's own marker. `.eados-dev` is how `eados_lint` already tells "I am EADOS" from
# "I am a bundle inside someone else's repo"; reusing it keeps one answer to that question.
DEV_MARKER = ".eados-dev"

_KEBAB = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*\Z")
_SUBJECT = re.compile(r"(?P<type>[a-z]+)(\((?P<scope>[^)]*)\))?(?P<bang>!)?: (?P<desc>.+)\Z")
# Fallback only — the cap is policy data (`commit.subject_max`, #363). Kept in step with the shipped
# git.yaml so a policy-less repo is judged by the same number, not a stricter historical one.
_SUBJECT_MAX = 80
# Squash-merge appends this. The author did not write it and cannot prevent it, so it is not theirs
# to be measured on — counting it made a PR title written exactly to the cap fail the moment it
# merged, which is a check reporting a violation that never had an author (#363).
_SQUASH_REF = re.compile(r"\s\(#\d+\)\Z")


def authored_subject(subject):
    """The part of a merged subject its author actually wrote — the trailing ` (#N)` GitHub adds on
    squash removed. One reference only: `fix(x): y (#350) (#362)` keeps the `(#350)` the author
    typed and drops the `(#362)` the merge did."""
    return _SQUASH_REF.sub("", str(subject or "").strip())


def load_policy(path=GIT_POLICY):
    with open(path, encoding="utf-8") as handle:
        return render.load_yaml(handle.read()) or {}


def resolve_policy(repo=".", explicit=None):
    """`(path, origin)` for the policy that governs `repo` — or `(None, reason)`.

    The bug this replaces (#358) was not a wrong path but an unaskable question: `GIT_POLICY` was
    hardcoded and `main()` exposed no way to change it, so after `scaffold` handed governance to a
    generated repo's own `AGENTS.md`, this tool still judged that repo's commits against **EADOS's**
    scope list. On a real consumer the two lists overlapped in 2 of 13 entries — it rejected 11 valid
    project scopes and would have waved through `fix(profiles):` in a Java library that has neither.

    The ladder, and the reason each rung exists:

      1. `--policy PATH` — an explicit answer always wins.
      2. `<repo>/docs/workflow/git-policy.yaml` — the generated repo's own, rendered from its
         manifest. First, because in a consumer repo the vendored `.eados-core/` is present and its
         factory spec is exactly the wrong answer.
      3. the factory's `os/git/git.yaml`, **only** when `<repo>` is EADOS itself (`.eados-dev`).
         Gated rather than used as a fallback: an ungated fallback is the original defect.
      4. nothing. Repos generated before this shipped have no rendered policy and are never
         re-rendered (ADR-0003), so this is a permanent, expected state — not an error."""
    if explicit:
        return explicit, "--policy"
    project = os.path.join(repo, PROJECT_POLICY)
    if os.path.exists(project):
        return project, f"this repository's own {PROJECT_POLICY.replace(os.sep, '/')}"
    if os.path.exists(os.path.join(repo, DEV_MARKER)) and os.path.exists(GIT_POLICY):
        return GIT_POLICY, "the EADOS factory's os/git/git.yaml (this IS the factory)"
    return None, (f"no {PROJECT_POLICY.replace(os.sep, '/')} in {repo} — and this is not the EADOS "
                  "factory, so its policy does not apply here")


def universal_policy(spec_path=GIT_POLICY):
    """What can still be checked in a repo that declares no policy of its own.

    Not "the factory's policy minus a bit" — the two fields kept are the ones that are **the same
    in every EADOS contract by construction**: the Conventional Commit convention and its type
    vocabulary. `commit.scopes` is deliberately dropped, because scopes are exactly what differs per
    project, and applying the factory's is the defect (#358).

    Checking less, honestly, beats checking more, wrongly: the loud half of that defect rejected
    valid commits, but the quiet half **accepted** `fix(profiles):` in a repo with no profiles —
    and nobody ever notices a check that passes."""
    try:
        spec = load_policy(spec_path)
    except (OSError, ValueError):
        return {}
    return {"branch_naming": {"pattern": (spec.get("branch_naming") or {}).get("pattern"),
                              "types": (spec.get("branch_naming") or {}).get("types") or []},
            "commit": {"convention": (spec.get("commit") or {}).get("convention")}}


def branch_problems(branch, policy):
    """Violations of `branch_naming` for `branch`. The default branch is exempt (agents never
    push to it — a different rule, enforced by the human merge gate, not by naming)."""
    naming = policy.get("branch_naming") or {}
    types = [str(t) for t in (naming.get("types") or [])]
    default = str(((policy.get("pr") or {}).get("default_branch") or "main"))
    branch = str(branch or "").strip()
    if not branch or branch == "HEAD":
        return [f"cannot determine the current branch (got {branch!r}) — detached HEAD?"]
    if branch in (default, "main", "master"):
        return []
    if "/" not in branch:
        return [f"branch '{branch}' does not match '{naming.get('pattern') or '<type>/<kebab>'}' "
                f"— no '<type>/' prefix (declared types: {', '.join(types)})"]
    btype, _, rest = branch.partition("/")
    problems = []
    if types and btype not in types:
        problems.append(f"branch '{branch}': type '{btype}' is not a declared branch type "
                        f"({', '.join(types)})")
    if not _KEBAB.match(rest):
        problems.append(f"branch '{branch}': '{rest}' is not short-kebab "
                        "(lowercase a-z0-9 segments joined by '-')")
    return problems


def commit_problems(subject, policy):
    """Violations of `commit.convention` for one commit `subject`. Merge commits and the
    bootstrap root are exempt — they are not authored Conventional-Commit subjects."""
    commit = policy.get("commit") or {}
    if str(commit.get("convention") or "") != "conventional-commits":
        return []                                   # a policy without the convention checks nothing
    types = [str(t) for t in ((policy.get("branch_naming") or {}).get("types") or [])]
    scopes = [str(s) for s in (commit.get("scopes") or [])]
    subject = str(subject or "").strip()
    if not subject:
        return ["HEAD has no commit subject to check"]
    if subject.startswith(("Merge ", "Revert \"", "Initial commit")):
        return []
    m = _SUBJECT.match(subject)
    if not m:
        return [f"commit subject {subject!r} is not Conventional-Commit shaped "
                "(`type(scope): imperative subject`)"]
    problems = []
    if types and m.group("type") not in types:
        problems.append(f"commit type '{m.group('type')}' is not a declared type "
                        f"({', '.join(types)})")
    scope = m.group("scope")
    if scope is not None and scopes and scope not in scopes:
        problems.append(f"commit scope '{scope}' is not a declared scope "
                        f"({', '.join(scopes)})")
    cap = commit.get("subject_max")
    cap = int(cap) if isinstance(cap, int) or str(cap or "").isdigit() else _SUBJECT_MAX
    authored = authored_subject(subject)
    if len(authored) > cap:
        extra = ("" if authored == subject else
                 f" (measured without the ` {subject[len(authored):].strip()}` the squash-merge "
                 f"appended; the full line is {len(subject)})")
        problems.append(f"commit subject is {len(authored)} chars — the policy caps it at "
                        f"{cap} (commit.subject_max){extra}")
    return problems


def _git(repo, *args):
    """One git plumbing call; None when git is unavailable or the call fails."""
    try:
        proc = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def count_open_prs(payload, counts="authored"):
    """Pure. How many of `gh pr list --json number,author`'s entries the one-PR limit counts.

    `counts="authored"` drops **bot-authored** PRs, matched on `author.is_bot` — the property, not a
    login denylist. A denylist is a list to keep current, and the next bot would be counted until
    somebody remembered to add it; `is_bot` is true for Dependabot, Renovate, and whatever comes
    after, on the day it arrives."""
    if not isinstance(payload, list):
        return None
    if str(counts) == "all":
        return len(payload)
    return sum(1 for pr in payload
               if isinstance(pr, dict) and not ((pr.get("author") or {}).get("is_bot")))


def open_pr_count(repo, counts="authored"):
    """The number of open PRs the policy counts, via gh; None == gh unavailable/unauthenticated
    (SKIP, not FAIL — offline work must not fail a courtesy count it cannot perform)."""
    import json
    try:
        proc = subprocess.run(["gh", "pr", "list", "--state", "open", "--json", "number,author"],
                              cwd=repo, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=GH_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        return count_open_prs(json.loads(proc.stdout or "null"), counts)
    except ValueError:
        return None


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    import argparse
    ap = argparse.ArgumentParser(description="EADOS git-policy check — the git.yaml evaluator "
                                             "(branch naming, commit convention, one-PR).")
    ap.add_argument("--repo", default=".", help="repository root (default: .)")
    ap.add_argument("--branch", help="branch name to check (default: the current branch)")
    ap.add_argument("--message", help="commit subject to check (default: HEAD's subject)")
    ap.add_argument("--advisory", action="store_true",
                    help="report violations but exit 0 (the local pre-flight mode; CI omits it)")
    ap.add_argument("--policy", help="the git policy to evaluate against (default: this "
                                     "repository's docs/workflow/git-policy.yaml)")
    args = ap.parse_args(argv)

    policy_path, origin = resolve_policy(args.repo, args.policy)
    degraded = None
    if policy_path is None:
        # NOT an error, and never a silent substitution of someone else's contract: a repo
        # generated before #358 has no rendered policy and is never re-rendered (ADR-0003).
        policy, degraded = universal_policy(), origin
    else:
        try:
            policy = load_policy(policy_path)
        except (OSError, ValueError) as exc:
            print(f"git-check: ERROR — cannot read the git policy at {policy_path}: {exc}",
                  file=sys.stderr)
            return 2

    branch = args.branch if args.branch is not None else _git(args.repo, "rev-parse",
                                                              "--abbrev-ref", "HEAD")
    subject = args.message if args.message is not None else _git(args.repo, "log", "-1",
                                                                 "--format=%s")
    problems, skips = [], []
    if branch is None:
        skips.append("branch: git unavailable — SKIP")
    else:
        problems += branch_problems(branch, policy)
    if subject is None:
        skips.append("commit: git unavailable — SKIP")
    else:
        problems += commit_problems(subject, policy)
    commit_policy = policy.get("commit") or {}
    if commit_policy.get("one_pr_at_a_time"):
        # Default `authored`, not `all` (#350): counting bots was never the rule's intent — it is
        # about an agent not stacking work in flight — and the accident put a generated repo in
        # violation of its own policy minutes after bootstrap, with nobody having done anything.
        counts = str(commit_policy.get("one_pr_counts") or "authored")
        count = open_pr_count(args.repo, counts)
        if count is None:
            skips.append("one-PR: gh unavailable — SKIP")
        elif count > 1:
            problems.append(f"{count} PRs are open — commit.one_pr_at_a_time allows one"
                            + (" (bot-authored PRs are not counted)" if counts == "authored"
                               else " (counting every open PR, including bots — "
                                    "commit.one_pr_counts: all)"))

    print(f"git-policy check ({args.repo}) — branch: {branch or '?'}")
    print(f"  policy: {origin if policy_path else 'NONE'}")
    if degraded:
        # Stated, never inferred from silence: what is checked here is a strict subset, and a
        # reader must be able to tell "your commits are fine" from "I could not judge them" (L-0006).
        print(f"  [PARTIAL] {degraded}.")
        print("            Checking only what is identical in every EADOS contract: branch shape "
              "and the Conventional Commit type vocabulary.")
        print("            NOT checked: commit SCOPES (they are this project's, declared in "
              "AGENTS.md §6) and one-PR-at-a-time.")
        print(f"            To enable them, add {PROJECT_POLICY.replace(os.sep, '/')} — see the "
              "EADOS template of the same name — or pass --policy PATH.")
    for s in skips:
        print(f"  [SKIP] {s}")
    if problems:
        print("  FAIL")
        for p in problems:
            print(f"  - {p}")
        if args.advisory:
            print("  (advisory mode — reporting only, exit 0)")
            return 0
        return 1
    print("  OK — branch, commit subject, and PR count meet "
          + ("the checkable subset above." if degraded else "this repository's policy."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
