# 2026-09-14 — a template is code: render it (roadmap 6.2)

- **Session scope:** roadmap 6.2 — the docs site and the plugin cookiecutter.
- **PR:** `feat/docs-site-and-plugin-cookiecutter`, following #146 (roadmap 6.1, merged
  as `5e2d524`).
- **Milestone 6:** 6.1 and 6.2 delivered; 6.3–6.13 open (6.13 filed this session).
- **Decision it records:** [ADR-0115](../../../adr/0115-render-the-plugin-cookiecutter-to-check-it-and-link-out-instead-of-duplicating.md).

## What the item actually asked for, versus what existed

Spec 06 §Phase 4 names four things: a tutorial, how-tos, a plugin-author guide, a
plugin cookiecutter. Nothing in the repository built any of them before today — no
`mkdocs.yml`, no `docs-site/`, no generator. The AGENTS.md quality bar has carried
*"API docs: mkdocs-material builds without warnings"* as a row since it was written,
and nothing had ever run that build.

## Two decisions the sentence did not answer

**Where does new content sit next to the ADRs, the spec and the pattern catalogue that
already live in `docs/`?** Answered by *linking out*, not duplicating: `docs-site/`'s
own pages are content that exists nowhere else — a tutorial walked against the real CLI
signatures, task-oriented how-tos, the plugin contract — and a `project.md` page points
at everything canonical on GitHub instead. This is ADR-0072's restatement argument read
in the opposite direction: that ADR excluded `docs/changelog` from the corpus because it
*restates* what the ADRs already say; the docs site's pages are not a restatement of
anything, which is the reason they are written rather than copied.

**Which of the four plugin Protocols does a "plugin-author guide" actually cover?**
Checked against the registry rather than the spec's sketch: `Connector` and `Parser`
resolve through `mycelium.plugins`, `Module` through `mycelium.modules`, and
`Synthesizer` — despite being a real, frozen Protocol in `mycelium.sdk.protocols` —
has no entry-point path at all. `mycelium.synthesis.build_synthesizer` resolves exactly
the built-in `wiki` and `[synthesis] plugin` refuses every other name. The guide and the
cookiecutter both cover the three that work and say, by name, why the fourth does not.
Offering a `synthesizer` kind would have generated a complete, correct, entirely
unusable package.

## A template is code, and it found bugs by being run

The cookiecutter was built to the same standard the rest of this repository holds a
generator to: render it, check the output, never trust the source. That discipline
caught three real defects before this ever reached a plugin author:

1. Two docstrings — one explaining the substitution mechanism, one explaining why the
   design avoids a shared conditional file — happened to contain the literal text
   `{{ }}` and `{% if %}`. Cookiecutter renders every file through Jinja, hooks
   included, so both were `TemplateSyntaxError`s at generation time, not merely odd
   reading.
2. Three implementations wrote `api_min={{ cookiecutter.mycelium_api_min }}` outside a
   string literal. Python's grammar reads unrendered `{{x}}` as a set containing a
   set, so this parsed — with an undefined name inside it — and would have surfaced
   only as a runtime `NameError` on the *original*, un-rendered template file, never
   caught by looking at it. Fixed by wrapping every non-string substitution in
   `int("...")`, keeping every Jinja placeholder inside a string.
3. Running `mypy --strict` against a rendered project under pytest's `tmp_path` (on
   `C:`) while this repository's own config sits on `D:` raised a `ValueError` inside
   `mypy`'s own exclude-matching — this repository's `pyproject.toml` was being found
   by directory-walk, and its exclude regex for the *template* directory computed a
   path relative to a drive the rendered project was never on. Fixed by pointing
   `mypy` at the rendered project's own `pyproject.toml` with `--config-file`, which is
   also the right thing to do independent of the bug: a rendered plugin should be
   checked against its own configuration, not its generator's.

None of these would have been caught by reading the template, because template files
are prose to a human reader and code to Jinja. `tests/test_plugin_cookiecutter.py`
renders all three kinds and runs `ruff`, `ruff format --check`, `mypy --strict`, a
runtime Protocol check, and the rendered project's own test suite against each.

## What else moved

`docs-site/` joins `mycelium.toml`'s exclude list, provisionally — filed as 6.13 rather
than decided here, because whether new, non-restating documentation should join this
repository's own corpus is a measured decision on its own terms, not a default this PR
gets to set as a side effect of writing the content. `tools/verify.py` gains an
`mkdocs build --strict` step at the `docs` tier, so every mode runs it; CI gains a
`docs` job that, unlike `lint` and `build`, runs even on a documentation-only change —
that is exactly the change most likely to break the site.

## Lesson

A cookiecutter template is not documentation of what a plugin should look like; it is
a program whose output is a package, held to the same bar as any other generator in
this repository. Reading it for correctness is reading the wrong artifact — Jinja
reads it, and Jinja does not know what a docstring is.
