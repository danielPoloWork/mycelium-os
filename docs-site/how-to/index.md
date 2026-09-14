# How-to guides

Task-oriented guides for something you already know you want to do. Each one assumes
you have already worked through the [tutorial](../tutorial.md) — a compiled repository
and a working `mycelium` command.

- [Ingest an external document](ingest-a-document.md) — bring a PDF, DOCX, HTML or
  wiki export into the corpus, with its original bytes kept in custody and a fidelity
  report saying what did and did not survive.
- [Query from an agent over MCP](query-over-mcp.md) — the four tools, what each
  response carries, and how to read a `mycelium_explain` plan when a result looks
  wrong.
- [Verify and promote a synthesized document](verify-and-promote.md) — let an LLM draft
  prose from ingested evidence, check its grounding, and move it into `verified/`.
- [Roll back to an earlier snapshot](roll-back-a-snapshot.md) — undo a bad build
  without recompiling, and understand what a rollback does and does not touch.
