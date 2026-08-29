#!/usr/bin/env python3
"""Validate that every CI fragment EADOS ships parses as well-formed YAML.

This closes the gap the congruence lint and self-review leave open: they prove a generated
repo is *structurally complete* and *placeholder-resolved*, but not that the GitHub Actions
YAML it emits actually parses. A profile whose `extra_jobs`/`setup_steps`/`race_job` block is
subtly malformed (e.g. `run: { ... } && cmd`) would sail through every existing gate because
the render-smoke only exercises the hand-tuned reference manifest — not the raw profiles.

It uses a REAL YAML parser (PyYAML). To keep EADOS's tools dependency-free for everyday use,
this check degrades gracefully: if PyYAML is not importable it prints a notice and exits 0.
CI installs PyYAML, so the gate is enforced there.

    python tools/profile_ci_lint.py                 # validate every profile's CI fragments
    python tools/profile_ci_lint.py --rendered DIR  # also validate a rendered repo's *.yml
"""

import argparse
import glob
import os
import sys
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES = os.path.join(ROOT, "orchestrator", "profiles")


def _wrap(kind, fragment):
    """Embed a CI fragment in a minimal valid workflow context so it can be parsed on its own:
    `setup_steps` is a step *sequence*, `extra_jobs`/`race_job` are job *mappings*."""
    body = textwrap.indent(fragment.rstrip("\n"), "  ")
    return f"steps:\n{body}\n" if kind == "setup_steps" else f"jobs:\n{body}\n"


def main():
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Validate EADOS CI fragments are well-formed YAML.")
    ap.add_argument("--rendered", help="also validate every *.yml/*.yaml under this rendered repo")
    args = ap.parse_args()

    try:
        import yaml
    except ImportError:
        print("profile-ci-lint: SKIP — PyYAML not installed (pip install pyyaml to enforce).")
        return 0

    problems = []

    for path in sorted(glob.glob(os.path.join(PROFILES, "*.yaml"))):
        if os.path.basename(path).startswith("_"):
            continue
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        with open(path, encoding="utf-8") as fh:
            try:
                prof = yaml.safe_load(fh) or {}  # real parser — independent of render.load_yaml
            except yaml.YAMLError as exc:
                problems.append(f"{rel}: profile is not well-formed YAML: "
                                f"{str(exc).splitlines()[0]}")
                continue
        ci = prof.get("ci") or {}
        for key in ("setup_steps", "extra_jobs", "race_job"):
            frag = ci.get(key)
            if not frag or not str(frag).strip():
                continue
            try:
                yaml.safe_load(_wrap(key, str(frag)))
            except yaml.YAMLError as exc:
                problems.append(f"{rel}: ci.{key} is not well-formed YAML: "
                                f"{str(exc).splitlines()[0]}")

    if args.rendered:
        repo = os.path.abspath(args.rendered)
        seen = set()
        for pat in ("**/*.yml", "**/*.yaml"):
            for f in glob.glob(os.path.join(repo, pat), recursive=True):
                if f in seen:
                    continue
                seen.add(f)
                rel = os.path.relpath(f, repo).replace(os.sep, "/")
                try:
                    with open(f, encoding="utf-8") as fh:
                        yaml.safe_load(fh)
                except yaml.YAMLError as exc:
                    problems.append(f"{rel}: rendered YAML does not parse: "
                                    f"{str(exc).splitlines()[0]}")

    if problems:
        print("profile-ci-lint: FAIL\n")
        for p in problems:
            print(f"  {p}")
        print(f"\n{len(problems)} malformed-YAML problem(s).")
        return 1
    print("profile-ci-lint: OK — all profile CI fragments and rendered YAML parse.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
