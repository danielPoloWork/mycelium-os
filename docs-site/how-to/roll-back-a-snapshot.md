# How to roll back to an earlier snapshot

Every `mycelium build` publishes an immutable, numbered snapshot; `CURRENT` is a
pointer to one of them, swapped atomically so a reader never observes a half-published
build. Rolling back repoints `CURRENT` — it never recompiles.

## List what you have

```bash
mycelium snapshots
```

Newest first, with the current one marked. Each entry is a manifest: schema versions,
config digest, embedding model identity, per-artifact counts and digests, and any
degradation (for example `vectors: absent`, when a build ran without an embedder).

## Roll back

```bash
mycelium rollback <snapshot-id>
```

This restores the corpus state that snapshot describes and repoints `CURRENT` to it —
served queries see the restored state immediately, and nothing under
`knowledge/` is touched, because a snapshot is a fact about the compiled *output*, not
about your source tree. A build after a rollback is still incremental from the
restored state, not a clean rebuild.

## What a rollback refuses

- **An unknown snapshot id** — refused by name rather than silently picking the
  nearest one.
- **A snapshot whose artifacts are missing** — if referenced blobs were garbage
  collected, rolling back to it would serve holes, so it is refused instead.
- **State that does not reproduce the manifest it claims to** — the restore is checked
  against the manifest before `CURRENT` moves, not assumed correct because the files
  are present.

Rolling back to the snapshot that is already current is a lawful no-op, not an error.

## Garbage collection and rollback interact

```bash
mycelium gc --dry-run
```

`gc` removes blobs no retained snapshot or build-cache row needs, and never collects
the snapshot `CURRENT` points at. A snapshot you might want to roll back to stays
reachable only while something still references it — check `mycelium snapshots` for
what is retained before assuming an old one is still there to roll back to.
