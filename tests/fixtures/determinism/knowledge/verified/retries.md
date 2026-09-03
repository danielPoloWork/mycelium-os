---
mycelium_id: 01KDVDNA020000000000000002
title: Retry Policy
collection: core-docs
tags: [delivery, retries]
verified_by: daniel
verified_at: 2026-07-31
grounding: 0.97
---

# Retry Policy

Failed deliveries retry with exponential backoff. The ceiling is five attempts, after
which the message is quarantined rather than dropped silently.

> [!warning] Quarantine is not deletion
> A quarantined message keeps its provenance and can be replayed once the cause is fixed.

## Schedule

| Attempt | Delay | Cumulative |
|---------|-------|------------|
| 1       | 1s    | 1s         |
| 2       | 2s    | 3s         |
| 3       | 4s    | 7s         |
| 4       | 8s    | 15s        |
| 5       | 16s   | 31s        |

## Configuration

```python
retry_policy = RetryPolicy(
    attempts=5,
    base_delay_s=1.0,
    multiplier=2.0,
)
```

The values above are defaults; a connector may lower the ceiling but never raise it past
the build's own budget. See ![[architecture]] for where this sits in the pipeline.

## Worked example

```python
snapshot = build(root, clean=True)
assert snapshot.counts.chunks > 0
```
