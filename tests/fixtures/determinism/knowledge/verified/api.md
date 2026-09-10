---
mycelium_id: 01KDVDNA070000000000000007
title: API Reference
collection: core-docs
tags: [api, compiler]
---

# API Reference

What the compiler exposes, defined once here and cited from the other documents. The
symbol table (roadmap 5.1) is folded from documents like this one: a heading that names
a thing, a fence that defines it, a definition list that says what a term means.

## RetryPolicy

The policy every connector shares. The Python and Rust forms define the same name under
two languages, which is exactly the case the symbol id keys on.

```python
class RetryPolicy:
    """Bounded retries with exponential backoff."""

    attempts = 5

    def delay(self, attempt: int) -> float:
        return 2.0**attempt


def build_policy(attempts: int = 5) -> RetryPolicy:
    return RetryPolicy()
```

```rust
pub struct RetryPolicy {
    pub attempts: u32,
}

impl RetryPolicy {
    pub fn delay(&self, attempt: u32) -> f64 {
        2f64.powi(attempt as i32)
    }
}
```

## Terms

snapshot
: An immutable, published build of the corpus.

anchor
: Where a chunk lives — path, heading slug, ordinal.

## Worked example

A fence that assigns and calls, and therefore defines nothing:

```python
policy = build_policy(attempts=3)
assert policy.delay(2) == 4.0
```
