#!/usr/bin/env python3
"""`/eados upgrade` tells a generated repo what changed — and touches nothing (#320, ADR-0003).

The load-bearing property is the **write boundary**. ADR-0003 rejected re-rendering because it
clobbers the divergence a self-governing repo is supposed to accumulate; the 2026-07-27 addendum
admits an advisory channel *on condition* that it never writes. That condition is one helpful patch
away from erosion, and no amount of prose prevents it — so it is asserted here by hashing a scratch
tree before and after a real run.

The rest is the honesty contract: no stamp -> say so and stop, never guess a baseline; a missing
CHANGELOG -> skip with a stated cause, never "you are up to date"; factory-internal changes stay out
of a consumer's report; a template change names the file in THEIR repo, via the renderer's own map.

    python .eados-core/tools/tests/test_upgrade_advice.py
"""

import hashlib
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import upgrade_advice as ua   # noqa: E402

GITATTRIBUTES = """
/.github                export-ignore
/.issues                export-ignore
/CHANGELOG.md           export-ignore
/README.md              export-ignore
/.eados-core/docs/i18n  export-ignore
/setup                  export-ignore
"""

CHANGELOG = """# Changelog

## [Unreleased]

### Added

- **A change that has not shipped (#999).** Must never reach a consumer report.

## [2.2.0] - 2026-07-20

### Security

- **Installer hardening (#129).** `setup/setup.sh` refuses symlink entries.

### Fixed

- **A rendered CI workflow was wrong (#310).** `templates/.github/workflows/ci.yml.tmpl` pinned a
  mislabeled commit.

### Added

- **A new gate (#326).** `os/routing/routing.yaml` gains freshness bounds.
- **A note in the issue backlog (#1).** `.issues/README.md` gained a column.
- **A profile bump.** `profiles/rust.yaml` raises its toolchain.
- **Something with no path named at all (#7).** Prose only.

## [2.1.0] - 2026-07-10

### Changed

- **Only the factory's own README (#2).** `README.md` gained a badge.

## [2.0.0] - 2026-07-01

### Fixed

- **Older than the stamp (#3).** `tools/render.py` — must not appear.
"""


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def tree_hash(root):
    """Every path and byte under `root`. The write boundary is not 'no exception was raised'."""
    h = hashlib.sha256()
    for base, dirs, files in os.walk(root):
        dirs.sort()
        for fn in sorted(files):
            p = os.path.join(base, fn)
            h.update(os.path.relpath(p, root).replace("\\", "/").encode())
            with open(p, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


def entry_named(releases, needle):
    for rel in releases:
        for e in rel["entries"]:
            if needle in e["title"]:
                return e
    return None


def main():
    failures = []
    ignored = ua.export_ignored(GITATTRIBUTES)
    check("export-ignore is read from .gitattributes, not hardcoded",
          ".github" in ignored and "CHANGELOG.md" in ignored and
          ".eados-core/docs/i18n" in ignored, failures)

    releases = ua.parse_changelog(CHANGELOG)
    versions = [r["version"] for r in releases]
    check(f"releases parse newest-first ({versions})", versions == ["2.2.0", "2.1.0", "2.0.0"],
          failures)
    check("[Unreleased] is not a release — unshipped work cannot leak into a consumer report",
          all(entry_named([r], "has not shipped") is None for r in releases), failures)

    delta = ua.newer_than(releases, "2.1.0")
    check("the delta is what is strictly NEWER than the stamp",
          [r["version"] for r in delta] == ["2.2.0"], failures)
    check("an unparseable stamp yields no delta rather than the whole history",
          ua.newer_than(releases, "not-a-version") == [], failures)

    # --- the consequence class comes from the section, never from semver or prose -------------
    for title, want in (("Installer hardening", "security"),
                        ("A rendered CI workflow was wrong", "correctness"),
                        ("A new gate", "capability")):
        e = entry_named(releases, title)
        check(f"'{title}' classifies from its section", e and e["klass"] == want, failures)

    # --- the filter: what does THIS repo actually carry? --------------------------------------
    cases = {
        "Installer hardening": ("affects", "asset"),          # export-ignored BUT a release asset
        "A rendered CI workflow was wrong": ("affects", "rendered"),
        "A new gate": ("affects", "vendored"),
        "A note in the issue backlog": ("internal", None),    # .issues/ never reaches a consumer
        "Something with no path named at all": ("unattributed", None),
    }
    for title, (want_rel, want_kind) in cases.items():
        e = entry_named(releases, title)
        if not e:
            failures.append(f"fixture entry '{title}' did not parse")
            continue
        a = ua.assess(e, ignored, profile="rust")
        check(f"'{title}' -> {want_rel} (got {a['relevance']})", a["relevance"] == want_rel,
              failures)
        if want_kind:
            check(f"'{title}' -> a {want_kind} surface (got {[c[0] for c in a['carries']]})",
                  any(c[0] == want_kind for c in a["carries"]), failures)

    # A template change must name the file in THEIR repo, resolved by the renderer's own map —
    # so the report cannot name a file render.py would never have produced.
    ci = ua.assess(entry_named(releases, "A rendered CI workflow was wrong"), ignored)
    check(f"a template change names the rendered artifact (got {ci['carries']})",
          any(w == ".github/workflows/ci.yml" for _, w, _ in ci["carries"]), failures)

    # A gate/spec surface upgrades Added -> governance; an entry that named no path gets no class
    # it did not earn.
    check("a change under os/ is governance, not bare 'capability'",
          ua.assess(entry_named(releases, "A new gate"), ignored)["klass"] == "governance",
          failures)
    check("an unattributed entry keeps its section class",
          ua.assess(entry_named(releases, "Something with no path"), ignored)["klass"]
          == "capability", failures)

    # Another language's profile is not this repo's business; its own is.
    prof = entry_named(releases, "A profile bump")
    check("another language's profile is filtered out",
          ua.assess(prof, ignored, profile="python")["relevance"] == "internal", failures)
    check("this repo's own profile is reported",
          ua.assess(prof, ignored, profile="rust")["relevance"] == "affects", failures)

    # --- an internal-only entry stays out of the default report, and --all is the escape ------
    stamp = {"version": "2.1.0", "commit": "abc1234", "source": "test"}
    lines, shown, acted = ua.build_report(stamp, delta, ignored, profile="rust")
    body = "\n".join(lines)
    check("factory-internal entries are not reported", "issue backlog" not in body, failures)
    check("consumer-visible entries are", "Installer hardening" in body, failures)
    check(f"act-now counts security+correctness only (got {acted})", acted == 2, failures)
    check("the readout states the advisory boundary", "ADVISORY ONLY" in body, failures)
    all_body = "\n".join(ua.build_report(stamp, delta, ignored, profile="rust", show_all=True)[0])
    check("--all is the escape hatch for internal entries", "issue backlog" in all_body, failures)
    check("an unfilterable run SAYS it is unfiltered",
          "NOT FILTERED" in "\n".join(ua.build_report(stamp, delta, (), filtered=False)[0]),
          failures)
    check("no newer release reads as 'up to date', and only then",
          "up to date" in "\n".join(ua.build_report(stamp, [], ignored)[0]), failures)

    with tempfile.TemporaryDirectory() as tmp:
        # --- no stamp: explain and stop; never guess a baseline ------------------------------
        bare = os.path.join(tmp, "bare")
        os.makedirs(bare)
        check("an unstamped repo yields no stamp (not a default)", ua.stamp_of(bare) is None,
              failures)
        buf, real = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            rc = ua.main([bare, "--no-fetch"])
        finally:
            sys.stdout = real
        out = buf.getvalue()
        check("an unstamped repo exits cleanly — it is not a failure of that repo", rc == 0,
              failures)
        check("...and says what is missing and how to record it",
              "NO PROVENANCE STAMP" in out and "generated_by:" in out, failures)
        check("...and never claims the repo is current",
              "up to date" not in out.lower(), failures)

        # --- both recorded stamp sources, structured first ------------------------------------
        repo = os.path.join(tmp, "repo")
        os.makedirs(os.path.join(repo, "orchestrator"))
        with open(os.path.join(repo, "AGENTS.md"), "w", encoding="utf-8") as fh:
            fh.write("> **Provenance:** generated by EADOS v2.1.0 (commit deadbee) on 2026-07-10.\n")
        s = ua.stamp_of(repo)
        check(f"the AGENTS.md provenance line is a stamp source (got {s})",
              s and s["version"] == "2.1.0" and s["commit"] == "deadbee", failures)
        with open(os.path.join(repo, "orchestrator", "project.yaml"), "w",
                  encoding="utf-8") as fh:
            fh.write('language:\n  lang: rust\ngenerated_by:\n  eados_version: "2.0.0"\n'
                     "  eados_commit: cafe123\n")
        s = ua.stamp_of(repo)
        check(f"a RECORDED generated_by wins over the prose line (got {s})",
              s and s["version"] == "2.0.0" and "generated_by" in s["source"], failures)

        cl = os.path.join(tmp, "CHANGELOG.md")
        with open(cl, "w", encoding="utf-8") as fh:
            fh.write(CHANGELOG)
        ga = os.path.join(tmp, ".gitattributes")
        with open(ga, "w", encoding="utf-8") as fh:
            fh.write(GITATTRIBUTES)

        # --- THE BOUNDARY: a real run leaves the tree byte-identical --------------------------
        before = tree_hash(repo)
        buf, real = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            rc = ua.main([repo, "--changelog", cl, "--gitattributes", ga, "--no-fetch"])
        finally:
            sys.stdout = real
        report = buf.getvalue()
        check("a real run succeeds", rc == 0, failures)
        check("THE WRITE BOUNDARY: the repository is byte-identical after the run "
              "(ADR-0003 — the moment it writes, the rejected re-render branch is back)",
              tree_hash(repo) == before, failures)
        check("the run reported the releases newer than the stamp",
              "2.2.0" in report and "2.1.0" in report, failures)
        check("...and none older", "2.0.0" not in report.split("## v2.1.0")[0].split("since:")[-1],
              failures)

        # --- no CHANGELOG: skip with a stated cause, never a false all-clear ------------------
        buf, real = io.StringIO(), sys.stdout
        sys.stdout = buf
        try:
            rc = ua.main([repo, "--changelog", os.path.join(tmp, "absent.md"), "--no-fetch"])
        finally:
            sys.stdout = real
        out = buf.getvalue()
        check(f"an unreadable CHANGELOG exits non-zero (got {rc})", rc == 2, failures)
        check("...stating the cause", "SKIP" in out and "CHANGELOG" in out, failures)
        check("...and explicitly NOT claiming 'up to date' (L-0006)",
              "up to date" not in out.lower().split("not reporting")[0], failures)

    if failures:
        print("test-upgrade-advice: FAIL\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("test-upgrade-advice: OK — the advisor reads a recorded stamp (never guesses one), "
          "classifies from the changelog section, filters to the surfaces a consumer actually "
          "carries, states what it could not establish, and leaves the repository byte-identical.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
