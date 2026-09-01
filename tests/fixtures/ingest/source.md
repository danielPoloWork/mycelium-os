# Retry Policy

Webhook deliveries are retried five times, and the [delivery log](https://example.com/log) records each attempt.

## Backoff

Backoff doubles after every failed attempt.

- first retry after 1 s
- second retry after 2 s

| attempt | delay |
|---------|-------|
| 1       | 1 s   |
| 2       | 2 s   |

```python
delay = 2 ** attempt
```

> Deliveries stop after the fifth failure.

Term
:   A definition, which GFM cannot express and pandoc's Markdown writer would drop.
