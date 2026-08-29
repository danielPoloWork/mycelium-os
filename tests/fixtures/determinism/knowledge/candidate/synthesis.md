---
mycelium_id: 01KDVDNA040000000000000004
title: Delivery Semantics (draft)
origin: synthesized
source: "https://example.invalid/sources/delivery.pdf"
source_trust: medium
generated_by: anthropic/claude-sonnet-5
tags: [delivery]
---

# Delivery Semantics (draft)

An unreviewed synthesis of the delivery guarantees, awaiting `mycelium verify`. Every
claim below cites the evidence it came from: retries are bounded at five attempts
([[retries#Schedule]]), and quarantine preserves provenance ([[retries]]).

## Open questions

- Whether the ceiling should be per-connector or global.
- How a replayed message interacts with the snapshot it was quarantined under.
