#!/usr/bin/env python3
"""EADOS risk score — the audit phase's deterministic risk model (roadmap 4.1 / 4.4 / 6.2).

A change's risk is a function of its **security surface** (sensitive paths touched), its **size**
(lines changed), and its **blast radius** (distinct areas). At/above the (per-domain) mandatory-gate
level, the `security-auditor` gate is REQUIRED. Everything is data
(`orchestrator/os/risk/risk.yaml`) — the factor **weights**, the blast-radius threshold, and the
points->level cutoffs included (roadmap 6.2 / F3) — and every knob is per-domain overridable, exactly
as `mandatory_gate_level` already was (OQ2). No model in the loop — same inputs, same score.
Dependency-free (stdlib + the sibling renderer's YAML loader).

    python .eados-core/tools/risk_score.py <path> [<path> ...] [--lines N] [--domain D]
    git diff --cached --name-only | xargs python .eados-core/tools/risk_score.py --lines 250
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # .eados-core/
sys.path.insert(0, HERE)
import render  # noqa: E402  — the hand-rolled, dependency-free YAML loader

RISK_SPEC = os.path.join(ROOT, "orchestrator", "os", "risk", "risk.yaml")

# Fallbacks when a key is absent from risk.yaml — back-compat with a pre-6.2 spec.
DEFAULT_LEVELS = ["low", "medium", "high", "critical"]
DEFAULT_WEIGHTS = {"security_surface": 3, "large_change": 2, "medium_change": 1,
                   "wide_blast_radius": 1}
DEFAULT_BLAST_THRESHOLD = 3
DEFAULT_SCORE_THRESHOLDS = [0, 2, 4]   # cumulative points -> level: <=0 low, <=2 medium, <=4 high


def load_risk(path=RISK_SPEC):
    with open(path, encoding="utf-8") as handle:
        return render.load_yaml(handle.read())


def _glob_re(glob):
    """`**` matches across directories; `*` within a segment; everything else literal."""
    out, i = [], 0
    while i < len(glob):
        if glob[i:i + 2] == "**":
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def _matches_any(path, globs):
    return any(_glob_re(g).match(path) for g in globs or [])


def resolve(cfg, domain=None):
    """The effective risk config for `domain`: base values with `domain_overrides[domain]` applied.
    `weights` are shallow-merged (a domain may tune one factor); the other tunables are replaced when
    present. Absent keys fall back to the module defaults, so a pre-6.2 risk.yaml still scores."""
    cfg = cfg or {}
    override = (cfg.get("domain_overrides") or {}).get(domain or "", {})
    override = override if isinstance(override, dict) else {}

    def pick(key, default):
        return override[key] if key in override else cfg.get(key, default)

    weights = dict(DEFAULT_WEIGHTS)
    weights.update(cfg.get("weights") or {})
    weights.update(override.get("weights") or {})
    return {
        "levels": pick("levels", DEFAULT_LEVELS),
        "security_globs": pick("security_globs", []),
        "size_buckets": pick("size_buckets", {}),
        "weights": weights,
        "blast_radius_threshold": int(pick("blast_radius_threshold", DEFAULT_BLAST_THRESHOLD)),
        "score_thresholds": pick("score_thresholds", DEFAULT_SCORE_THRESHOLDS),
        "mandatory_gate_level": pick("mandatory_gate_level", "high"),
    }


def _level_for_points(points, thresholds, levels):
    """The first level whose inclusive max-points cutoff is >= `points`; the last level if none match.
    `thresholds` carries len(levels)-1 cutoffs (the top level is the catch-all)."""
    for idx, cutoff in enumerate(thresholds or []):
        if points <= int(cutoff):
            return levels[min(idx, len(levels) - 1)]
    return levels[-1]


def score(paths, lines, cfg, domain=None):
    """Return (level, factors) for a change touching `paths` with `lines` changed, under `domain`'s
    effective weights and thresholds."""
    eff = resolve(cfg, domain)
    levels = eff["levels"] or DEFAULT_LEVELS
    weights = eff["weights"]
    buckets = eff["size_buckets"] or {}
    paths = [p.replace("\\", "/") for p in paths]
    points, factors = 0, []

    if any(_matches_any(p, eff["security_globs"]) for p in paths):
        points += int(weights.get("security_surface", 0))
        factors.append("security-surface")

    big, med = int(buckets.get("L", 400)), int(buckets.get("M", 100))
    if lines >= big:
        points += int(weights.get("large_change", 0))
        factors.append("large-change")
    elif lines >= med:
        points += int(weights.get("medium_change", 0))
        factors.append("medium-change")

    areas = {p.split("/", 1)[0] for p in paths if p}
    if len(areas) >= eff["blast_radius_threshold"]:
        points += int(weights.get("wide_blast_radius", 0))
        factors.append("wide-blast-radius")

    return _level_for_points(points, eff["score_thresholds"], levels), factors


def requires_security_gate(level, cfg, domain=None):
    """True when `level` is at/above the effective mandatory-gate level for `domain` (the domain
    override if present, else the default). Fail-safe: if either `level` or the configured
    `mandatory_gate_level` is not in `levels` (a hand-edited risk.yaml), require the gate rather
    than crashing on `list.index`."""
    eff = resolve(cfg, domain)
    levels = eff["levels"] or DEFAULT_LEVELS
    gate = eff["mandatory_gate_level"]
    if level not in levels or gate not in levels:
        return True
    return levels.index(level) >= levels.index(gate)


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    import argparse
    ap = argparse.ArgumentParser(description="EADOS risk score for a change.")
    ap.add_argument("paths", nargs="+", help="the paths the change touches")
    ap.add_argument("--lines", type=int, default=0, help="lines changed (default 0)")
    ap.add_argument("--domain", default=None,
                    help="the project domain (per-domain weights + gate threshold)")
    args = ap.parse_args(argv)
    cfg = load_risk()
    level, factors = score(args.paths, args.lines, cfg, args.domain)
    gate = requires_security_gate(level, cfg, args.domain)
    print(f"risk: {level}  (factors: {', '.join(factors) or 'none'})")
    dom = f" [domain={args.domain}]" if args.domain else ""
    print(f"security-auditor gate: {'REQUIRED' if gate else 'optional'}{dom}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
