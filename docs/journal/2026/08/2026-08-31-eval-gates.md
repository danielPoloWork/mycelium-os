# 2026-08-31 — the gates (roadmap 3.7, and 3.10 with it)

- **Session scope:** roadmap 3.7 — eval slices, CI gates G1–G6, agent-task suite v0 against
  the grep baseline (spec 04 §7, D-010) — and roadmap 3.10, which this item's own text said
  belonged here.
- **PR:** #37 (`feat/eval-gates`). Follows #36 (3.6), merged as `65eefc0`.
- **Milestone 3:** 3.1–3.7 and 3.10 done; 3.8, 3.9, 3.11–3.13 open.

## The item could not start where it was meant to

Wiring the gates into CI was the deliverable, and gate G4 was red before a line was
written: a query about message brokers was answered by a *test fixture*, because building
this repository indexes every Markdown file in it. Wiring a known-red gate teaches everyone
to ignore it on the day it lands, so the corpus had to be scoped first — which is exactly
what roadmap 3.10 had been filed to say.

The fix is `[project] exclude`, and it is a feature rather than a test accommodation: every
repository's tree carries Markdown that is not knowledge, and the only previous answers
were "put it all under `knowledge/`" or "live with it". Ours cannot use the first — this
project's documentation *is* its root.

Scoping it properly meant putting the rule in one place. Discovery and watch mode both had
to answer "is this a document", and they answered with the same rule written twice, which
is agreement by coincidence — a watcher firing for files the compiler ignores rebuilds
nothing forever. `mycelium.corpus` is now the single answer, and it is where "never index
your own output" belongs too.

## What scoping the corpus uncovered

Four defects, none of them visible until the corpus was the corpus:

- **[BUG-0012](../../../bugs/2026/08/BUG-0012-a-date-property-quarantines-the-document.md)**
  is the serious one. A YAML date in a non-contract property fails the record contract, so
  the build quarantined the document — and every record in `docs/bugs/` carries
  `discovered: <date>`. This project's entire bug ledger had been missing from its own
  index, which means every eval number before today was measured over a corpus nine
  documents short. Dates now become their ISO spelling, which is what the author wrote
  before YAML typed it.
- **[BUG-0011](../../../bugs/2026/08/BUG-0011-quoted-yaml-key-hides-frontmatter.md)**: a
  quoted YAML key made frontmatter parse as prose. Found by a property test that had been
  green since 2.4 — hypothesis simply had not drawn the key `off` before, which is the
  whole argument for property tests.
- **[BUG-0010](../../../bugs/2026/08/BUG-0010-build-indexes-its-own-export.md)**: builds
  indexed the export bundle they had just written, quarantining the copies as duplicate
  identities. Introduced by 3.6 last session.
- **[BUG-0013](../../../bugs/2026/08/BUG-0013-links-to-existing-files-warn-as-unresolved.md)**:
  links to files that exist but are not documents were reported as unresolved. ~150 warnings
  per build of this repository, down to 3 — and the 3 are real.

## The trap worth remembering

Writing up BUG-0007 put an unanswerable query's own words into the documentation, so
documenting the case *answered* it and G4 went red for a document about the eval set.

The fix is not a convention. The case builder now refuses to write a set in which an
`unanswerable` case is answerable, checking the grep baseline as well as ours — grep matches
word prefixes, so a term that merely starts a corpus word ("bulk" inside "Bulkhead")
separates the two retrievers for reasons that have nothing to do with abstention. It caught
a replacement query on its first run.

A second lint came out of the same session: a grade-3 anchor of fourteen tokens reads like
the right section and carries none of the answer. Both builders now report anchors under
thirty tokens, and it immediately found four mis-judgments — three of mine, one in the
existing case set, all corrected before the baseline was frozen.

## The gates, and the agent-task suite

Every gate spec 04 §7.3 names is now enforced, delegated, or explained — a table with
silent omissions reads as though the missing gates passed. Two calls worth recording:

- **G3's baseline is a committed file, not the last run on this machine.** CI starts from
  an empty derived store every time, so "compare against the previous run" compares against
  nothing exactly where it matters. `--bless` writes `eval/baselines/<set>.json`, so moving
  the line is a commit someone can challenge.
- **G5 is enforced with its limit in the same sentence.** The 150 ms budget is defined at
  the 10⁵-chunk reference profile; our corpus is 568 chunks. Failing here is certainly
  broken, passing here proves only that it passes at this size.

The agent-task suite measures what neither a model nor a key is needed for: what each
strategy puts in front of an agent. Mycelium found the required evidence on **64 %** of 22
tasks against grep's **27 %**, at **half the context** and a tenth of the latency. The gap
in tokens is the point — a grep hit is a line number, so the loop reads whole files.

What it cannot say is whether the model then answers correctly, and ADR-0022 says so in
those words rather than letting 64 % be quoted as a task-success rate.

## Numbers, and what they are not

With the corpus finally scoped, gate G4 went 25 % → 0 % and overall nDCG@10 moved
0.497 → 0.636 on the same judged set. That is **not** a retrieval improvement: it is the
same retrieval measured over the corpus it was always supposed to be measured over. The
numbers in ADR-0017 were taken before the ledger came back into the index, and the two sets
are not comparable — stated in the ADR so nobody quotes them side by side.

## Where the project stands

- Milestone 3: 3.1–3.7 and 3.10 complete; 3.8, 3.9, 3.11, 3.12 open, plus **3.13** filed
  here for the dev/release split, ≥ 60 cases across two corpora, and independent judgments.
- Gates green locally: `ruff format --check`, `ruff check`, `mypy --strict src`,
  `pytest -q` (651 passed, 18 skipped), `python tools/consistency_lint.py`, and a full
  local rehearsal of the new CI job.
- The G6 golden moved by one line — `config_digest`, because `[project]` gained `exclude` —
  verified field by field before re-blessing.

## How the next session resumes

- Wait for PR #37 to merge. The natural next item is **3.8** (target-aware packing), which
  now has something it lacked: a gate that will notice if moving every chunk boundary makes
  retrieval worse, and a baseline to notice it against.
- Anything touching retrieval quality should run `mycelium eval --tasks` as well as the
  case set: the two disagree usefully. Eight tasks fail for us today, and at least one for a
  reason worth fixing — a task asking about a "licence" misses a corpus that spells it
  "license", because the lexical path has no stemming.
