---
title: Mycelium OS
---

# Mycelium OS

**The knowledge compiler for AI agents.** Compile a repository's knowledge — authored
Markdown plus ingested PDFs, DOCX, HTML and wikis — into a deterministic, versioned,
queryable substrate, and serve it to agents over the CLI and MCP with citations they
can check.

Mycelium OS is a knowledge **compiler and serving layer**. It is not an agent runtime,
not a RAG framework, and not a chat product.

<div class="grid cards" markdown>

- :material-rocket-launch:{ .lg .middle } **New here?**

    ---

    Install, build and get a cited answer over MCP in under ten minutes.

    [:octicons-arrow-right-24: Tutorial](tutorial.md)

- :material-book-open-variant:{ .lg .middle } **Have a task?**

    ---

    Task-oriented guides: ingest a document, query from an agent, verify and
    promote synthesized text, roll back a snapshot.

    [:octicons-arrow-right-24: How-to guides](how-to/index.md)

- :material-puzzle:{ .lg .middle } **Building a plugin?**

    ---

    The `Connector`, `Parser` and `Module` contracts, the naming rule, and what the
    compatibility promise means for a plugin author.

    [:octicons-arrow-right-24: Plugin author guide](plugin-author-guide.md)

- :material-file-code:{ .lg .middle } **Looking something up?**

    ---

    The record contracts and identity library `mycelium.sdk` exports, generated
    from their own docstrings.

    [:octicons-arrow-right-24: SDK reference](reference/index.md)

</div>

## What makes it different

Retrieval is lexical (BM25) by default — hybrid vector search and graph expansion
exist, are measured against it on every release, and ship switched off where the
measurement says so. A symbol table says where a name is defined and which sections
document it. Ingested content is dual-lane: a deterministic evidence projection
always runs, and an LLM may additionally *synthesize* readable prose, but only with a
citation into that evidence for every claim it makes — an uncited sentence is a build
failure, not a warning. A citation is a `mycelium://` URI keyed to a document's logical
identity, so it survives a rename or a promotion from `candidate/` to `verified/`; if
the passage it names has moved or been rewritten since, `mycelium_fetch` says so rather
than quietly returning something else.

For the full account, with the measurement and the decision record behind each claim, see
[How Mycelium OS works](https://github.com/danielPoloWork/mycelium-os/blob/main/docs/how-it-works.md).

## Status

Pre-1.0 and milestone-driven. See the
[roadmap](https://github.com/danielPoloWork/mycelium-os/blob/main/ROADMAP.md) for what
is done and what is next, and the [Project](project.md) page for where the
specification, the decision records and the compatibility promise live.
