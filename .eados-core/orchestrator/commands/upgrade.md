# `/eados upgrade` — what changed upstream since this repo was generated

A **read-only** advisory readout for an **already-generated repository**: which factory releases
have landed since the version that produced it, which of them touch a surface this repo actually
carries, and how much each one should worry its maintainer. It **reports; it never writes.**
Phase-agnostic — run it in any state; owned by no single role.

## Why this exists, and where its boundary comes from

[ADR-0003](../../docs/adr/0003-generated-repos-are-self-governing.md) decided that a generated
repository is **self-governing** and is never re-rendered. It weighed two branches — couple the repo
to the factory, or re-render it on every change — and rejected both. Both were about *writing*, so
the operative answer became *nothing*, and twelve releases of fixes reached new repositories only.

The **2026-07-27 addendum** admits the third branch: **tell them, never touch them.** That is this
command, and it is the same shape the project already holds everywhere else it knows something the
human must decide — routing is advisory ([ADR-0017](../../docs/adr/0017-model-effort-routing.md)),
`/eados review` recommends and never merges
([ADR-0014](../../docs/adr/0014-inbound-contribution-trust-model.md)), `lesson_sweep` prints drafts
and never writes the ledger.

**Out of scope, permanently:** applying changes, generating patches, three-way merges, any `git`
operation, any manifest edit. The moment this command writes, ADR-0003's rejected re-render branch
is back through the side door — so `test_upgrade_advice.py` hashes the target tree before and after
a real run rather than trusting the convention.

## Procedure

Run it **from the factory, against the generated repo's path** — not from inside the repo's own
vendored `.eados-core/`, which is pinned at the version whose staleness you are trying to measure:

```bash
python .eados-core/tools/upgrade_advice.py /path/to/generated-repo
```

| Flag | Effect |
|---|---|
| `--all` | include factory-internal entries (normally filtered out) |
| `--changelog PATH` / `--gitattributes PATH` | read the delta / bundle membership from disk |
| `--repo-slug OWNER/REPO` | a fork of the factory |
| `--no-fetch` | never call `gh`; skip rather than reach the network |
| `--json` | the same assessment as data |

It prints, for the repo at that path:

- **the recorded stamp** — the factory version that produced it, and which recorded source said so;
- **the releases newer than it**, each with the entries that name a surface this repo carries;
- **a consequence class per entry** — `security` · `correctness` · `governance` · `capability` ·
  `behavior` · `deprecation` · `removal`. `!` marks the classes worth acting on **now**;
- **where each change lands in *your* repo** — a `templates/**` change resolves through the
  renderer's own `out_relpath`, so the report can never name a file `render.py` would not produce;
  a vendored path names itself; a `setup/` change names the release asset to re-download.

## Three honesty rules it holds itself to

Each is here because the alternative is a **confident lie**, which for an advisory channel is worse
than no channel at all:

1. **The provenance stamp is read, never guessed** (#319). Sources, structured first: the manifest's
   `generated_by:` block, then the provenance line in a rendered `AGENTS.md`. With neither, it says
   what is missing and how to record it, and exits **0** — an unstamped repo is not a broken repo.
   A guessed baseline produces a delta against the wrong version that reads exactly like a real one.
2. **The consequence class comes from data.** The Keep a Changelog section heading — which the
   maintainer already chose at write time — refined to `governance` only by paths the entry *itself*
   names. Prose is never mined for a class it does not state, and semver is not a consequence class:
   one MINOR carries both a security fix and a README tweak.
3. **What could not be established is stated** (L-0006). No CHANGELOG reachable → a skip naming the
   cause and both remedies, **never** "you are up to date" inferred from missing data. No
   `.gitattributes` → the report says it is unfiltered rather than quietly dropping the filter. An
   entry naming no path is shown as `unattributed`, **not** dropped: an advisory channel that hides
   what it could not classify is the exact silent failure this command was filed against.

## Filtering — what "this repo carries" means

`.gitattributes` `export-ignore` is the authority for what `git archive` strips, so it is read
rather than re-stated. **One stated exception:** `setup/` is export-ignored *because it ships as
separate release assets*, not because consumers do not use it — the installer is how they install,
and export-ignore alone would have silently dropped the tar-slip hardening (#129), which is
precisely the class of change this command exists to surface.

A profile change is filtered to the repo's own language. Factory-internal paths (`.github/**`,
`.issues/**`, the factory's own `README`/`CHANGELOG`, the i18n set) never appear without `--all`.

## Boundary

Assessment only. `/eados upgrade` proposes no transition, advances no phase, and drafts nothing —
adopting anything it reports is a **human** act, taken in the generated repo under **that** repo's
contract (the two-contracts rule). Its own ADRs stay authoritative; nothing here is a directive.

**Calibrate the readout** (`AGENTS.md` §10): tag load-bearing calls by evidence
(`certain`/`likely`/`guessing`, cite the check). "24 entries affect you" is `certain` only about the
surfaces the entries *named* — say so rather than implying the sweep was exhaustive.
