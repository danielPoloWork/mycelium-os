# Snapshot publication

2026-08-14 — a transcript kept by hand, in the shape this module's own projection writes.

## User

Does a reader ever see a torn snapshot?

## Assistant: gpt-5

No. Publication is a pointer swap:

```python
with store.transaction():
    store.put_document(document)
swap_current(mycelium_dir, snapshot_id)
```

Until `CURRENT` moves, every reader sees the previous snapshot.

## User

And if the process dies between the two?

## Assistant: gpt-5

Then `CURRENT` still names the old snapshot and the next build heals it. `mycelium doctor`
reports the window.
