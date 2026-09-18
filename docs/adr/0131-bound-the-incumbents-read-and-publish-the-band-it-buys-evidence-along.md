# ADR-0131: Bound the incumbent's read, and publish the band along which it buys evidence

- **Status:** Accepted
- **Date:** 2026-09-18
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.4
- **Related:** [ADR-0022](0022-measure-the-agent-loop-without-an-agent.md) (the suite, and
  the whole-file read this bounds), [ADR-0120](0120-build-the-reference-profile-publish-what-it-says-and-gate-the-instrument-not-the-verdict.md)
  (which found the defect, filed it here, and quantified the verdict gate against the
  instrument this changes), [ADR-0013](0013-adopt-the-evaluation-harness.md) (the harness and
  the grep baseline), [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md)
  (report on the corpus we author, gate on the one we do not),
  [ADR-0047](0047-flip-the-packed-chunker-on-and-let-the-gate-say-so.md) (the chunker whose
  sections this read is rounded to), [ADR-0112](0112-date-the-baseline-to-a-release-because-the-drift-is-the-incumbents.md)
  (a measurement whose denominator moves under it); spec 04 §7.4; D-010; roadmap 6.4, 6.22,
  6.23, 6.28

## Context

Roadmap 6.4 built this project's first benchmark report and found two defects in its own
instrument. The first — judged anchors the chunker had moved — it fixed. The second it filed
as 6.22, because the fix needs a decision rather than a repair:

> `MAX_GREP_FILES` is 5 — *"an agent does not read forty files; it reads the first few and
> re-greps"* — but `_grep_context` read the first matching file **whole regardless of
> budget** and then stopped.

Measured on this repository's corpus, that produced a degenerate incumbent:

| | before |
|---|---|
| documents the loop read | **1.00**, on 22 of 22 tasks |
| evidence in front of the model | **1 / 22** (4.5 %) |
| mean context | 52 529 tokens |
| median context | 88 111 tokens — one file, `ROADMAP.md` |
| share of total cost in that one file | **93 %** |

So the headline ratio was mostly a fact about our roadmap file, grep's 4.5 % was *"its one
file was the wrong file and it never got a second"*, and five-sixths of the loop the model
describes never ran. ADR-0022 measured 27 % and a 2× ratio when the corpus's documents were
small; the comparison changed character as they grew and nothing noticed, which is the same
shape as the anchor rot beside it.

**The question the item names is real, and it is not a bug report.** What does a grep loop do
with a file larger than its context budget? It does not read it whole. It reads a window
around the hit, or it re-greps — so modelling it as a whole-file read overstates the
incumbent's cost exactly where documents are large, which flatters us. D-010 cuts both ways:
*fix the product, not the benchmark* forbids a change that makes our number better, and
equally forbids leaving in place a model that makes it better by accident.

## Decision

**One read costs at most what one search may, and the loop opens the files its own constant
says it opens.** `budget_tokens` is what a caller is willing to spend on one step of
context-gathering. Mycelium spends it once, on passages it ranked across the corpus. A grep
loop has no packing and no ranking across files, so it spends it **per file it opens**, and it
opens `MAX_GREP_FILES` of them. A document that fits inside one read is still read whole,
because an agent that has decided to open a four-kilobyte file does not page through it;
a document that does not fit is read *around the hit*, which is what `grep -n` plus a read
tool with an offset actually does.

Three consequences of that rule are stated rather than left implicit:

- **The incumbent's ceiling is now the model of the loop** — five reads — where before it was
  the size of the largest document that happened to match. A benchmark whose scale is set by
  one file in the corpus is measuring the corpus, not the strategies.
- **A section larger than the window is read up to the window and counts as evidence for
  nothing.** The agent saw part of a passage, which is not the same as being handed it, and
  scoring it as evidence would credit grep for text nobody can point at. This corpus has five
  such sections and four of them are in `ROADMAP.md`.
- **The window is rounded to section boundaries, not lines.** The whole harness works in the
  store's rendered view of the corpus, so this measures grep's cost in the same tokens as
  Mycelium's rather than charging it for markup a model never sees. What it costs is fidelity
  at the window's edge, where a real read stops mid-section.

**Both constants of the incumbent's model are parameters, and the band is published**
(`tools/measure_agent_task_band.py`, and the report beside this record). The verdict depends
on how much one read costs and how many files the loop opens; a number nobody can vary is a
number nobody can check, and this instrument has now been wrong twice for one reason — an
assumption that was true when it was written and was never asked again, first the judged
anchors the chunker moved and now the read. The band is the answer to *"why five, why that
window"*: the reader sees what the choice is worth instead of taking it.

**The claim that survives is two-sided, and it is the one the band supports.** Measured on
this repository's corpus at the shipped budget:

| | Mycelium | grep (1 read) | grep (3 reads) | grep (5 reads) |
|---|---:|---:|---:|---:|
| evidence found | **16 / 22** | 1 / 22 | 8 / 22 | 14 / 22 |
| mean context | **2 735** | 3 842 | 9 984 | 15 268 |
| median context | **2 684** | 3 980 | 10 114 | 15 179 |

*At equal cost* — the incumbent's first read costs slightly more than a search — Mycelium
returns sixteen times the evidence. *At comparable evidence* the incumbent needs every read
the model allows and pays **5.7×** the context. Neither half is quotable alone, which is why
the report prints both.

**The verdict gate's condition (a) now fails, and it is not re-cut here.** ADR-0120 quantified
the gate that arms at the v1.0.0 tag: Mycelium's evidence rate must exceed grep's *by more than
two tasks*, and its median context must be at most half grep's. On the repaired instrument the
lead is **exactly two** — 16 against 14 — so (a) fails, while (b) passes by 5.7×. That is the
honest outcome of fixing a measurement, and the rule stays as it is: re-cutting a bar in the
same act that discovers you no longer clear it is the benchmark-fixing D-010 forbids, and
ADR-0120 already refused it for the performance budgets. What the finding *does* justify is a
question, filed as **6.23** with the corpus question it already owns: the rule compares
evidence rates at unequal cost, and it was calibrated against an incumbent that read one file.
Whoever arms it at Milestone 7 decides, with this band in front of them.

## Alternatives Considered

- **Cap the grep loop at the same total budget as Mycelium, so both spend at most 4 000
  tokens.** The cleanest-looking comparison — same context, who finds more? — and rejected
  because it models a loop nobody runs. An agent with a large context does not stop grepping at
  four thousand tokens; it reads a few files because it does not know which one holds the
  answer, and *that* is the cost compiling knowledge removes. Capping both sides would delete
  the product's actual claim from the measurement in order to tidy it.
- **Keep reading whole files, but skip a file larger than the budget.** The smallest possible
  change, and wrong in the opposite direction: an agent does not skip the file its grep just
  matched, it reads part of it. Skipping would hand grep a free pass on exactly the documents
  that are hardest to use — and on this corpus it would have removed `ROADMAP.md` from the
  comparison entirely, which is fixing the number by deleting the case.
- **Model the re-grep instead of the window.** The item names both branches, and only one is
  reachable: re-gripping means formulating a better query, which needs a model in the loop —
  the thing ADR-0022 ruled out and spec 04 §7.4 defers to 1.0. Modelling the window and
  *saying* that the re-grep is unmodelled is honest; inventing a query-refinement heuristic
  and calling it the incumbent is not.
- **Address the window in lines, from the file on disk.** More faithful to what a read tool
  returns, and rejected on two grounds. It would charge grep for raw Markdown while charging
  Mycelium for rendered text, which makes our ratio better for a reason that has nothing to do
  with retrieval; and line count is not a proxy for cost in this corpus, where `ROADMAP.md`
  averages **330 tokens a line** against prose's thirteen. The loop already reads the store's
  view of the corpus rather than the disk — the unused `root` parameter it carried since
  ADR-0022 suggested otherwise, and is removed here.
- **Move `MAX_GREP_FILES`, in either direction, now that the loop reaches it.** Rejected, and
  the direction that mattered was *down*: the band shows that at three files the incumbent
  reaches 8/22 and our lead would be +8 rather than +2, comfortably past the verdict gate. Five
  was ADR-0022's judgement about what a reasonable loop does, nothing has been learned that
  bears on it, and touching it in the pull request that repairs the instrument would be choosing
  the constant that produces the verdict. It is unchanged; what changed is that it is now
  measured rather than asserted, and the band prints what every other choice is worth.
- **Fix the Mycelium side's own constant in the same change.** `_mycelium_context` asks for ten
  hits whatever the budget, so above ~4 000 tokens it cannot spend what it is given while grep
  scales with the budget — the mirror image of the defect fixed here, and one that makes *our*
  numbers worse. Rejected precisely because it would flatter us: a change that lifts our own
  side belongs in its own pull request with its own argument, filed as **6.28**.
- **Report only the shipped point.** Rejected on this project's own rule that a measurement is
  a curve and not a point (ADR-0120). One row of a band whose shape decides the verdict is how
  the last two instrument defects survived.

## Consequences

- **The incumbent got much stronger, and our margin got much smaller.** Evidence found: 1/22 →
  **14/22**. Mean context: 52 529 → **15 268**. The ratio: 19.2× → **5.6×** on means, 32.8× →
  5.7× on medians. The product's lead on evidence is **+2 tasks**, not +15. This is the number
  to quote from now on, and the old one is not to be quoted at all.
- **Two tasks are now won by grep and lost by us** (`t-0007`, `t-0008`), which the old
  instrument could not have shown because grep won nothing. A failure the incumbent does not
  share is a product finding; a failure it does share is a corpus finding, and the suite can
  finally tell them apart.
- **The verdict gate does not pass today.** Stated in the report beside the rule, unchanged.
- **The measurement is bounded by its model.** grep's cost can no longer exceed
  `MAX_GREP_FILES × budget_tokens`, so a document growing in the corpus moves the comparison by
  at most its share of one read. The failure mode that produced this item cannot recur in the
  same form.
- **Small corpora are unaffected**, which is the check that this is a bound and not a rewrite:
  every document in the test fixture still reads whole, and the suite's shape tests did not
  change.
- **`tools/measure_agent_task_band.py` joins the measure-the-constant family**, writes a run
  manifest in the benchmark schema, and adds `task_profile` to the sections that schema
  recognises — the first whose measurements are tokens rather than milliseconds. The `p95` every
  measurement must carry still means a distribution's tail, so the rule needed no exception.
- **A limit, stated.** The loop does not stop when it has the answer, so its cost is overstated
  on tasks answered by the first read; and it does not re-grep, so its evidence is understated
  on tasks where a second query would have found the file. The two point in opposite directions
  and neither is modelled, which is why the band is published rather than a single verdict. And
  the corpus is still our own — ADR-0053's objection, which 6.23 owns.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §7.4 (the grep baseline, the agent-task
  suite, and the two gates ADR-0120 separated), §7.5 (run manifests).
- The report: `docs/benchmarks/2026-09-18-the-incumbent-reads-a-window.md`, with its manifest.
- Decision log: D-010 (the incumbent, and fixing the product rather than the benchmark).
- Re-runnable: `mycelium build . --no-pin && mycelium eval . --tasks --json`, and
  `python tools/measure_agent_task_band.py .` for the band.
