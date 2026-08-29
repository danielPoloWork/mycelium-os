#!/usr/bin/env python3
"""EADOS inbound-PR evaluator (roadmap M8 8.3) — the `contribution-reviewer` role's procedure as a
tool. Given a PR's data it classifies the author's trust tier, runs the contribution-policy checks,
composes the authority (owned-path) and risk (security/size/blast) lenses, and recommends a
disposition. It reports and recommends; it never merges or closes (AGENTS.md §6).

Everything is data-driven: the policy is `orchestrator/os/contribution/contribution.yaml`, owned
paths come from `authority.yaml`, risk from `risk.yaml`. The evaluator core (`evaluate`) is pure and
fixture-tested; only the optional `--pr N` fetch shells out to `gh`, degrading cleanly (clear
message, exit 2) when `gh` is missing, unauthenticated, or offline — like `derive_links.py`.

    python .eados-core/tools/pr_review.py --pr 94 [--repo OWNER/REPO] [--domain D] [--json]
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # .eados-core/
sys.path.insert(0, HERE)
import render            # noqa: E402  — the dependency-free YAML loader
import authority_check as ac  # noqa: E402  — owned-path lens (compose, don't re-implement)
import risk_score as rs       # noqa: E402  — security/size/blast lens

# Subprocess budgets (#321). `subprocess.run` without one waits FOREVER: a `gh` call that
# stalls on a TLS handshake, a rate-limit backoff, or an auth prompt with no stdin does not
# fail — it blocks until the CI job times out, and then reports as a generic job timeout
# rather than as "the network call hung". A timeout turns an unattributable stall into a
# clean, named degradation on the path this tool already has for `gh` being unavailable.
GH_TIMEOUT = 30    # network-bound

CONTRIB_SPEC = os.path.join(ROOT, "orchestrator", "os", "contribution", "contribution.yaml")


def load_policy(path=CONTRIB_SPEC):
    with open(path, encoding="utf-8") as handle:
        return render.load_yaml(handle.read())


# --- classification -------------------------------------------------------
def classify_tier(author_association, is_fork):
    """Map a GitHub `authorAssociation` (+ fork flag) to a policy trust tier. Unknown / first-time /
    fork authorship is `external-fork` (the strict default — scrutiny attaches to the diff, not the
    person, but an unknown author gets the most)."""
    assoc = (author_association or "").upper()
    if assoc == "OWNER":
        return "owner"
    if assoc in ("MEMBER", "COLLABORATOR"):
        return "collaborator"
    return "external-fork"   # CONTRIBUTOR | FIRST_TIME_CONTRIBUTOR | FIRST_TIMER | NONE | unknown


def owned_globs(authority):
    """Every governed path glob: each role's `owns` plus the `ownership_map` (generalized CODEOWNERS)."""
    globs = []
    for role in authority.get("roles") or []:
        if isinstance(role, dict):
            globs += list(role.get("owns") or [])
    for om in authority.get("ownership_map") or []:
        if isinstance(om, dict) and om.get("glob"):
            globs.append(om["glob"])
    return globs


# --- the checks (data-driven over policy.required_checks) -----------------
def _check(check_id, pr):
    """(status, note) for one required-check id. status ∈ pass | fail | review. The auto-derivable
    checks are computed; the human-judgment ones return `review` honestly rather than a false pass."""
    cp = pr.get("checks_passing")
    if check_id == "ci-green":
        return ("pass", "CI checks are green") if cp is True else \
               ("fail", "CI is failing") if cp is False else \
               ("review", "CI status unknown — verify the run")
    if check_id == "gate-coverage-holds":
        # self-lint (which includes gate-coverage) runs in CI, so a green run subsumes this.
        return ("pass", "self-lint incl. gate-coverage is green") if cp is True else \
               ("review", "verify via self-lint (gate-coverage runs in CI)")
    if check_id == "provenance-clear":
        return ("pass", f"author '{pr.get('author')}' known (fork={pr.get('is_fork')})") \
            if pr.get("author") else ("review", "author unknown — verify provenance")
    if check_id == "no-added-secrets":
        return ("review", "security-auditor lens — confirm no added secrets/tokens or secret exposure")
    if check_id == "scope-matches-intent":
        return ("review", "confirm the diff matches the linked issue / stated intent")
    return ("review", f"no automatic evaluator — review '{check_id}' by hand")


def _disp(policy, disposition_id):
    d = next((x for x in (policy.get("dispositions") or [])
              if isinstance(x, dict) and x.get("id") == disposition_id), {})
    out = {"id": disposition_id, "label": d.get("label")}
    if d.get("requires"):
        out["requires"] = list(d["requires"])   # the courtesy ritual (co-author, rationale, thank…)
    return out


def evaluate(pr, policy, authority, risk_cfg, domain=None):
    """Pure evaluator. `pr` is a dict: {number, author, author_association, is_fork, files[],
    additions, deletions, checks_passing(bool|None)}. Returns a structured review report dict."""
    files = [str(p).replace("\\", "/") for p in (pr.get("files") or [])]
    tier = classify_tier(pr.get("author_association"), pr.get("is_fork"))

    owned = owned_globs(authority)
    touched_owned = [p for p in files if ac.in_authority(p, owned)]

    lines = int(pr.get("additions") or 0) + int(pr.get("deletions") or 0)
    level, factors = rs.score(files, lines, risk_cfg, domain)
    security_gate = rs.requires_security_gate(level, risk_cfg, domain)

    checks = [{"id": cid, "status": s, "note": n}
              for cid in (policy.get("required_checks") or [])
              for (s, n) in [_check(cid, pr)]]

    # The load-bearing rule: an external fork touching an owned path is never auto-disposed.
    escalated = tier == "external-fork" and bool(touched_owned)
    courtesy = policy.get("courtesy") or {}
    non_owner = tier != "owner"
    failing = [c["id"] for c in checks if c["status"] == "fail"]

    alternative = None
    if not non_owner:
        # The owner's own change is not an inbound contribution — nothing for this role to triage.
        disposition = {"id": None, "label": None}
        reason = "owner-authored change — not an inbound contribution"
    elif escalated or security_gate:
        disposition = _disp(policy, (policy.get("escalation") or {}).get("disposition", "needs-maintainer"))
        reason = ("external fork touches an owned path" if escalated
                  else f"risk {level} requires the security-auditor gate")
    else:
        # A non-owner's commits are NEVER merged (courtesy.merge_nonowner_commits): a wanted change is
        # ADOPTED via an in-house re-implementation (co-author), or declined. The tool recommends the
        # adopt path and offers decline as the alternative; the human picks. No auto-accept.
        disposition = _disp(policy, courtesy.get("adopt_via", "re-implement-in-house"))
        alternative = _disp(policy, "close-with-thanks")
        reason = ("adopt the idea via an in-house re-implementation — we never merge a non-owner's "
                  "commits; decline via close-with-thanks if not pursuing"
                  + (f" (note: {', '.join(failing)} failing)" if failing else ""))

    notes = []
    if non_owner and courtesy.get("always_thank"):
        notes.append("thank the contributor — every non-owner disposition does (courtesy.always_thank)")
    if non_owner and courtesy.get("acceptance_requires_reasoning"):
        notes.append("no auto-accept — this is a recommendation with its reasoning; the human disposes")
    if non_owner and courtesy.get("merge_nonowner_commits") is False:
        notes.append("never merge the contributor's commits — adopt via re-implement-in-house (co-author)")

    return {
        "pr": pr.get("number"), "author": pr.get("author"), "tier": tier,
        "is_fork": bool(pr.get("is_fork")),
        "risk": {"level": level, "factors": factors, "security_gate": security_gate},
        "owned_paths_touched": touched_owned,
        "checks": checks,
        "escalated": escalated,
        "disposition": disposition,
        "alternative": alternative,
        "reason": reason,
        "notes": notes,
        "boundary": "recommends only — the human disposes / merges / closes (AGENTS.md §6)",
    }


def format_report(report):
    """Render an `evaluate` report as a human-readable review (the draft the human acts on)."""
    out = [f"inbound-PR review: #{report.get('pr')} by {report.get('author')} "
           f"[tier: {report['tier']}, fork={report['is_fork']}]"]
    r = report["risk"]
    out.append(f"  risk: {r['level']}  (factors: {', '.join(r['factors']) or 'none'})  "
               f"security-auditor gate: {'REQUIRED' if r['security_gate'] else 'optional'}")
    if report["owned_paths_touched"]:
        out.append(f"  owned paths touched: {', '.join(report['owned_paths_touched'])}")
    out.append("  checks:")
    mark = {"pass": "[OK]  ", "fail": "[FAIL]", "review": "[????]"}
    for c in report["checks"]:
        out.append(f"    {mark.get(c['status'], '[????]')} {c['id']} — {c['note']}")
    d = report["disposition"]
    if d.get("id"):
        out.append(f"  -> recommended disposition: {d['id']}"
                   f"{' (' + d['label'] + ')' if d.get('label') else ''} — {report['reason']}")
        if d.get("requires"):
            out.append(f"     requires: {', '.join(d['requires'])}")
    else:
        out.append(f"  -> {report['reason']}")
    alt = report.get("alternative")
    if alt and alt.get("id"):
        req = f" — requires: {', '.join(alt['requires'])}" if alt.get("requires") else ""
        out.append(f"  -> alternative: {alt['id']}{req}")
    for note in report.get("notes") or []:
        out.append(f"  note: {note}")
    out.append(f"  {report['boundary']}")
    return "\n".join(out)


# --- the thin `gh` shell (best-effort; degrades cleanly) ------------------
def _gh_json(args):
    import json
    try:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True,
                              encoding="utf-8", timeout=GH_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"`gh {' '.join(args)}` timed out after {GH_TIMEOUT}s — the network "
                           "stalled, the API is rate-limiting, or it is waiting on an auth prompt "
                           "that will never be answered")
    except (FileNotFoundError, OSError) as exc:
        raise RuntimeError(f"could not run `gh` (is the GitHub CLI installed and on PATH?): {exc}")
    if proc.returncode != 0:
        raise RuntimeError(f"`gh {' '.join(args)}` failed (authenticated? online?): "
                           f"{(proc.stderr or proc.stdout or '').strip()}")
    try:
        return json.loads(proc.stdout or "null")
    except ValueError as exc:
        raise RuntimeError(f"could not parse `gh` JSON output: {exc}")


def _checks_passing(rollup):
    """Reduce a `statusCheckRollup` to True (all green) / False (a failure) / None (pending/unknown)."""
    if not rollup:
        return None
    states = [(c.get("conclusion") or c.get("state") or "").upper() for c in rollup
              if isinstance(c, dict)]
    if any(s in ("FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "ERROR") for s in states):
        return False
    if any(s in ("", "PENDING", "QUEUED", "IN_PROGRESS", "EXPECTED", "REQUESTED") for s in states):
        return None
    return True


def fetch_pr(number, repo=None):
    """Assemble the evaluator's `pr` dict from `gh`. Raises RuntimeError (not a crash) when gh is
    missing/unauthenticated/offline. `authorAssociation` is not a `gh pr view` field in all CLI
    versions, so it is read from the REST API; the fork flag uses `isCrossRepository`."""
    view_fields = "number,author,additions,deletions,files,statusCheckRollup,isCrossRepository"
    view = ["pr", "view", str(number), "--json", view_fields]
    if repo:
        view += ["--repo", repo]
    data = _gh_json(view) or {}
    api_path = f"repos/{repo}/pulls/{number}" if repo else f"repos/:owner/:repo/pulls/{number}"
    assoc = _gh_json(["api", api_path, "--jq", "{a: .author_association}"]) or {}
    return {
        "number": data.get("number"),
        "author": (data.get("author") or {}).get("login"),
        "author_association": assoc.get("a"),
        "is_fork": bool(data.get("isCrossRepository")),
        "files": [f.get("path") for f in (data.get("files") or []) if isinstance(f, dict)],
        "additions": data.get("additions") or 0,
        "deletions": data.get("deletions") or 0,
        "checks_passing": _checks_passing(data.get("statusCheckRollup")),
    }


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    import argparse
    import json
    ap = argparse.ArgumentParser(description="Evaluate an inbound PR against the contribution policy.")
    ap.add_argument("--pr", type=int, required=True, help="the PR number to evaluate")
    ap.add_argument("--repo", help="OWNER/REPO (default: the repo gh infers)")
    ap.add_argument("--domain", default=None, help="the project domain (per-domain risk thresholds)")
    ap.add_argument("--json", action="store_true", help="emit the structured report as JSON")
    args = ap.parse_args(argv)
    try:
        pr = fetch_pr(args.pr, repo=args.repo)
    except RuntimeError as exc:
        print(f"pr-review: SKIP — {exc}", file=sys.stderr)
        return 2
    report = evaluate(pr, load_policy(), ac.load_authority(), rs.load_risk(), args.domain)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
