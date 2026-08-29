#!/usr/bin/env python3
"""Tests for the EADOS pre-flight self-check (#223) — the checklist is DERIVED from the specs (so it
cannot rot from the rules it front-runs), advisory, complete, and dependency-free.

    python .eados-core/tools/tests/test_self_check.py
"""

import contextlib
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import self_check as sc  # noqa: E402  (the module under test)


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def main():
    failures = []
    authority, git = sc._load(sc.AUTHORITY), sc._load(sc.GIT)
    interaction = sc._load(sc.INTERACTION)
    items = sc.preflight_checklist(authority, git, interaction)
    qs = " | ".join(q for q, _ in items)
    srcs = " | ".join(s for _, s in items)

    # --- shape: a short, sourced, advisory checklist -------------------------
    check("the checklist has 5–8 items", 5 <= len(items) <= 8, failures)
    check("every item carries a question and a source", all(q and s for q, s in items), failures)

    # --- each item is derived from (or cited to) its source of truth ---------
    check("an ownership item is sourced from authority.ownership_map",
          "ownership_map" in srcs and "own" in qs, failures)
    check("a one-PR item is sourced from git.commit", "one_pr_at_a_time" in srcs, failures)
    check("a PR-metadata item names the real git.pr.metadata fields",
          "pr.metadata" in srcs and "assignee=owner" in qs, failures)
    check("a cross-links item names the real git.pr.required_crosslinks",
          "required_crosslinks" in srcs and "rfc" in qs and "milestone" in qs, failures)
    check("the human draft/PR boundary item is present", "opens and merges" in qs, failures)
    check("English-on-disk is cited to AGENTS.md §2", "AGENTS.md §2" in srcs, failures)
    check("the precedence invariant is cited", "Precedence" in srcs, failures)

    # --- the interaction contract is front-run (M17 17.4, #280): the operative rules re-asserted,
    #     sourced from the real interaction spec + AGENTS.md §10 ------------------
    check("the interaction item re-asserts the operative rules (calibrate / dissent template)",
          "calibrate" in qs and "dissent template" in qs, failures)
    check("the interaction item is sourced from the interaction spec + AGENTS.md §10",
          "interaction:" in srcs and "AGENTS.md §10" in srcs, failures)
    # Derived, not hardcoded: the source names the blocks the spec actually declares — a renamed
    # block surfaces here rather than rotting (mirrors the git-metadata derivation proof below).
    fake_ix = {"confidence": {"levels": ["x"]}, "dissent": {"template": "t"}}  # sycophancy/pushback absent
    ix_src = " | ".join(s for _, s in sc.preflight_checklist({}, {}, fake_ix))
    check("the interaction source names the blocks the spec declares (derived)",
          "confidence" in ix_src and "dissent" in ix_src and "sycophancy" not in ix_src, failures)
    # Absent spec -> the item is dropped (it depends on 17.2's contract existing, like every other
    # spec-sourced item), so the two cited invariants remain the floor.
    check("without the interaction spec the interaction item is dropped",
          not any("interaction:" in s for _, s in sc.preflight_checklist(authority, git, None)), failures)

    # --- derivation proof: a NEW field added to the git spec flows straight through, nothing is
    #     hardcoded (mirrors the #221 fake-authority-terminus proof) -----------
    fake_git = {"commit": {"one_pr_at_a_time": True},
                "pr": {"metadata": {"assignee": "owner", "reviewer": "the-council"},
                       "required_crosslinks": ["rfc"], "opened_by": "human"}}
    fq = " | ".join(q for q, _ in sc.preflight_checklist({"ownership_map": []}, fake_git))
    check("a metadata field added to git.yaml appears in the checklist (derived, not hardcoded)",
          "reviewer=the-council" in fq, failures)

    # --- a spec that is empty simply drops its sourced items (advisory, never a crash) ---
    minimal = sc.preflight_checklist({}, {})
    check("with no specs the checklist still yields the two cited invariants",
          any("AGENTS.md §2" in s for _, s in minimal)
          and any("Precedence" in s for _, s in minimal), failures)

    # --- the formatter + CLI: an advisory header, one checkbox per item, exit 0 ---
    lines = sc.format_checklist(items)
    check("format_checklist emits the advisory header", any("advisory" in ln for ln in lines), failures)
    check("format_checklist renders one checkbox per item",
          sum(1 for ln in lines if ln.strip().startswith("[ ]")) == len(items), failures)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = sc.main([])
    check("main() exits 0 (advisory, changes nothing)", rc == 0, failures)
    check("main() prints the checklist", "pre-flight self-check" in buf.getvalue(), failures)

    if failures:
        print("test-self-check: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} self-check invariant(s) broken.")
        return 1
    print("test-self-check: OK — the pre-flight checklist is spec-derived, advisory, and complete (#223).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
