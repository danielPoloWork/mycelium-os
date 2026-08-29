#!/usr/bin/env python3
"""EADOS pre-flight self-check (#223, M14) — the cheap, agent-facing checklist to answer on your OWN
draft BEFORE opening a PR (and before the gate).

Three neighbours, three jobs — this is the one that had no home:
  * `preflight.py`    verifies the *toolchain* (python / git / gh present + authenticated);
  * `self_review.py`  is the CI-style gate over a *rendered repo* (the scaffold self-review);
  * `self_check.py`   (this) is a short, ADVISORY checklist the acting agent answers about the CHANGE
                      it is about to propose — the common, cheap misses (a path it does not own, more
                      than one PR, a non-English on-disk value, unfilled PR metadata) that a gate
                      would otherwise catch only after a round-trip. The gate stays authoritative;
                      this just front-runs it so the miss is caught before the PR, not after.

Every item is DERIVED from a spec — `authority.ownership_map`, `git.commit`, `git.pr.metadata`,
`git.pr.required_crosslinks`, and (M17 17.4, #280) the `interaction` policy's operative blocks —
so the checklist can never rot away from the rules it front-runs (a
metadata field added to `git.yaml` shows up here automatically, proven in the tests). English-on-disk
and the precedence order are the two invariants with no single machine-readable field; they are cited
to `AGENTS.md` §2 and the `os/` README *Precedence* section, the way every file in the tree cites its
governing section.

**Whose contract does it front-run?** (#368) The `git` items come from the repository's **own**
policy where it has one — `docs/workflow/git-policy.yaml`, via `git_check`'s discovery ladder
(#358) — **merged over** the vendored `os/git/git.yaml`, never replacing it. The rendered policy
deliberately carries only what varies per project, so reading it *instead* would drop the items it
does not mention, and a pre-flight that quietly stops asking about PR metadata is worse than one
asking with the wrong repo's values. `authority` and `interaction` stay vendored-spec-relative on
purpose: `ownership_map`'s globs are already project-shaped (`src/**`, `docs/rfc/**`), and how an
agent communicates is universal. The readout names the source it used.

Dependency-free (stdlib + the sibling renderer's YAML loader). It prints; it changes nothing.

    python .eados-core/tools/self_check.py [--repo DIR] [--policy PATH]
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # .eados-core/
sys.path.insert(0, HERE)
import render  # noqa: E402  — the hand-rolled, dependency-free YAML loader (sibling tool)

AUTHORITY = os.path.join(ROOT, "orchestrator", "os", "authority", "authority.yaml")
GIT = os.path.join(ROOT, "orchestrator", "os", "git", "git.yaml")
INTERACTION = os.path.join(ROOT, "orchestrator", "os", "interaction", "interaction.yaml")


def _load(path):
    """A spec loaded as data, or `{}` when it is absent/unreadable — a missing spec drops the items it
    would have sourced, never a traceback (the checklist is advisory, not load-bearing)."""
    try:
        with open(path, encoding="utf-8") as handle:
            return render.load_yaml(handle.read()) or {}
    except OSError:
        return {}


def _merge(base, overlay):
    """`overlay` over `base`, recursing into mappings. A scalar or list in `overlay` replaces the
    value under it; anything `overlay` does not mention keeps `base`'s value.

    Recursive rather than one level deep so a project declaring *part* of a block (say two of the
    four `pr.metadata` fields) keeps the rest instead of silently blanking them — losing checklist
    items is the failure this whole change is about. The trade, stated because it is real: a project
    can override an inherited field but not remove one. No project needs to today, and a subtractive
    syntax would be a much larger thing to justify."""
    if not isinstance(base, dict) or not isinstance(overlay, dict):
        return overlay if overlay is not None else base
    out = dict(base)
    for key, value in overlay.items():
        out[key] = _merge(base.get(key), value) if isinstance(value, dict) else value
    return out


def resolve_git_policy(repo=".", explicit=None):
    """`(policy, origin)` — the git contract this checklist should front-run (#368).

    The checklist exists to front-run **the gate that will actually run**. It read the factory's
    `os/git/git.yaml` unconditionally, so inside a generated repo it described EADOS's PR contract
    rather than that project's — the #358 shape, in the last tool that still had it.

    Resolved through `git_check`'s ladder, then **merged over** the factory spec rather than
    replacing it. That second half is the point: the rendered `git-policy.yaml` deliberately carries
    only what varies per project (#358), so reading it *instead* would have dropped four of the
    seven items — every one is guarded on its field being present, and a pre-flight check that
    quietly stops asking about PR metadata is worse than one asking with the wrong repo's values."""
    base = _load(GIT)
    try:
        import git_check
        path, origin = git_check.resolve_policy(repo, explicit)
    except (ImportError, OSError, ValueError):
        return base, "the vendored os/git/git.yaml (policy discovery unavailable)"
    if not path:
        return base, f"{origin} — falling back to the vendored os/git/git.yaml"
    if os.path.abspath(path) == os.path.abspath(GIT):
        return base, origin
    project = _load(path)
    if not project:
        return base, f"{origin} (unreadable) — falling back to the vendored os/git/git.yaml"
    return _merge(base, project), f"{origin}, merged over the vendored os/git/git.yaml"


def preflight_checklist(authority, git, interaction=None):
    """The pre-PR self-check as a list of `(question, source)` pairs, each DERIVED from a spec field —
    or cited, for the two invariants with no machine-readable field. Pure (no I/O). When `interaction`
    is present (M17 17.4, #280), the checklist also front-runs the interaction contract's operative
    rules — the *how you communicate* half of the contract, sourced from the blocks the policy
    actually declares so a renamed block surfaces here rather than rotting."""
    commit = git.get("commit") or {}
    prpol = git.get("pr") or {}
    meta = prpol.get("metadata") or {}
    crosslinks = prpol.get("required_crosslinks") or []
    owns_rules = authority.get("ownership_map") or []

    items = [(
        f"does every path I changed resolve to a glob my role owns or may draft? "
        f"({len(owns_rules)} rules in authority.ownership_map)",
        "authority: ownership_map / roles[].may_draft")]
    if commit.get("one_logical_change_per_pr") or commit.get("one_pr_at_a_time"):
        items.append((
            "is this ONE logical change, and the only PR in flight?",
            "git: commit.one_logical_change_per_pr / one_pr_at_a_time"))
    if meta:
        fields = ", ".join(f"{k}={v}" for k, v in meta.items())
        items.append((
            f"will the PR carry every metadata field set on creation ({fields})?",
            "git: pr.metadata"))
    if crosslinks:
        items.append((
            f"does the PR body reference its required cross-links ({', '.join(crosslinks)})?",
            "git: pr.required_crosslinks"))
    if prpol.get("opened_by") == "human" or prpol.get("merged_by") == "human":
        items.append((
            "have I stopped at the draft/PR boundary — the human opens and merges, not me?",
            "git: pr.opened_by / pr.merged_by = human; AGENTS.md §6"))
    if interaction:
        blocks = ", ".join(k for k in ("confidence", "sycophancy", "dissent", "pushback")
                           if interaction.get(k)) or "the contract"
        items.append((
            "does the reply I am about to send calibrate — load-bearing claims confidence-tagged by "
            "evidence, no courtesy opener, and the dissent template (position/alternative/risk) when "
            "I disagree?",
            f"interaction: {blocks}; AGENTS.md §10"))
    items.append((
        "is every value I wrote on disk English?",
        "AGENTS.md §2"))
    items.append((
        "if I touched an overlapping layer, does my change respect precedence "
        "(a lesson / profile never overrides a gate, a spec, or the human)?",
        "os/README.md — Precedence"))
    return items


def format_checklist(items):
    """Render the `(question, source)` pairs as an aligned, tickable checklist block."""
    lines = ["pre-flight self-check — answer before opening the PR "
             "(advisory; the gate is authoritative):"]
    for question, source in items:
        lines.append(f"  [ ] {question}")
        lines.append(f"        ↳ {source}")
    return lines


def main(argv=None):
    # issue #128: force UTF-8 stdio so the ↳ arrow never mojibakes or crashes on cp1252 (Windows).
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    import argparse
    ap = argparse.ArgumentParser(
        description="EADOS pre-flight self-check - the agent-facing checklist to run before a PR.")
    ap.add_argument("--repo", default=".", help="repository whose git policy applies (default: .)")
    ap.add_argument("--policy", help="the git policy to front-run (default: discovered from --repo)")
    args = ap.parse_args(argv)
    git, origin = resolve_git_policy(args.repo, args.policy)
    for line in format_checklist(preflight_checklist(_load(AUTHORITY), git, _load(INTERACTION))):
        print(line)
    # Named, not implied: a checklist that front-runs the wrong contract looks exactly like one that
    # front-runs the right one, and that is how this went unnoticed (#368).
    print(f"        (git items from: {origin})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
