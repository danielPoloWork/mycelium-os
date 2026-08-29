#!/usr/bin/env python3
"""Structural self-review of a generated repository (beyond the congruence lint).

Dependency-free. Run against a rendered repo:

    python .eados-core/tools/self_review.py <path-to-generated-repo>

consistency_lint.py proves the generated repo is internally *congruent*; this proves it is
*complete* — every governance file, doc subsystem, and GitHub artifact the enterprise bar
expects is actually present, the ROADMAP has its required sections, and no {{PLACEHOLDER}}
leaked through. It is the mechanical half of eval/rubric.md (the human/agent scores the rest).

Exit non-zero if any REQUIRED item is missing or a stray placeholder is found; capability-gated
items (i18n, announcements) are checked only if present.
"""

import glob
import os
import re
import sys

REQUIRED_FILES = [
    "AGENTS.md", "CLAUDE.md", "GEMINI.md", "README.md", "ROADMAP.md", "CHANGELOG.md",
    "SECURITY.md", "LICENSE", ".gitignore",
    ".github/workflows/ci.yml", ".github/workflows/release.yml", ".github/dependabot.yml",
    ".github/CODEOWNERS", ".github/labels.yml", ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml", ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    "docs/README.md",
    "docs/adr/0001-record-architecture-decisions.md",
    "docs/adr/0002-adopt-cross-language-source-layout.md",
    "docs/adr/template.md", "docs/adr/README.md",
    "docs/patterns/README.md", "docs/patterns/design-patterns.md",
    "docs/specs/template.md",
    "docs/bugs/README.md", "docs/bugs/template.md",
    "docs/security/README.md", "docs/security/threat-model.md",
    "docs/journal/README.md",
    "docs/releases/README.md",
    "docs/workflow/git-workflow.md", "docs/workflow/documentation.md",
    "docs/workflow/release.md", "docs/workflow/maintenance.md", "docs/workflow/github-setup.md",
    "docs/development/local-build.md",
    "tools/consistency_lint.py",
]
REQUIRED_GLOBS = ["docs/specs/01_spec_*.md"]
ROADMAP_SECTIONS = ["## Milestone 1", "## Spec Coverage Map"]
PLACEHOLDER_RE = re.compile(r"(?<!\$)\{\{")


def main():
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        print("usage: python self_review.py <path-to-generated-repo>")
        return 2
    repo = os.path.abspath(sys.argv[1])
    problems, warnings = [], []

    for rel in REQUIRED_FILES:
        if not os.path.exists(os.path.join(repo, rel.replace("/", os.sep))):
            problems.append(f"missing required artifact: {rel}")
    for pattern in REQUIRED_GLOBS:
        if not glob.glob(os.path.join(repo, pattern.replace("/", os.sep))):
            problems.append(f"no file matches required pattern: {pattern}")

    roadmap = os.path.join(repo, "ROADMAP.md")
    if os.path.exists(roadmap):
        with open(roadmap, encoding="utf-8") as handle:
            text = handle.read()
        for section in ROADMAP_SECTIONS:
            if section not in text:
                problems.append(f"ROADMAP.md is missing the '{section}' section")

    readme = os.path.join(repo, "README.md")
    if os.path.exists(readme):
        with open(readme, encoding="utf-8") as handle:
            readme_text = handle.read()
        if "img.shields.io/badge/Status-v" not in readme_text:
            warnings.append("README.md has no Status-vX.Y.Z badge")

    # Stray, unrendered placeholders anywhere (GitHub Actions ${{ }} is allowed).
    for cur, dirs, files in os.walk(repo):
        # Don't descend into git internals or a co-located factory copy (.eados-core/, whose
        # *.tmpl files legitimately contain {{placeholders}} and would be false positives).
        dirs[:] = [d for d in dirs if d not in (".git", ".eados-core")]
        for fn in files:
            path = os.path.join(cur, fn)
            try:
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
            except (UnicodeDecodeError, OSError):
                continue
            if PLACEHOLDER_RE.search(text):
                rel = os.path.relpath(path, repo).replace(os.sep, "/")
                problems.append(f"stray unrendered placeholder in {rel}")

    # Capability-gated, checked only if the surface exists.
    if os.path.isdir(os.path.join(repo, "docs", "i18n")):
        if not os.path.exists(os.path.join(repo, "docs", "i18n", "translation-status.md")):
            problems.append("docs/i18n/ present but translation-status.md is missing")
    if os.path.isdir(os.path.join(repo, "docs", "benchmarks")):
        for need in ("README.md", "template.md"):
            if not os.path.exists(os.path.join(repo, "docs", "benchmarks", need)):
                problems.append(f"docs/benchmarks/ present but {need} is missing")

    for w in warnings:
        print(f"  [warn] {w}")
    if problems:
        print("Self-review: INCOMPLETE\n")
        for p in sorted(set(problems)):
            print(f"  [missing] {p}")
        print(f"\n{len(set(problems))} completeness problem(s).")
        return 1
    print("Self-review: OK — the generated repo is structurally complete"
          + (f" ({len(warnings)} warning(s))" if warnings else "") + ".")
    return 0


if __name__ == "__main__":
    sys.exit(main())
