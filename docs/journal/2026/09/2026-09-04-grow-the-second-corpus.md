# 2026-09-04 — one row to five, and the two rules that were stopping it (roadmap 4.26)

- **Session scope:** roadmap 4.26 — grow the second corpus's thin slices, and settle the two
  couplings that made growing it impossible (spec 04 §§7.1, 7.3, 7.6; D-010).
- **PR:** #79 (`feat/grow-the-second-corpus`). Follows #78 (4.31), merged as `c11b271`.
- **Milestone 4:** 4.26 done; 4.23, 4.25, 4.28, 4.29, 4.32 open, and 4.33–4.35 filed here.

## The item was not about judgements

Nine cases went in and the judging took an afternoon. The two days before that were spent on
rules that had nothing to do with what the corpus should be asked.

**The rotation was position-dependent.** The third corpus renders judged documents into DOCX,
HTML and PDF by rotation over the judged paths *sorted*. Three of the new cases judge
`projects/run.md`, `projects/sync.md` and `getting-started/features.md`, which sort between
documents already judged — so every index after them shifts and documents already rendered
change format. Those renderings are committed provenance: typst embeds a build identifier, so
they cannot be re-derived (ADR-0039). Landing the cases the old way would have re-rendered
eighty-one documents and moved the per-format cost table, for a reason unconnected to the
cases.

The fix is one idea: **an assignment, once made, is never remade.** The rotation runs over a
recorded order — `format-rotation.json` — and a newly judged document appends. Measured
outcome: **two** documents re-rendered (`run.md` → PDF, `sync.md` → DOCX), seventy-nine
byte-identical, and `features.md` untouched because the plan gave it the HTML it already had.

What it costs is that the assignment is no longer derivable from the case sets alone. That is
the same trade ADR-0039 already made about the renderings: a corpus whose inputs cannot be
re-derived has to keep them, and the assignment is one of those inputs. The tests assert the
record against disk in both directions, and one of them inserts a document that sorts *first*
and checks that nothing moves.

**A derived set could not follow its source.** The frozen-set guard forbade the carried set
moving in the same change as the judged set it is carried from. But the carry *is a function
of* that source — CI byte-checks it — so growing the source must move it. The rule and the
requirement could not both be satisfied; 4.15 met the same wall from the chunking side.

Retired, and the argument is that the direct check already exists and is stronger.
`build_ingested_cases.py --check` regenerates the carry and byte-compares it, whichever commit
the file arrived in. A rule about *when* two files changed cannot say anything a regeneration
cannot say better. `DERIVED_SETS` is left as an empty mapping so the shape stays visible.

## Nine, not eight

Eight cases were drafted at 4.20. Eight arm `conceptual`, `exact` and `relationship` and leave
`symbol` at three — one short of ADR-0052's four. So `uv export` joins `uv lock --check` and
`uv python pin`, and the count is nine. Eight was a number from a draft; four per row is the
rule.

```text
before:  1 of 6 slice(s) enforced
after:   5 of 6 slice(s) enforced
```

`symbol` is the one worth naming. It was blessed at **0.0000 on a single case**, which ADR-0052
refused to enforce precisely because a relative threshold cannot fail a zero. It now reads
**0.585** over four. A row that could not move became a row that can.

## What the per-case scores made easy

`conceptual` fell 0.878 → 0.659 and `relationship` 0.852 → 0.659, which reads like a
regression twice over. The attribution ADR-0052 added answers it in one line each: every
pre-existing case is **unchanged to six decimals**, and the fall is entirely the new cases —
`u-1023` and `u-1024`, both 0.0000.

Exactly three pre-existing cases moved on each corpus, all in `fact`. That is not this change:
PR #75 said "the baselines are deliberately not re-blessed, so the gain shows up as headroom
in the next bless", and this is the next bless. Being able to say that with case ids rather
than with a paragraph of hedging is what the per-case baseline bought.

## The two zeros are the finding

`u-1023` — "can I adopt part of uv without adopting all of it" — is answered by the features
overview: the interface "can be broken down into sections, which are usable independently or
together". `u-1024` asks where a project's Python version is recorded and what reads it; the
`.python-version` section says exactly that. Both score zero, and the queries use none of
those documents' words.

I measured them under `hybrid` as well, with 568 vectors in the store, expecting the vector leg
to be the answer. **It scores them 0.0000 too, and moves the overall not at all** — 0.5858
either way. That is a sharper statement than "lexical cannot reach these", and it points at
ADR-0025: a vector leg gated behind a lexical foothold can re-rank what lexical found and
cannot introduce what lexical missed. Filed as **4.33**, because whatever closes it is a
retrieval change and may not ride with a judgement change or a bless.

And `u-1007` (`uv tool install`) still scores 0.0000, while the three new `symbol` cases score
0.63 to 1.00. The mean of one had hidden it. Filed as **4.34** with the diagnosis left open —
it may be a ranking problem or a judgement naming the wrong home for a command with two.

## The gate that would not have run

`tools/verify.py --list` said `mode: retrieval`, and `retrieval` builds and gates *our*
corpus. Not the vendored ones — only `full` does those, and those are the sets G3 enforces on.
So the change that grows the enforcing set would have left that set's own gate unrun, locally
and in CI, on the strength of a prefix match: `eval/corpora/**` is `eval/`.

Fixed narrowly — a corpus path derives `full` — because the wide version of the question is a
change to ADR-0055's measured economy: should every retrieval change gate the vendored
corpora? PR #75 reported uv numbers, so its author ran them; nothing made them. Filed as
**4.35**.

## The rule I had to narrow

Four days ago I wrote in ADR-0053 that a re-bless "never rides along with a retrieval or a
judgement change". Adding cases to an enforced set makes that impossible to obey: the
case-set digest moves, G3 disarms by design (ADR-0051), and not blessing would have shipped a
set that arms five rows together with a gate enforcing none of them.

The clause was reasoned about our *reported* baseline, where nothing is disarmed because
nothing was armed, and then stated as though it held everywhere. What survives on both kinds
of set is the rule about **retrieval** — that is the conjunction that could fit the retriever
to the set, and the guard still refuses it. On an enforced set a bless *must* ride with the
judgement change. ADR-0053 now carries the narrowing as a quoted note rather than being left
to read as though it still said the other thing.

## What this hands on

G3 now enforces five rows on both frozen sets, which is what the milestone's exit gate needed
from the evaluation side. What it does not fix is set *size* — 25 cases is still small, and
spec 04 §7.6 wants more by 1.0. The next thing to grow is not this corpus's slices but its
population, and 4.33 is the first case where the product, not the benchmark, is what has to
change.
