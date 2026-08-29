# `risk.yaml` — schema

The **risk model** as data (roadmap 4.1 / 4.4 / 6.2; RFC-0001 §7). A change's risk is a function of
its **security surface** (which sensitive paths it touches), its **size**, and its **blast radius**
(how many areas it spans). At or above the **mandatory-gate level** the `security-auditor` gate is
required. Every knob — the factor **weights**, the blast-radius threshold, the points→level cutoffs,
and the gate level — is data, and each may be tuned **per domain** (OQ2 + roadmap 6.2 / F3). The
scorer is [`../../../tools/risk_score.py`](../../../tools/risk_score.py); it generalizes the
`reviewer` + `security-auditor` roles into a standing audit.

`eados_lint` (`os-spec-completeness`) requires the instance to define every top-level key below.

## Required structure

```yaml
version:                # integer schema version
security_globs:         # path globs whose change raises the security-surface factor
size_buckets:           # lines-changed thresholds, { M: <int>, L: <int> }
levels:                 # ordered risk levels, lowest -> highest
weights:                # points per factor: { security_surface, large_change, medium_change, wide_blast_radius }
blast_radius_threshold: # distinct top-level areas at/above which the wide-blast-radius factor applies
score_thresholds:       # cumulative-points cutoffs mapping points -> levels (len == len(levels) - 1)
mandatory_gate_level:   # at/above this level the security-auditor gate is REQUIRED (default)
domain_overrides:       # per-domain overrides of any key above (weights shallow-merged) + mandatory_gate_level
threat_model:           # the audit threat-modeling sub-mode (#241): { artifact, method, owner_role }
```

## Item shapes & scoring

The scorer sums the **`weights`** of the factors that apply, then maps the total to a `levels` entry
via **`score_thresholds`**:

- **security surface** (`weights.security_surface`) — any changed path matches a `security_globs`
  entry (e.g. `.github/**` = CI/supply-chain, `tools/**` = the renderer/write-guards per ADR-0007,
  `**/auth/**`, secrets).
- **size** — `weights.large_change` when lines changed ≥ `size_buckets.L`, else
  `weights.medium_change` when ≥ `size_buckets.M`.
- **blast radius** (`weights.wide_blast_radius`) — the change spans ≥ `blast_radius_threshold`
  distinct top-level areas.

**Points → level:** `score_thresholds` lists the inclusive max points for each level except the last
(a catch-all), in `levels` order. With `levels: [low, medium, high, critical]` and
`score_thresholds: [0, 2, 4]`: `0` → low · `1–2` → medium · `3–4` → high · `5+` → critical.

`requires_security_gate` is true when the level ≥ the effective `mandatory_gate_level`.

## Per-domain overrides

`domain_overrides[<domain>]` may set any of the keys above. `weights` is **shallow-merged** onto the
base (a domain can tune a single factor); the other tunables (`score_thresholds`,
`blast_radius_threshold`, `size_buckets`, `mandatory_gate_level`, `levels`, `security_globs`) are
**replaced** when present. A domain that omits a key inherits the base value.

## Threat-modeling sub-mode (#241)

**`threat_model`** — `{ artifact, method, owner_role }`: the generated-repo path of the
threat-model artifact (`docs/security/threat-model.md`, scaffolded by the templates), the analysis
method (`STRIDE`), and the owning role (`security-auditor`, a declared `authority.yaml` role that
also holds the `docs/security/**` ownership-map entry). The audit sub-mode (`/eados security` →
`commands/audit.md`) reads this block; the scorer ignores it (deterministic scoring unchanged).

## Invariants

- `mandatory_gate_level` and every `domain_overrides[*].mandatory_gate_level` is a value in `levels`.
- `score_thresholds` has exactly `len(levels) - 1` entries (the top level is the catch-all).
- Factor weights are integers; absent knobs fall back to the scorer's built-in defaults (back-compat).
- The scorer is **deterministic** — same inputs, same score (no model/LLM in the loop).
