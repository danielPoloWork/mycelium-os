# Benchmark Report: the incumbent reads a window

- **Date:** 2026-09-18
- **Version / commit:** v0.5.0 @ `899e0d8`, with roadmap 6.22's change to the instrument
- **Environment:** see [`manifests/2026-09-18-the-incumbent-reads-a-window.json`](manifests/2026-09-18-the-incumbent-reads-a-window.json) — the machine of record, as in the [reference-profile report](2026-09-17-reference-profile.md)
- **Command:** `mycelium build . --no-pin && python tools/measure_agent_task_band.py .`
- **Roadmap:** 6.22 · **Decision:** [ADR-0131](../adr/0131-bound-the-incumbents-read-and-publish-the-band-it-buys-evidence-along.md)

## Scenario

The [reference profile](2026-09-17-reference-profile.md) found two defects in the agent-task
suite. It fixed the first — judged anchors the chunker had moved — and filed the second,
because it needed a decision rather than a repair: the grep loop read the **first matching
file whole regardless of budget** and then stopped, so on a corpus whose largest document had
grown to 88 000 tokens it read one document on 22 of 22 tasks and 93 % of its entire measured
cost was `ROADMAP.md`.

What this measures: the same suite, spec 04 §7.4's twenty-two tasks, with the read bounded —
one read costs at most what one search may, and the loop opens the five files its own constant
has always claimed. And, because the verdict depends on both of those numbers, the **band**
either one traces.

**Corpus.** This repository's own, compiled at `899e0d8`: **212 documents, 1 548 chunks.** The
maintainer's untracked work was set aside before the build, so these figures describe the tree
that exists on `main` rather than one working copy of it. That matters more here than it
sounds: the corpus is self-hosting, so writing this report changes it (the
[reference profile](2026-09-17-reference-profile.md) grew `ROADMAP.md` by about a thousand
tokens in the act of describing it), and the manifest names the commit for that reason.

**And here is what that was worth, which is the first time this project has checked.** Writing
this report, its decision record and the roadmap entry added two documents and some thousands
of tokens to the corpus it describes. Re-measured on the tree this pull request merges — 214
documents — the comparison reads **16/22 at 2 668 tokens against 14/22 at 15 179**, a ratio of
5.69× and the same **+2** lead. The figures below are from the 212-document build and move in
the third significant figure. Under the old model the same edits would have moved everything,
because they grew the one file the whole measurement was made of; that they now do not is the
property the bound was for.

## Results

### What the bound moved

Both rows are the same twenty-two tasks over the same corpus, at the shipped 4 000-token
budget. The first is the instrument as it stood; the second is the instrument this report
describes.

| Incumbent's model | Evidence found | Mean context | Median | Documents read |
|---|---:|---:|---:|---:|
| reads the first matching file whole | 1 / 22 (4.5 %) | 52 529 | 88 111 | 1.00 |
| reads a bounded window of each of five | **14 / 22 (63.6 %)** | **15 268** | **15 179** | **5.00** |
| *Mycelium, unchanged* | *16 / 22 (72.7 %)* | *2 735* | *2 684* | *5.27* |

The incumbent gained thirteen tasks and shed two-thirds of its cost. Our lead on evidence went
from **+15 tasks to +2**; the context ratio from 19.2× to **5.6×** on means and from 32.8× to
5.7× on medians.

### The band: what the incumbent buys, and what it pays

Each extra file the loop opens costs about 3 800 tokens and returns about three more tasks.
Five reads is `MAX_GREP_FILES`, the shipped choice; the rest of the band is what a different
choice would have been worth.

| Files the loop opens | Evidence found | Mean | Median | p95 | vs Mycelium's median |
|---:|---:|---:|---:|---:|---:|
| 1 | 1 / 22 | 3 842 | 3 980 | 4 000 | 1.48× |
| 2 | 4 / 22 | 7 135 | 7 508 | 7 975 | 2.80× |
| 3 | 8 / 22 | 9 984 | 10 114 | 11 352 | 3.77× |
| **5** | **14 / 22** | **15 268** | **15 179** | 16 802 | **5.66×** |
| *Mycelium* | *16 / 22* | *2 735* | *2 684* | *3 816* | — |

Which read first carries the evidence, per task: **1** on one task, **2** on three, **3** on
four, **4** on three, **5** on three, and never on eight. The incumbent's evidence is spread
evenly down its reading order, which is the mechanism behind the line above — there is no
point at which it has cheaply got what it needs.

### The band: as the caller's budget moves

The budget is also the read window, so raising it makes each of the incumbent's five reads
bigger while Mycelium still returns one packed answer.

| Budget | Mycelium found | Mycelium median | grep found | grep median | Ratio | Lead |
|---:|---:|---:|---:|---:|---:|---:|
| 1 000 | 9 / 22 | 783 | 9 / 22 | 4 520 | 5.77× | 0 |
| 2 000 | 14 / 22 | 1 819 | 14 / 22 | 9 076 | 4.99× | 0 |
| **4 000** | **16 / 22** | **2 684** | **14 / 22** | **15 179** | **5.66×** | **+2** |
| 8 000 | 17 / 22 | 2 957 | 15 / 22 | 23 916 | 8.09× | +2 |
| 16 000 | 17 / 22 | 2 957 | 16 / 22 | 35 504 | 12.01× | +1 |

Two things to read off it. The evidence lead never exceeds two tasks at any budget. And
Mycelium's cost stops growing at about 3 100 tokens because its side of the harness asks for
ten hits whatever the budget — so above 4 000 tokens the comparison understates us, and the
constant that causes it is the mirror image of the one this report fixes. It is filed as
roadmap 6.28 rather than corrected here, because a change that lifts our own side needs its
own argument in its own pull request.

## Interpretation

**1. The claim that survives is two-sided.** *At equal cost*, the incumbent's first read costs
3 842 tokens against Mycelium's 2 735 and returns 1 task against 16. *At comparable evidence*,
the incumbent reaches 14/22 only by opening every file the model allows, and pays 5.7× the
context to get there. Both come from one band, and neither is quotable on its own — quoting
the first alone flatters us, quoting the second alone hides that the cheap end of the
incumbent's curve is where it is weakest.

**2. The verdict gate's first condition no longer passes.** The [reference
profile](2026-09-17-reference-profile.md#the-agent-task-verdict-gate-quantified) quantified the
gate that arms at the v1.0.0 tag: the evidence rate must exceed grep's **by more than two
tasks**, and the median context must be at most half grep's. On the repaired instrument the
lead is exactly two, so **(a) fails**; (b) passes with room, at 5.7× against a bar of 2×.

The rule is **not** re-cut here. It was calibrated in the same report that found the incumbent
degenerate, which is an argument for looking at it again — not for moving it in the act of
discovering we no longer clear it (D-010, and the same refusal ADR-0120 made for the
performance budgets). Roadmap 6.23 carries the question to whoever arms the gate at Milestone
7, beside the corpus objection it already owns: a rule that compares evidence rates while the
two sides pay different costs is comparing two things at once.

**3. The defect was a scale set by the corpus rather than by the model.** Before the bound, the
incumbent's cost was the size of whichever document happened to match first; `ROADMAP.md` is
18.1 % of this corpus and 49× the median document, so the measurement was mostly a fact about
one file, and it had drifted there quietly as that file grew. After it, the cost cannot exceed
five reads, so a document growing in the corpus moves the comparison by at most its share of
one of them. That property — the instrument's scale being a property of the instrument — is
what makes the next reading comparable to this one.

**4. Two tasks are now won by the incumbent and lost by us**, which the old instrument could
not have shown, because grep won nothing. Both are *why* questions whose answer is an ADR's
`Decision` section — `t-0007` on overlapping windows, `t-0008` on the `mycelium_id` write — and
the mechanism is the same on both: our ten hits are spread over **three and seven documents**
respectively, with eight of the ten going to one bug record on `t-0007`, while grep's
file-level granularity reads the whole ADR and gets the section entire.

That is worth a number of its own. Across the twenty-two tasks, one document takes an average
of **4.3 of the ten slots**, and on **10 of 22** tasks a single document takes half of them or
more. It is not a defect on its face — the concentrated document is usually the right one, and
returning six chunks of the ADR that answers the question is exactly what should happen. It is
an unmeasured knob: nothing has ever asked what a per-document cap would do, and the agent-task
suite cannot answer it. Filed as roadmap **6.29**, to be settled on the judged sets where a
ranking change belongs.

A failure the incumbent shares is a corpus finding; a failure it does not share is a product
finding, and the suite can now tell them apart. That is the second thing bounding the read
bought.

## What these numbers do not say

- **The loop does not stop when it has the answer.** It opens five files whether or not the
  first one answered, so its cost is overstated on the tasks answered early. Modelling the stop
  would need to know when the model was satisfied, which is the thing this suite cannot see.
- **The loop does not re-grep.** An agent that reads a window and finds nothing formulates a
  better query; that needs a model in the loop (ADR-0022), so the incumbent's evidence rate is
  understated by however much a second query would have bought. This and the point above push
  in opposite directions and neither is modelled — which is why the band is published instead
  of a verdict.
- **The window is rounded to section boundaries.** A real read stops mid-section. Rounding
  outward keeps grep's cost denominated in the same rendered tokens as Mycelium's, rather than
  charging it for markup a model never sees, and the cost is fidelity at the window's edge.
- **A section larger than the window is read and carries no evidence.** The agent saw part of a
  passage, which is not being handed it. Five sections in this corpus are larger than a 4 000-
  token read and four of them are in `ROADMAP.md`.
- **The corpus is our own.** ADR-0053's objection applies with full force to a verdict, and
  roadmap 6.23 owns it: these numbers report, and nothing here gates.
- **Evidence in front of a model is not a task completed** (ADR-0022). This says what reached
  the model, never what the model did with it.

## Reproduce

From a clean checkout, with `uv sync --all-extras --dev`:

```bash
# The corpus these figures describe. --no-pin, always: the default writes
# frontmatter into every indexed document.
mycelium build . --no-pin

# The headline comparison, at the shipped budget.
mycelium eval . --tasks --json

# Both bands, and the manifest this report cites.
python tools/measure_agent_task_band.py . \
    --manifest docs/benchmarks/manifests/2026-09-18-the-incumbent-reads-a-window.json
```

The "reads the first matching file whole" row is the instrument before this change: check out
`899e0d8` and run `mycelium eval . --tasks --json` there.
