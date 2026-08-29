# ADR-0008: Loader scalar fidelity and a PyYAML differential gate

## Status

Accepted

## Context

[ADR-0006](0006-manifest-loader-and-emitted-yaml-validation.md) made the dependency-free
manifest loader (`tools/render.py:load_yaml`) spec-correct for **block sequences**, but a
follow-up audit found its **scalar** layer still diverged from standard YAML — and, as before,
silently. A differential run against PyYAML 6 showed:

- Double-quoted escapes were not processed: `"const Version = \"X.Y.Z\""` rendered with literal
  backslashes (`\"X.Y.Z\"`). The comment/quote tracker also desynced on an embedded `\"`.
- Single-quoted escaping was ignored: `'it''s'` rendered as `it''s`.
- Block-scalar chomping was ignored: `|-` (strip) behaved like `|` (clip).

These are the most common things a real manifest contains — an apostrophe in a tagline, a quote
in an objective. The reference fixture happens to avoid all of them, so every existing gate
stayed green while a generated repo's prose was silently corrupted. This contradicts EADOS's core
promise of *measurable correctness over assertion*.

## Decision

1. **Make scalar parsing spec-correct, staying dependency-free.** Process double-quoted escapes
   (`\n \t \r \0 \" \\ \/`), collapse single-quoted `''` → `'`, and honor `|` (clip) and `|-`
   (strip) chomping. `_strip_comment`/`_split_top` are now escape-aware so `\"` cannot desync
   quote tracking. (Also hardens the block-scalar dedent so a less-indented continuation line is
   never sliced into.)
2. **Keep a single parser on the hot path.** Rather than branch to PyYAML-when-present — which
   would make a local render (no PyYAML) and a CI render (PyYAML) disagree, breaking reproducible
   generation — the hand-rolled loader stays the one source of truth, now correct.
3. **Pin it with a differential gate.** `tools/tests/test_loader.py` asserts `load_yaml` equals
   `yaml.safe_load` over a corpus of idiomatic manifest YAML (including the three regressions
   above) **and** on the full `reference.yaml` (deep equality). PyYAML is CI-only; the test skips
   when it is absent. CI runs it in the render-smoke job and byte-compiles it in self-lint.
4. **Document the supported subset and its deliberate deviations** in the loader header:
   `yes/no/on/off` are *not* coerced to booleans (avoids the "Norway problem"); unquoted decimals
   stay strings (a version like `1.22` is not turned into a float). `|+` keep-chomping, folded
   `>`, anchors, tags, and multi-document streams are explicitly out of the guaranteed subset.

## Consequences

- Apostrophes and quoted phrases in any manifest field now render faithfully; the
  most-used component no longer corrupts prose silently.
- Reproducibility is preserved: one parser, one result, regardless of whether PyYAML is
  installed. The everyday rendering path remains standard-library-only.
- A future regression in the loader fails the differential gate loudly instead of shipping a
  subtly wrong repo. The supported subset is now executable documentation, not prose.
- The hand-rolled loader is retained (per ADR-0006's "no third-party dep on the hot path"); the
  differential gate is the agreed safeguard for keeping it honest as the subset evolves.
