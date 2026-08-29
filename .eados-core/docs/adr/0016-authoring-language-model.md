# ADR-0016: Authoring-language model — confirmed defaults, recorded exceptions

## Status

Accepted (2026-07-01)

## Context

The 2026-06-30 interview-completeness audit (issue #150) found the authoring-language choices were
either hidden or never asked:

- the **documentation language** (`DOC_DEFAULT_LANG`) was only surfaced inside `Q4.7 — translations
  (i18n)`, which defaults **off** — with i18n off, the doc language was silently English;
- the **code-comment / identifier language** was **never asked** — the house rule "all on-disk
  artifacts are English" (`CLAUDE.md` / `AGENTS.md` §2, and the rendered `AGENTS.md.tmpl` §2 of every
  generated repo) hard-coded it as an invisible mandate;
- **extra languages** existed only as i18n doc targets behind the same toggle.

English-only is the right *default* — it is what keeps a family of generated repos navigable by the
same agent and reviewable by the widest audience — but a default the maintainer never sees is a
mandate, not a choice. The audit brief explicitly asks for these to be asked.

## Decision

1. **`Q4.7` becomes the unconditional authoring-languages question.** It states and confirms, for
   every project: the **documentation language** (`DOC_DEFAULT_LANG`, default `en`), the
   **code-comment language** (a new `language.comment_lang` → `{{CODE_COMMENT_LANG}}`, default
   `en`), and any **extra documentation languages** — and naming extra target languages is what
   enables i18n (`IF_I18N` + `DOC_LANGS`), rather than i18n gating the language question. Defaults
   are echoed back for confirmation, never applied silently.

2. **English stays the invariant for the machine-facing surface.** Identifiers, public API names,
   commit messages, branch names, and PR titles/descriptions are English **regardless** of the
   comment/doc choice. This is the cross-project consistency bar EADOS exists to reproduce; it is
   not up for per-project relaxation.

3. **A non-English comment or doc choice is honoured as a *recorded exception*, not a silent
   deviation.** Two derived render flags (`IF_COMMENT_LANG_NONEN`, `IF_DOC_LANG_NONEN`) inject an
   explicit "Recorded exception" block into the generated `AGENTS.md` §2, naming the chosen
   language and restating what stays English. The generated contract therefore always tells the
   agent the truth about the repo it governs — the exception is as visible as the rule.

4. **EADOS itself is unchanged.** The factory's own artifacts remain English-only per its own
   `AGENTS.md` §2; this ADR governs what the *generated* contract offers its maintainer.

## Consequences

- The interview now satisfies the audit: doc + comment language are stated, confirmable, and
  overridable without touching i18n; `project.yaml` carries `language.comment_lang`.
- With every default confirmed (`en`/`en`, no extra languages), the rendered output is
  **byte-identical to before** — the exception blocks collapse to nothing.
- A generated repo with, say, Italian comments carries the decision in its own `AGENTS.md` §2, so
  a future agent neither "corrects" the comments to English nor spreads Italian into identifiers.
- Translation freshness (ADR-0010) is unaffected: `DOC_DEFAULT_LANG` remains the canonical source
  the i18n machinery hashes; only its visibility at intake changed.

## References

- Issue #150 (M12 — interview completeness); `orchestrator/interview.md` Q4.7;
  `orchestrator/questionnaire.yaml`; `templates/AGENTS.md.tmpl` §2; ADR-0010.
