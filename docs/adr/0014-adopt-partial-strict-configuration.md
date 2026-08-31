# ADR-0014: Load `mycelium.toml` strictly, honour it partially, and say which is which

- **Status:** Accepted — the `target_tokens` ruling is amended by [ADR-0023](0023-make-the-chunk-target-steer-size.md): the knob is honoured, and steers chunk size
- **Date:** 2026-08-30
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 05 §2
- **Related:** [ADR-0007](0007-adopt-structure-first-chunking.md) (the chunking policy this
  configures), [ADR-0009](0009-adopt-build-publication-semantics.md) (the manifest that
  records the digest), [ADR-0012](0012-adopt-the-g6-determinism-gate.md) (the golden this
  re-blesses); spec 05 §2, spec 03 §5; D-002, D-008; roadmap 2.14, 3.8

## Context

`mycelium init` has scaffolded `mycelium.toml` since roadmap 2.8, with a comment admitting
nothing reads it. Item 2.14 makes it real. Spec 05 §2 prints the whole file — `[project]`,
`[ingest]`, `[chunking]`, `[embedding]`, `[modules]`, `[synthesis]`, `[verification]`,
`[sources]`, `[retrieval]`, `[eval]` — and requires two things of the loader: *"validated
with precise errors"*, and *"the config digest participates in build keys, so config
changes correctly invalidate exactly the stages they affect"*.

The awkward part is that most of that file configures features this milestone has not
built. Ingestion connectors arrive at 4.1, synthesis at 4.4, verification at 4.5, hybrid
retrieval at 3.3. A loader must decide what to do with settings it cannot honour, and
there is no good silent answer: rejecting a spec-valid file is wrong, and accepting one
while quietly ignoring half of it is worse — an operator tunes a knob, sees no error, and
believes it worked.

A second problem hides in `[chunking]`. Spec 05 §2 exposes `target_tokens = 400` alongside
`max_tokens = 800`, but the packer built at 2.5 fills toward the ceiling and treats a
minimum as advisory, because reaching a minimum would mean merging across a heading
boundary (ADR-0007). The two documents describe different packers.

## Decision

**Strict where it can be honoured; explicit where it cannot.** `[project]`, `[chunking]`,
`[embedding]`, and `[modules]` are modelled as frozen, `extra="forbid"` sections: an
unknown key, an unsatisfiable value, or an unknown section is a `ConfigError` naming the
file, the key, and what was expected. The remaining documented sections are accepted into
an uninterpreted `future` mapping, and `mycelium doctor` reports them by name as *not
honoured yet*. A section outside both sets is an error that lists the ones spec 05 §2
defines — so a typo (`[retreival]`) is caught with the correct spelling in the message.

**A missing file is not an error.** `mycelium build` works in a bare directory; `init`
writes the file for the operator's convenience, not as a precondition. A file that exists
and is broken *is* an error, and it stops the build before the lock is taken: nothing is
published, and the fix is in the operator's hands. The CLI exits 2 (usage), not 1
(failed), because nothing was attempted.

**The digest covers resolved settings, not file bytes.** Comments, spacing, and key order
do not invalidate a build; every value that reaches the compiler does. Sections that are
not honoured yet *are* digested: they will be honoured, and a snapshot built under a config
that already carried them should not silently match one that did not.

**`max_tokens` is honoured; `target_tokens` is not, and this ADR says so.** `max_tokens`
maps to the policy ceiling. `target_tokens` maps to the policy's advisory lower target,
which the packer does not enforce — so lowering it does not shrink chunks today. Making it
steer chunk size moves every chunk boundary in every corpus, which is an eval question
(does smaller retrieve better?) and a determinism re-bless, not a side effect of wiring up
a config loader. Filed as roadmap 3.8; the generated template says `advisory today` on that
line.

**Values that cannot be satisfied are refused rather than approximated**: `[modules]
enabled` with any name (no module exists before 5.5), an `atomic` list that drops `table`
or `code` (atomicity is not a knob the chunker has), and a `knowledge_dir` that is absolute
or escapes the repository.

## Alternatives Considered

- **Model every spec section fully now** — one complete config object. Rejected: it means
  inventing validation semantics for features whose behaviour is not designed yet
  (`synthesis.enabled = "auto"` — auto by what rule?), and those invented rules would be
  the first thing the real feature contradicts.
- **Reject sections that are not honoured** — maximally strict, no false promises.
  Rejected: it makes the file printed in the specification invalid, and punishes an
  operator for planning ahead.
- **Accept and silently ignore them** — the common library behaviour. Rejected outright:
  the failure mode is an operator who believes a setting took effect. Naming them in
  `doctor` costs one check and removes the whole class of confusion.
- **Digest the file's bytes** — trivially correct invalidation. Rejected: reformatting or
  adding a comment would invalidate every cached artifact, which makes the build cache
  (roadmap 3.1) hostile to editing your own config.
- **Make `target_tokens` steer the packer now** — honours the key as written. Rejected
  *for this item*: it is a behaviour change disguised as configuration. It would move every
  chunk boundary, shift the eval numbers, and require re-blessing the determinism golden —
  each of which deserves its own measurement (roadmap 3.8).
- **Environment-variable overrides** — familiar, and useful in CI. Rejected for now: a
  build must be explainable from its manifest, and an invisible override in the environment
  is the opposite of that. If it is ever needed, it needs to appear in the config digest.

## Consequences

- The manifest's `config_digest` changes value: it now digests the real configuration
  instead of the `{"namespace": …, "chunking": "defaults"}` placeholder. The determinism
  golden is re-blessed in this PR, and the diff is **one line** — every chunk digest,
  anchor, count, and text is byte-identical, which is the evidence that reading config did
  not change what the compiler produces. G6 asserts that a rebuild is reproducible, not
  that the compiler never changes; the golden is reviewable precisely so this shows up in
  review.
- `mycelium doctor` gains a `config` check: `ok` when absent or fully honoured, `warn` when
  the file names sections that do nothing yet, `fail` when it is invalid.
- Defaults are unchanged by construction — the scaffolded template states them explicitly,
  and a test asserts the template resolves to the same policy the built-in defaults do.
- Settings not honoured yet are inert but *digested*, so enabling one later invalidates
  cached artifacts correctly on the first build that reads it.
- `build(root, namespace=…)` still overrides the configured namespace, which is how a
  caller scopes a build without editing a file; the override is digested separately so two
  builds of the same config under different namespaces do not collide.

## References

- Spec: `.draft-specs/05-interfaces-and-plugins.md` §2 (the file), §1 (exit codes);
  `.draft-specs/03-data-model.md` §5 (chunking policy)
- Decision log: D-002 (single namespace in v1), D-008 (build keys and the config digest)
- [ADR-0007](0007-adopt-structure-first-chunking.md) — why a minimum cannot be enforced
