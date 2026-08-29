# Run records

One YAML file per generation run, named `<YYYY-MM-DD>-<project-slug>.yaml`. A second run for the
same slug on the same real date (a failed bootstrap then its fixed re-run) is disambiguated with a
sequence suffix — `<YYYY-MM-DD>-<project-slug>-2.yaml`, `-3`, … — while the `date:` field inside
stays the true run date (#197). After a run (generate.md **Step 9**), the architect appends a
record with **one command** — no hand-authored YAML (#172):

```bash
python .eados-core/tools/record_run.py <manifest> [--outcome ok|failed] \
    [--failure GATE=MESSAGE ...] [--lesson L-NNNN ...] [--rubric DIM=SCORE ...]
```

The `overrides:` list is derived **mechanically** from the manifest's `interview:` provenance
block (#169) against the built-in defaults in `project.yaml.template` — never from end-of-run
recollection. The records feed the auto-tuner
([`../../tools/autotune.py`](../../tools/autotune.py)), which mines defaults that are
*consistently* overridden, and the failure channel is where the highest-value signal EADOS
generates — a **red bootstrap CI** on a fresh repo — lands durably:
`--failure ci-bootstrap="<one-line summary>"` (with `--outcome failed`).

The same records feed the learning-loop watchdog
([`../../tools/lesson_audit.py`](../../tools/lesson_audit.py), #173), which is report-only like
the auto-tuner but reads the *other* channels: a `failures` entry that repeats ground an
existing lesson already covers is flagged as a **regression** (the trigger to promote that
advisory lesson to a mechanical gate), a lesson never present in any `lessons_applied` is
flagged as **dead weight**, and a `rubric` dimension scoring low in the majority of runs is
proposed as a **new lesson**.

## Record schema

```yaml
slug: <project-slug>
date: YYYY-MM-DD
phase: scaffold        # which delivery phase produced it (#215); scaffold by default
lang: <lang>
kind: <library|service|cli|app>
outcome: ok            # ok | failed
# Values the maintainer changed away from a built-in default (derived from provenance):
overrides:
  - key: ownership.license_id
    default: MIT
    chosen: Apache-2.0
  - key: toolchain.coverage_target
    default: 80
    chosen: 90
lessons_applied: []    # the lesson ids applied at Step 0.a, e.g. [L-0001, L-0002]
failures: []           # on a failed run: [{gate: ci-bootstrap, message: "..."}]
rubric: {}             # eval/rubric.md dimensions scored 0-2, e.g. spec_measurability: 2
```

The **`migrate` phase** — the riskiest surface, since it modifies real user code — records incidents
through the same channel: `record_run.py <manifest> --phase migrate --outcome failed --failure
migration-gate="<one-line summary>"`. `lesson_audit`'s regression detection then covers migrate, not
just generation (#215). A record with no `phase:` is treated as `scaffold` (legacy, backward-compatible).

Records are facts about past runs — never edited after the fact (`record_run.py` never overwrites
an existing record; a same-day re-run lands under a `-2`/`-3` suffix with a truthful `date:`, #197).
They contain no secrets: a manifest should carry none (tokens/webhooks never live in one), and as a
backstop an override whose **key** names a host / url / registry / endpoint / token is recorded with
its `chosen:` value as `<redacted>` (#215) — the tuner still sees the key was overridden, the value
does not leak. The auto-tuner reads `overrides` and ignores the other channels; it is a no-op until
enough records accumulate (the confidence floor scales with the corpus, #215).

Every record here is **schema-validated by the self-lint** (`eados_lint`'s `run-records` gate,
#175): the five required keys, the `outcome` vocabulary, override triples, `failures` shape (a
failure implies `outcome: failed`), and rubric dimensions 0–2 drawn from the ten. A malformed
record fails CI rather than silently poisoning the auto-tuner and the lesson audit — the write
side (`record_run.py`) and the gate share one schema.
