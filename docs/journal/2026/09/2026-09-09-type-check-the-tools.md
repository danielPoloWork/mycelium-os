# 2026-09-09 — the directory that decides which gates run, checked by nothing (roadmap 4.43)

- **Session scope:** roadmap 4.43 — ship `py.typed`, re-measure, and decide whether `tools/`
  joins the lint and the type check (AGENTS.md §10; ADR-0055/0059).
- **PR:** #94 (`build/type-check-the-tools`). Follows #93 (4.42), merged as `6aac7ff`.
- **Milestone 4:** 4.43 done. 6.9 filed with its measurement.

## The premise held, and drifted upward while it waited

4.40 filed this with numbers: `ruff check tools` = 1 error, `mypy --strict tools` = 184.
Re-measured today, ruff reports **2** — a 109-character line had arrived in `verify.py`'s own
docstring, added by 4.40 itself, in the file that decides which gates a change runs. One new
defect in a week, in the directory nothing checks. That is the item's argument making itself
while the item sat in the backlog.

The 184 had one dominant cause and the item named it correctly. No `py.typed`, so every
`from mycelium…` outside `src/` was `import-untyped` and everything downstream was `Any`.
One empty file removed **73** of them, 184 → 109. Annotating the rest took it to **0**.

## Pricing a rung, because ADR-0055 says rungs are priced

I expected to argue about cost and there was nothing to argue about. Three cold `mypy` pairs:

```
src         79.2 s   58.3 s   56.5 s
src tools   60.0 s   58.3 s   57.4 s
```

The wider check is never reliably slower, and the spread of the *same* command — 56.5 to
79.2 s — is twenty times any difference between the two. The reason is structural rather than
lucky: the time goes into the third-party graph (pydantic, numpy, typer), which `src` already
imports and `tools/` merely reuses. 87 files analysed becomes 105. Ruff is under a second
either way.

So the honest answer to "should `tools/` join `code` mode" is yes, and the interesting part is
that nobody had checked whether it was expensive before assuming it might be.

## What annotating actually found

Three things, and none of them is a typing nuisance.

**A latent crash in the congruence lint.** Two call sites did
`max(versions, key=semver_tuple)`, and that key returns `None` for a string carrying no
version — so a single unparseable entry would compare `None` against a tuple and take the
whole lint down. Unreachable today, because both lists are built from a regex that guarantees
the shape. Unreachable is not impossible, and nothing said so because nothing type-checked the
file. `newest()` now states the invariant.

**Two functions reusing one name for two types.** `measure_chunking.py`'s `after` is the
packed build's *chunks* in one loop and its *anchors* in the next; `build_ingested_cases.py`'s
`path` is a `Path` in one loop and a `str` in the next. Both work. Both read as continuations
of the loop above them, which is the sort of thing that is wrong for five minutes and then
wrong for a year.

**ADR-0070's lesson, one PR later, in a different package.** `AgentTask.kind` is a
`Literal["answer", "locate", "relate"]` in the record and was `str` in the generator's tuple
types, so a typo there produced a plain string that failed only when the record was
constructed. Yesterday's PR found the same shape in the field weights. It is now
`TaskKind`, defined once and imported.

## And a gap in the guard that was supposed to prevent exactly this

Adding `tools/` to `verify.py`'s plan and to the CI workflow are two edits, and I checked
whether anything would catch me doing only one. Nothing would. `tests/test_verify_ladder.py`
exists because ADR-0059 found the plan drifting from CI — but it compares *which* gates run,
never *what they read*. The three path lists live in two files, so adding `tools/` locally and
not in CI would have passed every test in that file while leaving CI checking less than the
local loop.

The path lists are now compared too, and verified by mutation: dropping `tools` from either
side fails with both lists named. The generalisation is uncomfortable and worth writing down —
a guard against duplication is itself duplicated until something compares its two halves.

## And then CI found the thing I could not

The lint job — the one job this PR changes — went red on the first run, on one line:

```
tools/build_ingested_corpus.py:191: error: Cannot find implementation or library stub
for module named "typst"  [import-not-found]
```

`typst` is imported behind a `try/except ImportError` that names the install command, and it
is declared **nowhere**: not a dependency, not an extra, because it is a generator-only tool a
maintainer installs by hand to re-render the PDF fixtures. It is on this machine because I
have rendered them. It is not in CI and cannot be.

The fix is one line — the sixth entry in an `ignore_missing_imports` list that already held
five guarded optional imports for exactly this reason, missing only because nothing
type-checked `tools/`. I verified it under CI's condition rather than mine, by hiding the
installed package from mypy and re-running.

What it costs me is a claim I made earlier in this same session. `verify.py` promises that *"a
contributor who passes the local loop cannot then be told something new by CI"*, and I spent
the afternoon making that more true — comparing the path lists so the two callers cannot
disagree. It holds for **what** runs. It does not hold for the **environment**, and no
comparison of plans will ever catch that: an optional dependency present locally hides a CI
failure, and the more of the toolchain a contributor has installed the more it can hide. The
docstring's other half is the one that applied — *let CI be the authority on the rest*.

## What I did not do

`tests/` stays unchecked, measured rather than waved off: **81 errors in 24 of 66 files**, and
unlike `tools/`'s 184 they are not one cause. Twenty-two `arg-type` and twelve `union-attr`
come from deliberate test-time looseness, seven `import-not-found` from the `conftest` path
trick. A test that constructs an invalid record on purpose is doing its job, and `--strict`
has no vocabulary for that. That is a policy question, not an effort question, so it is filed
as **6.9** with the numbers.

The asymmetry is the reason it can wait: `tools/` had to be checked because nothing else
checks it. `tests/` is executed on every run by the thing it tests.
