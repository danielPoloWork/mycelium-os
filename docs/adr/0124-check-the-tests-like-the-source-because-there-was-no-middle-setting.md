# ADR-0124: Check the tests like the source, because there was no middle setting

- **Status:** Accepted
- **Date:** 2026-09-18
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / AGENTS.md §10
- **Related:** [ADR-0071](0071-advertise-the-types-and-check-the-tools.md) (which put `src`
  and `tools` behind `mypy --strict`, shipped `py.typed` for the core, and filed this),
  [ADR-0055](0055-run-the-gates-the-change-implicates.md) (the ladder, chosen on numbers),
  [ADR-0077](0077-give-a-module-an-entry-point-a-section-and-a-command-and-report-what-it-could-not-reach.md)
  (the second distribution this found untyped), [ADR-0007](0007-adopt-structure-first-chunking.md);
  D-003, D-025; AGENTS.md §10; roadmap 4.43, 6.9

## Context

Roadmap 6.9, filed by ADR-0071: *"Decide how strict a test file has to be, and type-check
`tests/` accordingly."* It framed the question as policy rather than effort — *"a test that
constructs an invalid record on purpose is doing its job, and `--strict` has no vocabulary for
that beyond a per-line ignore"* — and proposed a middle setting: a non-strict
`[[tool.mypy.overrides]]` for `tests/` that would still catch the `type-arg` and
`var-annotated` classes.

Measured before deciding, because the item's own numbers were a milestone old. `mypy --strict`
over both test suites reported **212 errors in 47 of 98 files**, against the 81 in 24 of 66
recorded at 4.43.

## Two findings, and the second one settles the item

**The proposed middle setting does not exist.** The errors the item wanted to keep and the
errors it wanted to forgive are on opposite sides of the strictness switch from where it
placed them:

| class | count | strict-only? |
|---|---:|---|
| `arg-type` | 38 | **no** — base check |
| `union-attr` | 16 | **no** — base check |
| `attr-defined` | 8 | **no** — base check |
| `var-annotated` | 7 | **no** — base check |
| `no-untyped-def` | 30 | yes (`disallow_untyped_defs`) |
| `no-untyped-call` | 20 | yes (`disallow_untyped_calls`) |
| `unused-ignore` | 18 | yes (`warn_unused_ignores`) |
| `type-arg` | 11 | yes (`disallow_any_generics`) |

Dropping `strict` for `tests/` would have left every `arg-type` and `union-attr` in place —
the ones the item called deliberate looseness — while switching off `disallow_untyped_defs`,
whose absence means mypy does not check an unannotated function's **body at all**. The middle
setting keeps what the item wanted forgiven and forgives what it wanted kept. There is no
useful position between checking `tests/` and not checking it.

**And the errors were not what the item expected.** Read rather than assumed, the bulk were
ordinary looseness with a better fix than an ignore:

- `verified_at="2026-07-31"` where a `date` belongs, and `verification_status="verified"`
  where the enum does — pydantic coerces, so the test passed while asserting against a
  coerced value.
- `settings.default.deadline` on a `settings | None`, six times: a run with no profile loaded
  would have raised `AttributeError` on whichever line came first instead of saying so.
- `grammar_for("rs") is not None and grammar_for("rs").language == "rust"` — two calls, the
  second unnarrowed, where one bound result is clearer and cheaper.
- `there.projection_path` used after only `here.projection_path` was asserted non-`None` —
  a real gap in a test's own narrowing.

**A third finding, on the way, and it is a product defect rather than a test one.**
`mycelium-chats` ships **no `py.typed`**. ADR-0071 gave the core one at 4.43 so that
`pip install mycelium-os` advertises its types; the module became a real distribution at 5.5
and never got the same treatment, so a consumer installing it gets none — and mypy skipped 30
of the 212 errors because it could not see into a package it had already type-checked. The
marker is added here.

## Decision

**`tests/` and `contrib/chats/tests/` are read by `mypy --strict`, exactly as `src`,
`tools` and `contrib/chats/src` are.** All 212 errors are resolved: 216 files check clean.

**Where a test feeds an invalid value on purpose, the per-line `# type: ignore[...]` is the
vocabulary for saying so** — which the item treated as a drawback and which is, on the
evidence, an improvement. An ignore sits at the site and names the reason; a settings file
covers every test equally and explains nothing. Seven such sites remain, each with a comment:
a `**kwargs` splat into a constructor with individually typed parameters (three), a pydantic
alias mypy cannot see without its plugin, a `Final`-literal comparison mypy folds to a
constant, an untyped `pytest-benchmark` fixture, and hypothesis's category literals.

**Three configuration defects are fixed rather than suppressed**, and they were 52 of the 212:

- `contrib/chats/src/mycelium_chats/py.typed` — the module now advertises the types it
  already has.
- `mypy_path = ["tools"]` — `tests/` imports `verify`, `consistency_lint` and
  `update_journal_index` to hold the tools to their own contracts, through a `sys.path`
  insertion mypy cannot see. The path is declared rather than the imports ignored.
- `cookiecutter.*` and `jsonschema.*` join the existing `ignore_missing_imports` list, for
  the reason the rest of that list is there: no stubs, two call sites each.

**One production signature is widened, and it is the clearest argument for the whole item.**
`_gate_g3` declared `baseline: dict[str, object] | None` while only ever reading it. `dict` is
invariant, so no caller holding a `dict[str, float]` could pass one without copying; the
correct type is `Mapping`. Nineteen of the 212 errors were that one signature, and no amount
of test-side ignoring would have found it — checking the tests is what surfaced it.

**The price is nil, measured.** Two paired cold runs: **69.5 / 55.2 s** without the test
suites against **60.1 / 56.8 s** with. The run-to-run variance exceeds the difference, because
mypy's time is the third-party graph these files import rather than the files themselves. 110
files checked becomes 216. This is the same result ADR-0071 measured when it added `tools/`,
and for the same reason.

## Alternatives Considered

- **A non-strict `[[tool.mypy.overrides]]` for `tests/`, as the item proposed.** Rejected on
  the table above: it keeps the class the item wanted forgiven and forgives the class it
  wanted kept, and switching off `disallow_untyped_defs` stops mypy checking the bodies of the
  30 functions that most needed it.
- **Leave `tests/` unchecked and close the item as answered "no".** Defensible on the item's
  own asymmetry — `tools/` had to be checked because nothing else checks it, while `tests/` is
  executed on every run. Rejected on what the run cannot see: a test that asserts against a
  coerced value passes, and a test that would raise `AttributeError` rather than fail an
  assertion passes until the day it does not. Execution checks the behaviour the test
  exercises; typing checks the test itself.
- **Silence the deliberate sites with a blanket `disable_error_code` for `tests/`.** Rejected:
  it would have hidden the nineteen-error invariance finding and the four narrowing gaps along
  with the seven real exemptions.
- **Enable pydantic's mypy plugin**, which would resolve the `Edge(from_=…)` alias properly.
  Genuinely the better fix for that one site, and rejected here for blast radius: the plugin
  changes how every record in `src` is checked, which is a decision with its own evidence and
  not one a test-typing item should take in passing. Recorded at the site.
- **Add `types-jsonschema` and stubs for `cookiecutter`.** Rejected as disproportionate: four
  call sites, a dev-only dependency, and a lockfile change against the existing precedent for
  exactly this situation.

## Consequences

- **`tools/verify.py`'s `TYPED_PATHS` and CI's `lint` job both gain the two test paths**, and
  `tests/test_verify_ladder.py` holds them in agreement as it already did. A contributor and
  the workflow cannot drift about what is checked.
- **A consumer of `mycelium-chats` now gets types** — the fix outlives this item.
- **A test that adds an unannotated function fails the ladder at `code` mode**, which is where
  the house style was already followed by 96 % of the suite and unenforced.
- **Nothing about the product's behaviour changes.** No gate, baseline, golden or corpus
  moves; the only `src` edit is the `Mapping` widening, which no caller can observe.
- **A limitation, stated.** Seven ignores are a standing invitation to add an eighth without
  thinking. They are comment-bearing by convention rather than by check, and nothing here
  enforces that — if the count grows, the right response is to ask why, not to add a lint.

## References

- Re-runnable: `uv run mypy --strict src tools contrib/chats/src tests contrib/chats/tests`,
  and `python tools/verify.py` at `code` mode.
- [ADR-0071](0071-advertise-the-types-and-check-the-tools.md) — which filed this, and whose
  `py.typed` reasoning applies unchanged to the second distribution.
- AGENTS.md §10 (the quality bar); D-003 (Python 3.12+, typed).
