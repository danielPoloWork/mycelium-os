# `/eados migrate` — bring an existing repo up to the standard

The `migrate` (brownfield) phase migrates an **existing** repository toward the EADOS standard via
**incremental, gated, sandboxed** PRs. It is the only phase that edits real user code, so it is
sequenced **last** and every write is write-contained. Owned by the **enterprise-architect**.

> **Naming (ADR-0020, #236).** This phase was called `refactor` through v2.7.0; it was renamed
> `migrate` to free `refactor` for the code-quality command (#243) and to name honestly what it
> does (bring a repo up to the standard, not restructure code). A manifest that still records
> `delivery_state.phase: refactor` is accepted as a deprecated alias for one minor version.

> **Safety first.** Every write goes through [`tools/sandbox.py`](../../tools/sandbox.py)
> `safe_write` (no escape, no `.git`, additive by default), each step is **one reviewable, gated
> PR** the human merges, and the agent never clobbers user code.

## Preconditions

- A target repository to migrate, and the `audit` phase's risk register
  (`audit → migrate` is human-gated on `risk-register-present`).

## Procedure

1. **Read (read-only)** — map the repo against the standard:
   ```bash
   python .eados-core/tools/brownfield.py <repo>
   ```
2. **Plan (read-only)** — order the gaps into incremental steps, one logical change each:
   ```bash
   python .eados-core/tools/migration_planner.py <repo>
   ```
3. **Migrate — one step = one PR**, in plan order (lowest-risk first). For each step:
   1. **authority** — `authority_check.py enterprise-architect <paths>` (the role may write them).
   2. **render + place** the missing artifact in one step — `render_artifact.py` renders the template
      with the manifest (the same gates as a full render) and writes it through the **sandbox**
      (contained, not `.git`, **additive** — a pre-existing file is a conflict the human resolves,
      not a clobber). Never hand-write what a template produces:
      ```bash
      python .eados-core/tools/render_artifact.py AGENTS.md.tmpl <manifest> <repo>
      ```
   3. **risk** — `risk_score.py <paths> --domain <domain>`; if **REQUIRED**, run
      [`/eados audit`](audit.md) (the `security-auditor` gate) before proposing.
   4. **draft the PR** — one logical change, with the `git` cross-links (RFC/milestone); the human
      reviews and merges.
   5. **confirm** — re-run `brownfield.py <repo>`: the step's gap is closed. Proceed to the next.
4. **Record the run** — append the phase-tagged run record after each migration step (the
   learning loop's uniform shape; a migrate incident on real user code records with `--failure`,
   #250):
   ```bash
   python .eados-core/tools/record_run.py <manifest> --phase migrate   # add --failure GATE=MSG on an incident
   ```
5. **Done** — when `brownfield.py` reports no gaps, the repo meets the EADOS standard. `migrate`
   is the terminal phase; from here the repo governs itself under its rendered `AGENTS.md`.

## Boundary

The agent **reads**, **plans**, **renders**, **writes inside the sandbox**, and **drafts** each PR;
the human **merges** every step and resolves any conflict. No write escapes the target repo, touches
`.git`, or overwrites user code; no migration runs unattended (`AGENTS.md` §6). Assessment and
additive migration only — never a destructive rewrite.
