# 2026-08-31 — the filter that could only hold one value (roadmap 3.9)

- **Session scope:** roadmap 3.9 — honour `[retrieval] include_candidate = false`
  (spec 05 §2), which had been refused by name since 3.3.
- **PR:** #40 (`feat/serve-verified-only`). Follows #39 (3.8), merged as `6aeef73`.
- **Milestone 3:** 3.1–3.10 done; 3.11–3.13 open.

## An XS item that was really about one data structure

The setting says "serve verified and evidence, not candidates". `SearchFilters` held
`verification_status: VerificationStatus | None` and became `d.verification_status = ?`, so
the only questions it could ask were "this one value" and "any value". The setting asks for
the *complement* of one value, and that is why ADR-0017 refused it by name rather than
accepting it and quietly ignoring it.

Widening the field to a set is the whole feature. What made the item worth more than its
size is that the same one-value limit had already forced a compromise elsewhere, and I
found it by looking for who else used the filter: spec 05 §4's `trust` is a **list**, so the
MCP tool accepted a list, could not pass it down, and applied it after ranking — fetching
`4 × k` candidates first so the loss would be less likely. Spec 04 §2 exists to forbid
exactly that: post-filtering a top-k list returns fewer results than were asked for, and
"fewer" is indistinguishable from "there are no more". One set-valued filter fixes both,
and the over-fetch is deleted rather than tuned.

## The defect I did not file

The post-filter is a defect, and it is not in the bug ledger. It can only under-return once
a corpus holds documents of several trust classes, and this compiler assigns `authored` to
everything it builds — `curated`, `ingested` and `external` arrive with ingestion at
milestone 4. So there is nothing reproducible to record, and a ledger entry claiming
otherwise would be fiction. The ledger's own rule is "verified, reproducible defect"; the
honest place for a design that would have failed on the day M4 landed is the ADR.

That distinction is worth keeping sharp. A bug record is a claim about the past — this
happened, here is how to make it happen again. This is a claim about the future.

## Where a serving policy belongs

`include_candidate` is not a query option, it is a property of the process answering
queries, so no caller should have to remember it. It is enforced in
`mycelium.retrieval.search`, the seam ADR-0017 built so the CLI, the MCP server and the
evaluation harness cannot answer the same question differently — a rule enforced in three
places is enforced by whichever was updated last, and the one that forgets is the one that
leaks a draft.

Two decisions inside that:

**It narrows, never widens.** A query already filtered to `verified` keeps asking for
exactly that; the policy intersects rather than replaces.

**No overlap is an empty answer with a note, not an error.** A query filtered to `candidate`
under this policy is a well-formed question whose answer is "nothing". An exception would be
rendered differently by the CLI and the MCP server, and an MCP client reads an error as "the
tool is broken" rather than "there is nothing to show you". Every query answered under the
policy carries the note, because an answer smaller than the corpus could give should say why.

## Small thing, deliberately kept

An *empty* filter set is refused at construction rather than read as "unrestricted" or as
"nothing matches". Both readings are defensible, which is the problem: these filters decide
what a server is willing to serve, and a silent reading of an empty set is how a policy
becomes a no-op. `None` means unrestricted, and a mistake fails loudly.
