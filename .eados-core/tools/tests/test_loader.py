#!/usr/bin/env python3
"""Differential test: the hand-rolled manifest loader must agree with a real YAML parser.

EADOS renders with a dependency-free loader (yamlmini.load_yaml, re-exported as render.load_yaml;
#166) so the everyday path needs no third-party deps. This test pins that loader to PyYAML on the
documented supported subset, so a future regression (the kind ADR-0006/0008 were written about)
fails loudly instead of silently corrupting a generated repo. PyYAML is a CI-only dependency;
absent it, the test skips (exit 0).

Two corpora, two jobs (#317):

  * `CASES` / `MUST_RAISE` / `SUBSET_REJECTIONS` — synthetic, and pin the **subset boundary**:
    what the loader promises to read, and what it must reject rather than guess at.
  * `sweep_corpus` — the repository's own tracked YAML, and pins **reality**. Every synthetic case
    was written by someone who already knew what the loader supports, which is precisely the blind
    spot: the two defects this sweep was added for (#315 sequence-root, #316 kebab first key) each
    sat one character outside the synthetic corpus and stayed invisible behind a green gate, live
    on shipped files. A boundary corpus cannot find a construct nobody knew they had.

    python .eados-core/tools/tests/test_loader.py
"""

import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
from yamlmini import load_yaml  # noqa: E402  (the loader under test)
import render  # noqa: E402  (the re-export every caller relies on)

# Each case is idiomatic manifest YAML; load_yaml must equal yaml.safe_load on all of them.
# The previously-silent corruptions (quote escaping, block chomping) are first-class cases.
CASES = [
    # --- the regressions C2 fixes ---
    ("single-quote escaping",      "tagline: 'it''s a developer''s friend'"),
    ("double-quote escaping",      r'objective: "Parse \"key: value\" pairs"'),
    ("double-quote newline+tab",   r'msg: "line1\nline2\tend"'),
    ("block clip |",               "note: |\n  a\n  b\n"),
    ("block strip |-",             "note: |-\n  a\n  b\n"),
    # `|+` keep-chomping is intentionally out of the guaranteed subset (see render.py header).
    # --- core subset that must keep agreeing ---
    ("plain string",               "name: pbr-cpp-memory-pool"),
    ("string with colon value",    "url: http://example.com:8080/path"),
    ("comma-bearing plain scalar", "tier1: Linux x86_64, Windows x86_64, macOS arm64"),
    ("int",                        "coverage_target: 80"),
    ("bool true/false",            "bench: true\nthreading: false"),
    ("null forms",                 "a: null\nb: ~\nc:"),
    ("quoted empty",               'secondary_lang: ""'),
    ("at-sign quoted",             'assignee: "@me"'),
    ("flow list",                  "scopes: [api, build, tests, docs, ci]"),
    ("flow map in seq",            "matrix:\n  - { os: ubuntu-24.04, toolchain: gcc, preset: debug }\n"),
    ("block seq same indent",      "scopes:\n- api\n- build\n"),
    ("block seq deeper indent",    "scopes:\n  - api\n  - build\n"),
    ("nested mapping",             "language:\n  lang: cpp\n  group_path: it/d4np\n"),
    ("block-style map items",      "matrix:\n  - os: ubuntu-24.04\n    toolchain: gcc\n"),
    # #315: a SEQUENCE-ROOT document. parse_map broke on the first `- ` item and returned {},
    # silently discarding the whole file — live on learning/lessons.yaml, which is exactly this
    # shape. PyYAML reads it fine, so returning {} was a misparse, not a subset boundary.
    ("sequence-root of mappings",  "- id: L-0001\n  scope: global\n- id: L-0002\n  scope: global\n"),
    ("sequence-root of scalars",   "- alpha\n- beta\n"),
    # #316: a block-seq item's FIRST key was probed with `[A-Za-z0-9_]+:`, so a hyphen, dot, space
    # or quote made the whole item degrade to a STRING and silently dropped every continuation
    # line. Only the first key was ever charset-restricted — which is why the key-order case below
    # is the sharpest regression guard of the four: reordering keys is a YAML no-op.
    ("kebab first key in a seq item",  "tiers:\n  - frontier-reasoning: true\n    id: x\n"),
    ("dotted first key in a seq item", "items:\n  - foo.bar: 1\n    id: x\n"),
    ("quoted first key in a seq item", 'items:\n  - "foo": bar\n    id: x\n'),
    ("spaced first key in a seq item", "items:\n  - some text: v\n    id: x\n"),
    # Quoted / colon-bearing keys at mapping level: `partition(":")` kept the quotes ('"foo"') and
    # split `"a: b"` down the middle. `_split_key` applies YAML's real rule instead.
    ("quoted key keeps no quotes",  '"foo": 1'),
    ("quoted key containing ': '",  '"a: b": 1'),
    ("plain key containing a colon", "a:b: c"),
    ("sequence-root after a comment + '---'", "# ledger\n---\n- id: L-0001\n  scope: global\n"),
    ("hash inside quotes",         'hint: "#include <memory_pool.h>"'),
    ("leading '---' tolerated",    "---\nname: acme\n"),
    # A leading UTF-8 BOM (Windows Notepad / PowerShell 5.1 Out-File) is stripped, exactly
    # like PyYAML — before the fix it glued itself to the first key and broke validation.
    ("UTF-8 BOM stripped (utf-8-sig semantics)", chr(0xFEFF) + "name: acme\n"),
    ("UTF-8 BOM before a leading '---'",         chr(0xFEFF) + "---\nname: acme\n"),
    # --- #166 false-positive guards: lines the truncation rejection must NOT fire on ---
    ("apostrophe in a plain scalar",   "desc: the maintainer's own namespace"),
    ("quoted item in a block seq",     'scopes:\n  - "api"\n  - plain\n'),
    ("unbalanced quote/bracket in a block-scalar body",
     'note: |\n  an unclosed "quote and a stray [ bracket\n  are literal here\n'),
]

# Inputs OUTSIDE the supported subset must fail LOUDLY (ValueError), not be silently
# mis-parsed (ADR-0008's "fail loudly" promise). PyYAML also rejects these.
MUST_RAISE = [
    ("multi-document stream", "a: 1\n---\nb: 2"),
    ("document end marker",   "a: 1\n...\n"),
    ("tab indentation",       "root:\n\tchild: 1"),
]

# LEGAL YAML the subset deliberately does not read — the #153 silent-truncation constructs
# (#166): the loader used to keep the first line and silently DROP the rest. It must now raise
# a loud ValueError. PyYAML parses every one of these fine, and the differential section below
# asserts exactly that: the rejection is a conscious subset boundary, never a misparse.
SUBSET_REJECTIONS = [
    ("multi-line double-quoted scalar", 'prompt: "first line\n  and a second"'),
    ("multi-line single-quoted scalar", "prompt: 'first line\n  and a second'"),
    ("wrapped flow sequence",           "sets: [GROUP_PATH,\n  GROUP_DOTTED]"),
    ("wrapped flow mapping",            "matrix: { os: linux,\n  arch: x64 }"),
    ("wrapped flow in a list item",     "steps:\n  - [a,\n    b]\n"),
    # Folded `>` block scalars (#194): parse_map has no `>` branch, so the loader used to skip
    # the body and keep the bare ">" — the #153 silent-truncation class, live in the repo's own
    # `notes: >` profiles. A literal `|` is byte-exact; `>` must now reject loudly, and PyYAML
    # (the differential below) parses every one of these fine, proving it is a subset boundary.
    ("folded scalar > (clip)",   "objective: >\n  a rate limiter\n  with O(1) admission\n"),
    ("folded scalar >- (strip)", "note: >-\n  folded\n  then stripped\n"),
    ("folded scalar >+ (keep)",  "note: >+\n  folded\n  then kept\n"),
    ("folded scalar in a seq",   "objectives:\n  - >\n    fold this item\n"),
    # A sequence item whose value lives on the FOLLOWING lines ("-" alone). parse_list only reads
    # "- <content>", so parse_map swallowed the dash as a KEY and produced {'-': {...}} — the same
    # silent-misparse class, found while fixing #315. Legal YAML; now rejected loudly.
    ("bare-dash item, nested",   "k:\n  -\n    a: 1\n"),
    ("bare-dash item, at root",  "-\n  a: 1\n"),
]

# Documented deviations where load_yaml deliberately differs from PyYAML — asserted
# explicitly because the strict-equality corpus above structurally cannot cover them.
DEVIATIONS = [
    ("leading-zero int stays string", "code: 08540", {"code": "08540"}),
    ("decimal stays string",          "ver: 1.20",   {"ver": "1.20"}),
    ("norway: yes is not bool",       "flag: yes",   {"flag": "yes"}),
    # PyYAML resolves this to datetime.date(2026, 7, 26); yamlmini keeps the string, consistent
    # with its no-coercion rule for decimals and versions (#315 — surfaced by the corpus sweep the
    # moment lessons.yaml started parsing at all).
    ("ISO date stays string",         "date: 2026-07-26", {"date": "2026-07-26"}),
]


# ---------------------------------------------------------------------------
# Corpus sweep (#317) — the synthetic CASES above pin the SUBSET BOUNDARY; this sweeps the
# REPOSITORY'S OWN tracked YAML and pins REALITY. Different jobs, both needed: every synthetic
# case was written by someone who already knew what the loader supports, which is exactly the
# blind spot — the two defects this sweep was written for (#315, #316) each sat one character
# outside the corpus and stayed invisible through a green gate.
# ---------------------------------------------------------------------------

# Divergences the loader makes DELIBERATELY. Not exclusions — the file is still swept in full;
# only the named divergence is normalized away before comparing, with its reason on the record.
# An opaque skip-list would have hidden lessons.yaml exactly as well as no sweep at all.
Y11_TRUE = ("on", "yes", "y", "true")
Y11_FALSE = ("off", "no", "n", "false")
DECLARED_DEVIATIONS = [
    ("YAML 1.1 boolean KEYS", "PyYAML (YAML 1.1) coerces bare keys like `on:` / `yes:` to booleans; "
     "yamlmini keeps them strings — deliberately the YAML 1.2 side, the same 'Norway problem' rule "
     "the module already documents for VALUES. Live on .github/workflows/*.yml (`on:`) and "
     "os/contribution/contribution.yaml (`escalation.on`)."),
    ("ISO dates stay strings", "PyYAML resolves `2026-07-26` to a datetime.date; yamlmini keeps the "
     "string, consistent with its no-coercion rule for decimals and versions. Every consumer "
     "compares, sorts or renders these as text, so one representation end to end avoids a "
     "round trip back to string. Live on learning/lessons.yaml (`date:`)."),
]

# Files whose reading is KNOWN to diverge, each bound to its open defect. The suite stays green so
# this gate can guard everything else, but the binding runs BOTH ways: a file listed here that
# starts AGREEING is itself a failure, so the list cannot quietly outlive the bugs it documents
# (the L-0008 discipline — an assertion that stops asserting must go red, not quiet).
# Empty since #316: the audit's two loader defects are both fixed and every tracked file either
# agrees or is loudly rejected at the documented subset boundary. Keep the mechanism — the next
# defect of this class gets recorded here with its issue, and the sweep will force its removal the
# day the fix lands (a listed file that starts agreeing is itself a failure).
KNOWN_DIVERGENT = {}


def _normalize(node):
    """Apply the DECLARED_DEVIATIONS so both parsers can be compared on everything else:
      * a bool key from PyYAML and its string spelling from yamlmini collapse to one marker;
      * a date/datetime value from PyYAML collapses to its ISO string, which is what yamlmini
        already produces.
    Nothing else about the document is touched — this normalizes the two named divergences, it
    does not exclude any file or any other field."""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k is True or (isinstance(k, str) and k.lower() in Y11_TRUE):
                k = "<y11-true>"
            elif k is False or (isinstance(k, str) and k.lower() in Y11_FALSE):
                k = "<y11-false>"
            out[k] = _normalize(v)
        return out
    if isinstance(node, list):
        return [_normalize(x) for x in node]
    if isinstance(node, (datetime.date, datetime.datetime)):
        return node.isoformat()
    return node


def _tracked_yaml(repo_root):
    """Tracked YAML under .eados-core/ and .github/, via `git ls-files` so a newly added data file
    is covered the moment it is staged (the run-lint-after-`git add` discipline). Returns None when
    git cannot answer — the sweep then reports a skip with the reason rather than a false pass."""
    import subprocess
    try:
        out = subprocess.run(["git", "-c", "core.quotePath=false", "ls-files",
                              ".eados-core", ".github"],
                             cwd=repo_root, capture_output=True, text=True,
                             encoding="utf-8", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return [p for p in (line.strip() for line in (out.stdout or "").splitlines())
            if p.endswith((".yaml", ".yml"))]


def sweep_corpus(repo_root, failures, notes):
    """Compare load_yaml against PyYAML over the tracked corpus. Appends to `failures` / `notes`."""
    import yaml as _yaml
    paths = _tracked_yaml(repo_root)
    if paths is None:
        notes.append("corpus sweep SKIPPED — `git ls-files` unavailable (not a git checkout?); "
                     "no file was compared")
        return
    swept = agreed = rejected = deviated = 0
    stale = []
    for rel in paths:
        full = os.path.join(repo_root, rel)
        try:
            with open(full, encoding="utf-8-sig") as fh:
                raw = fh.read()
        except OSError:
            continue
        try:
            ref = _yaml.safe_load(raw)
        except Exception:  # noqa: BLE001 — not legal YAML at all; not this gate's business
            continue
        swept += 1
        try:
            mine = load_yaml(raw)
        except ValueError as exc:
            # A loud rejection is a PASS: the documented subset boundary, working as designed.
            rejected += 1
            notes.append(f"{rel}: loader rejects (subset boundary) — {str(exc)[:100]}")
            continue
        except Exception as exc:  # noqa: BLE001 — anything else is a crash, and a crash is a bug
            failures.append(f"{rel}: load_yaml raised {exc!r} (expected a parse or a ValueError)")
            continue
        norm_mine, norm_ref = _normalize(mine), _normalize(ref)
        if norm_mine != norm_ref:
            deviated += 1
            if rel in KNOWN_DIVERGENT:
                notes.append(f"{rel}: KNOWN divergence — {KNOWN_DIVERGENT[rel]}")
            else:
                failures.append(f"{rel}: load_yaml disagrees with PyYAML and the divergence is "
                                "neither declared nor a known defect — a silent misparse of a "
                                "governed data file")
        else:
            agreed += 1
            if rel in KNOWN_DIVERGENT:
                stale.append(rel)
    for rel in stale:
        failures.append(f"{rel}: listed in KNOWN_DIVERGENT ({KNOWN_DIVERGENT[rel]}) but now AGREES "
                        "with PyYAML — the defect is fixed, so remove the entry in the same PR; a "
                        "stale known-failure entry hides the next real one")
    notes.append(f"corpus sweep: {swept} tracked file(s) — {agreed} agree, {rejected} loudly "
                 f"rejected (subset boundary), {deviated} known-divergent, "
                 f"{len(DECLARED_DEVIATIONS)} declared deviation(s) normalized")


def main():
    failures = []

    # Loader-only invariants (no PyYAML needed): unsupported input must fail loudly, and the
    # documented deviations from PyYAML must hold exactly (the strict-equality corpus below
    # cannot cover them, since by definition they disagree with PyYAML).
    for label, text in MUST_RAISE + SUBSET_REJECTIONS:
        try:
            load_yaml(text)
            failures.append(f"{label}: expected a loud ValueError, but load_yaml accepted it")
        except ValueError:
            pass
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{label}: expected ValueError, got {exc!r}")
    # #166: the extraction keeps every caller working — render.load_yaml IS yamlmini.load_yaml.
    if render.load_yaml is not load_yaml:
        failures.append("render.load_yaml is not the yamlmini.load_yaml re-export")
    # BOM fix, loader-only (also differentially pinned in CASES when PyYAML is present): the
    # first key must come out clean, and exactly ONE BOM is stripped — a second is content
    # and stays, matching utf-8-sig.
    got = load_yaml(chr(0xFEFF) + "identity: 1")
    if got != {"identity": 1}:
        failures.append(f"UTF-8 BOM not stripped from the first key: got {got!r}")
    got = load_yaml(chr(0xFEFF) + chr(0xFEFF) + "identity: 1")
    if "identity" in got:
        failures.append(f"a double BOM must not be swallowed (one is content): got {got!r}")
    # #316's sharpest guard, asserted directly rather than via the equality corpus: reordering two
    # keys inside a block-seq item is a YAML no-op, so the parse must be identical. It was not —
    # only the FIRST key was charset-checked, so moving a kebab key to the front destroyed the item
    # and every line after it. A defect that a semantically null edit can introduce needs a test
    # that speaks in those terms.
    ordered = load_yaml("tiers:\n  - id: x\n    frontier-reasoning: true\n")
    reordered = load_yaml("tiers:\n  - frontier-reasoning: true\n    id: x\n")
    if ordered != reordered:
        failures.append(f"key ORDER inside a block-seq item changed the parse: "
                        f"{ordered!r} != {reordered!r}")
    if not (isinstance(reordered.get("tiers", [None])[0], dict)):
        failures.append(f"a block-seq item with a kebab first key is not a mapping: {reordered!r}")
    for label, text, expected in DEVIATIONS:
        got = load_yaml(text)
        if got != expected:
            failures.append(f"{label}: load_yaml={got!r} != expected {expected!r}")

    try:
        import yaml
    except ImportError:
        if failures:
            print("test-loader: FAIL\n")
            for f in failures:
                print(f"  {f}")
            print(f"\n{len(failures)} loader-only failure(s).")
            return 1
        print("test-loader: SKIP (differential) — PyYAML not installed; "
              "loader-only checks passed.")
        return 0

    for label, text in CASES:
        try:
            mine = load_yaml(text)
        except Exception as exc:  # noqa: BLE001 — any crash is a failure
            mine = f"<EXC {exc!r}>"
        ref = yaml.safe_load(text)
        if mine != ref:
            failures.append(f"{label}: load_yaml={mine!r} != pyyaml={ref!r}")

    # #166 differential proof for the truncation rejections: each construct IS legal YAML
    # (PyYAML parses it), so silently returning anything would have been a misparse — the
    # loud rejection is the only honest behavior for the subset.
    for label, text in SUBSET_REJECTIONS:
        try:
            yaml.safe_load(text)
        except Exception:  # noqa: BLE001
            failures.append(f"{label}: expected PyYAML to PARSE this (it is legal YAML) — "
                            "the case belongs in MUST_RAISE, not SUBSET_REJECTIONS")

    # End-to-end: the shipped reference manifest must parse identically with both.
    ref_path = os.path.join(ROOT, "orchestrator", "examples", "reference.yaml")
    with open(ref_path, encoding="utf-8") as fh:
        raw = fh.read()
    if load_yaml(raw) != yaml.safe_load(raw):
        failures.append("orchestrator/examples/reference.yaml: load_yaml != pyyaml (deep)")

    # #317: the synthetic corpus pins the boundary; this pins reality.
    notes = []
    sweep_corpus(os.path.dirname(ROOT), failures, notes)

    if failures:
        print("test-loader: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} loader-fidelity divergence(s).")
        return 1
    print(f"test-loader: OK — agrees with PyYAML on {len(CASES)} cases + reference.yaml, "
          f"rejects {len(MUST_RAISE)} unsupported + {len(SUBSET_REJECTIONS)} truncation-class "
          f"inputs, honours {len(DEVIATIONS)} deviations.")
    for note in notes:
        print(f"  {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
