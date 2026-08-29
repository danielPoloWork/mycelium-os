#!/usr/bin/env python3
"""A SHA pin's `# vX.Y.Z` comment must be TRUE of its SHA (#312, ADR-0009).

`action-pins` (#6) compares a pin's SHA *across files*. Nothing checked that the trailing version
comment was true of it. On 2026-07-26 a merge resolved two `ci.yml` lines to `main`'s SHA while
keeping the branch's comment, landing the **v7.0.0** commit under a `# v7.0.1` label (#309/#310).
`main` went red only because the mangling was **non-uniform** and #6 saw the cross-file
disagreement — had it hit every file alike, the gate would have been green over a pin that lied
about its own version, in the one place where that is paid for worst.

So the load-bearing fixture below is the real incident, verbatim: `9c091bb21b…` under `# v7.0.1`.

Two properties beyond "it flags a mismatch", and both are about **not becoming ignorable**: an
annotated tag must be dereferenced to its commit (or the gate cries wolf on every correct pin), and
an unreachable network must produce a stated NOTE — never a red build, and never a silent OK that
implies a verification which did not happen (L-0006).

    python .eados-core/tools/tests/test_pin_label_truth.py
"""

import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import eados_lint as lint      # noqa: E402

# The 2026-07-26 incident (#309/#310), and the truth it violated.
CHECKOUT = "actions/checkout"
V701_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
V700_SHA = "9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"   # what the `# v7.0.1` label actually got


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def stub_gh(responses):
    """A `subprocess.run` stand-in mapping `gh api <path>` to a canned JSON body or an exception."""
    class Done:
        def __init__(self, out):
            self.returncode, self.stdout, self.stderr = 0, out, ""

    def run(argv, **kwargs):
        path = argv[-1]
        body = responses.get(path)
        if body is None:
            return type("R", (), {"returncode": 1, "stdout": "",
                                  "stderr": "gh: Not Found (HTTP 404)"})()
        if isinstance(body, Exception):
            raise body
        return Done(json.dumps(body))
    return run


def main():
    failures = []

    # --- 1. the pure core: a lying label is caught, a truthful one is not --------------------
    def resolver(action, tag):
        return {"v7.0.1": V701_SHA, "v7.0.0": V700_SHA}[tag], False

    truthful = {(CHECKOUT, "v7.0.1"): {V701_SHA: [".github/workflows/ci.yml"]}}
    problems, unverified = lint.pin_label_problems(truthful, resolver)
    check(f"a truthful pin passes ({problems})", problems == [] and unverified == [], failures)

    lying = {(CHECKOUT, "v7.0.1"): {V700_SHA: [".github/workflows/ci.yml",
                                               ".eados-core/templates/.github/workflows/ci.yml.tmpl"]}}
    problems, _ = lint.pin_label_problems(lying, resolver)
    check("THE INCIDENT: the v7.0.0 commit under a `# v7.0.1` label fails", len(problems) == 1,
          failures)
    if problems:
        msg = problems[0]
        check("...naming both the pinned sha and the tag's real sha",
              V700_SHA[:10] in msg and V701_SHA[:10] in msg, failures)
        check("...naming every file that carries it (uniform mangling is the case #6 misses)",
              "ci.yml" in msg and "ci.yml.tmpl" in msg, failures)
        check("...and warning that `sync_action_pins.py --fix` is the WRONG remedy here",
              "sync_action_pins" in msg, failures)

    # --- 2. an unreachable upstream is a NOTE, never a failure and never a false pass --------
    def offline(action, tag):
        raise RuntimeError("could not run `gh` (is the GitHub CLI installed and on PATH?)")

    problems, unverified = lint.pin_label_problems(truthful, offline)
    check("offline does not fail the run", problems == [], failures)
    check(f"...but is REPORTED as unverified ({unverified})", len(unverified) == 1, failures)
    check("...stating the cause, not just 'skipped'",
          unverified and "gh" in unverified[0], failures)

    # The dangerous shape: offline must not silently vouch for a pin that is in fact a lie.
    problems, unverified = lint.pin_label_problems(lying, offline)
    check("offline never turns a LYING pin into a pass-with-no-word-said",
          problems == [] and len(unverified) == 1, failures)

    # --- 3. tag resolution, including the annotated two-hop --------------------------------
    lightweight = stub_gh({f"repos/{CHECKOUT}/git/ref/tags/v7.0.1":
                           {"object": {"type": "commit", "sha": V701_SHA}}})
    check("a lightweight tag resolves in one hop",
          lint.resolve_tag_commit(CHECKOUT, "v7.0.1", run=lightweight) == V701_SHA, failures)

    tag_obj = "8f8e3ada11ef538d1334b15f863025221ceb6ade"
    annotated = stub_gh({f"repos/{CHECKOUT}/git/ref/tags/v7.0.1":
                         {"object": {"type": "tag", "sha": tag_obj}},
                         f"repos/{CHECKOUT}/git/tags/{tag_obj}":
                         {"object": {"type": "commit", "sha": V701_SHA}}})
    check("an ANNOTATED tag is dereferenced to its commit — otherwise the gate cries wolf on "
          "every correct pin and gets switched off",
          lint.resolve_tag_commit(CHECKOUT, "v7.0.1", run=annotated) == V701_SHA, failures)

    for label, run in (("an unresolvable tag", stub_gh({})),
                       ("a timeout", stub_gh({f"repos/{CHECKOUT}/git/ref/tags/v7.0.1":
                                              subprocess.TimeoutExpired("gh", 30)})),
                       ("gh not installed", stub_gh({f"repos/{CHECKOUT}/git/ref/tags/v7.0.1":
                                                     FileNotFoundError("gh")}))):
        try:
            lint.resolve_tag_commit(CHECKOUT, "v7.0.1", run=run)
            failures.append(f"{label}: resolved to something instead of raising")
        except RuntimeError:
            pass
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{label}: leaked {type(exc).__name__} instead of RuntimeError")

    # --- 4. the cache is a memo, not an authority -------------------------------------------
    calls = []

    def counting(action, tag):
        calls.append((action, tag))
        return V701_SHA

    today = datetime.date(2026, 7, 27)
    store = {}
    get = lint.cached_resolver(resolve=counting, cache=store, today=today)
    check("a cold lookup hits the network", get(CHECKOUT, "v7.0.1") == (V701_SHA, False), failures)
    check("a warm lookup does not", get(CHECKOUT, "v7.0.1") == (V701_SHA, False)
          and len(calls) == 1, failures)
    check("...and records WHEN it was resolved, so it can expire",
          store[f"{CHECKOUT}@v7.0.1"]["resolved_at"] == "2026-07-27", failures)

    later = lint.cached_resolver(resolve=counting, cache=store,
                                 today=today + datetime.timedelta(days=lint.PIN_CACHE_TTL_DAYS + 1))
    later(CHECKOUT, "v7.0.1")
    check("past the TTL the network is asked again — a cache trusted forever would rebuild the "
          "very defect this gate catches, one level up", len(calls) == 2, failures)

    def dead(action, tag):
        raise RuntimeError("offline")

    fallback = lint.cached_resolver(resolve=dead, cache=store,
                                    today=today + datetime.timedelta(days=999))
    sha, stale = fallback(CHECKOUT, "v7.0.1")
    check("an expired entry still answers when upstream is unreachable...", sha == V701_SHA,
          failures)
    check("...flagged as not-re-verified, so the caller must say so", stale is True, failures)
    _, unverified = lint.pin_label_problems(truthful, fallback)
    check(f"...and it does say so ({unverified})",
          any("cached" in u for u in unverified), failures)
    empty = lint.cached_resolver(resolve=dead, cache={}, today=today)
    try:
        empty(CHECKOUT, "v7.0.1")
        failures.append("a cold cache + offline invented an answer instead of raising")
    except RuntimeError:
        pass

    # --- 5. scope: a floating profile tag has no SHA to contradict (ADR-0009 §3) -------------
    floating = "      - uses: actions/setup-go@v5\n      - uses: actions/checkout@master\n"
    check("a floating `@v6`-style pin is not governed by this gate",
          lint.PIN_RE.findall(floating) == [], failures)

    # --- 6. the real tree, driven through the real check ------------------------------------
    # A resolver that agrees with whatever the tree pins — built FROM the tree, so a Dependabot
    # bump does not turn this into a test that needs editing (and therefore gets weakened).
    tree = {}
    for root in (os.path.join(os.path.dirname(TOOLS), "..", ".github", "workflows"),
                 os.path.join(os.path.dirname(TOOLS), "templates", ".github", "workflows")):
        if not os.path.isdir(root):
            continue
        for fn in sorted(os.listdir(root)):
            if fn.endswith((".yml", ".tmpl")):
                for action, sha, tag in lint.PIN_RE.findall(
                        lint.read(os.path.join(root, fn))):
                    tree[(action, tag)] = sha.lower()
    check(f"the real tree has SHA pins to check ({len(tree)})", len(tree) >= 3, failures)

    rep = lint._Reporter()
    lint.check_pin_label_truth(rep, resolve=lambda a, t: (tree[(a, t)], False))
    check(f"the real workflows pass when upstream agrees ({rep.failures})",
          rep.failures == [] and rep.notes == [], failures)

    rep = lint._Reporter()
    lint.check_pin_label_truth(rep, resolve=lambda a, t: ("f" * 40, False))
    check(f"...and every real pin fails against a resolver that disagrees ({len(rep.failures)})",
          len(rep.failures) >= 3, failures)
    check("a disagreeing resolver produces FAILURES, not notes", rep.notes == [], failures)

    rep = lint._Reporter()
    lint.check_pin_label_truth(rep, resolve=dead)
    check("an offline run of the real check fails nothing", rep.failures == [], failures)
    check(f"...and notes every pin it could not verify ({rep.notes})",
          len(rep.notes) == 1 and "NOT verified" in rep.notes[0][1], failures)

    if failures:
        print("test-pin-label-truth: FAIL\n")
        for f in failures:
            print(f"  {f}")
        return 1
    print("test-pin-label-truth: OK — the 2026-07-26 lying pin is caught in every file that "
          "carries it, annotated tags are dereferenced, the cache expires rather than becoming a "
          "second unchecked claim, and an unreachable upstream is stated instead of passing "
          "silently.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
