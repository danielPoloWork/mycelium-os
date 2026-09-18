# 2026-09-18 — there was no middle setting (roadmap 6.9)

- **Session scope:** roadmap 6.9 — decide how strict a test file has to be, and type-check
  `tests/` accordingly.
- **PR:** `feat/type-check-tests`, following #158.
- **Milestone 6:** 6.9 delivered. Open: 6.8 (the authoring half), 6.10, 6.12–6.15, 6.17–6.23.
- **Decision it records:** [ADR-0124](../../../adr/0124-check-the-tests-like-the-source-because-there-was-no-middle-setting.md).

## The item framed it as policy, and the switch decided it

6.9 proposed a non-strict `[[tool.mypy.overrides]]` for `tests/` that would still catch the
`type-arg` and `var-annotated` classes. Those two sit on opposite sides of mypy's strictness
switch from where the item placed them, which is the finding that settles the whole question.

`arg-type`, `union-attr`, `attr-defined` and `var-annotated` are mypy's **base** checks. They
are on at every setting, so a non-strict override would have kept every one of the errors the
item called deliberate looseness. What it *would* have switched off is
`disallow_untyped_defs` — and an unannotated function is one whose body mypy does not check at
all. The proposal keeps what it wanted forgiven and forgives what it wanted kept. There is no
useful position between checking the tests and not checking them.

## And the errors were not deliberate invalidity

The item's picture was *"a test that constructs an invalid record on purpose is doing its
job."* Read rather than assumed, almost none of them were that:

- `verified_at="2026-07-31"` where a `date` belongs; `verification_status="verified"` where
  the enum does. pydantic coerces, so the tests passed while asserting against a coerced
  value.
- `settings.default.deadline` on a `settings | None`, six times. With no profile loaded those
  tests raise `AttributeError` on whichever line comes first rather than saying what is wrong.
- `grammar_for("rs") is not None and grammar_for("rs").language == "rust"` — two calls, the
  second narrowed by nothing.
- A test asserting `here.projection_path is not None` and then indexing
  `there.projection_path`. A real gap in its own narrowing.

Seven sites genuinely are deliberate, and they keep a per-line ignore with a comment. That is
the item's own feared remedy, and it is better than the alternative it proposed: the ignore
sits where the intent is and names it, while a settings file covers every test equally and
explains nothing.

## What only the tests could show

`_gate_g3` declared `baseline: dict[str, object] | None` and only ever read it. `dict` is
invariant, so no caller holding a `dict[str, float]` could pass one without copying — the
correct type is `Mapping`. **Nineteen of the 212 errors were that single parameter.** No
amount of test-side suppression would have found it; checking the callers is what did.

And a product defect, three milestones old: **`mycelium-chats` ships no `py.typed`**. ADR-0071
gave the core its marker at 4.43 precisely so `pip install` advertises the types; the module
became a distribution of its own at 5.5 and never got one. A consumer of it gets no types, and
mypy was skipping thirty errors because it could not see into a package this repository
already type-checks.

## The price, because ADR-0055 asks for one

Two paired cold runs: 69.5 / 55.2 s without the test suites against 60.1 / 56.8 s with. The
run-to-run variance is larger than the difference — the time is the third-party graph these
files already import, not the files. 110 files checked becomes 216. Exactly the result
ADR-0071 measured when it added `tools/`, for exactly the same reason.

## Two mistakes worth recording

Partway through I annotated three helpers by guessing their types from their names rather than
reading their bodies — `by_kind: dict[str, int]` for a dict of lists, `results: list[object]`
for a list of build results, `-> tuple[object, ...]` for a function returning `Verified`. The
error count went *up*, from 59 to 73, which is how I found out. Annotating from the signature
you wish existed is the same error as asserting what you wish were true, and the type checker
catches it just as fast.

The second one the type checker could *not* catch, and the suite did. Narrowing
`get_command(app)` for `.commands`, I asserted `isinstance(group, click.Group)` — which
type-checks, because `TyperGroup` is declared as a `click.Group` subclass, and fails at
runtime here, because the object typer returns is not an instance of the `click.Group` this
process imported. A narrowing assertion is a runtime claim wearing a type annotation's
clothes, and only running it says whether it holds. It is now `TyperGroup`, which is what the
call actually returns.

## Lesson

When an item proposes a setting, check what the setting actually controls before arguing about
whether to use it. Half this decision was already made by which flags mypy puts behind
`strict` and which it leaves on — a fact available before any of the 212 errors were read.
