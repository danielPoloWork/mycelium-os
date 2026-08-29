#!/usr/bin/env python3
"""EADOS action-pin sync — keep the rendered workflow templates in lockstep with the factory CI.

`eados_lint`'s **`action-pins`** gate (check #6) *detects* drift between the factory CI
(`.github/workflows/ci.yml`) and the rendered workflow templates
(`.eados-core/templates/.github/workflows/*.tmpl`): a SHA-pinned action shared by both must pin the
same commit. But Dependabot's `github-actions` ecosystem only scans real workflow files — never the
`.tmpl` copies (ADR-0009, 2026-06-18 addendum) — so every Dependabot bump drifts the templates and
the gate (correctly) blocks the PR until someone re-pins the templates by hand.

This is the matching **fixer**: it rewrites each template pin to the factory CI's pin for that
action, so the gate passes with no manual edit. It reuses `eados_lint`'s pin regex and path
constants verbatim — one source of truth, so `--check` here and the gate there can never disagree.
Deterministic and dependency-free (it copies the SHA the factory already trusts; it never resolves
a tag to a SHA itself).

    python .eados-core/tools/sync_action_pins.py          # --check: report drift, exit 1 if any
    python .eados-core/tools/sync_action_pins.py --fix     # rewrite template pins to match; exit 0

The intended use is on a Dependabot `github-actions` PR: run `--fix`, commit the result. See
`.eados-core/maintenance/stay-current.md`. Hands-off CI auto-remediation is tracked in #76.
"""

import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eados_lint  # noqa: E402  — reuse PIN_RE, read(), and the path constants (one source of truth)

FACTORY_CI = os.path.join(eados_lint.REPO_ROOT, ".github", "workflows", "ci.yml")
TEMPLATE_WORKFLOWS = os.path.join(eados_lint.TEMPLATES, ".github", "workflows")


def _display(path):
    """A repo-relative, forward-slash path for messages. Falls back to the path as-is when it is
    on a different drive than the repo (Windows `relpath` raises across mounts) — cosmetic only."""
    try:
        return os.path.relpath(path, eados_lint.ROOT).replace(os.sep, "/")
    except ValueError:
        return path.replace(os.sep, "/")


def parse_pins(text):
    """{action: (sha, ver)} for every fully SHA-pinned `uses:` line in `text`."""
    return {action: (sha, ver) for action, sha, ver in eados_lint.PIN_RE.findall(text)}


def rewrite(text, factory):
    """Return (new_text, changes): rewrite each pin whose action is in `factory` and whose
    (sha, ver) differs, to the factory's pin. Lines whose action is not shared, and floating-tag
    `uses:` lines the regex does not match, are left untouched. `changes` is a list of
    (action, (old_sha, old_ver), (new_sha, new_ver))."""
    changes = []

    def repl(match):
        action, sha, ver = match.group(1), match.group(2), match.group(3)
        if action in factory and (sha, ver) != factory[action]:
            new_sha, new_ver = factory[action]
            changes.append((action, (sha, ver), (new_sha, new_ver)))
            return f"uses: {action}@{new_sha} # {new_ver}"
        return match.group(0)

    return eados_lint.PIN_RE.sub(repl, text), changes


def drift(factory, paths):
    """List of (rel, action, (sha, ver), (factory_sha, factory_ver)) for each out-of-lockstep pin —
    the same condition `eados_lint.check_action_pins` reports, exposed here for `--check`."""
    out = []
    for path in paths:
        rel = _display(path)
        for action, sha, ver in eados_lint.PIN_RE.findall(eados_lint.read(path)):
            if action in factory and (sha, ver) != factory[action]:
                out.append((rel, action, (sha, ver), factory[action]))
    return out


def template_workflow_files():
    """The rendered baseline workflow templates the gate governs (non-recursive `*.tmpl`,
    matching `eados_lint.check_action_pins`)."""
    return sorted(glob.glob(os.path.join(TEMPLATE_WORKFLOWS, "*.tmpl")))


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    import argparse
    ap = argparse.ArgumentParser(description="Sync the workflow templates' action pins to the "
                                             "factory CI (the action-pins lockstep gate).")
    ap.add_argument("--fix", action="store_true",
                    help="rewrite the template pins to match the factory CI (default: check only)")
    args = ap.parse_args(argv)

    if not os.path.exists(FACTORY_CI) or not os.path.isdir(TEMPLATE_WORKFLOWS):
        print("sync-action-pins: nothing to cross-check (standalone .eados-core checkout).")
        return 0

    factory = parse_pins(eados_lint.read(FACTORY_CI))
    paths = template_workflow_files()

    if args.fix:
        fixed = 0
        for path in paths:
            new_text, changes = rewrite(eados_lint.read(path), factory)
            if not changes:
                continue
            with open(path, "w", encoding="utf-8", newline="\n") as handle:  # preserve LF on Windows
                handle.write(new_text)
            rel = _display(path)
            for action, (_old_sha, old_ver), (new_sha, new_ver) in changes:
                print(f"  fixed {rel}: {action} {old_ver} -> {new_ver} ({new_sha[:10]})")
            fixed += len(changes)
        print(f"sync-action-pins: fixed {fixed} pin(s) to match the factory CI." if fixed
              else "sync-action-pins: already in lockstep — nothing to fix.")
        return 0

    problems = drift(factory, paths)
    if problems:
        print("sync-action-pins: DRIFT — the templates are behind the factory CI; run with --fix:")
        for rel, action, (sha, ver), (factory_sha, factory_ver) in problems:
            print(f"  {rel}: {action} {ver} ({sha[:10]}) != factory {factory_ver} "
                  f"({factory_sha[:10]})")
        return 1
    print("sync-action-pins: OK — the workflow templates are in lockstep with the factory CI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
