# ADR-0062: A `symbol` judgment names where the thing is documented, not where it is framed

- **Status:** Accepted
- **Date:** 2026-09-08
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.1
- **Related:** [ADR-0029](0029-let-a-judgment-name-a-section.md) (chunk-or-section notation),
  [ADR-0043](0043-judge-across-the-configurations-a-set-is-scored-under.md) (the unit a
  judgment names), [ADR-0052](0052-give-a-slice-cases-or-stop-gating-it.md) (per-case scores,
  which made this visible), [ADR-0058](0058-decompose-a-conceded-slice-before-believing-it.md)
  (read the cases, not the mean), [ADR-0056](0056-make-the-format-assignment-append-only.md)
  (the set this case sits in); D-010; roadmap 4.34

## Context

`u-1007` — query `uv tool install`, slice `symbol`, on the second corpus's release set — has
scored **0.0000** since it was written, and 4.26 made that visible: the slice used to hold
one case and could not be gated on, so its mean absorbed the zero; it now holds four, gate
G3 enforces the row, and ADR-0052 prints the case behind it. The other three score 0.63,
0.71 and 1.00.

Roadmap 4.34 offered two hypotheses and said to read the case from the documents before
choosing. Both were checkable, and the measurements are unambiguous.

**It is not a reach failure.** The judged chunk comes back at **rank 11** of 50, with a BM25
score of 4.0321 against rank 10's 4.0789 — a **1.1 %** gap. Ranks 1 to 11 span 5.09 to 4.03,
so eleven chunks sit inside 21 % of each other and every one of them genuinely mentions the
command. A case whose verdict turns on which of two near-tied chunks lands tenth is
measuring the retriever's tie-breaking, not its retrieval.

**The judgment names the wrong home.** The case's single grade-2 anchor is
`docs/concepts/tools.md#the-uv-tool-interface`, whose relevant sentence is one clause among
three: *"Tools can also be installed with `uv tool install`, in which case their executables
are available on the `PATH`."* The section's subject is the interface, and its own document
opens by pointing elsewhere — *"See the [tools guide](../guides/tools.md) for an introduction
to working with the tools interface — this document discusses details of tool management."*

Where the corpus documents the command is `docs/guides/tools.md#installing-tools`: what it
does, where the executables land, `uv tool update-shell`, how it differs from `uv pip
install`, that it operates on a package rather than a command, versions, sources, `--with`,
`--with-executables-from`. This corpus vendors **no CLI reference** — `docs/reference/cli.md`
is one of the unresolved links every build of it reports — so that section is not one home
among many. It is the documentation.

Two further facts settle it. Its three sibling `symbol` cases all grade **the section that
documents the command** at 3 (`u-1017` → `#checking-the-lockfile`, `u-1019` →
`#requesting-a-version/python-version-files`, `u-1025` → `#exporting-the-lockfile`), and
`u-1019` grades the feature-list mention at **1** with the reason written out: *"the list is
graded 1 because it answers only that the command exists."* `u-1007` followed neither
convention. And the anchor it did name is the right one for a *different* query: `u-0006`
(`uvx`, uv/dev) grades that same section 3, correctly — it is where `uvx` is **defined**
(*"a `uvx` alias is provided for `uv tool run` — the two commands are exactly equivalent"*).
The section that defines `uvx` is not the section that documents `uv tool install`, and the
judgment reused it as though it were.

> **Narrowed at roadmap 4.37 ([ADR-0065](0065-one-section-cannot-document-two-commands.md)).**
> The clause "grades that same section 3, correctly" was reasoned in passing about a case
> this ADR deferred, and it does not survive the rule this ADR wrote. A section's subject
> does not change with the query asked of it: if
> `concepts/tools.md#the-uv-tool-interface` is *framing* for `uv tool install` — which is
> why it is graded 2 here — it is framing for `uvx` too. `uvx` is documented by
> `guides/tools.md#running-tools` (*"The uvx command invokes a tool without installing it"*),
> the direct counterpart of the `#installing-tools` section this ADR promoted. What survives
> is everything else: the rule, `u-1007`'s re-judging, and the observation that the section
> *defines* the alias — which is why it keeps a grade 2 in `u-0006` rather than losing its
> place.

## Decision

**A `symbol` judgment names the section that documents the named thing.** A page that
*frames* it, *defines a sibling*, or *mentions* it in passing is a lesser grade or no grade —
never the primary anchor. Concretely, `u-1007` is re-judged from the documents:

| anchor | grade | why |
|---|---|---|
| `docs/guides/tools.md#installing-tools/` | 3 | the command's documentation; **section-scoped**, because the answer is spread across the whole of it (ADR-0029) |
| `docs/concepts/tools.md#the-uv-tool-interface/0` | 2 | frames the interface and states what the command is for, in one clause — more than "it exists", less than its documentation |
| `docs/getting-started/features.md#tools/0` | 1 | *"uv tool install: Install a tool user-wide."* — `u-1019`'s precedent, verbatim |

**No code changes.** Not one line under `src/`, so the conjunction
`tools/check_frozen_release_sets.py` refuses is not merely satisfied, it is irrelevant
(the shape 4.12 established). The judgment lives in `tools/build_uv_docs_cases.py`, which
validates every anchor against a real build before writing the set, and the derived ingested
twin is re-carried by its own generator and byte-checked in CI.

**Both frozen release baselines are re-blessed**, both retrievers, in this change — a bless
rides with the judgment change that occasions it and never with a retrieval change
(ADR-0056 narrowing ADR-0053), because leaving G3 disarmed makes re-arming it somebody's
errand.

## Alternatives Considered

- **Re-anchor to the guide's section alone, at grade 3.** The highest-scoring option
  available: **0.4307** against the three-anchor judgment's 0.3742, because nDCG's ideal gain
  grows with each relevant item while the retriever still misses the concepts section at rank
  11. Rejected because the concepts section *is* relevant and was judged so by the original
  judge; dropping a true relevance to raise a score is re-fitting in the direction nobody
  inspects. That the judgment written from the documents scores **less** than the one written
  for the number is the check that this was written from the documents.
- **Leave the case at 0.0000 and file a ranking item.** Rejected on the measurement: the
  top ten are all genuinely about the command, so there is no ranking error to fix at rank
  11 — and a permanent zero inside an enforced row is a gate that cannot move, which is what
  ADR-0052 refused for the single-case slice.
- **Judge the whole neighbourhood relevant** — `#tool-versions`, `#including-additional-dependencies`,
  `#installing-executables-from-additional-packages`, `#tool-executables/overwriting-executables`,
  `reference/storage.md#types-of-data/tools` all discuss the command. Rejected: those are
  *aspects* of it, not its documentation, and crediting "right neighbourhood" is exactly the
  generosity ADR-0029 warned about.
- **Fix `u-0006` in the same change.** It has the same shape — its grade-3 anchor sits at
  rank 13 for `uvx` while `docs/guides/tools.md#running-tools`, where the guide teaches the
  command, sits at rank **3** and is unjudged — and it also scores 0.0000. Rejected here
  because it is a *dev*-set judgment: the dev set is the surface future tuning is developed
  against, so moving it deserves its own visible decision rather than a paragraph inside
  another case's change. Filed as roadmap 4.37 with the ranks measured.

## Consequences

- **Exactly one case moves, on all four (corpus × retriever) combinations.** Every other case
  and every other slice is identical to within 1e-6, which is what a judgment-only change
  should look like:

  | set | retriever | `u-1007` | `symbol` | overall |
  |---|---|---|---|---|
  | uv/release | mycelium | 0.0000 → **0.3742** | 0.5852 → 0.6787 | 0.5858 → **0.6021** |
  | uv/release | grep | 0.0000 → **0.7453** | 0.4281 → 0.6144 | 0.4849 → **0.5173** |
  | uv-ingested/release | mycelium | 0.0000 → **0.3390** | 0.4741 → 0.5588 | 0.6153 → **0.6300** |
  | uv-ingested/release | grep | 0.0000 → **0.3936** | 0.3747 → 0.4731 | 0.5046 → **0.5217** |

- **It costs the product lead, and that is the honest part.** On uv/release the incumbent
  gains twice what we do (+0.0324 against +0.0163), so the lead narrows from **+0.1009 to
  +0.0848**; on the ingested twin, +0.1107 to +0.1083. A judgment change made to flatter the
  product does not hand the incumbent a case it wins 0.745 to 0.374.
- **That loss has a measurable mechanism, and it is an old one.** `#installing-tools` is
  **409 tokens** — the longest chunk in the candidate set — and BM25's length normalisation
  puts it 4th, while grep's `(distinct terms, total occurrences)` ranking puts it 1st on
  install\*=20, uv=13, tool=20. This is the shape ADR-0031 identified and ADR-0058 found again
  in `u-1006` (*"its gap is in `text` … 385 tokens against 164"*). Two named cases in two
  slices now, filed as roadmap 4.38 — **not** as a licence to re-open a family that is
  thirteen refusals deep, but because 4.25 closed asking for named cases and these are two.
- **One anchor does not survive the carry.** `features.md#tools/0` maps onto the ingested
  twin at coverage 0.42, below the floor, so the ingested `u-1007` carries two anchors of
  three — the generator prints the drop and `--check` reproduces it byte-for-byte. That is
  the carry working as designed (ADR-0039); it is why the twin's `u-1007` scores 0.3390 where
  the source set's scores 0.3742.
- **G3 is armed again on both frozen sets** — "same corpus, same boundaries, same judgements,
  no enforced slice regressed", 5 of 6 slices enforced. Between the re-judgement and the
  bless it correctly disarmed itself and said so.
- **The `symbol` slice's convention is now written down**, so the next command-name case has
  a rule to follow rather than three examples to infer one from.

## References

- Spec 04 §7.1 (slices, frozen sets), §7.2 (metrics), §7.4 (the incumbent).
- `eval/corpora/uv-docs/docs/concepts/tools.md`, `.../docs/guides/tools.md`,
  `.../docs/getting-started/features.md` — the documents the judgment was written from.
- Re-runnable: `mycelium search "uv tool install" --path eval/corpora/uv-docs --explain`,
  then `mycelium eval eval/corpora/uv-docs --set eval/release.jsonl --against grep`.
- [ADR-0029](0029-let-a-judgment-name-a-section.md), [ADR-0043](0043-judge-across-the-configurations-a-set-is-scored-under.md)
  — the two rules this one joins: *which unit* a judgment names, and *which place*.
