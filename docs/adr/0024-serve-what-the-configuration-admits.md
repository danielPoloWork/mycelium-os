# ADR-0024: Make the vocabulary filters set-valued, and enforce the serving policy at one seam

- **Status:** Accepted
- **Date:** 2026-08-31
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §2, spec 05 §2, §4
- **Related:** [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) (which
  refused this setting by name), [ADR-0008](0008-adopt-sqlite-store-behind-a-store-protocol.md),
  [ADR-0011](0011-implement-mcp-stdio-in-repo.md); D-021; roadmap 3.9

## Context

`[retrieval] include_candidate = false` is spec 05 §2's way of saying "this deployment
serves verified and evidence documents, and does not serve candidates". ADR-0017 refused it
by name rather than accepting it and ignoring it, because the store's filter held **one**
value per vocabulary — `verification_status = ?` — and the setting needs the complement of
one value, which a single-value equality cannot express.

The same shape had already forced a compromise one layer up. Spec 05 §4's `trust` filter is
a *list*, so the MCP tool accepted a list, could not pass it down, and applied it **after**
ranking — over-fetching `4 × k` candidates first to make the loss less likely. Spec 04 §2
requires every candidate generator to pre-filter for exactly this reason: post-filtering a
top-k list silently returns fewer results than were asked for, and "fewer" is
indistinguishable from "there are no more".

D-021 is the other force. A candidate is *labelled*, not hidden — the folder is the source
of status, and a reader who can see the label can judge the document. So the default must
keep serving candidates; `include_candidate = false` is a deployment posture (compliance,
or an audience that should not see drafts at all), not a retrieval improvement.

## Decision

**`SearchFilters` takes a set of admissible values for each vocabulary** —
`trust_classes` and `verification_statuses` — which become an `IN (…)` clause built from
the sorted member values, so the SQL text is a function of the set rather than of iteration
order. `None` means unrestricted; an **empty** set is refused at construction, because a
filter that admits nothing is always a mistake and these filters decide what a server is
willing to serve. Both the MCP `trust` list and `include_candidate = false` are now the
same mechanism, applied in SQL before ranking, and the MCP tool's over-fetch-and-trim is
deleted.

**The serving policy is applied in `mycelium.retrieval.search`, the one seam the CLI, the
MCP server and the evaluation harness all pass through.** It *narrows* a caller's filters
and never widens them. When a caller asks for precisely what the policy refuses — a query
filtered to `candidate` under `include_candidate = false` — the result is an **empty
outcome carrying a note**, not an exception: the question is well formed and its answer is
"nothing, and here is why". Every query answered under the policy carries that note, so the
scope of an answer is visible in the answer rather than only in the config file.

## Alternatives Considered

- **Add `exclude_candidate: bool` beside the existing single-value filter.** Rejected: two
  fields describing one dimension can contradict each other (`verification_status =
  candidate` with `exclude_candidate = true`), and the contradiction has no correct answer.
  It also leaves the `trust` list post-filtered, so the same defect stays in the codebase
  under a different key.
- **Enforce the policy in each caller** (CLI, MCP, harness). Rejected: a serving rule
  enforced in three places is enforced by whichever was updated last, and the one that
  forgets is the one that leaks a draft. The seam exists precisely so the three cannot
  drift (ADR-0017 built it for the same reason).
- **Raise an error when the query and the policy have no overlap.** Rejected: the CLI and
  the MCP server would each render that failure differently, and an MCP client reads an
  error as "the tool is broken" rather than "there is nothing to show you". A note beside
  an empty result says the true thing in one shape.
- **Filter candidates out after ranking, as `trust` already did.** Rejected on the same
  grounds spec 04 §2 gives, and this ADR removes the existing instance rather than adding
  a second.

## Consequences

- **`SearchFilters` changes shape.** `trust_class` → `trust_classes`,
  `verification_status` → `verification_statuses`, both sets. It is a pre-1.0 internal
  surface (it is not in `mycelium.sdk.types`), and every call site in the repository moves
  with it, but a downstream reader of `mycelium.store` would have to adjust.
- **The latent defect is fixed before it could bite, and that is worth stating plainly.**
  The post-filter could only under-return once a corpus held documents of *several* trust
  classes, and today's compiler assigns `authored` to everything it builds — `curated`,
  `ingested` and `external` arrive with ingestion at milestone 4. So there is no bug ledger
  entry here: nothing reproducible was ever observed, and a record claiming otherwise would
  be fiction. What exists is a design that would have failed the moment M4 landed.
- **`include_candidate = false` costs nothing at query time**: it is one more `IN` clause
  on a filter path the store already had, not a second pass over results.
- **A deployment that sets it gets one more line of output per query.** That is deliberate:
  a smaller answer than the corpus could give should say so.
- Doctor's "not honoured" report loses nothing — the setting was refused at load time, not
  listed as unhonoured, so a config that used it never built at all.

## References

- Spec 04 §2 (every generator pre-filters), spec 05 §2 (`[retrieval]`), spec 05 §4 (`filters`)
- D-021 — the folder is the source of verification status
- [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md) — refused the setting by name
- Roadmap 3.9
