---
mycelium_id: 01KDVDNA050000000000000005
title: Delivery Guarantees (extract)
origin: ingested
source: "https://example.invalid/sources/delivery.pdf"
source_trust: high
tags: [delivery]
---

# Delivery Guarantees (extract)

A verbatim projection of an ingested source, mechanically faithful and regenerable from
the original bytes.

## Section 4.2

"Each message is delivered at least once. Duplicate delivery is possible when a consumer
acknowledges after a partition heals; consumers are expected to be idempotent."

## Section 4.3

"Delivery attempts are bounded. After the final attempt the message is moved to a
quarantine queue and is not retried automatically."
