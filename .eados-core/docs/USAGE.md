# Using EADOS — capabilities, how it works, what is fixed, what you customize

A practical map of the Enterprise Agentic Delivery Operating System for anyone who just
downloaded it. For the install/quickstart see the [getting-started README](../README.md); the
binding rules live in [`AGENTS.md`](../../AGENTS.md). This page is the orientation in between.

---

## 1. What you can do

EADOS is a **factory**, not a product: it stamps out enterprise-grade repositories that all
share the same governance, quality gates, and AI-agent contract — in **any** language.

| Use | How |
|---|---|
| **Generate a new enterprise repo** (C++, Rust, Go, Java, Python, TypeScript, or any other language) | Conversationally via an AI agent (Claude / Gemini / Codex) that runs the interview, **or** deterministically: fill `project.yaml` and run [`render.py`](../tools/render.py) |
| **Work on the factory** (add a language, maintain templates) | The `profile-author` role + [`eados_lint.py`](../tools/eados_lint.py) + the render-smoke |

A generated repo ships, on day zero: the agent contract (AGENTS/CLAUDE/GEMINI), the
cross-language source tree `it.d4np.<project>`, the full docs system (ADR, patterns, spec, bug
ledger, journal, workflow, **releases**), the GitHub automation pack (CI + release + Dependabot
+ CODEOWNERS + issue forms + labels + a setup script), the quality gate
(`consistency_lint.py`), the SemVer/release flow, and — opt-in — **i18n**, **social
announcements**, and **benchmarks**.

**Composable agent roles** ([registry](../agent/README.md)): `enterprise-architect`,
`reviewer`, `security-auditor`, `release-manager`, `profile-author`.

**Self-improvement (safe, versioned, human-gated):** a [lessons ledger](../learning/README.md)
(memory), [`autotune.py`](../tools/autotune.py) (default tuning from run history),
[`self_review.py`](../tools/self_review.py) + [`eval/rubric.md`](../eval/rubric.md)
(self-evaluation), and the [stay-current routine](../maintenance/stay-current.md) (keeps
profiles modern). Every improvement is a draft PR a human approves — no opaque magic.

---

## 2. How it works

Three layers feed one renderer:

```
PROFILES (toolchain knowledge as data)  ┐
MANIFEST (your answers: project.yaml)   ┼──→ TEMPLATES ({{PLACEHOLDER}}) ──→ generated repo
PLACEHOLDER DICTIONARY (authoritative)  ┘
```

The architect runs a 5-step loop (plus memory): **Recall** (read lessons) → **Interview** →
**Resolve profile** → **Manifest** (you confirm) → **Render** → **Verify & hand off** →
**Record** (write lessons). Rendering is a Mustache subset; an unresolved placeholder is a hard
error. [`eados_lint.py`](../tools/eados_lint.py) and the render-smoke keep the factory itself
congruent in CI.

**The tools** (all standard-library Python, run from the repo root):

| Tool | Purpose |
|---|---|
| `python .eados-core/tools/render.py <manifest> --in-place \| --out <dir>` | Render a manifest into a repository (deterministic) |
| `python .eados-core/tools/eados_lint.py` | Self-lint: placeholder integrity, profile completeness, playbook references |
| `python .eados-core/tools/self_review.py <repo>` | Structural completeness review of a generated repo |
| `python .eados-core/tools/autotune.py` | Propose default changes from accumulated run records |
| `tools/consistency_lint.py` | Shipped *into* each generated repo; enforces its cross-artifact congruence |

---

## 3. Running it (two paths)

**Conversational** — open the repo with an AI agent; it reads `AGENTS.md`, runs
[`interview.md`](../orchestrator/interview.md), writes `project.yaml` for your confirmation, then
follows [`generate.md`](../orchestrator/generate.md). If a step fails, it follows
[`recovery.md`](../orchestrator/recovery.md). _Need an agent?_ Install Claude Code, Gemini
Antigravity, or ChatGPT Codex — the [README's *Prerequisites*](../../README.md) has the install
links — or take the **Deterministic** path below.

**Deterministic** — no agent needed. With this factory copied into your repo
(`<your-repo>/.eados-core/`), `--in-place` generates the project into that repo, next to
`.eados-core/` (which the rendered `.gitignore` excludes); use `--out <dir>` for a separate copy:

```bash
cp .eados-core/orchestrator/project.yaml.template .eados-core/orchestrator/project.yaml
# edit it — see .eados-core/orchestrator/examples/reference.yaml for a worked manifest
python .eados-core/tools/render.py .eados-core/orchestrator/project.yaml --in-place
python tools/consistency_lint.py
```

_On **Windows (PowerShell)**: replace `cp` with `Copy-Item .eados-core/orchestrator/project.yaml.template .eados-core/orchestrator/project.yaml`; the `python …` commands are identical (paths with `/` work in PowerShell)._

_New to the phases? Walk the whole pipeline once against a tiny worked example —
the [phase-by-phase walkthrough](walkthrough.md) runs every command (`init → audit`) and shows the
human gate at each step._

### The command surface on any host

`/eados <cmd>` is a native slash command **only where the host has one** — today that is Claude
Code. Under Codex, Gemini, OpenCode, or a model driven through a plain API, the host-independent
surface is the CLI, and it covers **every** command the
[registry](../orchestrator/commands/README.md) declares:

```bash
python .eados-core/tools/eados.py commands        # every verb, and how this CLI treats it
```

Three kinds of answer, and the readout says which one you got:

| | |
|---|---|
| the phases + `status` | runs that phase's deterministic gates |
| `adopt` · `review` · `upgrade` | delegates to the tool that does the work |
| `debug` · `refactor` · `optimize` · `testcases` | **agent-authored** — these produce code and tests, so the CLI prints the procedure, its summary and its class, and stops |

That last row is a boundary, not a shortfall: a CLI cannot write your fix. Naming the procedure
turns "find the right file inside a vendored bundle" into one command.

**Real autocomplete, no memorising.** The completion script is generated from the same registry —
never checked in, because a stale completion offers commands that no longer exist:

```bash
eval "$(python .eados-core/tools/eados.py completion bash)"     # or: zsh
```

```powershell
python .eados-core/tools/eados.py completion powershell | Out-String | Invoke-Expression
```

Each defines an `eados` shim as well, so it is `eados plan <manifest>` from then on.

---

## 4. What is FIXED — strict, do not change

These invariants are enforced by the lints and the agent contract; changing them breaks the
factory's guarantees.

| Invariant | Why it is load-bearing |
|---|---|
| **English on disk** (except derived i18n copies) | Cross-project consistency |
| **Agent-vs-human boundary** — the agent *drafts*; the human *opens / merges / publishes*. Never push to the default branch, never merge, never publish | Safety & auditability |
| **The placeholder dictionary is authoritative** — a template may only use defined placeholders | Enforced by `eados_lint` |
| **Profile completeness** — every `<lang>.yaml` defines every `_schema.md` key | Enforced by `eados_lint` |
| **Language knowledge is data, not code** — never hardcode a tool into a template | Genericity / open to any language |
| **Normative source tree** `src/{main,test,bench}/<lang>/<group>/<slug>/` | One shape across languages (ADR-0002) |
| **One source of truth per fact** (manifest → placeholders) | Anti-drift |
| **The generated repo governs itself** (no coupling back to EADOS) | Independence |
| **A rendered repo must pass `consistency_lint` + `self_review`** day zero | Quality floor |
| **Conventional Commits · one logical change per PR · one PR at a time** | Workflow |
| **`.eados-core/` tooling self-locates** (ROOT-relative) | Don't scatter the machinery |

---

## 5. What you CAN customize

| What | Where | Effect |
|---|---|---|
| **Org defaults** | [`config/defaults.yaml`](../config/defaults.yaml) | branch, license, group path, coverage, scopes, i18n — precedence: overlay > profile > built-in |
| **House rules** | [`config/house-rules.md`](../config/house-rules.md) | injected as §13 of every generated `AGENTS.md` (wins over a conflicting default) |
| **Custom agent roles** | [`config/agents/`](../config/README.md) | add or override a role |
| **A new language** | copy [`profiles/_template.yaml`](../orchestrator/profiles/_template.yaml) → `<lang>.yaml` + ADR | any language; never edit templates |
| **The interview** | [`questionnaire.yaml`](../orchestrator/questionnaire.yaml) + [`interview.md`](../orchestrator/interview.md) | questions / follow-ups |
| **Scaffolding content** | `templates/**` | as long as placeholders stay in the dictionary |
| **Per project** | `project.yaml` | every value + the capability flags (`bench, threading, public_api, i18n, packaging, service, announce`) |
| **Memory / tuning** | [`learning/lessons.yaml`](../learning/README.md), `autotune` threshold, `stay-current` cadence | how the agent learns and stays current |

**Golden rule:** if a change would make `eados_lint`/`consistency_lint` fail or violate the
agent-vs-human boundary → it is **fixed**. If it is a *value*, an *overlay*, a *profile*, or a
*capability* → it is **customizable**. Either way it stays versioned and reviewable.

---

## 6. Distribution bundle (ship just the factory)

The bundle is the factory you **operate** — `.eados-core/` + the agent contract + `LICENSE` —
without this repository's own CI, changelog, and governance files. It is the easiest way to hand
EADOS to someone who only needs to *use* it.

### Guided installer (one step) — recommended

A guided installer (published in each release as `setup.{sh,command,ps1,bat}`) downloads the bundle,
**verifies its SHA256** (fail-closed — it refuses to extract an unverified bundle unless
`--no-verify`), and extracts it **additively** (never overwriting an existing file — the
[ADR-0007](adr/0007-renderer-write-guards-and-validation-independence.md) no-clobber principle) into a
target repo. Run **bare** it is **interactive** (asks new-vs-existing repo, the path — for a new
repo, the name — and whether to also install the **`/eados` slash-command adapters** for Claude Code,
default yes; on a new repo it `git init`s and offers `gh repo create`); with flags it is fully
**scriptable** — the adapters are then **opt-in** via `--with-adapters` / `-WithAdapters`
(`--no-adapters` / `-NoAdapters` declines; see the
[host-adapters section](../orchestrator/commands/README.md) of the command surface, ADR-0019 class 4).

**Which file do I grab?** Each is at
`https://github.com/danielPoloWork/pgs-eados/releases/latest/download/<name>`:

| Platform | Download | Run it |
|---|---|---|
| **Linux / macOS** (terminal) | `setup.sh` | `sh setup.sh` |
| **macOS** (double-click) | `setup.command` **and** `setup.sh` (same folder) | open `setup.command` |
| **Windows** (terminal) | `setup.ps1` | `powershell -ExecutionPolicy Bypass -File setup.ps1` |
| **Windows** (double-click) | `setup.bat` **and** `setup.ps1` (same folder) | double-click `setup.bat` |

`setup.command` and `setup.bat` are thin double-click shims — each just launches the matching script,
so its sibling (`setup.sh` / `setup.ps1`) **must sit in the same folder**.

**Terminal — the reliable path** (works everywhere, no permission fuss):

```bash
# Linux / macOS
curl -fsSL https://github.com/danielPoloWork/pgs-eados/releases/latest/download/setup.sh -o setup.sh
sh setup.sh
```

```powershell
# Windows (PowerShell)
Invoke-WebRequest https://github.com/danielPoloWork/pgs-eados/releases/latest/download/setup.ps1 -OutFile setup.ps1
powershell -ExecutionPolicy Bypass -File setup.ps1
```

**Double-click — no terminal.** Download **both** files for your OS (table above) into one folder, then:

- **macOS** — the first time, **right-click `setup.command` → Open** (macOS *quarantines* a downloaded
  script, so a plain double-click is blocked by Gatekeeper; "Open" approves it once). If Finder still
  refuses, mark the scripts executable once: `chmod +x setup.command setup.sh`.
- **Windows** — double-click **`setup.bat`** (it runs `setup.ps1` with `-ExecutionPolicy Bypass`, so no
  policy change is needed). A bare `setup.ps1` would just open in an editor — use the `.bat`.

**Non-interactive / scripted** (CI, dotfiles) — pass flags instead of answering prompts:

```bash
sh setup.sh --mode existing --path . --non-interactive       # into the current repo
sh setup.sh --mode new --path ~/code --repo-name my-app      # new repo dir + git init
```

`setup.sh --help` (or `setup.ps1 -Help`) lists every flag: `--ref <tag>` pins a release, `--repo
OWNER/REPO` retargets the source, and `--from <file>` + `--sums-file <file>` do an **air-gapped**
install (verify a hand-downloaded bundle against a hand-downloaded `SHA256SUMS`). The default integrity
source is the release's `SHA256SUMS` asset; `releases/latest/download/setup.{sh,ps1}` are stable links.

### Or get the bundle manually — no clone required

The bundle is **prefix-less**: extract it **at the root of your project's repo** and its contents
(`.eados-core/` plus the agent contract and `LICENSE`) land directly there — *not* in a subfolder —
so you end up with `<your-repo>/.eados-core/`.

```bash
cd <your-repo>          # your project's repo root (new or existing)
curl -L -o /tmp/pgs-eados-bundle.tar.gz \
  https://github.com/danielPoloWork/pgs-eados/releases/latest/download/pgs-eados-bundle.tar.gz
tar xzf /tmp/pgs-eados-bundle.tar.gz    # extracts .eados-core/, AGENTS.md, … into the CWD
ls .eados-core                          # sanity: orchestrator/ templates/ tools/ …
# ZIP alternative: unzip the .zip asset at the repo root (its contents at the top level).
# GitHub CLI: gh release download --repo danielPoloWork/pgs-eados --pattern 'pgs-eados-bundle.*'
```

On **Windows (PowerShell)** — `tar` ships with Windows 10+:

```powershell
cd <your-repo>
Invoke-WebRequest -Uri https://github.com/danielPoloWork/pgs-eados/releases/latest/download/pgs-eados-bundle.tar.gz -OutFile $env:TEMP/pgs-eados-bundle.tar.gz
tar -xzf $env:TEMP/pgs-eados-bundle.tar.gz    # extracts .eados-core/, AGENTS.md, … into the CWD
```

Then read [`.eados-core/README.md`](../README.md) and run the factory: open the repo with an AI
agent (it auto-loads `AGENTS.md`), or render deterministically with `render.py --in-place` (§3).
`git clone` is the *other* path — the full repository, for **contributing to EADOS**.

### What's in it

The whole factory (`.eados-core/`, including its tools, templates, profiles, docs, and
[`.eados-core/README.md`](../README.md)), the agent contract (`AGENTS.md` / `CLAUDE.md` /
`GEMINI.md`), and `LICENSE`. **`LICENSE` is kept on purpose**: `render.py` reads it as the source
for each generated project's license, so removing it would yield license-less projects.

The `export-ignore` rules in `.gitattributes` strip two groups: **repo-management plumbing** (CI,
issue/PR templates, Dependabot, CODEOWNERS, the portfolio card, `.gitignore`, `CHANGELOG.md`) and
**this repo's identity/governance docs** (`README.md`, `SECURITY.md`, `CONTRIBUTING.md`, and the
i18n translations under `docs/i18n/` — the generated project renders its own, and the i18n
translates this repo's own README).

### Build or publish one (maintainers)

Every published release attaches the bundle automatically: the `.github/workflows/release.yml`
workflow runs on release and uploads `pgs-eados-bundle.tar.gz` / `.zip` with version-less names, so
`…/releases/latest/download/pgs-eados-bundle.tar.gz` is a stable link. To build one by hand from a
clone:

```bash
git archive --format=tar.gz -o pgs-eados-bundle.tar.gz HEAD   # prefix-less: extracts to the repo root
git archive HEAD | tar tf - | sort                          # preview contents without writing a file
```

## 7. Reviewing an inbound contribution (`/eados review`)

When a PR arrives from a **non-owner** (a collaborator, or an unknown fork), evaluate it against the
contribution policy and draft a recommended disposition — it **recommends; the human disposes**
(`AGENTS.md` §6). The policy is data ([`os/contribution/contribution.yaml`](../orchestrator/os/contribution/contribution.yaml));
the model is [ADR-0014](adr/0014-inbound-contribution-trust-model.md).

```bash
python .eados-core/tools/pr_review.py --pr <PR#> [--repo OWNER/REPO] [--domain D]
```

Worked example — EADOS's own **#94** (an external fork that edited the manifest template):

```text
inbound-PR review: #94 by gxuxhxm [tier: external-fork, fork=True]
  risk: medium  (factors: medium-change)  security-auditor gate: optional
  owned paths touched: .eados-core/orchestrator/project.yaml.template
  checks:
    [????] ci-green — CI status unknown — verify the run
    [OK]   provenance-clear — author 'gxuxhxm' known (fork=True)
    [????] no-added-secrets — security-auditor lens — confirm no added secrets/tokens or secret exposure
    [????] scope-matches-intent — confirm the diff matches the linked issue / stated intent
    [????] gate-coverage-holds — verify via self-lint (gate-coverage runs in CI)
  -> recommended disposition: needs-maintainer (review:needs-maintainer) — external fork touches an owned path
  note: thank the contributor — every non-owner disposition does (courtesy.always_thank)
  note: no auto-accept — this is a recommendation with its reasoning; the human disposes
  note: never merge the contributor's commits — adopt via re-implement-in-house (co-author)
  recommends only — the human disposes / merges / closes (AGENTS.md §6)
```

That recommendation is exactly what happened: #94 touched an owned factory file, so it escalated to
the maintainer, who **adopted** the idea via an in-house re-implementation (co-author credit + a
rationale comment) and closed the PR with thanks — never merging the fork's commits. Drive it via the
[`/eados review`](../orchestrator/commands/review.md) command, which deepens with the
`security-auditor` + `reviewer` on an owned-path / high-risk hit and drafts the comment + label.
No `gh` / offline → it SKIPs cleanly.

**The rule:** we never merge a non-owner's commits — a good idea enters the tree only as our own
re-implementation with co-author credit, so provenance stays in-house. Trust sets the *scrutiny*,
not the *outcome* (the change is judged, not the author).

## 8. Telling an already-generated repo what changed (`/eados upgrade`)

A generated repository is **self-governing** and is never re-rendered
([ADR-0003](adr/0003-generated-repos-are-self-governing.md)) — so every improvement the factory
ships reaches *new* repositories only. That is the right call about **writing**, and for twelve
releases it was read as the answer to the whole question, leaving no way to even *inform* a repo
already in the field. The 2026-07-27 addendum admits the third branch: **tell them, never touch
them.**

Run it **from an EADOS checkout, against the generated repo's path** — not from that repo's own
vendored `.eados-core/`, which is pinned at the version whose staleness you are measuring:

```bash
python .eados-core/tools/upgrade_advice.py /path/to/generated-repo
```

```text
generated by EADOS v2.9.0 (commit 3afe81c) — from AGENTS.md provenance line
3 release(s) since: 2.12.0, 2.11.0, 2.10.0

## v2.12.0 (2026-07-27)
 ! [correctness] A sequence-root YAML document loaded as `{}` — silent, total data loss (#315)
      vendored `.eados-core/learning/lessons.yaml`
   [governance] `os/routing` moves to schema v2 — a two-level provider/host catalog (#323)
      vendored `.eados-core/orchestrator/os/routing`

24 entr(y/ies) affecting this repository; 10 in a class worth acting on now.
```

`!` marks the classes worth acting on now (`security` / `correctness` / `removal`). The class comes
from the **changelog section heading** — data the maintainer already chose — never from mining
prose, and never from semver: one MINOR carries both a security fix and a README tweak. A
`templates/**` change is resolved through the renderer's own map, so the report names the file in
**your** repo, not the template it came from. Factory-internal paths (`.github/**`, `.issues/**`,
the factory's own README) are filtered out; `--all` shows them.

Three things it refuses to do, because for an advisory channel a confident lie is worse than
silence: it **never guesses the provenance stamp** (no stamp → it says what is missing and how to
record it, and exits 0); it **never reports "up to date" from missing data** (no CHANGELOG reachable
→ a skip naming the cause); and it **never writes** — no patches, no merges, no `git`, no manifest
edits. That last one is asserted by hashing the target tree before and after a run, because it is
one helpful patch away from becoming the re-render ADR-0003 rejected.

## 9. What a calibrated agent sounds like

EADOS governs *what* the agent may do; the **Interaction Contract**
([`os/interaction/`](../orchestrator/os/interaction/interaction.yaml), ADR-0022) governs *how it
communicates while doing it* — rendered into [`AGENTS.md` §10](../../AGENTS.md#10-interaction-contract-how-the-agent-communicates)
(and the equivalent §12 of a generated repo's contract) and kept congruent with the data by the
`interaction-lockstep` gate.

| Element | What it means in practice |
|---|---|
| **Confidence tags** | Load-bearing claims (recommendations, risk calls, decision-driving facts) carry `certain` / `likely` / `guessing`, each *earned* by an evidence criterion — not every sentence, and never chosen by tone. Mostly-guessing replies say so first. |
| **No courtesy opener** | Opens with the most informative statement, never "Great question" / "You're absolutely right" / reflexive agreement — but also never forced disagreement; the rule is most-informative-first, not disagree-first. |
| **Dissent template** | `I disagree because <reason>. Alternative: <what I would do instead>. The risk in your approach: <specific downside>.` — uncomfortable answer first, no warm-up prose. |
| **Pushback protocol** | A factual *claim* is re-verified on pushback and held only while the evidence supports it (concede explicitly when it doesn't); a human *decision* is precedence layer 1 (`AGENTS.md` §6) — comply and record the dissent, never relitigate. |

**Enforcement ceiling, stated honestly:** a live conversation turn is *instructed*, never
gate-verified — only on-disk artifacts are linted (`interaction-lockstep`), and the M14 hooks
*re-ground* the posture at phase boundaries and pre-PR checks. This is never marketed as a
guarantee (ADR-0015/0016 posture); a host's own system prompt sits above `AGENTS.md`.

**Tuning it:** the sycophancy denylist and confidence wording are overridable — drop a same-name
`config/interaction.yaml` overlay (not shipped; create it the day you need it — see the override
table in [`config/README.md`](../config/README.md)) to add your organization's own banned phrases
or adjust the vocabulary. The `dissent:`/`pushback:` protocol blocks are the contract itself, not
overlay surface — `pushback.human_decision` never relaxes.

---

## 10. How the OS routes model & effort

EADOS treats **which model, at which effort** each unit of work deserves as data — the
[`os/routing`](../orchestrator/os/routing/routing.yaml) policy (ADR-0017), evaluated by
[`route_advice.py`](../tools/route_advice.py). It is **advisory-first**: the OS *recommends*, the
human keeps final model authority; **no agent ever switches its own session model** (auto-selection
exists only for work a run *delegates* beneath itself, [`os/routing/delegation.md`](../orchestrator/os/routing/delegation.md)).

**Tiers, not model names.** The policy speaks capability **tiers** (`fast` / `standard` /
`frontier-reasoning`) × an **effort** (`low` / `medium` / `high` / `extra` / `max`); concrete model
names live only in the policy's dated `catalog:`, so a market shift is a one-line catalog edit —
never a policy, roadmap, or code change.

**It works under any LLM (ADR-0024).** The catalog is two levels: **providers** say what exists and
what each model *clears*; **hosts** say which providers a runtime can reach. So a mono-vendor host
(Claude Code, Codex) and a model-agnostic one (OpenCode driving seven vendors) are both one entry,
and adding either is configuration — no code, no schema change.

Resolution is by **capability, not by name**, in two phases that do different jobs:

1. **Escalation → the floor.** Your signals raise a quality floor. Monotonic: rules only ever raise.
2. **Selection → the model.** Among the models your host can reach that *clear* that floor, take
   the cheapest.

> **Cost may only choose among models that already clear the earned floor. It can never lower it.**

That is how *quality-first with cost awareness* is structural rather than a promise: "use the
minimum sufficient model" is simply what the floor already computes, and cost picks the cheapest
way to reach it. A `security` or `adr` route cannot be quietly degraded to save tokens, because
cost never touches the floor at all.

**Which host you are on is worked out from evidence** — an explicit `--host`, `routing.host` in the
manifest, or environment markers each host declares as data. Never by asking the agent what model
it is: models misdescribe their own identity, and a route built on that is wrong *and*
authoritative-looking. When the host cannot be determined, EADOS says so and still gives you the
tier and effort — those are vendor-neutral, so only the model *name* is lost.

**Steps route too.** A step inside an item (`design` / `implement` / `test` / `review` /
`optimize`) can raise the route, never lower it — so a trivial item's design step earns real
thinking while its test step does not, and a protected item keeps its floor in *every* step:

```bash
python .eados-core/tools/route_advice.py --labels "severity:low" --step design --explain
```

**Where you see it:**

| Surface | What it shows |
|---|---|
| **`/eados plan`** | Each `ROADMAP.md` item carries its route — `size: M · route: standard / medium` — attached during negotiation next to the T-shirt size. |
| **`scaffold` (the generated repo)** | The rendered `ROADMAP.md` opens with a routing legend (tiers/efforts, floor, dated catalog snapshot) and any roadmap item recorded with intake signals carries its derived advisory route (`— route: <tier> / <effort>`, #306/ADR-0023); the generated `AGENTS.md` §6 restates the advisory boundary. |
| **Step-0 triage / `/eados status`** | The recommended tier + effort for the work ahead. |
| **Phase boundaries** | `phase_runner.py` re-states the advisory posture and points at the checkpoint. |

**The route checkpoint** — before starting a step, compare the route to the model you are actually on:

```bash
python .eados-core/tools/route_advice.py --labels "adr,severity:high" --flags decision-heavy \
  --check --current-model "Opus 4.8"
```

- **`ROUTE-OK`** — the session tier matches the route.
- **`ROUTE-MISMATCH`** — you are below (or above) the routed tier; switch with your host's model
  control (e.g. Claude Code's `/model`), **or** proceed and record the accepted mismatch:
  `record_run.py --route-mismatch "frontier-reasoning/high=standard"`.
- **`ROUTE-CHECK`** — the session model is not in the dated catalog, so tiers cannot be compared.

It **always exits 0** — advisory, never a gate. Two limits are stated honestly, not hidden: the
**effort** setting is not observable by any host's agent (the checkpoint verifies the *model* half
only and says so), and the session model is the agent's **self-report** (`--current-model`), not an
API the tool can read. Claiming a gate could police either would violate the ADR-0015/0016 honesty
posture.

---

## 11. Go deeper

- [`AGENTS.md`](../../AGENTS.md) — the binding contract (source of truth).
- [`orchestrator/`](../orchestrator/README.md) — the engine (interview, generate, placeholders, profiles, recovery).
- [`agent/`](../agent/README.md) — the role registry.
- [`config/`](../config/README.md) · [`learning/`](../learning/README.md) · [`eval/rubric.md`](../eval/rubric.md) · [`maintenance/stay-current.md`](../maintenance/stay-current.md) — customization & self-improvement.
