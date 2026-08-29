#!/usr/bin/env python3
"""Issue #150 — authoring languages are asked, not silently defaulted. Pins: Q4.7 is the
unconditional authoring-languages question (doc + comment language + i18n chained from naming
targets); the manifest carries language.comment_lang; render defaults both to `en` with NO
behavioural change (the generated AGENTS.md §2 stays the plain English-only rule); a non-English
choice renders an explicit "Recorded exception" block naming the language; ADR-0016 records the
model. Dependency-free (stdlib + the sibling render module).

    python .eados-core/tools/tests/test_authoring_language.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
EADOS = os.path.dirname(TOOLS)
ORCH = os.path.join(EADOS, "orchestrator")
sys.path.insert(0, TOOLS)
import render   # noqa: E402

AGENTS_TMPL = os.path.join(EADOS, "templates", "AGENTS.md.tmpl")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def render_agents(manifest):
    scalars, flags, sections = render.build_context(manifest)
    errors = []
    out = render.render(read(AGENTS_TMPL), scalars, flags, sections, None, "AGENTS.md.tmpl", errors)
    return out, errors, flags


def main():
    failures = []

    # --- Q4.7 is the unconditional authoring-languages question -------------
    q = render.load_yaml(read(os.path.join(ORCH, "questionnaire.yaml")))
    phase4 = next((p for p in q.get("phases", []) if p.get("id") == 4), {})
    q47 = next((qq for qq in (phase4.get("questions") or [])
                if isinstance(qq, dict) and qq.get("id") == "Q4.7"), None)
    check("Q4.7 exists", q47 is not None, failures)
    if q47:
        sets = q47.get("sets") or []
        check("Q4.7 sets DOC_DEFAULT_LANG", "DOC_DEFAULT_LANG" in sets, failures)
        check("Q4.7 sets CODE_COMMENT_LANG (the new comment-language axis)",
              "CODE_COMMENT_LANG" in sets, failures)
        check("Q4.7 still chains i18n (IF_I18N + DOC_LANGS)",
              "IF_I18N" in sets and "DOC_LANGS" in sets, failures)
        check("Q4.7 has no ask_when gate (asked unconditionally)", "ask_when" not in q47, failures)
        dflt = q47.get("default") or {}
        check("Q4.7 defaults: doc=en, comments=en, i18n off",
              dflt.get("DOC_DEFAULT_LANG") == "en" and dflt.get("CODE_COMMENT_LANG") == "en"
              and dflt.get("IF_I18N") is False, failures)

    # --- default (en/en): byte-identical behaviour, no exception blocks -----
    base = {"language": {}, "i18n": {}}
    out, errors, flags = render_agents(base)
    check("default build_context: CODE_COMMENT_LANG == en",
          render.build_context(base)[0].get("CODE_COMMENT_LANG") == "en", failures)
    check("default flags: no non-English exception",
          flags.get("IF_COMMENT_LANG_NONEN") is False and flags.get("IF_DOC_LANG_NONEN") is False,
          failures)
    check("default §2 keeps the plain English-only rule", "written in English" in out, failures)
    check("default §2 renders NO exception block", "Recorded exception" not in out, failures)

    # --- non-English comment language: an explicit recorded exception -------
    ita = {"language": {"comment_lang": "it"}, "i18n": {}}
    out_it, errors_it, flags_it = render_agents(ita)
    check("comment_lang=it flips IF_COMMENT_LANG_NONEN", flags_it.get("IF_COMMENT_LANG_NONEN") is True,
          failures)
    check("§2 renders the recorded comment-language exception",
          "Recorded exception — comment language" in out_it and "**it**" in out_it, failures)
    check("the exception restates what stays English", "stay\nEnglish" in out_it or "stay English" in out_it
          or "English regardless" in out_it, failures)
    check("English-only headline still present alongside the exception",
          "written in English" in out_it, failures)

    # --- non-English doc language: its own recorded exception ---------------
    doc_it = {"language": {}, "i18n": {"default_lang": "it"}}
    out_doc, _e, flags_doc = render_agents(doc_it)
    check("default_lang=it flips IF_DOC_LANG_NONEN", flags_doc.get("IF_DOC_LANG_NONEN") is True, failures)
    check("§2 renders the recorded documentation-language exception",
          "Recorded exception — documentation language" in out_doc, failures)

    # --- the reference manifest end-to-end (en defaults, no leftovers) ------
    ref = render.load_yaml(read(os.path.join(ORCH, "examples", "reference.yaml")))
    check("reference carries language.comment_lang",
          (ref.get("language") or {}).get("comment_lang") == "en", failures)
    out_ref, errors_ref, _f = render_agents(ref)
    check("reference AGENTS.md render has no unresolved placeholders in §2 area", not [
        e for e in errors_ref if "COMMENT" in e or "DOC_DEFAULT" in e], failures)
    check("reference §2 has no exception block (en defaults)", "Recorded exception" not in out_ref,
          failures)

    # --- manifest template + ADR record --------------------------------------
    tmpl = read(os.path.join(ORCH, "project.yaml.template"))
    check("project.yaml.template carries comment_lang -> {{CODE_COMMENT_LANG}}",
          "comment_lang" in tmpl and "CODE_COMMENT_LANG" in tmpl, failures)
    adr = os.path.join(EADOS, "docs", "adr", "0016-authoring-language-model.md")
    check("ADR-0016 exists and records the recorded-exception model",
          os.path.isfile(adr) and "recorded exception" in read(adr).lower(), failures)

    if failures:
        print("test-authoring-language: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} authoring-language invariant(s) broken.")
        return 1
    print("test-authoring-language: OK - Q4.7 asks doc+comment language unconditionally; en defaults "
          "change nothing; non-English choices render recorded exceptions in AGENTS.md §2 (#150).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
