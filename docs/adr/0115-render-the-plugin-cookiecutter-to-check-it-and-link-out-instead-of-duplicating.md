# ADR-0115: Render the plugin cookiecutter to check it, and link the docs site out to canonical content instead of duplicating it

- **Status:** Accepted
- **Date:** 2026-09-14
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 06 §Phase 4
- **Related:** [ADR-0114](0114-freeze-the-five-contracts-as-goldens-and-publish-the-promise-before-the-tag-that-binds-it.md)
  (`docs/compatibility.md`, which the docs site links to rather than restates),
  [ADR-0086](0086-declare-the-module-facing-surface-and-refuse-to-freeze-it-from-one-consumer.md)
  (`MODULE_SURFACE`, which the plugin-author guide points at rather than restates),
  [ADR-0072](0072-keep-our-own-restatements-out-of-our-own-benchmark.md) (the
  restatement argument this docs-site exclusion deliberately does *not* make),
  [ADR-0012](0012-adopt-the-g6-determinism-gate.md) (the render-then-check discipline
  this borrows); spec 05 §§4.1, 4.4, spec 06 §Phase 4; D-012, D-026, D-029; roadmap 6.2

## Context

Spec 06 §Phase 4 scopes Milestone 6's docs site as four things: a tutorial, how-to
guides, a plugin-author guide, and a plugin cookiecutter. Three decisions were not
obvious from that sentence.

**Where does the site's content live relative to the ADRs, the spec and the pattern
catalogue, all of which already live in `docs/`?** D-029 answers the *hosting* question
— "`mycelium-docs` may host the docs-*site* build at most; canonical content stays
in-repo" — but not the *authoring* one: whether the site's own pages restate the
architecture and decisions, or send a reader to them.

**Is a cookiecutter template that looks right enough to ship, or does it need to be
rendered and checked like any other code this repository produces?** Every other
generator in this repository (`build_ingested_cases.py`, `update_journal_index.py`,
`update_contract_goldens.py`) is checked against its own output. A template is a
generator whose product is a whole Python package, and it is unusually easy to get
subtly wrong: cookiecutter renders **every** file in the template through Jinja,
including hooks, so a docstring can contain what looks like harmless prose and is
actually invalid template syntax.

**Which of spec 05 §4.1's four plugin Protocols does a "plugin-author guide" and a
generator actually cover?** Two of them — `Connector` and `Parser` — resolve through
`mycelium.plugins`. `Module` resolves through the second entry-point group,
`mycelium.modules`. The fourth, `Synthesizer`, is declared in
`mycelium.sdk.protocols` and sketched in spec 05 §4.1's example — and
`mycelium.synthesis.build_synthesizer` resolves exactly the built-in `wiki` plugin,
with `[synthesis] plugin` refusing every other name outright. There is no
entry-point lookup for a third-party `Synthesizer` anywhere in the code.

## Decision

**The docs site links out to canonical content; it does not duplicate it.** `project.md`
is a page of links to the README, the specification, RFC-0001, the ADR index, the
pattern catalogue, `docs/compatibility.md`, the threat model, the roadmap and the
journal — all on GitHub, all pointed at `main`. The site's own pages (tutorial, how-tos,
plugin-author guide) are content that does not exist anywhere else in the repository:
walkthroughs against the real CLI and MCP surfaces, task-oriented instructions, and a
synthesis of the plugin contract for a reader who is about to write code. This is the
opposite call from ADR-0072's, on purpose: ADR-0072 excluded `docs/changelog` and
`docs/releases` from the corpus because they *restate*, in the same vocabulary, facts
the ADRs and the roadmap already state canonically; the docs site's pages are not a
restatement of anything, and the parts of it that would be (the ADRs, the spec) are
links instead of copies.

**The plugin-author guide and the cookiecutter cover exactly the contracts a plugin can
be resolved as today: `Connector`, `Parser`, `Module`.** `Synthesizer` is documented as
a gap, by name, rather than silently omitted or offered as if it worked: the guide
states plainly that a class satisfying it today loads nowhere, because the registry has
no path to it. Offering a `synthesizer` cookiecutter kind would generate a complete,
correct, entirely unusable package — worse than not offering it, because it looks like
it should work.

**The cookiecutter's own tests render it and check the output, never the template.**
`tests/test_plugin_cookiecutter.py` renders each of the three kinds with
`cookiecutter`'s Python API, then runs this repository's own `ruff`, `ruff format
--check` and `mypy --strict` against the rendered package, imports it and checks
Protocol conformance at runtime, and runs the rendered package's own generated test
suite as a subprocess. `ruff`/`mypy` are excluded from ever reading the template
directory itself (`tools/cookiecutter-mycelium-plugin` is untypeable, unrenderable
Python containing directory names like `{{cookiecutter.project_slug}}`): what is
checked is what the template *produces*, the same standard this repository holds every
other generator to.

**One contract file per plugin kind, chosen by a `post_gen_project` hook — never a
bare `{% if %}` inside a shared file.** Three complete implementations
(`_parser.py`, `_connector.py`, `_module.py`) ship in the template; the hook renames
the operator's chosen one to `plugin.py` and deletes the other two, after the
Jinja-rendered `pre_gen_project` hook has already refused an id that violates spec
05 §4.4's naming rule (kebab-case, one or two words, no reserved word, no technology
suffix) and left nothing behind. Every file in the template is therefore either plain
prose/config with `{{ cookiecutter.* }}` substitutions inside string or TOML values, or
one of three complete, independently syntax-checkable Python files — never a
conditional block that would stop being valid Python between one render and the next.

**Building the render-then-check suite found three defects a code-review pass would
plausibly have missed, and all three are recorded as the reason to keep this
discipline rather than relax it:**

1. Two docstrings contained bare Jinja syntax that was never meant as a template
   directive — `` `{{ }}` `` describing the substitution mechanism itself, and
   `` `{% if %}` `` describing why the design avoids one — and cookiecutter renders
   hook files through Jinja before running them, so each raised a
   `TemplateSyntaxError` at generation time rather than merely reading oddly.
2. `_module.py`, `_parser.py` and `_connector.py` originally wrote
   `api_min={{ cookiecutter.mycelium_api_min }}` outside a string literal — valid to a
   human skimming it, and parsed by Python's grammar as a set-of-a-set literal
   containing an undefined name, which only `mypy` (had the template been checked
   directly rather than excluded) or a render would have caught. Fixed by wrapping
   every non-string substitution in `int("...")`.
3. Running `mypy --strict` against a rendered project from a test whose `tmp_path`
   sits on a different Windows drive letter than the checkout raised a `ValueError`
   inside `mypy`'s own exclude-pattern matching — this repository's top-level
   `pyproject.toml` config was being discovered by directory-walk and its `exclude`
   regex for the *template* directory computed a path relative to a drive the
   rendered project was never on. The fix is `--config-file <rendered>/pyproject.toml`,
   pointing `mypy` at the generated project's own configuration rather than letting it
   find this repository's.

## Alternatives Considered

- **Embed the ADRs, the spec and the pattern catalogue into the mkdocs nav** (via a
  `gen-files`/`literate-nav` plugin pair, or plain copies). Rejected: it is exactly the
  restatement ADR-0072 measured and refused, at higher cost — every ADR would need
  re-authoring or re-formatting for a second renderer, and D-029 already settles that
  canonical content stays in-repo. Two mkdocs plugins (`mkdocs-gen-files`,
  `mkdocs-literate-nav`) were added to the dependency group and then removed once a
  single hand-written `reference/sdk.md` page with four `:::` directives proved
  sufficient for `mycelium.sdk`'s four modules — simpler, and nothing to keep in sync
  with a directory listing.
- **Offer `synthesizer` as a fourth cookiecutter kind, with a note that it "isn't wired
  up yet."** Rejected: a generated package that imports cleanly, satisfies the
  Protocol, and loads nowhere is a worse outcome than not offering the choice, and a
  note easily unread is not a substitute for the choice never being presented.
- **Keep the naming-rule check as documentation only** (state the rule in the guide,
  trust the reader). Rejected on this project's standing rule that a claim without a
  check is a claim: the `pre_gen_project` hook is the same rule enforced before a line
  of code exists, at the one moment refusing is free.
- **Lint and type-check the template directory directly, with inline `# noqa` /
  `# type: ignore` scattered through Jinja-templated lines.** Rejected: it would still
  not catch a Jinja `TemplateSyntaxError`, which is the failure mode that actually
  occurred twice while building this, and it would litter three implementation files
  with suppressions for a directory nothing imports.
- **Skip the docs job in CI for a documentation-only change**, matching `lint` and
  `build`'s existing mode gate. Rejected: the whole reason to build the site in CI is
  that a docs-only PR is exactly the PR most likely to break it, and skipping it there
  would defeat the point; the cost this accepts for such a PR (one `uv sync`) is stated
  in the workflow rather than hidden.

## Consequences

- **The docs site cannot drift from the code it documents in the way a hand-written
  wrapper could**: the SDK reference is generated from `mycelium.sdk`'s own docstrings,
  and CI fails if a docstring or a public name it points at goes missing.
- **A plugin author who reads the guide will not attempt to ship a `Synthesizer`
  plugin and wonder why nothing loads it** — the gap is named, with the reason, in the
  same paragraph that lists what does work.
- **The cookiecutter is a tested artifact, not a hand-verified one.** Its own test
  suite (30 cases) is the render-then-check loop: naming refusals, file survival per
  kind, `ruff`, `ruff format --check`, `mypy --strict`, Protocol conformance, and the
  rendered project's own tests, for all three kinds.
- **`docs-site/` is excluded from this repository's own corpus, provisionally** — filed
  as its own item (roadmap 6.13) rather than decided here, because whether new,
  non-restating documentation should join the corpus is a measured corpus decision on
  this project's own terms (ADR-0072's precedent), not a default this PR gets to set as
  a side effect of writing the content.
- **A residual cost, named rather than hidden**: the new `docs` CI job runs
  unconditionally, including for a documentation-only pull request that today pays no
  toolchain cost at all. It is accepted rather than measured away; if it is ever priced
  and found not worth it, `tools/verify.py`'s own economy argument (ADR-0055) is the
  standard to re-measure it against.

## References

- `.draft-specs/06-roadmap-and-governance.md` §Phase 4 — the docs-site scope.
- `.draft-specs/05-interfaces-and-plugins.md` §§4.1, 4.4 — the plugin Protocols and the
  naming rule the cookiecutter enforces.
- The site: `mkdocs.yml`, `docs-site/`. The cookiecutter:
  `tools/cookiecutter-mycelium-plugin/`. The tests:
  `tests/test_plugin_cookiecutter.py`.
- Re-runnable: `uv run mkdocs build --strict`;
  `uv run cookiecutter tools/cookiecutter-mycelium-plugin` (interactive), or with
  `--no-input plugin_kind=parser plugin_id=my-thing description="..."` for a
  non-interactive render.
