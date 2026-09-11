---
mycelium_id: 01KDVDNA080000000000000008
title: Delivery Guarantees (v0)
collection: core-docs
tags: [delivery, retries]
---

# Delivery Guarantees (v0)

The first delivery note, kept because a superseded decision is still the record of
what was decided. It described at-most-once delivery with a fixed one-second retry
and no backoff, which the replacement corrected.

## Fixed retry

Every failed delivery was retried once, one second later, and then dropped. Nothing
recorded why a message had failed, so an operator could not tell a transient error
from a permanent one.
