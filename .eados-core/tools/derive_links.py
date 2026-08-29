#!/usr/bin/env python3
"""EADOS traceability-link derivation (roadmap 6.6 / F2) — build the Git-side cross-link edges from
merged PRs via `gh`, instead of a hand-maintained `links.yaml`.

The `git` spec mandates each delivery PR cross-link its `rfc` + `milestone` (AGENTS.md §6); the
`traceability-lint` gate ([`traceability.py`](traceability.py) `--links`) consumes those
`{pr, rfc, milestone, commit, release}` edges. This derives them from real PR data:

  - **pr / commit / milestone** come from `gh` PR metadata (number, `mergeCommit.oid`, `milestone`);
  - **rfc** is parsed from the PR body/title (`RFC-NNNN`, the required cross-link);
  - **release** is the `vX.Y.Z` in a release PR's title, when present.

By default it emits an edge only for **delivery PRs** (those carrying an rfc *or* a milestone), so a
milestoned PR missing its RFC still surfaces (the gate flags `pr-no-rfc`) while chore/docs PRs don't
flood the graph; `--all` emits every PR. Output is `links.yaml`-shaped, fed straight to
`traceability.py --links`.

**`gh` is not a hard dependency:** the parser (`parse_links`) is pure and tested without it; only the
optional fetch shells out, and it degrades cleanly (clear message, exit 2) when `gh` is absent,
unauthenticated, or offline — so CI never depends on the network.

    python .eados-core/tools/derive_links.py [--limit N] [--repo R] [--all] [--out FILE]
    python .eados-core/tools/derive_links.py --out links.yaml && \
      python .eados-core/tools/traceability.py ROADMAP.md $(rfc ids) --links links.yaml
"""

import os
import re
import subprocess
import sys

# Subprocess budgets (#321). `subprocess.run` without one waits FOREVER: a `gh` call that
# stalls on a TLS handshake, a rate-limit backoff, or an auth prompt with no stdin does not
# fail — it blocks until the CI job times out, and then reports as a generic job timeout
# rather than as "the network call hung". A timeout turns an unattributable stall into a
# clean, named degradation on the path this tool already has for `gh` being unavailable.
GH_TIMEOUT = 30    # network-bound

_RFC_RE = re.compile(r"\bRFC-\d{3,}\b")
_VER_RE = re.compile(r"\bv\d+\.\d+\.\d+\b")
_MS_RE = re.compile(r"\bM\d+\b")

# The gh fields the parser needs (gh pr list --json <these>).
GH_FIELDS = "number,title,body,mergeCommit,milestone"


def _first(regex, *texts):
    for text in texts:
        if text:
            match = regex.search(text)
            if match:
                return match.group(0)
    return None


def parse_links(records, include_all=False):
    """Turn `gh` PR records (dicts with number/title/body/mergeCommit/milestone) into traceability
    edges. Emits an edge for a delivery PR — one carrying an `rfc` or a `milestone` — unless
    `include_all`. `rfc`/`milestone` are kept even when absent (so the gate can flag the gap);
    `commit` likewise; `release` is included only when found."""
    links = []
    for rec in records or []:
        if not isinstance(rec, dict):
            continue
        body, title = rec.get("body") or "", rec.get("title") or ""
        ms = rec.get("milestone")
        milestone = None
        if isinstance(ms, dict):
            milestone = ms.get("title") or ms.get("number")
        if milestone is None:
            milestone = _first(_MS_RE, body)
        merge = rec.get("mergeCommit")
        commit = merge.get("oid") if isinstance(merge, dict) else None
        rfc = _first(_RFC_RE, body, title)
        if not include_all and not rfc and not milestone:
            continue   # not a delivery PR — out of the traceability lineage
        link = {"pr": rec.get("number"), "rfc": rfc, "milestone": milestone, "commit": commit}
        release = _first(_VER_RE, title)
        if release:
            link["release"] = release
        links.append(link)
    return links


def _yaml_scalar(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def emit_links_yaml(links):
    """Render edges as block-style YAML the hand-rolled loader (and `traceability.py --links`) reads."""
    out = ["# Auto-derived by tools/derive_links.py from merged PRs — do not hand-edit.", "links:"]
    if not links:
        out[1] = "links: []"
        return "\n".join(out) + "\n"
    for link in links:
        out.append(f"  - pr: {_yaml_scalar(link.get('pr'))}")
        for key in ("rfc", "milestone", "commit"):
            out.append(f"    {key}: {_yaml_scalar(link.get(key))}")
        if "release" in link:
            out.append(f"    release: {_yaml_scalar(link['release'])}")
    return "\n".join(out) + "\n"


def fetch_records(limit=100, repo=None):
    """Fetch merged-PR records via `gh`. Raises RuntimeError (not a crash) when gh is missing,
    unauthenticated, or offline — the caller degrades cleanly."""
    import json
    cmd = ["gh", "pr", "list", "--state", "merged", "--limit", str(limit), "--json", GH_FIELDS]
    if repo:
        cmd += ["--repo", repo]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              timeout=GH_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"`gh` timed out after {GH_TIMEOUT}s — the network stalled, the API is "
                           "rate-limiting, or it is waiting on an auth prompt that will never be "
                           "answered")
    except (FileNotFoundError, OSError) as exc:
        raise RuntimeError(f"could not run `gh` (is the GitHub CLI installed and on PATH?): {exc}")
    if proc.returncode != 0:
        raise RuntimeError(f"`gh pr list` failed (authenticated? online?): "
                           f"{(proc.stderr or proc.stdout or '').strip()}")
    try:
        return json.loads(proc.stdout or "[]")
    except ValueError as exc:
        raise RuntimeError(f"could not parse `gh` JSON output: {exc}")


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    import argparse
    ap = argparse.ArgumentParser(description="Derive traceability links from merged PRs via gh.")
    ap.add_argument("--limit", type=int, default=100, help="max merged PRs to scan (default 100)")
    ap.add_argument("--repo", help="OWNER/REPO (default: the current repo gh infers)")
    ap.add_argument("--all", action="store_true",
                    help="emit every PR, not just delivery PRs (those with an rfc or milestone)")
    ap.add_argument("--out", help="write the links YAML here (default: stdout)")
    args = ap.parse_args(argv)
    try:
        records = fetch_records(limit=args.limit, repo=args.repo)
    except RuntimeError as exc:
        print(f"derive-links: SKIP — {exc}", file=sys.stderr)
        return 2
    text = emit_links_yaml(parse_links(records, include_all=args.all))
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        print(f"derive-links: wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
