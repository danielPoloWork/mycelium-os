# 2026-09-25 — a fact about the checkout (roadmap 7.7)

- **Session scope:** roadmap 7.7 — a document's timestamps were its checkout's, so no
  cache could make a fresh clone incremental. Decide what a record's time should be a
  function of.
- **PR:** #199 (`feat/decide-what-a-documents-time-is-a-function-of`). Follows #198, merged
  as `8670f3e`.
- **Milestone 7:** 7.7 closed. 7.1 and 7.2 held at their triggers. **7.8–7.12 filed** at
  the maintainer's request, in the order they pay off: the issue audit, the open-intake
  pull-request policy (the adoption gate's own blocker), the front-door review, the audit of
  7.2's standing, and the architects' panel review last, so it reads a current repository.
- **Decision it records:** D-032 (owner decision) in
  [ADR-0157](../../../adr/0157-take-the-timestamps-out-of-the-document-record.md).

## Two of the item's three constraints were not constraints

The item said the fields were covered by the 1.0 promise, and that the answer had to beat
`git restore-mtime`. Reading `docs/compatibility.md` found the first false in so many
words — `document` changes at a MINOR with a CHANGELOG line; only KIR and the manifest are
frozen — and the second turned out to be an argument for removal rather than for a rival:
a recipe every clone has to remember is what a field nobody reads was costing. The one
real constraint was the frozen manifest golden, which pins the tag `mycelium/document/v0`
by value, and it decided the tag stays.

## Ask what reads the field before deciding what it should hold

Nothing did. Not `show`, not `mycelium_fetch`, not retrieval — 6.38 had already said a
recency boost had no field to read. And `created_at` had never differed from `updated_at`:
both came from the same stat on every assemble. With that in hand the four options sorted
themselves: the Git time costs 5–20 s a build here; a first-seen time breaks either G6 or
incremental-equals-clean; a frontmatter key is a contract extension for no consumer. I
recommended the frontmatter-or-null reading and the owner chose the stricter one — the
fields do not belong to the record — which is cleaner than what I offered, and D-032
records it in the owner's words.

## The pin was the claim's own workaround

Gate G6 has pinned every fixture mtime since 2.10, because without that the golden would
have encoded the moment of the clone. Removing the timestamps let the pin go, and the test
that replaced it is the sentence the pin used to avoid: touch every file, build, and the
observation is identical. The golden lost sixteen lines and one digest, and nothing else
moved — which is also the byte-for-byte statement that the record was the only place the
mtime reached.

## What the next session should know

- **Every store is v9** and rebuilds once on its next build; that is D-016's policy, not
  a defect.
- **A touch reuses the document.** Tests that used `os.utime` to make a document *dirty
  enough* now delete its row instead (`forget()` in `test_build_incremental.py`).
- **`measure_cache_ceiling.py`'s two restored arms coincide now**; the control stays
  because a gap would be the mtime finding its way back.
