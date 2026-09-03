---
id: BUG-0019
title: turning `pack_atomic` on against an existing store changes nothing
status: fixed
severity: high
reporter: internal
discovered: 2026-09-03
affected-versions: ">=0.4.0"
fixed-in: "0.4.0"
---

# BUG-0019: turning `pack_atomic` on against an existing store changes nothing

## Summary

`[chunking] pack_atomic` moves every chunk boundary in the corpus — that is its entire
purpose (ADR-0042). It was **not** in the chunk stage's config slice, so changing it moved
neither the build environment digest nor the chunk build key. On a repository that has been
built before, the next build therefore found every document unchanged, reused every
`doc_state` row, and served the **previous boundaries under the new configuration** — while
reporting success and writing a manifest whose `config_digest` says the setting is on.

The operator sees a build that worked. The store holds the corpus they asked to change.

This is the failure class the config loader was designed to prevent — ADR-0014's *"an
operator would tune a knob and believe it worked"* — reappearing one layer down, in the
cache rather than in the loader.

## Environment

- **Affected versions:** ≥ 0.4.0 — the setting was introduced by PR #61 (roadmap 4.11) and
  has never invalidated the cache
- **Toolchain / platform:** CPython 3.12.10, Windows 11; platform-independent (the defect is
  in the key, not in the store)
- **Configuration:** any repository with an existing `.mycelium/` store

## Reproduction

One document, one section, prose around a code block:

```markdown
# Guide

Run the command below to start.

```bash
mycelium build
```

Then read the output.
```

```text
$ mycelium build .                       # pack_atomic unset (v0.3 default: off)
  knowledge/a.md#/0  prose  8 tokens
  knowledge/a.md#/1  code   2 tokens
  knowledge/a.md#/2  prose  5 tokens

$ printf '[chunking]\npack_atomic = true\n' >> mycelium.toml
$ mycelium build .                       # reports success
  knowledge/a.md#/0  prose  8 tokens     # …and nothing moved
  knowledge/a.md#/1  code   2 tokens
  knowledge/a.md#/2  prose  5 tokens

$ rm -rf .mycelium && mycelium build .   # the setting does work
  knowledge/a.md#/0  prose  15 tokens
```

`mycelium build --clean` also produces the correct result, which is how the defect stayed
hidden: every measurement of `pack_atomic` so far was taken either on a fresh store or with
`--clean` (ADR-0042's numbers are unaffected — `tools/measure_chunking.py` re-chunks in
memory from an explicit policy and never consults the cache).

## Root cause

`BuildEnv.compute` builds the chunk stage's config slice from three values:

```python
chunk_slice={
    "target_tokens": policy.target_tokens,
    "max_tokens": policy.max_tokens,
    "counter": _counter_id(policy),
}
```

That slice is the whole of what the chunk stage's cache identity knows about its
configuration. It feeds `BuildEnv.digest` — the per-document short-circuit that decides
whether any stage runs at all — and `BuildEnv.chunk_key`, the content-addressed cache key.
`pack_atomic` reached neither, so both were identical before and after the change and the
two guards agreed, wrongly, that nothing had happened.

The general shape of the mistake is worth naming: a setting was added to `ChunkingPolicy`
(the thing that computes) without being added to the slice (the thing that remembers). The
two are separate structures, and nothing forced them to agree.

## Fix

`pack_atomic` joins the chunk slice, in `src/mycelium/build/dag.py`. The key then moves with
the setting, dirty detection sees every document, and the cache misses — which is the
behaviour `target_tokens` and `max_tokens` already had.

Adding a member to the slice changes the digest for every repository, so the first build
after upgrading recompiles the corpus once. That is correct rather than unfortunate: the
default is flipping in the same release (roadmap 4.15), so every corpus needed re-chunking
anyway.

## Regression test

`tests/test_build_incremental.py::test_turning_pack_atomic_off_recompiles_every_document`
builds a packable document, flips the setting on an existing store, and asserts that the
document is rebuilt, that the parse stage is *not* re-run (only the chunk slice moved), and
that the resulting chunk kinds are the unpacked three. It is written against the **off**
direction because that is the edit an operator actually makes now that on is the default.

## Notes

Found while flipping the default at roadmap 4.15 — the flip is exactly the operation the
defect suppresses, so shipping it without this fix would have upgraded every existing
installation into the new configuration and the old boundaries, silently.
