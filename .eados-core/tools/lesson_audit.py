#!/usr/bin/env python3
"""lesson_audit — the "never make the same mistake twice" watchdog (#173, M13).

The auto-tuner ([`autotune.py`](autotune.py)) mines run records for *defaults* to change;
this tool mines the same records for the *learning loop's* health and reports three things
— report-only, like autotune, and for the same reasons (versioned data, reviewable proposal,
a human applies it). It never edits anything.

    python .eados-core/tools/lesson_audit.py [--threshold N]

1. **Regression detection.** A run record whose `failures` share keywords with a lesson the
   run was in scope for means the factory violated its own recorded knowledge. Per the
   escalation path (*incident → lesson → gate → meta-gate*) that is the trigger to promote the
   advisory lesson to a mechanical gate.
2. **Dead-lesson report.** A lesson never present in any `lessons_applied` across at least
   `--threshold` runs it was *applicable* to is flagged as dead weight for owner review.
3. **Rubric trending.** A rubric dimension scoring ≤ 1 in the majority of the runs that scored
   it proposes drafting a lesson / filing a factory issue — this mechanizes `eval/rubric.md`
   §4, which today asks the agent to notice recurring low scores from memory alone.

Dependency-free: reuses render.py's YAML loader for the records and record_run.py's canonical
rubric-dimension list, and parses the lessons ledger textually (its root is a YAML sequence,
outside the minimal loader's subset — the same approach as eados_lint's check_lessons).
"""

import argparse
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from render import load_yaml            # noqa: E402  (same-dir tool)
from record_run import RUBRIC_DIMENSIONS  # noqa: E402  (single source for the ten dimensions)

ROOT = os.path.dirname(HERE)            # .eados-core/
RUNS = os.path.join(ROOT, "learning", "runs")
LESSONS_PATH = os.path.join(ROOT, "learning", "lessons.yaml")

# Noise words (≥ 4 chars) dropped from keyword sets so a regression match rests on substantive
# overlap, not grammar. Shorter tokens are dropped by length; distinctive terms survive.
_STOPWORDS = {
    "must", "that", "this", "with", "from", "than", "then", "when", "into", "will",
    "each", "every", "have", "does", "they", "them", "their", "there", "some", "only",
    "also", "been", "over", "under", "both", "which", "where", "would", "could", "should",
    "such", "here", "were", "what", "your", "onto", "whose", "whom", "same", "made",
}
_TOKEN = re.compile(r"[a-z0-9]+")


# ---------------------------------------------------------------------------
# Pure core — no I/O, fixture-testable.
# ---------------------------------------------------------------------------
def keywords(text):
    """The substantive tokens of `text`: lowercased alphanumerics ≥ 4 chars, minus stopwords."""
    return {t for t in _TOKEN.findall(str(text).lower())
            if len(t) >= 4 and t not in _STOPWORDS}


def parse_lessons(text):
    """The ledger's entries as dicts (id/scope/context/rule/…).

    Read through the one loader since #315 taught it sequence-root documents; this used to be a
    regex split because load_yaml returned {} for that shape, and the workaround quietly capped
    what could be read to `[a-z_]+` field names. A malformed ledger degrades to [] rather than
    raising — the auditor is advisory and must not abort a run (the #198 posture)."""
    try:
        entries = load_yaml(text)
    except Exception:  # noqa: BLE001 — data-file-validity owns reporting the syntax error
        return []
    if not isinstance(entries, list):
        return []
    out = []
    for entry in entries:
        if isinstance(entry, dict) and str(entry.get("id", "") or "").strip():
            out.append({k: (v if isinstance(v, str) else str(v)) for k, v in entry.items()})
    return out


def scope_applies(scope, lang, kind):
    """Does a lesson scoped `scope` apply to a run in (lang, kind)? global (or empty) applies
    everywhere; lang:X / kind:Y match the run's field; anything else is conservatively no."""
    scope = (scope or "").strip().strip('"')
    if scope in ("", "global"):
        return True
    if scope.startswith("lang:"):
        return scope[len("lang:"):].strip() == (lang or "").strip()
    if scope.startswith("kind:"):
        return scope[len("kind:"):].strip() == (kind or "").strip()
    return False


def regressions(lessons, records):
    """Runs that failed on ground a lesson already covers. For each record with `failures`, the
    failure text's keywords are matched against every in-scope lesson's `rule`; a non-empty
    overlap is a candidate regression carrying the shared keywords for the human to judge."""
    findings = []
    for rec in records:
        fails = rec.get("failures") or []
        if not fails:
            continue
        lang, kind = rec.get("lang", ""), rec.get("kind", "")
        fail_kw = set()
        for f in fails:
            if isinstance(f, dict):
                fail_kw |= keywords(f.get("gate", "")) | keywords(f.get("message", ""))
        for lesson in lessons:
            if not scope_applies(lesson.get("scope", ""), lang, kind):
                continue
            shared = fail_kw & keywords(lesson.get("rule", ""))
            if shared:
                findings.append({"lesson": lesson["id"], "slug": rec.get("slug", ""),
                                 "date": rec.get("date", ""), "shared": sorted(shared)})
    return findings


def dead_lessons(lessons, records, threshold):
    """Lessons that no applicable run has ever applied. A lesson is judged only against the runs
    it was in scope for (≥ threshold of them), so a kind-scoped lesson is not called dead merely
    because no run of that kind exists yet — that is missing signal, not dead weight."""
    findings = []
    for lesson in lessons:
        lid, scope = lesson["id"], lesson.get("scope", "")
        applicable = [r for r in records
                      if scope_applies(scope, r.get("lang", ""), r.get("kind", ""))]
        if len(applicable) < threshold:
            continue
        if not any(lid in (r.get("lessons_applied") or []) for r in applicable):
            findings.append({"lesson": lid, "scope": scope, "applicable": len(applicable)})
    return findings


def rubric_trends(records, threshold):
    """Rubric dimensions the runs keep scoring low. A dimension whose score is ≤ 1 in a majority
    of the runs that scored it (and in at least `threshold` of them) is a standing weakness that
    eval/rubric.md §4 says to turn into a durable lesson."""
    findings = []
    for dim in RUBRIC_DIMENSIONS:
        scored = [r["rubric"][dim] for r in records
                  if isinstance(r.get("rubric"), dict) and isinstance(r["rubric"].get(dim), int)]
        low = [s for s in scored if s <= 1]
        if len(low) >= threshold and len(low) * 2 > len(scored):
            findings.append({"dimension": dim, "low": len(low), "scored": len(scored)})
    return findings


# ---------------------------------------------------------------------------
# Thin CLI shell.
# ---------------------------------------------------------------------------
def _load_records(runs_dir):
    records = []
    for path in sorted(glob.glob(os.path.join(runs_dir, "*.yaml"))):
        # Report-only: one record outside the loader's subset must not abort the audit with a
        # traceback (these run on bundles / fresh checkouts where the run-records gate may never
        # have run). Skip the file, name it, and keep going (#198).
        try:
            with open(path, encoding="utf-8") as handle:
                rec = load_yaml(handle.read())
        except (OSError, ValueError) as exc:
            print(f"lesson-audit: skipping {os.path.basename(path)}: {exc} "
                  "(run eados_lint run-records to see why)", file=sys.stderr)
            continue
        if isinstance(rec, dict):
            records.append(rec)
        else:
            print(f"lesson-audit: skipping {os.path.basename(path)}: not a YAML mapping "
                  "(run eados_lint run-records)", file=sys.stderr)
    return records


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(
        description="Audit the learning loop: regressions, dead lessons, low rubric trends.")
    ap.add_argument("--threshold", type=int, default=2,
                    help="min runs before a lesson is called dead / a dimension trends low "
                         "(default 2)")
    args = ap.parse_args(argv)

    records = _load_records(RUNS)
    lessons = parse_lessons(open(LESSONS_PATH, encoding="utf-8").read()) \
        if os.path.exists(LESSONS_PATH) else []
    if not records:
        print("lesson-audit: no run records yet — nothing to audit. "
              "(Records accumulate under learning/runs/ as projects are generated.)")
        return 0

    regs = regressions(lessons, records)
    dead = dead_lessons(lessons, records, args.threshold)
    trends = rubric_trends(records, args.threshold)

    print(f"lesson-audit: {len(records)} run record(s), {len(lessons)} lesson(s) analyzed.\n")

    print("Regressions (the factory violated a recorded lesson — promote it to a gate):")
    if regs:
        for r in regs:
            print(f"  • REGRESSION against {r['lesson']}: run {r['date']}-{r['slug']} failed on "
                  f"ground the lesson covers (shared: {', '.join(r['shared'])}). "
                  f"Escalate: incident → lesson → GATE.")
    else:
        print("  none")

    print("\nDead lessons (never applied across the runs they were in scope for — review):")
    if dead:
        for d in dead:
            print(f"  • {d['lesson']} (scope {d['scope'] or 'global'}): applicable to "
                  f"{d['applicable']} run(s), applied in none. Retire or make it mechanical.")
    else:
        print("  none")

    print("\nRubric trends (a dimension scoring ≤ 1 in the majority of runs — draft a lesson):")
    if trends:
        for t in trends:
            print(f"  • {t['dimension']}: scored ≤ 1 in {t['low']}/{t['scored']} run(s). "
                  f"eval/rubric.md §4 — turn a recurring low score into a durable lesson.")
    else:
        print("  none")

    print("\nThese are proposals only — lesson-audit changes nothing on disk.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
