# 2026-09-04 — the question ranking cannot answer about itself (roadmap 4.21)

- **Session scope:** roadmap 4.21 — `explain` should say when a query term matched nothing.
- **PR:** #71 (`feat/explain-per-term-hits`). Follows #70 (4.8), merged as `2112e36`.
- **Milestone 4:** 4.21 done; 4.18, 4.20, 4.22 open.

## Why the obvious version would have been wrong

The item was filed at 4.17 with a precise complaint: two of five query words matched zero
documents, nothing in the product said so, and diagnosing it took a leave-one-out script.
The obvious implementation is a boolean per term — *did this word match* — and it would
have shipped a diagnostic that is wrong on its own motivating case.

4.19 landed in between. The index now carries a stem column beside every surface column
(ADR-0048), so `signs` reaches the document through `sign`. A single "did it match" number
now answers **yes** for exactly the term whose silence cost 4.17 an afternoon — and it would
make 4.19's own before/after invisible, which is the second thing the item asked for.

So the report keeps three outcomes apart: matched as the author wrote it, reached *only* by
its stem, or reaches nothing in this corpus in any inflection. The middle one is the whole
point, and it is a row that reads as its own finding:

```text
escapement: 0 doc(s); stem "escap" 10  <- only via its stem
```

That is ADR-0048's own cited hazard — Porter conflates *escapement* with *escape* — now
visible in one command instead of in an ADR.

## What the corpus had already done to the evidence

Running the report on `r-0011`'s actual query was the first thing I did, and the historical
zeros are gone: `signs` reaches 5 documents today and `contributed` 4, because this
repository's own ADRs and journal entries now discuss *signs off* and *contributed* at
length. The 4.17 finding is not reproducible on the corpus that grew out of writing it up.

The instrument still works — a query with genuinely absent words reports them — and the
tests use a fixed corpus for exactly this reason. But it is worth recording that a
measurement taken on a corpus that documents its own measurements decays in a way nobody
plans for. It is the same force 4.17 diagnosed, arriving from the other direction.

## The two judgment calls

**Off by default.** Two index queries per term, and the harness that measures p95 against
gate G5's budget runs thousands of queries. A diagnostic that taxes the number it exists to
explain is a bad diagnostic, so `search()` grew an `explain=True` rather than doing this for
everyone. Measured cost when it *is* asked for: 1 ms for a nine-word query, against a 2 ms
lexical leg.

**`--json` gets it anyway.** `--json` is a format, not a request for extra work — but the
JSON document already carries a per-result `explain` block whether or not `--explain` was
passed. A machine-readable surface that is self-explanatory by default is the convention
this command already has, and breaking it to save a millisecond would be the wrong trade.

## What the table looks like, stopwords included

```text
terms: 9
   contributed: 4 doc(s); stem "contribut" 17
   signs: 5 doc(s); stem "sign" 8
   contribution: 9 doc(s); stem "contribut" 17
   who: 24 doc(s)
   off: 29 doc(s)
   may: 37 doc(s); stem "mai" 37
   be: 81 doc(s)
   that: 102 doc(s)
   a: 110 doc(s)
```

Sorted worst-first, which is where the answer usually is. `a: 110` at the bottom is noise
and stays: which words are noise is corpus-dependent, and a stopword list would be a tuning
parameter nobody measured.

## Not touched

4.20 (thin slices) and 4.22 (our stale baseline) are the other two actions 4.17 filed. This
makes both easier to argue and settles neither.
