# `/eados init` — initialize a governed project

The **entry command** of the pipeline. It frames the project and writes the initial manifest so
every later phase has state to read. Owned by the **enterprise-architect** role. `init` frames a
**new** project — for a repository that already has code and history, its brownfield sibling
[`/eados adopt`](adopt.md) (#247, ADR-0021) is the front door: gap map → goal menu → a legal
route into `design`/`audit`/`migrate`.

## Housekeeping (first run)

If the repo was set up via the **guided installer** ([`setup/`](../../../setup/setup.sh)), its
downloaded scripts are just the bootstrap and are no longer needed once `.eados-core/` is in place.
Tidy them — this removes **only** the known installer artifacts (`setup.sh` / `setup.ps1` /
`setup.bat` / `setup.command`, and a `setup/` dir only when it holds nothing but those); it never
touches `.eados-core/`, the agent contract, or your own files:

```bash
python .eados-core/tools/cleanup_installer.py .          # dry-run: list what would be removed
python .eados-core/tools/cleanup_installer.py . --apply  # remove them
```

## Procedure

1. **Preflight** — verify the toolchain the pipeline assumes is present before anything else:
   ```bash
   python .eados-core/tools/preflight.py        # add --no-gh for the pure, no-GitHub render path
   ```
   It checks the Python version, `git`, `gh`, and `gh auth status`, printing an OS-specific
   install/auth hint for anything missing and exiting non-zero — so a missing or unauthenticated
   tool surfaces here, not mid-run. (Python-missing-entirely is out of scope for a Python tool; the
   guided installer under [`setup/`](../../../setup/setup.sh) carries that non-Python bootstrap hint.)
   On a non-zero result, resolve what it flags, then continue.
2. **Frame** — run interview [Phase 0](../interview.md) (Q0.1–Q0.5), **including
   `Q0.4 — development target`** (`software` / `web` / `game` / `mobile`), which loads the
   matching [`domains/<domain>.yaml`](../domains/_schema.md), and `Q0.5 — enterprise posture`
   (`standard` default / `enterprise`) — orthogonal to the target, not a fifth domain.
3. **Write the manifest skeleton** — copy [`project.yaml.template`](../project.yaml.template) to
   `orchestrator/project.yaml` and fill the framing facts: `identity`, the top-level `domain`, the
   `schema_version`, and a `delivery_state` block with `phase: init` (empty `checkpoints` /
   `refs`). Leave the deeper sections (language, toolchain, spec, …) for their phases.
4. **Confirm** — present the skeleton to the maintainer (the cheap checkpoint; `AGENTS.md` §5).
   **Echo every assumed default explicitly.** An answer taken from the questionnaire default
   (provenance `defaulted`, glossed *assumed*, #169) is the manifest analogue of a `guessing`
   confidence tag: flagged and echoed back at confirmation, never blended into verified fact.
   Interview provenance and chat calibration share one vocabulary — the Interaction Contract
   (`AGENTS.md` §10).
5. **Report the next move** — run the deterministic phase runner:
   ```bash
   python .eados-core/tools/phase_runner.py orchestrator/project.yaml
   ```
   At `phase: init` it reports `-> design` (gate `manifest-valid`, **human-gated**) — the
   greenfield default — plus the two adoption edges (`-> audit`, `-> migrate`), which stay
   NOT READY for an ordinary project (their `adoption-recorded` gate reads `skipped` without the
   `adoption:` block only [`/eados adopt`](adopt.md) writes). Surface the preflight verdict from
   step 1 in the hand-off so the maintainer sees the environment is ready (or what to fix)
   alongside the next move.
6. **Hand off** — the maintainer chooses the next phase:
   - the **delivery pipeline** → `/eados design` (authoring RFCs; lands in M2); or
   - the **classic one-shot path** → finish the full interview (Phases 1–5) and `/eados scaffold`
     ([`generate.md`](../generate.md)) to render the repository as today.

## Boundary

The agent **drafts** the manifest and **proposes** the transition the phase runner reports; the
**human confirms** every human-gated move and owns the irreversible steps. `init` never renders
or commits anything on its own.

**Calibrate the hand-off** (`AGENTS.md` §10): surface the preflight/readiness verdict tagged by
evidence (`certain`/`likely`/`guessing`), and when you would steer the maintainer away from the
path they named, lead with the dissent template — position / alternative / risk.

## Command surface — generate the tree for the host in use (#375)

`/eados <cmd>` is a native slash command only where the host has one. Once the manifest exists,
offer to generate that host's tree:

```bash
python .eados-core/tools/adapter_render.py --list            # what each declared host supports
python .eados-core/tools/adapter_render.py --host <id>       # generate this repo's tree
```

**Resolve the host explicitly, and say which one you used** — manifest `routing.host` → the
catalog's `detect[]` markers → **ask the maintainer**. Never default: a silent default is how every
non-Claude host quietly received Anthropic model names before #325, and the same mistake here writes
a tree the maintainer's actual host will never read.

Three outcomes, all of them stated rather than implied:

- **`scope: project`** — written into the repo; invoke with the host's own notation.
- **`scope: home`** (Codex) — rendered *inside* the project with the one command to install it.
  EADOS never writes outside the target.
- **`scope: none`** — no verified mechanism. Say so: the surface is `AGENTS.md` §13 plus
  `eados.py commands`, which works on every host including those with no command mechanism at all.

Whether the generated tree is *committed* is the maintainer's call (see #372) — `adapter_render.py`
is additive and never clobbers an existing adapter without `--force`.

## Backward compatibility

`init` is additive. A maintainer who ignores the pipeline and runs the classic interview →
`render.py` flow is unaffected: `delivery_state` is optional and the renderer ignores it.
