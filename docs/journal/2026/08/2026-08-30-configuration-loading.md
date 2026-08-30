# 2026-08-30 — configuration loading (roadmap 2.14)

- **Session scope:** roadmap item 2.14 — `mycelium.toml` → build/chunking/embedding
  settings (spec 05 §2).
- **PR:** #27 (`feat/config-loading`), one item, one PR. Follows #26 (2.13), merged.
- **Milestone 2 is complete** — every item 2.1–2.14 is checked, and the README's milestone
  table says so. The v0.2.0 release cut is the owner's move.

## What got done

- `src/mycelium/config.py` — `load_config(root)` reads and validates the file.
  `[project]` (name, namespace, `knowledge_dir`), `[chunking]` (`max_tokens`),
  `[embedding]`, and `[modules]` are honoured; the sections whose features do not exist
  yet are accepted into an uninterpreted mapping, digested, and named by `doctor`.
- The orchestrator takes a `MyceliumConfig`: discovery uses the configured tree, chunks
  use the configured policy, the namespace comes from the file (an explicit argument still
  overrides it), and the manifest's `config_digest` is now the digest of the real
  configuration rather than the `{"namespace": …, "chunking": "defaults"}` placeholder.
- `mycelium doctor` gains a `config` check; an invalid file exits 2 (usage), not 1, because
  nothing was attempted.
- The `init` template no longer says "nothing reads this file yet" — it states the defaults
  and marks which lines are not honoured yet.
- **ADR-0014** records the shape of the decision, and **roadmap 3.8** is filed for the one
  key deliberately left advisory.

## The two judgment calls

**`target_tokens` is honoured as advisory, not as a size target.** Spec 05 §2 exposes
`target_tokens = 400` next to `max_tokens = 800`, but the packer built at 2.5 fills toward
the ceiling and treats a minimum as advisory, because reaching one would mean merging
across a heading boundary (ADR-0007). Making the target steer chunk size is a behaviour
change wearing a configuration costume: it moves every chunk boundary in every corpus,
shifts the eval numbers, and needs a determinism re-bless. That deserves its own
measurement, so it is roadmap 3.8, and the generated template says `advisory today` on
that line rather than implying a knob that does nothing.

**Sections that cannot be honoured are named, not ignored.** Rejecting them would make the
file printed in the specification invalid. Ignoring them silently is worse — an operator
tunes `[retrieval] profile` and believes it took effect. So they are accepted, digested
(they will be honoured, and a snapshot built under a config that carried them should not
silently match one that did not), and `doctor` reports them by name.

## The determinism diff, and why it is one line

Changing how `config_digest` is computed changes the manifest, so the golden had to be
re-blessed. Before re-blessing, the fresh observation was diffed against the golden field
by field:

```text
1 field(s) differ from the golden:
   .config_digest: 'sha256:4fd437af…' -> 'sha256:d1af0b3e…'
```

Every chunk digest, anchor, text, and count is byte-identical. That is the evidence that
reading configuration did not change what the compiler produces — which is exactly what a
reviewer needs to see, and why ADR-0012 made the golden reviewable instead of a single
hash. G6 asserts that a rebuild is reproducible, not that the compiler never changes.

## A cross-platform bug the tests caught

`ProjectConfig` refuses an absolute `knowledge_dir`, and the first implementation used
`Path(value).is_absolute()`. On Windows that is `False` for `/etc` — so the same config
would have been rejected on Linux and accepted on Windows, and CI's Linux cells would have
been the only ones to notice. It now checks `PurePosixPath` **and** `PureWindowsPath`.
Worth remembering: any validation over a path string is platform-sensitive unless both
flavours are asked.

## Where the project stands

- **Milestone 2 complete (2.1–2.14).** Milestone 3 — the incremental compiler — is next,
  starting with 3.1 (content-addressed DAG, build cache, dirty detection).
- Gates green locally: `ruff format --check`, `ruff check`, `mypy --strict src`,
  `pytest -q` (433 passed), `python tools/consistency_lint.py`.

## How the next session resumes

- Wait for PR #27 to merge. The natural next step is the **v0.2.0 release cut** (pre-1.0
  versioning increments MINOR per completed milestone) — an owner-gated release PR — and
  then **3.1**.
- 3.1 inherits the config digest as a real input: build keys are
  `(stage_id, impl_version, input_digests, config_digest, schema_version)`, and
  `config_digest` finally carries meaning. A config change must invalidate exactly the
  stages it affects — which is the first time the "exactly" in spec 05 §2 will be testable.
