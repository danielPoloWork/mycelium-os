#!/usr/bin/env python3
"""EADOS upgrade advisor — the `/eados upgrade` advisory channel to an already-generated repo (#320).

ADR-0003 decided that a generated repository is **self-governing** and is never re-rendered. It
weighed two branches, both about *writing* into that repo, and rejected both — so the operative
answer became *nothing*, and twelve releases of fixes (a UTF-8 crash across the CLI tools, installer
tar-slip hardening, a pin that lied about its own version) reached new repositories only. The
2026-07-27 addendum admits the third branch: **tell them, never touch them.**

So this tool **reports and stops**. No patches, no merges, no `git` operations, no manifest edits —
the moment it writes, ADR-0003's rejected re-render branch is back through the side door, which is
why `test_upgrade_advice.py` asserts a byte-identical tree rather than trusting the convention.

Three rules it holds itself to, each because the alternative is a confident lie:

  * **The provenance stamp is read, never guessed** (#319). No stamp -> say what is missing and how
    to record it, and stop. A guessed baseline produces a delta against the wrong version and looks
    exactly like a real one.
  * **The consequence class comes from data**, never from mining prose: the Keep a Changelog section
    heading (`Security`/`Fixed`/`Added`/`Changed`/`Deprecated`), refined to `governance` only from
    paths the entry *itself names*.
  * **What could not be established is stated** (L-0006). An unfiltered report says it is unfiltered;
    it never reports "you are up to date" from an absence of evidence.

    python .eados-core/tools/upgrade_advice.py <repo-path> [--changelog PATH] [--repo OWNER/REPO]
                                               [--all] [--json]
"""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # .eados-core/
FACTORY = os.path.dirname(ROOT)                    # the factory checkout, when there is one
sys.path.insert(0, HERE)
import render                                      # noqa: E402  — loader + the template->output map

GH_TIMEOUT = 30                                    # network-bound (#321)
DEFAULT_REPO = "danielPoloWork/pgs-eados"

# Paths a consumer never receives, so a change to one is invisible to them and must not be
# reported. NOT hardcoded: `.gitattributes` `export-ignore` is the authority for what `git archive`
# strips, and re-stating it here would be a second copy free to drift from the bundle it describes.
_EXPORT_IGNORE_RE = re.compile(r"(?m)^\s*(\S+)\s+export-ignore\s*$")

# ...with ONE stated exception. `setup/` is export-ignored *because it is published separately as
# release assets* (`.gitattributes` says so in its own comment), not because a consumer does not use
# it — the installer is how they install. Export-ignore alone would silently drop the tar-slip
# hardening (#129), which is precisely the class of change this command exists to surface.
CONSUMER_ASSETS = ("setup",)

# A backticked token in a changelog bullet is a path the AUTHOR named. These roots are written
# relative to `.eados-core/` in the prose; re-anchoring them is normalization, not inference.
_CORE_ROOTS = ("templates", "orchestrator", "tools", "docs", "agent", "config", "learning")
_TOKEN_RE = re.compile(r"`([^`\n]+)`")
_RELEASE_RE = re.compile(r"(?m)^##\s*\[(\d+\.\d+\.\d+)\](?:\s*-\s*(\S+))?\s*$")
_SECTION_RE = re.compile(r"(?m)^###\s+(\S+)")
_REF_RE = re.compile(r"#(\d+)")
_VERSION_RE = re.compile(r"\b(\d+)\.(\d+)\.(\d+)\b")

# The section heading IS the consequence class — Keep a Changelog already made the maintainer
# choose one at write time. Semver does not: a MINOR carries both a security fix and a README tweak.
SECTION_CLASS = {"Security": "security", "Fixed": "correctness", "Added": "capability",
                 "Changed": "behavior", "Deprecated": "deprecation", "Removed": "removal"}
ACT_NOW = ("security", "correctness", "removal")

# Surfaces whose change is a GOVERNANCE change — a gate, a policy spec, or a decision record. This
# refinement fires only on a path the entry named; an entry that names no path gets no class it did
# not earn.
GOVERNANCE_HINTS = (".eados-core/orchestrator/os/", ".eados-core/tools/eados_lint.py",
                    ".eados-core/docs/adr/", ".eados-core/orchestrator/commands/")


def _version_tuple(text):
    m = _VERSION_RE.search(str(text or ""))
    return tuple(int(g) for g in m.groups()) if m else None


# ---------------------------------------------------------------------------
# 1. The consumer's stamp — read, never guessed (#319).
# ---------------------------------------------------------------------------
def stamp_of(repo):
    """`{version, commit, source}` for the repo at `repo`, or None when it carries no stamp.

    Two recorded sources, structured first: the manifest's `generated_by:` block, then the prose
    provenance line every rendered `AGENTS.md` carries. Both are things a render WROTE down. There
    is deliberately no third source and no default — `provenance_line` renders an unstamped repo as
    "an unrecorded version", and treating that as a version would silently diff against the wrong
    baseline."""
    for rel in ("orchestrator/project.yaml", ".eados-core/orchestrator/project.yaml"):
        path = os.path.join(repo, rel)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                manifest = render.load_yaml(handle.read())
        except (OSError, ValueError):
            continue
        block = (manifest or {}).get("generated_by") if isinstance(manifest, dict) else None
        if isinstance(block, dict) and _version_tuple(block.get("eados_version")):
            return {"version": str(block.get("eados_version")).strip(),
                    "commit": str(block.get("eados_commit") or "").strip(),
                    "source": f"{rel} `generated_by:`", "manifest": manifest}
    agents = os.path.join(repo, "AGENTS.md")
    if os.path.exists(agents):
        try:
            with open(agents, encoding="utf-8") as handle:
                m = re.search(r"generated by EADOS v(\d+\.\d+\.\d+)(?:\s*\(commit ([0-9a-f]+)\))?",
                              handle.read())
        except OSError:
            m = None
        if m:
            return {"version": m.group(1), "commit": m.group(2) or "",
                    "source": "AGENTS.md provenance line", "manifest": None}
    return None


def no_stamp_report(repo):
    """What is missing and how to record it. An unstamped repo and a repo stamped by an unknown
    version are different situations; this says which one you are in rather than inventing a
    baseline to diff against."""
    return [
        f"NO PROVENANCE STAMP — {repo} does not record which EADOS produced it, so there is no",
        "baseline to compare against. Not guessing one: a delta against the wrong version reads",
        "exactly like a real one.",
        "",
        "To record it, add to the manifest (`orchestrator/project.yaml`) the block a render prints:",
        "",
        "    generated_by:",
        '      eados_version: "2.12.0"     # the factory version that produced this repo',
        "      eados_commit: f6d487c       # optional",
        '      rendered_at: "2026-07-27"   # optional',
        "",
        "A repo rendered before the stamp existed (#319, v2.12.0) has to be told: check the",
        "bootstrap PR's date against the factory CHANGELOG. Re-rendering to obtain it is NOT the",
        "remedy — ADR-0003 refuses that, and this command exists because of it.",
    ]


# ---------------------------------------------------------------------------
# 2. The delta — from the released CHANGELOG, which the release process already keeps honest.
# ---------------------------------------------------------------------------
def _gh_file(path, repo=DEFAULT_REPO):
    """A factory file at HEAD via `gh`, for a bundle install with no factory checkout. Raises
    RuntimeError with a stated cause — never returns a plausible empty string."""
    try:
        proc = subprocess.run(["gh", "api", f"repos/{repo}/contents/{path}",
                               "-H", "Accept: application/vnd.github.raw"],
                              capture_output=True, text=True, encoding="utf-8", timeout=GH_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"`gh api` for {path} timed out after {GH_TIMEOUT}s — the network "
                           "stalled, the API is rate-limiting, or it is waiting on an auth prompt")
    except (FileNotFoundError, OSError) as exc:
        raise RuntimeError(f"could not run `gh` (is the GitHub CLI installed and on PATH?): {exc}")
    if proc.returncode != 0:
        raise RuntimeError(f"`gh api` for {path} failed (authenticated? online?): "
                           f"{(proc.stderr or proc.stdout or '').strip()}")
    return proc.stdout or ""


def factory_file(rel, explicit=None, repo=DEFAULT_REPO, fetch=True):
    """`(text, origin)` for a factory file: an explicit path, then the local factory checkout, then
    `gh`. The bundle `export-ignore`s CHANGELOG.md and .gitattributes, so a consumer install has
    neither locally — the fetch is the path that makes this command usable where it matters."""
    if explicit:
        with open(explicit, encoding="utf-8") as handle:
            return handle.read(), explicit
    local = os.path.join(FACTORY, rel)
    if os.path.exists(local):
        with open(local, encoding="utf-8") as handle:
            return handle.read(), f"local factory ({rel})"
    if not fetch:
        raise RuntimeError(f"{rel} is not in this checkout and fetching is disabled")
    return _gh_file(rel, repo=repo), f"{repo}@HEAD ({rel})"


def parse_changelog(text):
    """`[{version, date, entries:[{section, klass, title, refs, surfaces}]}]`, newest first.

    One bullet == one entry: a `- ` at column 0 opens it and its indented continuation lines belong
    to it, so a nested sub-bullet does not become a phantom change."""
    releases = []
    marks = [(m.start(), m.group(1), m.group(2) or "") for m in _RELEASE_RE.finditer(text)]
    for i, (start, version, date) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        body = text[start:end]
        entries, section = [], ""
        current = None
        for line in body.split("\n"):
            sec = _SECTION_RE.match(line)
            if sec:
                section = sec.group(1).strip()
                current = None
                continue
            if line.startswith("- "):
                current = {"section": section, "lines": [line[2:]]}
                entries.append(current)
            elif current is not None and (line.startswith("  ") or not line.strip()):
                current["lines"].append(line.strip())
            else:
                current = None
        out = []
        for e in entries:
            blob = " ".join(x for x in e["lines"] if x)
            # The bolded lead is the entry's own headline — taken from the JOINED text, because it
            # routinely wraps across lines and reading only the first would truncate mid-sentence.
            m = re.match(r"\s*\*\*(.+?)\*\*", blob)
            title = re.sub(r"\s+", " ", m.group(1) if m else blob.split(".")[0]).strip()
            out.append({"section": e["section"],
                        "klass": SECTION_CLASS.get(e["section"], "other"),
                        "title": title.rstrip(".").strip(),
                        "refs": sorted({int(n) for n in _REF_RE.findall(blob)}),
                        "surfaces": surfaces_in(blob),
                        "text": blob})
        releases.append({"version": version, "date": date, "entries": out})
    return releases


def newer_than(releases, version):
    """The released sections strictly newer than `version` — the delta a repo stamped at `version`
    has not seen. `[Unreleased]` never matches the release heading regex, so unshipped work cannot
    leak into a consumer report."""
    base = _version_tuple(version)
    if base is None:
        return []
    return [r for r in releases if (_version_tuple(r["version"]) or (0, 0, 0)) > base]


# ---------------------------------------------------------------------------
# 3. The filter — what THIS repo carries.
# ---------------------------------------------------------------------------
def surfaces_in(blob):
    """Factory paths a bullet names, normalized. Reads what the author wrote in backticks; a token
    that is not recognisably a factory path is dropped rather than guessed into one."""
    found = []
    for raw in _TOKEN_RE.findall(blob):
        tok = (raw.split() or [""])[0].strip().rstrip(".,;:)")   # `tool.py --fix` -> `tool.py`
        tok = re.sub(r"/\*+$", "", tok)                          # `templates/**` -> `templates`
        if not tok:
            continue
        first = tok.split("/", 1)[0]
        if first == ".eados-core":
            path = tok
        elif first in ("os", "profiles", "domains"):
            path = ".eados-core/orchestrator/" + tok
        elif first in _CORE_ROOTS:
            path = ".eados-core/" + tok
        elif first in (".github", "setup", ".issues") or tok in (
                "CHANGELOG.md", "README.md", "SECURITY.md", "CONTRIBUTING.md", "AGENTS.md",
                "CLAUDE.md", "GEMINI.md", ".gitattributes", ".gitignore"):
            path = tok
        elif tok.endswith(".py") and "/" not in tok:
            # A bare tool name is only a path if the factory actually has it — corroborated, not
            # assumed. Without a local checkout there is nothing to corroborate against, so it is
            # dropped: `tools/` vs `tools/tests/` is a coin flip, and a wrong path is worse than none.
            cand = os.path.join(".eados-core", "tools", tok)
            path = cand.replace("\\", "/") if os.path.exists(os.path.join(FACTORY, cand)) else None
        else:
            path = None
        if path and path not in found:
            found.append(path)
    return found


def export_ignored(gitattributes_text):
    """The `export-ignore` path prefixes, as `git archive` applies them (leading `/` anchors to the
    repo root but is not part of the path)."""
    return tuple(p.lstrip("/").rstrip("/") for p in _EXPORT_IGNORE_RE.findall(gitattributes_text))


def _under(path, prefix):
    """A directory token names the tree beneath it: `templates` covers `templates/x.tmpl`."""
    return path == prefix or path.startswith(prefix.rstrip("/") + "/")


def consumer_view(path, ignored, profile=None):
    """How a consumer sees a factory path: `('vendored'|'rendered'|'asset', where)`, or None when
    the path never reaches them.

    `rendered` resolves through `render.out_relpath` — the renderer's OWN mapping, so the report
    cannot name a file the renderer would not have produced."""
    if any(_under(path, pre) for pre in ignored):
        return ("asset", path) if any(_under(path, a) for a in CONSUMER_ASSETS) else None
    if _under(path, ".eados-core/orchestrator/profiles") and path.endswith(".yaml"):
        lang = os.path.basename(path)[:-5]
        if profile and lang not in (profile, "_template", "_schema"):
            return None
    if _under(path, ".eados-core/templates"):
        rel = path[len(".eados-core/templates/"):] if path != ".eados-core/templates" else ""
        if rel.endswith(".tmpl") or rel == "gitignore":
            return "rendered", render.out_relpath(rel, "<slug>")
        return "vendored", path
    if _under(path, ".eados-core") or path in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "LICENSE"):
        return "vendored", path
    return None


def assess(entry, ignored, profile=None):
    """`{relevance, klass, carries:[(kind, where, factory_path)]}` for one changelog entry.

    `relevance` is `affects` (it named a surface this repo carries), `internal` (every surface it
    named is stripped from the bundle), or `unattributed` (it named none). Unattributed entries are
    KEPT, not dropped: an advisory channel that hides changes it could not classify is the silent
    failure this whole command was filed against."""
    carries, internal = [], 0
    for path in entry["surfaces"]:
        view = consumer_view(path, ignored, profile=profile)
        if view is None:
            internal += 1
        else:
            carries.append((view[0], view[1], path))
    if carries:
        relevance = "affects"
    elif internal:
        relevance = "internal"
    else:
        relevance = "unattributed"
    klass = entry["klass"]
    if klass in ("capability", "behavior") and any(
            p.startswith(GOVERNANCE_HINTS) for _, _, p in carries):
        klass = "governance"
    return {"relevance": relevance, "klass": klass, "carries": carries}


# ---------------------------------------------------------------------------
# 4. The report — and nothing else.
# ---------------------------------------------------------------------------
def build_report(stamp, releases, ignored, profile=None, show_all=False, filtered=True):
    """The printable readout plus `(shown, acted)` counts. Pure — it opens nothing and writes
    nothing, which is what makes the write boundary testable."""
    lines = [f"generated by EADOS v{stamp['version']}"
             + (f" (commit {stamp['commit']})" if stamp.get("commit") else "")
             + f" — from {stamp['source']}"]
    if not releases:
        lines.append("up to date — no released version is newer than the recorded stamp.")
        return lines, 0, 0
    versions = ", ".join(r["version"] for r in releases)
    lines.append(f"{len(releases)} release(s) since: {versions}")
    if not filtered:
        lines.append("NOT FILTERED — bundle membership could not be established (no "
                     "`.gitattributes`), so factory-internal changes are NOT excluded below.")
    lines.append("")
    shown = acted = 0
    for rel in releases:
        keep = [(e, assess(e, ignored, profile)) for e in rel["entries"]]
        if not show_all:
            keep = [(e, a) for e, a in keep if a["relevance"] != "internal"]
        if not keep:
            continue
        lines.append(f"## v{rel['version']}" + (f" ({rel['date']})" if rel["date"] else ""))
        for entry, a in keep:
            shown += 1
            mark = "!" if a["klass"] in ACT_NOW else " "
            if a["klass"] in ACT_NOW:
                acted += 1
            refs = " ".join(f"#{n}" for n in entry["refs"][:4])
            lines.append(f" {mark} [{a['klass']}] {entry['title']}" + (f"  ({refs})" if refs else ""))
            for kind, where, path in a["carries"]:
                if kind == "rendered":
                    lines.append(f"      your `{where}` was rendered from `{path}`")
                elif kind == "asset":
                    lines.append(f"      release asset `{path}` — re-download to pick it up")
                else:
                    lines.append(f"      vendored `{path}`")
            if a["relevance"] == "unattributed":
                lines.append("      no surface named in the entry — read it before deciding "
                             "(not classified as irrelevant, only as unattributed)")
            if a["relevance"] == "internal":
                lines.append("      factory-internal — shown only because --all was passed")
        lines.append("")
    if shown == 0:
        lines.append("nothing in that range names a surface this repository carries.")
    lines.append(f"{shown} entr(y/ies) affecting this repository; {acted} in a class worth acting "
                 "on now (security / correctness / removal).")
    lines.append("")
    lines.append("ADVISORY ONLY — this command changed nothing and will never rewrite this "
                 "repository (ADR-0003, 2026-07-27 addendum). Adopt what you want by hand; your "
                 "repo's own ADRs stay authoritative.")
    return lines, shown, acted


def main(argv=None):
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    import argparse
    ap = argparse.ArgumentParser(description="What changed upstream since this repo was generated "
                                             "(#320). Reports; never writes.")
    ap.add_argument("repo", nargs="?", default=".", help="path to the generated repository")
    ap.add_argument("--changelog", help="factory CHANGELOG.md (default: local factory, else gh)")
    ap.add_argument("--gitattributes", help="factory .gitattributes (default: local factory, else gh)")
    ap.add_argument("--repo-slug", default=DEFAULT_REPO, help=f"factory repo (default {DEFAULT_REPO})")
    ap.add_argument("--all", action="store_true", help="include factory-internal entries")
    ap.add_argument("--no-fetch", action="store_true", help="never call gh; skip if not local")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    repo = os.path.abspath(args.repo)
    stamp = stamp_of(repo)
    if stamp is None:
        for line in no_stamp_report(repo):
            print(line)
        return 0                       # a clean, explained exit — not a failure of this repo

    profile = None
    if isinstance(stamp.get("manifest"), dict):
        profile = ((stamp["manifest"].get("language") or {}) or {}).get("lang")

    try:
        changelog, origin = factory_file("CHANGELOG.md", args.changelog, args.repo_slug,
                                         fetch=not args.no_fetch)
    except (RuntimeError, OSError) as exc:
        print(f"generated by EADOS v{stamp['version']} — from {stamp['source']}")
        print(f"SKIP — could not read the factory CHANGELOG: {exc}")
        print("  The bundle `export-ignore`s CHANGELOG.md, so a consumer install has no local copy.")
        print("  Pass --changelog PATH, or run this from a factory checkout, or authenticate `gh`.")
        print("  NOT reporting 'up to date': that would be a conclusion drawn from missing data.")
        return 2

    ignored, filtered = (), False
    try:
        attrs, _ = factory_file(".gitattributes", args.gitattributes, args.repo_slug,
                                fetch=not args.no_fetch)
        ignored, filtered = export_ignored(attrs), True
    except (RuntimeError, OSError):
        pass                            # reported in the readout, never silently assumed

    releases = newer_than(parse_changelog(changelog), stamp["version"])
    lines, shown, acted = build_report(stamp, releases, ignored, profile=profile,
                                       show_all=args.all, filtered=filtered)
    if args.json:
        import json
        print(json.dumps({"stamp": {k: v for k, v in stamp.items() if k != "manifest"},
                          "source": origin, "filtered": filtered, "shown": shown, "acted": acted,
                          "releases": [{"version": r["version"], "date": r["date"],
                                        "entries": [dict(e, **assess(e, ignored, profile))
                                                    for e in r["entries"]]} for r in releases]},
                         indent=2))
        return 0
    print(f"# /eados upgrade — {repo}")
    print(f"# delta source: {origin}")
    print("")
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
