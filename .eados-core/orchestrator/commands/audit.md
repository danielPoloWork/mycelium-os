# `/eados audit` — risk-score, traceability-lint, and the security gate

Continuous audit. Scores a change's risk, verifies the traceability graph is whole, and — above
the (per-domain) threshold — requires the `security-auditor` gate, emitting a **risk register**.
Owned by the **security-auditor** (with the **reviewer** for structured findings). Config:
[`../os/risk/risk.yaml`](../os/risk/risk.yaml); the graph: [`traceability.py`](../../tools/traceability.py).

## Preconditions

- The `scaffold` phase passed `consistency-lint` + `self-review` (so `scaffold → audit` is legal —
  this transition is automatic, not human-gated).

## Procedure

1. **Traceability-lint** — the graph must have **no dangling edge**:
   ```bash
   python .eados-core/tools/traceability.py ROADMAP.md $(refs.rfcs) --links links.yaml
   ```
   (`links.yaml` = the PR cross-link edges the `git` spec mandates: `{pr, rfc, milestone, commit,
   release}`.) An RFC with no PR, a PR missing its RFC/milestone, or a release with no PR+commit
   fails the audit. **Derive `links.yaml` from the merged PRs** instead of hand-writing it:
   `python .eados-core/tools/derive_links.py --out links.yaml` (via `gh`; roadmap 6.6).
2. **Risk score** — score the change and learn whether the security gate is mandatory:
   ```bash
   python .eados-core/tools/risk_score.py $(changed paths) --lines N --domain <domain>
   ```
3. **Security gate (conditional)** — when the score says **REQUIRED**, the `security-auditor` runs
   the deep audit (trust boundaries, code-level risk, dependency/supply-chain, secret hygiene, the
   `SECURITY.md` policy — per the role; the trust-boundary work is the **threat-modeling sub-mode**
   below) and the `reviewer` returns **structured findings** the owner resolves.
4. **Emit the risk register** — record the outcome: the risk **score**, the **traceability** status,
   and each finding with `severity` (low/medium/high/critical), affected component, realistic
   impact, and a concrete mitigation. A confirmed defect → the bug ledger; a vulnerability → a
   **draft** advisory (the human publishes).
5. **Record & hand off** — note the audit in `delivery_state` **and append the phase-tagged run
   record** (the learning loop's uniform shape; an audit incident records with `--failure` — the
   riskiest surface feeding regression detection, #250):
   ```bash
   python .eados-core/tools/record_run.py <manifest> --phase audit   # add --failure GATE=MSG per finding
   ```
   If a migration is needed, propose the human-gated `audit → migrate`:
   ```bash
   python .eados-core/tools/phase_runner.py <manifest> --propose migrate
   ```
   Otherwise the audit is the standing gate before a release.

## Threat-modeling sub-mode — `/eados security` (#241, ADR-0019 §2)

The maintainer's `security` wishlist verb is a **sub-mode of `audit`** — no new phase, no new
state, no new authority; the alias adapter (`/eados:security`) and the `commands/README.md` alias
table route here. Invoked directly (or whenever step 3's deep audit runs), the `security-auditor`:

   > **Who writes this:** the phase's **`state_writer`** (`enterprise-architect`), not the
   > acting role. `authority.yaml` grants `orchestrator/project.yaml` and `.eados-core/**`
   > to the architect alone, so the acting role doing it is an authority violation this
   > project's own gate catches (#346, ADR-0025). Hand off, or act as the state writer for
   > this step — `/eados status` names both roles.
1. **Maps the trust boundaries** — every edge an attacker could stand on either side of, the
   untrusted inputs crossing it, and the design's assumptions about it.
2. **Runs the STRIDE pass** — Spoofing / Tampering / Repudiation / Information disclosure /
   Denial of service / Elevation of privilege, per boundary, into the project's
   **`docs/security/threat-model.md`** (scaffolded for every generated repo; the artifact, method,
   and owner are data in [`../os/risk/risk.yaml`](../os/risk/risk.yaml) `threat_model:`). Every
   cell gets an entry — a threat, a mitigation, or an explicit `n/a (reason)`; never a blank.
3. **Feeds the register** — a threat that survives analysis lands in the step-4 risk register with
   severity / component / impact / mitigation; a confirmed defect → the bug ledger; a
   vulnerability → a **draft** advisory (the human publishes).

The `risk-register-present` gate stays `wired: external` (a human-verified artifact): partially
mechanizing it — assert the register exists and covers the declared attack surface — was
considered here and **deferred to the #250 enforcement-hardening residuals**, where the
`gate_results` machinery it would plug into lives.

## Boundary

The audit is **assessment and remediation only** — it never weaponizes a finding, never disables a
control to "unblock", and never publishes an advisory (the human does). The agent runs the checks,
**drafts** the register, and **proposes** the transition; the human confirms (`AGENTS.md` §6).

**Calibrate the register** (`AGENTS.md` §10): each severity and score is a confidence call earned by
evidence — cite the file, command, or test; an unearned `certain` is a policy violation, not a style
choice. A finding the owner disputes is held per the pushback protocol: re-verify the evidence,
concede explicitly when it no longer holds — no hedging.
