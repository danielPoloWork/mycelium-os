# ADR-0071: Advertise the types, then check the tools with them

- **Status:** Accepted
- **Date:** 2026-09-09
- **Deciders:** project architect (agent), maintainer (owner)
- **Related:** ROADMAP 4.43 (this item), 4.40 (where it was filed), 4.35, 6.1, 6.9; RFC-0001;
  AGENTS.md §10; PEP 561;
  [ADR-0004](0004-adopt-pydantic-v2-record-contracts.md),
  [ADR-0055](0055-run-the-gates-the-change-implicates.md),
  [ADR-0059](0059-make-the-plan-one-implementation-too.md),
  [ADR-0068](0068-give-gate-g2-a-runner-by-dating-its-verdict.md),
  [ADR-0070](0070-take-the-leaf-heading-weight-on-the-third-asking.md)

## Context

`tools/` holds eighteen files. They build the ingested corpus, carry the judgements onto it,
measure the ranking, decide gate G2's currency in CI, and derive which gates a change has to
run at all. Nothing checked them. The verification plan and the CI workflow both ran
`ruff check src tests` and `mypy --strict src`, so the only thing standing between a defect
in that directory and `main` was review.

Roadmap 4.40 measured it and filed this item: `ruff check tools` reported **1** error and
`mypy --strict tools` reported **184** in 16 of 18 files. It also named the likely order —
ship `py.typed`, re-measure, then decide whether `tools/` joins the ladder, **and price it**,
because ADR-0055 chose the ladder's rungs on numbers rather than on taste.

Re-measured at the start of this item, `ruff check tools` reports **2**: a second error had
arrived since the filing (a 109-character line in `verify.py`'s own docstring table, added by
4.40). A drift of one in a directory nobody checks, in a week — small, and exactly the
argument.

The 184 had one dominant cause. `mycelium` shipped **no `py.typed` marker**, so every
`from mycelium…` outside `src/` was `import-untyped` and everything downstream of it was
`Any`. That is not only a `tools/` problem: a package whose entire pitch is typed record
contracts (ADR-0004) was advertising no types to the consumers importing them.

## Decision

**Ship the PEP 561 marker, then put `tools/` behind the format, lint and type gates at `code`
mode — and state the path lists once each.**

`src/mycelium/py.typed` is an empty file, and it is worth 73 of the 184 errors on its own:

| step | errors |
|---|---:|
| as filed at 4.40 | 184 in 16 files |
| after `py.typed` | **109** in 6 files |
| after annotating `tools/` | **0** in 105 checked files |

The remaining 109 were genuine: 21 untyped function definitions (all but four of them in
`consistency_lint.py`, which EADOS generated unannotated), the 75 calls to them, and a
dozen inference gaps. Annotating them is the bulk of this change's diff.

**`tools/` joins `code` mode, priced at zero.** ADR-0055 chose the rungs on measurements, so
this rung gets one:

| check | `src tests` / `src` | with `tools` |
|---|---|---|
| `ruff check` | 0.97 / 0.86 / 0.88 s | 0.77 / 0.89 / 0.84 s |
| `ruff format --check` | 0.81 / 1.92 / 0.93 s | 0.89 / 0.86 / 0.87 s |
| `mypy --strict`, cold cache | 79.2 / 58.3 / 56.5 s | 60.0 / 58.3 / 57.4 s |

Three cold runs each, and in none of them is the wider check reliably slower — the
run-to-run spread of the *same* command (56.5 to 79.2 s for `mypy src`) is twenty times any
difference between the two commands. The reason is structural rather than lucky: the cost is
the third-party graph — pydantic, numpy, typer — which `src` already imports and `tools/`
merely reuses. Eighteen more files takes the type check from 87 analysed to 105.

**And the path lists become one declaration each.** `CHECKED_PATHS` and `TYPED_PATHS` in
`tools/verify.py` are what the plan reads, and `tests/test_verify_ladder.py` now asserts that
the workflow's lint job names the same paths. That comparison did not exist: the ladder test
compared *which* gates ran and never *what they read*, so adding `tools/` to the plan alone
would have left CI checking less than the local loop and passed every test in the file. It is
ADR-0059's defect one level down, and the fix is the same shape — compare the two callers
rather than trust them.

## Alternatives Considered

- **Add `tools/` to the gates without `py.typed`.** Rejected: 73 of the 184 errors are the
  missing marker, and `mypy` cannot be made to see through it from the consumer side except
  by `--ignore-missing-imports`, which would switch off the checking this item exists to turn
  on. The marker is also the right change on its own merits, independent of `tools/`.
- **`py.typed` alone, and leave `tools/` unchecked.** The cheap half. Rejected because it
  fixes the *cause* of 148 errors and gates none of them: the directory would still be
  reviewed and nothing else, and the marker's own correctness would go unproven — which is
  the next point.
- **A `[[tool.mypy.overrides]]` block silencing `tools/`.** Rejected for what it would mean:
  the eighteen files that decide which gates run would be the only Python in the repository
  exempt from the gates.
- **Type-check `tests/` in the same change.** Measured rather than assumed:
  `mypy --strict tests` reports **81 errors in 24 of 66 files**, and unlike `tools/` they are
  not one cause — 22 `arg-type` and 12 `union-attr` from deliberate test-time looseness,
  7 `import-not-found` from the `conftest`/`fakes` path insertion, 8 `unused-ignore`. That is
  a different proposition needing its own argument about how strict a test file should be, so
  it is filed as **6.9** with the number rather than folded in here.
- **Leave `consistency_lint.py` alone because EADOS generated it.** Rejected on the
  contract's own terms: ADR-0003 records that this repository governs itself and is never
  re-rendered by a later EADOS, so a generated file is this project's file. 4.43 names it
  explicitly.
- **Annotate with `Any` where inference was hard.** Rejected wherever the real type was
  knowable, which was everywhere. The one deliberate `Any` is `Select` in
  `measure_vector_index.py`, a `Callable` alias over numpy arrays whose shapes are not in
  the stubs.

## Consequences

- **Consumers get types.** `pip install mycelium-os` now advertises them (PEP 561), which the
  1.0 freeze (6.1) would have had to do anyway. Verified in both artifacts rather than
  assumed from a packaging default: `mycelium/py.typed` in the wheel,
  `mycelium_os-0.3.0/src/mycelium/py.typed` in the sdist, with **no `pyproject.toml`
  change** — hatchling ships package data for a `packages = ["src/mycelium"]` layout by
  default.
- **The marker's absence would now fail by name.** `tests/test_smoke.py` asserts it, because
  the failure mode it had was the worst kind: no build error, no test failure, and a flood of
  unrelated errors for whoever type-checked a consumer.
- **`tools/` is checked and clean**: `ruff check`, `ruff format --check` and `mypy --strict`
  all pass across `src`, `tests` and `tools`, locally and in CI, at `code` mode and above.
- **Two real findings came out of annotating, neither of them a typing nuisance.**
  `consistency_lint.py` called `max(versions, key=semver_tuple)` in two places, and that key
  returns `None` for a string carrying no version — one unparseable entry would have compared
  `None` against a tuple and crashed the whole lint. Unreachable today, because both lists
  are built from a regex that guarantees the shape; `newest()` now states the invariant
  instead of relying on it. And two functions reused one local name for two types —
  `measure_chunking.py`'s `after` (chunks, then anchors) and
  `build_ingested_cases.py`'s `path` (a `Path`, then a `str`) — which type-checked as nothing
  and read as continuations of the loops above them.
- **One vocabulary stopped being spelled twice.** `AgentTask.kind`'s
  `Literal["answer", "locate", "relate"]` was inlined in the record and again as `str` in the
  generator's tuple types, so a typo there produced a plain string that failed only at
  construction. It is now `mycelium.eval.tasks.TaskKind`, imported by the generator — the
  same defect shape ADR-0070 found in the field weights, arriving in a different package on
  the very next PR.
- **A step in the plan is no longer free to disagree with CI.** The ladder test compares the
  three path lists, verified by mutation: dropping `tools` from either side fails it with the
  names of both lists.
- **And CI found one thing the local loop could not**, which is worth more than the line it
  cost. `tools/build_ingested_corpus.py` imports `typst` behind a `try/except ImportError`
  that names the install command, and `typst` is declared *nowhere* — not a dependency, not an
  extra — because it is a generator-only tool a maintainer installs by hand to re-render the
  PDF fixtures. So it is present on a machine that has rendered them and absent everywhere
  else. `mypy --strict tools` passed here and failed in CI on that one import.

  It is the sixth entry in an `ignore_missing_imports` list that already held five guarded
  optional imports for the same reason, and it was missing only because nothing type-checked
  `tools/`. Verified under CI's condition rather than mine, by hiding the installed package
  from mypy and re-running.

  The general point is a correction to `verify.py`'s own promise — *"a contributor who passes
  the local loop cannot then be told something new by CI"*. That holds for **what** runs,
  which ADR-0059 and this ADR make checkable, and it does not hold for the **environment** it
  runs in: an optional dependency present locally can hide a CI failure, and no amount of
  comparing the two plans will catch it. The docstring's other half is the one that applies —
  *let CI be the authority on the rest* — and this is a real instance of it rather than a
  hypothetical.

- **`consistency_lint.py` gained a `TypedDict`.** The EADOS `CONFIG` block was
  `dict[str, object]` by inference, which made `CONFIG["version_file"].split("/")` an error
  and every other read an `Any`; four lines of declaration are what let the ten checks below
  it be analysed at all.

## References

- PEP 561 — distributing and packaging type information.
- Measured this session: `ruff check tools` 2 errors; `mypy --strict tools` 184 → 109 → 0;
  three cold `mypy` pairs and three `ruff` pairs, tabulated above; `mypy --strict tests` 81
  errors in 24 files (filed as 6.9); `py.typed` present in the wheel and the sdist.
- [ADR-0055](0055-run-the-gates-the-change-implicates.md) — the ladder, and the rule that a
  rung is priced.
- [ADR-0059](0059-make-the-plan-one-implementation-too.md) — the plan is one implementation
  with two callers, which this extends from *which gates* to *what they read*.
- [ADR-0004](0004-adopt-pydantic-v2-record-contracts.md) — the typed record contracts the
  marker finally advertises.
