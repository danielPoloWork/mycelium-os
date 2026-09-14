# How to verify and promote a synthesized document

The synthesis lane lets an LLM draft *readable* prose from ingested evidence — the
verbatim projections `mycelium ingest` writes into `knowledge/evidence/`. It is opt-in,
off by default, and every claim it writes must carry a citation into evidence that
actually exists: a draft with an uncited claim, or a citation to nothing, is refused
before it is ever written to disk.

## 1. Configure a provider

```toml title="mycelium.toml"
[synthesis]
provider = "anthropic"
```

Nothing calls out to a provider, and no key is read, until this line is present
(D-013/D-017). Naming a provider here is you consenting to send the evidence documents
you point at it to that provider — say so to anyone else who works in this repository.

## 2. Ingest, and let the synthesis lane run

```bash
mycelium ingest handbook.pdf
```

The synthesis lane is not a separate command: `mycelium ingest` runs it automatically,
for every source, whenever `[synthesis]` names a provider — pass `--no-synthesize` to
skip it for one call without editing the config. It authors from the evidence document
that same `ingest` call just projected, and the result lands in `knowledge/candidate/`,
which — like every verification-status folder — is the fact of its own status: nothing
here is trusted yet, and Git shows every reviewer exactly that.

Every wikilink the candidate contains resolves to the evidence it was written from; a
citation the model invented, or one that would resolve to a section that does not
exist, makes the write fail rather than land wrong. The console reports what happened:

```text
handbook.pdf -> wrote knowledge/evidence/handbook.md (docling)
  41 represented, 2 degraded, 0 lost of 43 elements; 6 reference(s) carried
  wrote knowledge/candidate/handbook.md (claude-...)
  cited 12/12 claim(s) across 1 evidence document(s), 1 attempt(s)
```

A synthesis failure — the model could not produce a document that cited everything it
claimed, even after one repair round-trip — never fails the ingestion that carried it:
the evidence lane has already done its job, and synthesis is the additional lane
(D-020).

## 3. Check its grounding

```bash
mycelium verify knowledge/candidate/handbook.md
```

With no argument, `verify` checks every synthesized document it finds. It computes two
things, and they are not the same kind of check: **citation coverage** is recomputed
against the corpus *as it stands now* — the evidence a candidate cites may have been
edited or deleted since it was written, and nothing checked at writing time can catch
that — and **sampled entailment** asks whether the cited text actually *supports* the
claim, which needs a judge; with no LLM provider configured it is reported as *not
measured* rather than as a number nobody computed (`--no-entailment` asks for exactly
that: coverage only, no LLM call). The score is written into the document's
frontmatter only when it changed, and `--gate` is the CI form — it fails on a
*measured* shortfall but not on an unmeasured entailment, because a gate that is red on
every offline checkout is one everyone learns to ignore.

## 4. Promote it

```bash
mycelium promote knowledge/candidate/handbook.md
```

This is a Git-visible move from `candidate/` to `verified/` — a human action, distinct
from `verify`'s measurement and stricter than it: promotion refuses below the
configured thresholds, including an *unmeasured* entailment, unless you pass `--force`.
A forced promotion writes *why* it was forced into `verified_by`, so the override is
visible in the file and in every diff after it — never a default anyone can drift
into.

## Demoting

```bash
mycelium demote knowledge/verified/handbook.md
```

The reverse move, for a document that turns out not to hold up — folder-encoded status
means this is always a one-line, auditable Git change.

## Why the citation resolves to a *document*, not a byte range

A citation URI keys on the document's logical id, not its path, so `promote` moving the
file from `candidate/` to `verified/` never breaks anything that already cites it — the
whole point of keying on identity rather than location (spec 03 §2).
