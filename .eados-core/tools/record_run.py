#!/usr/bin/env python3
"""record_run — mechanized run records for the learning loop (#172, generate.md Step 9).

learning/runs/ stayed empty because the write side asked the agent to hand-author YAML from
end-of-run recollection — the highest-friction interface for a chore. This tool replaces it
with one command: the `overrides:` list is derived MECHANICALLY from the manifest's
`interview:` provenance block (#169) against the built-in defaults in
orchestrator/project.yaml.template, and the failure/rubric/lesson channels arrive as flags.

Records default to the scaffold phase (Step 9) but tag any phase via `--phase` — a migrate/audit
incident, the riskiest surface, records with the same `--failure` channel (#215) so lesson_audit's
regression detection covers real-user-code work, not just generation. A sensitive override value
(a key naming a host/url/registry/token/…) is recorded as <redacted>, keeping the ledger safe to
commit while the tuner still sees the key was overridden (#215).

    python .eados-core/tools/record_run.py <manifest> [--outcome ok|failed] [--phase PHASE]
        [--failure GATE=MESSAGE ...] [--lesson L-NNNN ...] [--rubric DIM=SCORE ...]
        [--date YYYY-MM-DD] [--dry-run]

Derivation rule: for every top-level key whose provenance is NOT `defaulted` (asked/imported =
the maintainer was involved), each scalar leaf whose template default is non-empty and whose
manifest value differs becomes `{key, default, chosen}`. An empty template value means "no
built-in default exists" and never produces an entry; a `defaulted` section by definition kept
its defaults. A red bootstrap CI is recorded as `--failure ci-bootstrap="<summary>"`.

Pure core (build_run_record / derive_overrides / emit_record_yaml) + a thin CLI shell, per the
pr_review.py pattern. autotune.py consumes the records unchanged (it reads `overrides` and
ignores the other channels). Records are facts: an existing record file is never overwritten — a
second run on the same real date (the common failed→fixed re-run) gets a `-2`/`-3` filename suffix
while its `date:` field stays the true run date, so disambiguation never falsifies a fact (#197).
"""

import argparse
import datetime
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # .eados-core/
sys.path.insert(0, HERE)
import render  # noqa: E402  — load_yaml re-export + the manifest template lives beside it

TEMPLATE_PATH = os.path.join(ROOT, "orchestrator", "project.yaml.template")
LESSONS_PATH = os.path.join(ROOT, "learning", "lessons.yaml")
RUNS_DIR = os.path.join(ROOT, "learning", "runs")

OUTCOMES = ("ok", "failed")
# The delivery phases a run can be recorded for (mirrors eados.PHASES / workflow.yaml states).
# `scaffold` is the default (generate.md Step 9); a migrate/audit incident records with --phase so
# the record is phase-tagged and lesson_audit's regression detection covers real-user-code work (#215).
PHASES = ("init", "design", "plan", "scaffold", "audit", "migrate")
# eval/rubric.md's ten dimensions, scored 0-2 (0 absent, 1 partial, 2 solid).
RUBRIC_DIMENSIONS = (
    "spec_measurability", "spec_ci_traceability", "architecture_rationale",
    "profile_fidelity", "pattern_fit", "test_strategy", "docs_coherence",
    "governance_fit", "capability_hygiene", "security_posture",
)
_LESSON_ID = re.compile(r"L-\d{4}\Z")

# Override keys whose CHOSEN value may carry a sensitive string (internal hostnames, registry/repo
# URLs, endpoints, tokens/webhooks) are recorded as <redacted> in the version-controlled ledger
# (#215): the FACT of the override still feeds the tuner, but the value does not leak. Substring
# match, case-insensitive. The (public, template-derived) default and the key are kept.
_SENSITIVE_KEY_PARTS = ("host", "url", "uri", "endpoint", "registry", "token", "secret",
                        "password", "credential", "webhook")
_REDACTED = "<redacted>"


def redact_overrides(overrides):
    """Replace the `chosen` of a sensitive-keyed override with <redacted> before it is written to
    the committed ledger (#215) — the tuner still sees the key was overridden, not its value."""
    out = []
    for ov in overrides:
        if isinstance(ov, dict) and any(p in str(ov.get("key", "")).lower()
                                        for p in _SENSITIVE_KEY_PARTS):
            ov = {**ov, "chosen": _REDACTED}
        out.append(ov)
    return out


# ---------------------------------------------------------------------------
# Pure core — no I/O, fixture-testable.
# ---------------------------------------------------------------------------
def flatten_scalars(mapping, prefix=""):
    """Dotted-key -> scalar for the str/int/bool leaves of a nested mapping. Lists and None
    are skipped: they have no meaningful single 'default vs chosen' diff for the tuner."""
    out = {}
    for key, val in (mapping if isinstance(mapping, dict) else {}).items():
        if not isinstance(key, str):
            continue
        dotted = f"{prefix}{key}"
        if isinstance(val, dict):
            out.update(flatten_scalars(val, dotted + "."))
        elif isinstance(val, (str, int, bool)):
            out[dotted] = val
    return out


def derive_overrides(manifest, template):
    """The mechanical `overrides:` list — see the module docstring's derivation rule."""
    prov = {}
    iv = manifest.get("interview") if isinstance(manifest, dict) else None
    if isinstance(iv, dict) and isinstance(iv.get("provenance"), dict):
        prov = iv["provenance"]
    m_flat = flatten_scalars(manifest)
    t_flat = flatten_scalars(template)
    overrides = []
    for key in sorted(t_flat):
        top = key.split(".", 1)[0]
        if prov.get(top) in (None, "defaulted"):
            continue                       # unknown or explicitly defaulted: nothing chosen
        default = t_flat[key]
        if default == "" or default is None:
            continue                       # no built-in default exists for this field
        if key not in m_flat:
            continue
        chosen = m_flat[key]
        if str(chosen).strip() == "" or str(chosen) == str(default):
            continue
        overrides.append({"key": key, "default": default, "chosen": chosen})
    return overrides


def _single_line(text):
    return " ".join(str(text).split()) or "(no message)"


def parse_route_mismatch(spec):
    """`ROUTED=SESSION` -> {routed, session}, or (None, problem). An accepted route mismatch (M18
    18.2, #297): the human ran a unit of work on a model below/above its routed tier and proceeded
    — a legitimate override that should be visible, not silent (the recorded-dissent posture,
    ADR-0022 §10.4). Both sides are free strings (the routed 'tier/effort' shorthand and the
    session tier/model), non-empty; the tool does not re-derive the route, it records the accepted
    fact. Returns ({} , None) when `spec` is falsy — the flag was not passed."""
    if not spec:
        return {}, None
    routed, sep, session = str(spec).partition("=")
    routed, session = routed.strip(), session.strip()
    if not sep or not routed or not session:
        return None, f"--route-mismatch needs ROUTED=SESSION (both non-empty), got {spec!r}"
    return {"routed": _single_line(routed), "session": _single_line(session)}, None


def build_run_record(manifest, template, known_lessons, today, outcome="ok",
                     failures=(), lessons=(), rubric=(), phase="scaffold", route_mismatch=None):
    """(record, problems): the record dict ready for emission, and every validation problem
    found (empty == valid). `failures` are 'GATE=MESSAGE' strings, `lessons` lesson ids,
    `rubric` 'DIM=SCORE' strings — exactly the CLI's repeatable flags. `phase` is the delivery
    phase the record is for (#215: scaffold by default; migrate/audit for real-user-code work).
    `route_mismatch` is an optional 'ROUTED=SESSION' string — an accepted route override (#297)."""
    problems = []
    if phase not in PHASES:
        problems.append(f"phase must be one of {'|'.join(PHASES)}, got {phase!r}")
    ident = manifest.get("identity") if isinstance(manifest, dict) else None
    ident = ident if isinstance(ident, dict) else {}
    lang = manifest.get("language") if isinstance(manifest, dict) else None
    lang = lang if isinstance(lang, dict) else {}

    slug = str(ident.get("project_slug") or "").strip()
    if not slug:
        problems.append("the manifest has no identity.project_slug — the record filename "
                        "and slug need it")
    iv = manifest.get("interview") if isinstance(manifest, dict) else None
    if not (isinstance(iv, dict) and isinstance(iv.get("provenance"), dict) and iv["provenance"]):
        problems.append("the manifest has no interview: provenance block (#169) — the recorder "
                        "derives overrides from it; record provenance during the interview")
    if outcome not in OUTCOMES:
        problems.append(f"outcome must be one of {'|'.join(OUTCOMES)}, got {outcome!r}")

    parsed_failures = []
    for item in failures:
        gate, sep, message = str(item).partition("=")
        gate = gate.strip()
        if not sep or not gate:
            problems.append(f"--failure needs GATE=MESSAGE, got {item!r}")
            continue
        parsed_failures.append({"gate": gate, "message": _single_line(message)})
    if parsed_failures and outcome != "failed":
        problems.append("a recorded gate failure means the run failed — pass --outcome failed")

    applied = []
    for lid in lessons:
        lid = str(lid).strip()
        if not _LESSON_ID.match(lid):
            problems.append(f"--lesson must look like L-NNNN, got {lid!r}")
        elif lid not in known_lessons:
            problems.append(f"--lesson {lid} is not in learning/lessons.yaml — a run can only "
                            "apply a lesson that exists")
        else:
            applied.append(lid)

    scores = {}
    for item in rubric:
        dim, sep, score = str(item).partition("=")
        dim = dim.strip()
        if not sep or dim not in RUBRIC_DIMENSIONS:
            problems.append(f"--rubric needs DIM=SCORE with DIM one of the eval/rubric.md "
                            f"dimensions, got {item!r}")
            continue
        if score.strip() not in ("0", "1", "2"):
            problems.append(f"--rubric {dim} score must be 0, 1, or 2, got {score.strip()!r}")
            continue
        scores[dim] = int(score)

    mismatch, mismatch_problem = parse_route_mismatch(route_mismatch)
    if mismatch_problem:
        problems.append(mismatch_problem)

    record = {
        "slug": slug,
        "date": today,
        "phase": phase,
        "lang": str(lang.get("lang") or "").strip(),
        "kind": str(ident.get("project_kind") or "").strip(),
        "outcome": outcome,
        "overrides": redact_overrides(derive_overrides(manifest, template)),
        "lessons_applied": applied,
        "failures": parsed_failures,
        "rubric": scores,
        "route_mismatch": mismatch,
    }
    return record, problems


def _scalar(value):
    """Loader-safe YAML scalar: booleans/ints bare, strings double-quoted and single-line
    (the #166 loader rejects wrapped quoted scalars — a record must always parse)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    escaped = _single_line(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def emit_record_yaml(record):
    """Block-style YAML the hand-rolled loader reads back identically (round-trip tested)."""
    out = ["# Run record — appended by tools/record_run.py; a fact about a past run, never edited",
           "# after the fact. `phase` is the delivery phase that produced it (#215).",
           f"slug: {_scalar(record['slug'])}",
           f"date: {_scalar(record['date'])}",
           f"phase: {_scalar(record.get('phase', 'scaffold'))}",
           f"lang: {_scalar(record['lang'])}",
           f"kind: {_scalar(record['kind'])}",
           f"outcome: {_scalar(record['outcome'])}"]
    if record["overrides"]:
        out.append("overrides:")
        for ov in record["overrides"]:
            out.append(f"  - key: {_scalar(ov['key'])}")
            out.append(f"    default: {_scalar(ov['default'])}")
            out.append(f"    chosen: {_scalar(ov['chosen'])}")
    else:
        out.append("overrides: []")
    ids = ", ".join(_scalar(lid) for lid in record["lessons_applied"])
    out.append(f"lessons_applied: [{ids}]")
    if record["failures"]:
        out.append("failures:")
        for f in record["failures"]:
            out.append(f"  - gate: {_scalar(f['gate'])}")
            out.append(f"    message: {_scalar(f['message'])}")
    else:
        out.append("failures: []")
    if record["rubric"]:
        out.append("rubric:")
        for dim in RUBRIC_DIMENSIONS:
            if dim in record["rubric"]:
                out.append(f"  {dim}: {record['rubric'][dim]}")
    else:
        out.append("rubric: {}")
    # #297: an accepted route mismatch, emitted only when one was recorded — a rare, exceptional
    # override, unlike the always-present core channels, so absence keeps records byte-identical.
    mismatch = record.get("route_mismatch")
    if mismatch:
        out.append("route_mismatch:")
        out.append(f"  routed: {_scalar(mismatch['routed'])}")
        out.append(f"  session: {_scalar(mismatch['session'])}")
    return "\n".join(out) + "\n"


def known_lesson_ids(lessons_text):
    """The ids in lessons.yaml. Read through the one loader since #315 taught it sequence-root
    documents; this used to be a regex over the '- id:' entry heads because load_yaml returned {}
    for that shape. A ledger that will not parse yields no ids — the caller reports the reference
    as unknown, which is the safe direction."""
    try:
        entries = render.load_yaml(lessons_text)
    except Exception:  # noqa: BLE001 — data-file-validity owns reporting the syntax error
        return set()
    if not isinstance(entries, list):
        return set()
    return {str(e["id"]).strip() for e in entries
            if isinstance(e, dict) and str(e.get("id", "") or "").strip()}


def provenance_gaps(manifest):
    """Answer-bearing top-level sections present in the manifest but MISSING from
    interview.provenance. Each derives no override (derive_overrides treats an unrecorded key
    exactly like an explicit `defaulted`), so a partial block silently shortens the record and
    starves the tuner. Returns [] when no provenance block exists (build_run_record already refuses
    that) — this warns only about a partial block (#201)."""
    if not isinstance(manifest, dict):
        return []
    iv = manifest.get("interview")
    prov = iv.get("provenance") if isinstance(iv, dict) else None
    if not isinstance(prov, dict) or not prov:
        return []
    return sorted(k for k in manifest
                  if k not in render.PROVENANCE_EXEMPT and k not in prov)


# ---------------------------------------------------------------------------
# Thin CLI shell.
# ---------------------------------------------------------------------------
def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _rel(path):
    """Repo-relative display path, tolerant of a RUNS_DIR on a different drive than the factory
    (Windows `relpath` raises across mounts) — a display string must never crash the tool after the
    record is already written."""
    try:
        return os.path.relpath(path, os.path.dirname(ROOT))
    except ValueError:
        return path


def resolve_dest(runs_dir, date, slug):
    """The path this run's record lands at, WITHOUT ever overwriting an existing fact. The natural
    name is `<date>-<slug>.yaml`; when a same-day record for this slug already exists (a failed
    bootstrap then its fixed re-run — the exact failure→success pairing the tuner and lesson_audit
    mine), append the lowest free sequence suffix `-2`, `-3`, … The `date:` field inside the record
    is derived separately from `today` and stays the true run date, so the filename can disambiguate
    without falsifying the fact (#197). Touches the filesystem for existence only."""
    base = os.path.join(runs_dir, f"{date}-{slug}.yaml")
    if not os.path.exists(base):
        return base
    seq = 2
    while os.path.exists(os.path.join(runs_dir, f"{date}-{slug}-{seq}.yaml")):
        seq += 1
    return os.path.join(runs_dir, f"{date}-{slug}-{seq}.yaml")


def main(argv=None):
    # issue #128: force UTF-8 stdio so non-ASCII output won't mojibake or crash on cp1252 (Windows)
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(
        description="Append a mechanized run record to learning/runs/ (generate.md Step 9).")
    ap.add_argument("manifest", help="path to the confirmed project.yaml")
    ap.add_argument("--outcome", choices=OUTCOMES, default="ok",
                    help="how the run ended (default ok)")
    ap.add_argument("--failure", action="append", default=[], metavar="GATE=MESSAGE",
                    help="a failed gate (repeatable), e.g. --failure ci-bootstrap=\"matrix red "
                         "on windows\" — requires --outcome failed")
    ap.add_argument("--lesson", action="append", default=[], metavar="L-NNNN",
                    help="a lesson id applied at Step 0.a (repeatable; must exist in "
                         "learning/lessons.yaml)")
    ap.add_argument("--rubric", action="append", default=[], metavar="DIM=SCORE",
                    help="an eval/rubric.md dimension score 0-2 (repeatable), e.g. "
                         "--rubric spec_measurability=2")
    ap.add_argument("--phase", choices=PHASES, default="scaffold",
                    help="the delivery phase this record is for (default scaffold, generate.md "
                         "Step 9); use e.g. --phase migrate to log a migrate-phase incident (#215)")
    ap.add_argument("--route-mismatch", metavar="ROUTED=SESSION",
                    help="record an accepted route override (#297), e.g. --route-mismatch "
                         "\"frontier-reasoning/high=standard\" — the run proceeded on a model off "
                         "its routed tier; the checkpoint (route_advice.py --check) prints this string")
    ap.add_argument("--date", help="record date YYYY-MM-DD (default: today)")
    ap.add_argument("--dry-run", action="store_true", help="print the record; write nothing")
    args = ap.parse_args(argv)

    today = args.date or datetime.date.today().isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", today):
        print(f"record-run: --date must be YYYY-MM-DD, got {today!r}", file=sys.stderr)
        return 2
    try:
        manifest = render.load_yaml(_read(args.manifest))
        template = render.load_yaml(_read(TEMPLATE_PATH))
        lessons_text = _read(LESSONS_PATH)
    except (OSError, ValueError) as exc:
        print(f"record-run: cannot read inputs: {exc}", file=sys.stderr)
        return 2

    record, problems = build_run_record(
        manifest, template, known_lesson_ids(lessons_text), today,
        outcome=args.outcome, failures=args.failure, lessons=args.lesson, rubric=args.rubric,
        phase=args.phase, route_mismatch=args.route_mismatch)
    if problems:
        print("record-run: FAIL — the record would not be honest\n")
        for p in problems:
            print(f"  {p}")
        print(f"\n{len(problems)} problem(s).")
        return 1

    # #201: a partial provenance block passes the record (it has SOME entries) but silently derives
    # no override for the sections it omits. Surface each gap at record time — a warning, not a
    # failure (manifest-valid already rejects a partial block; this catches a manifest recorded
    # without going through --check).
    for section in provenance_gaps(manifest):
        print(f"record-run: WARNING — manifest section '{section}' has no interview.provenance "
              "entry; its overrides are not derived (treated as defaulted) (#201).", file=sys.stderr)

    text = emit_record_yaml(record)
    if args.dry_run:
        sys.stdout.write(text)
        return 0
    # Records are facts and are never overwritten; a same-day re-run gets a -2/-3 suffix while its
    # date stays true (#197), so the common failed→fixed pairing can be recorded honestly.
    dest = resolve_dest(RUNS_DIR, today, record["slug"])
    with open(dest, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(f"record-run: OK — {_rel(dest)} "
          f"({len(record['overrides'])} override(s), {len(record['lessons_applied'])} "
          f"lesson(s) applied, outcome {record['outcome']}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
