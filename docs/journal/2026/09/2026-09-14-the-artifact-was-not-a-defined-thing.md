# 2026-09-14 — the artifact was not a defined thing (roadmap 6.11)

- **Session scope:** roadmap 6.11 — publish the package. The precondition for 6.12, and
  therefore for a Phase-3 exit gate carried into M6.
- **PR:** `feat/publish-the-package`. Follows #147 (6.2, the docs site) and #146 (6.1, the
  contract freeze).
- **Milestone 6:** 6.1, 6.2 and 6.11 closed; 6.3–6.10, 6.12, 6.13 open.
- **Decision it records:** [ADR-0116](../../../adr/0116-publish-under-a-name-already-decided-and-let-the-artifact-be-a-defined-thing.md).

## Two of the four questions were already answered

The item asked which index, whether the name is available, how the credential is held, and
what the release procedure gains. It also carried a caution: *"do not reserve one before
[6.5's trademark decision] lands."*

D-024 — an **owner decision**, 2026-07-31 — already reads *"PyPI distribution:
`mycelium-os` (verified available 2026-07-31…)"*, and records in the same paragraph that a
trademark search remains a pre-1.0 task. The owner decided the name knowing the search was
outstanding. So the caution was written at 5.43 without D-024 in front of it — the second
time in three milestones that an item's premise turned out to be settled elsewhere, and the
same lesson as 5.41: check what a "delivered" decision actually decided before building on a
later item's summary of it.

Re-verified today rather than trusted: `mycelium-os` is free on PyPI and TestPyPI, and
`mycelium` is a luigi workflow library with one release last uploaded 2019-10-08 — exactly
what D-024 described, seven years stale.

And the exposure the caution guards is already spent. `mycelium://` citation URIs and the
`mycelium_*` MCP tool names sit inside the five stable contracts, whose identity rules
ADR-0114 made append-only *for good* one PR ago. A trademark outcome that forced a rename
would break those whether or not PyPI holds the name.

## The finding the item did not predict

Nothing had ever opened a built distribution. CI ran `hatch build` on every cell of the
matrix, proved the tag compiled, and threw the result away — the same shape as BUG-0006,
where the build proved the tag worked and then discarded the wheel the release was supposed
to attach.

So I built one and looked inside. The sdist was declared by a single exclusion
(`exclude = ["contrib"]`), which means *the working directory, minus contrib, minus whatever
the root `.gitignore` names*. At v0.5.0 that was 14.5 MB across thirty top-level entries:
2.7 MB of judged corpora, the vendored EADOS factory, 1.9 MB of brand assets, a 1,248-file
Hypothesis example database — ignored by a nested `.gitignore` that hatchling does not read
— and, the entry that settled the design, `docs/analysis/` and `.claudeignore`: **the
maintainer's untracked working files**, swept in because they are untracked rather than
ignored.

That is not bloat, it is two defects. A published version is immutable, so an artifact whose
contents depend on who built it and what they had open cannot be reproduced; and an
in-progress document that reaches an index cannot be recalled.

An allowlist fixes both and a longer denylist cannot, because a denylist is a prediction
about what will be lying around and both of these were unpredicted. Six entries now, 1.5 MB.

## Proving a publish pipeline you are not allowed to run

The interesting constraint. Three things stand between this repository and a published
package — a PyPI account, a pending publisher, an environment reviewer — and all three are
the maintainer's. So the question is what can be *checked* short of the upload.

`tools/check_distribution.py` is the answer: build both archives, assert the sdist carries
only what it declares, assert the wheel carries the package and its PEP 561 marker, run
`twine check --strict`, then install the wheel into a clean environment and walk it from
`mycelium init` to a `mycelium://` citation. That last step is the README's install line,
checked — the promise the project has been making since M1 and had never run. 64 s, the same
price as the ingested-corpus check beside it at `code` mode.

The other half is making the dangerous act impossible rather than discouraged. `publish.yml`
fires on `workflow_dispatch` and nothing else, so no tag push can publish as a side effect;
it defaults to TestPyPI; it runs inside an environment; and it holds no credential at all,
because Trusted Publishing mints a short-lived token per run. Seven tests pin those
properties, so an edit that adds a token or a push trigger fails a test rather than a
release.

## What is honest to claim

The pipeline is built and **unproven at its last inch**. No upload has happened, so the OIDC
handshake, the environment gate and the index's acceptance of this metadata are unexercised.
TestPyPI is in the flow so the first exercise is a rehearsal rather than the name-claiming
upload. The README says the package is not on PyPI and gives the install that works today,
verified in a clean venv; when the upload lands, three short blocks collapse to one line
each.

## Lesson

An artifact nobody has opened is a claim, exactly like a policy nobody has checked. The
publish step was missing and visible; the thing it would have published was wrong and
invisible, and only building the archive and reading its file list found it. Before adding
the step that sends something somewhere irreversible, look at what it would send.
