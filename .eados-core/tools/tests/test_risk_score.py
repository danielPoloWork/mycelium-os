#!/usr/bin/env python3
"""Tests for risk_score — the deterministic risk model: security surface, size, blast radius, the
per-domain mandatory-gate threshold (OQ2), and data-driven, per-domain-tunable weights (6.2 / F3).
Dependency-free.

    python .eados-core/tools/tests/test_risk_score.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import risk_score as rs  # noqa: E402  (the module under test)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    cfg = rs.load_risk()

    # --- level by factor (shipped risk.yaml) ---
    lvl, _ = rs.score(["docs/journal/2026-06.md"], 10, cfg)
    check("a small docs change is low", lvl == "low", failures)

    lvl, fac = rs.score([".github/workflows/ci.yml"], 20, cfg)
    check("a CI change is high (security surface)", lvl == "high", failures)
    check("security-surface factor is reported", "security-surface" in fac, failures)

    lvl, _ = rs.score(["tools/render.py"], 500, cfg)
    check("a large tools change is critical", lvl == "critical", failures)

    lvl, _ = rs.score(["src/a.py", "lib/b.py", "app/c.py"], 50, cfg)
    check("a wide non-security change is medium", lvl == "medium", failures)

    # --- glob matcher: security globs ---
    check("**/auth/** matches nested auth code",
          rs._matches_any("src/main/auth/login.py", cfg["security_globs"]), failures)
    check("a plain source file is not security surface",
          not rs._matches_any("src/main/util.py", cfg["security_globs"]), failures)

    # --- mandatory gate: default vs per-domain (OQ2) ---
    check("high requires the gate by default",
          rs.requires_security_gate("high", cfg, None), failures)
    check("medium does not require the gate by default",
          not rs.requires_security_gate("medium", cfg, None), failures)
    check("medium DOES require the gate for the mobile domain",
          rs.requires_security_gate("medium", cfg, "mobile"), failures)
    check("low never requires the gate",
          not rs.requires_security_gate("low", cfg, "mobile"), failures)

    # --- weights are data, tunable per domain (6.2 / F3) ---
    synthetic = {
        "levels": ["low", "medium", "high", "critical"],
        "security_globs": [".github/**"],
        "size_buckets": {"M": 100, "L": 400},
        "weights": {"security_surface": 3, "large_change": 2, "medium_change": 1,
                    "wide_blast_radius": 1},
        "blast_radius_threshold": 3,
        "score_thresholds": [0, 2, 4],
        "mandatory_gate_level": "high",
        "domain_overrides": {
            "lenient": {"weights": {"security_surface": 1}},   # tune ONE factor down
            "strict": {"score_thresholds": [0, 0, 1]},         # escalate faster
            "spread": {"blast_radius_threshold": 2},           # 2 areas already count as wide
        },
    }
    base_lvl, _ = rs.score([".github/workflows/ci.yml"], 20, synthetic)
    check("base: a CI change scores high (security_surface=3 -> 3 pts)", base_lvl == "high", failures)

    lenient_lvl, _ = rs.score([".github/workflows/ci.yml"], 20, synthetic, "lenient")
    check("a domain can lower a weight (security_surface=1 -> 1 pt -> medium)",
          lenient_lvl == "medium", failures)

    eff = rs.resolve(synthetic, "lenient")
    check("a domain weight override is shallow-merged onto the base",
          eff["weights"] == {"security_surface": 1, "large_change": 2, "medium_change": 1,
                             "wide_blast_radius": 1}, failures)

    strict_lvl, _ = rs.score([".github/workflows/ci.yml"], 20, synthetic, "strict")
    check("a domain can escalate via score_thresholds (3 pts -> critical)",
          strict_lvl == "critical", failures)

    spread_lvl, fac2 = rs.score(["src/a.py", "lib/b.py"], 10, synthetic, "spread")
    check("a domain can lower blast_radius_threshold (2 areas -> wide-blast-radius)",
          "wide-blast-radius" in fac2, failures)
    base_spread, base_fac = rs.score(["src/a.py", "lib/b.py"], 10, synthetic)
    check("at the base threshold (3) two areas are NOT wide blast radius",
          "wide-blast-radius" not in base_fac, failures)

    # --- _level_for_points maps cumulative points -> level via the cutoffs ---
    lv = ["low", "medium", "high", "critical"]
    check("0 pts -> low", rs._level_for_points(0, [0, 2, 4], lv) == "low", failures)
    check("2 pts -> medium", rs._level_for_points(2, [0, 2, 4], lv) == "medium", failures)
    check("4 pts -> high", rs._level_for_points(4, [0, 2, 4], lv) == "high", failures)
    check("5 pts -> critical (catch-all)", rs._level_for_points(5, [0, 2, 4], lv) == "critical",
          failures)

    # --- back-compat: a config with NO weights/thresholds block falls back to the defaults ---
    legacy = {"levels": ["low", "medium", "high", "critical"], "security_globs": [".github/**"],
              "size_buckets": {"M": 100, "L": 400}, "mandatory_gate_level": "high"}
    legacy_lvl, _ = rs.score([".github/workflows/ci.yml"], 20, legacy)
    check("a legacy config (no weights) still scores via DEFAULT_WEIGHTS (-> high)",
          legacy_lvl == "high", failures)

    # --- fail-safe: a mandatory_gate_level not in levels requires the gate instead of crashing ---
    misconfig = {"levels": ["low", "medium", "high", "critical"], "security_globs": [],
                 "size_buckets": {"M": 100, "L": 400}, "mandatory_gate_level": "extreme"}
    try:
        gated, crashed = rs.requires_security_gate("low", misconfig), False
    except ValueError:
        gated, crashed = None, True
    check("a mandatory_gate_level outside levels does not crash", not crashed, failures)
    check("…and fails safe to requiring the gate", gated is True, failures)

    if failures:
        print("test-risk-score: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-risk-score: OK -- surface, size, blast radius, per-domain gate, and data-driven "
          "per-domain weights all hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
