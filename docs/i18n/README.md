# Documentation translations

English is the **canonical source**. Every canonical page keeps its canonical path
(`README.md`, `CONTRIBUTING.md`, …); a translation is a **derived copy** under
`docs/i18n/<code>/` mirroring that path, and never replaces the original (D-028).

```text
README.md                     ← canonical (English)
docs/i18n/it/README.md        ← derived (Italian)
docs/i18n/zh-Hans/README.md   ← derived (Chinese, Simplified)
docs/i18n/ja/README.md        ← derived (Japanese)
```

A symmetric `en/it/zh/ja` layout was rejected: it demotes the canonical source into false
symmetry, breaks every existing path and inbound link, and loses the freshness gating that
makes translations trustworthy (D-028).

**Status: structure only.** The subsystem is enabled and every tracked page is `pending` —
there are no translations yet. Content work starts with the README, per D-028.

## Target languages

<a id="it"></a>

### Italiano (`it`)

Italian. Status: all pages `pending`. The maintainer's own language, so it is expected to
lead once content work starts.

<a id="zh-hans"></a>

### 中文（简体）(`zh-Hans`)

Chinese, Simplified. Status: all pages `pending`. The variant is an explicit choice —
Simplified reaches the larger audience first; the legacy repository's `README-ZH` was
Traditional (D-028).

<a id="ja"></a>

### 日本語 (`ja`)

Japanese. Status: all pages `pending`.

Adding a fourth language is a manifest change (`i18n.targets` in
[`orchestrator/project.yaml`](../../orchestrator/project.yaml)) plus its rows in
[`translation-status.md`](translation-status.md) — not a decision taken inside a PR that
happens to add a page.

## What is translated, and what is not

Tracked: the pages a **reader** needs in order to evaluate, install, and use the project,
plus the ones governing participation.

| Page | Why |
|---|---|
| [`README.md`](../../README.md) | The front door. |
| [`CONTRIBUTING.md`](../../CONTRIBUTING.md) | How to participate; nobody should need English to read the rules they are held to. |
| [`CODE_OF_CONDUCT.md`](../../CODE_OF_CONDUCT.md) | Same reason, more so. |
| [`SECURITY.md`](../../SECURITY.md) | Reporting a vulnerability must not be gated on language. |

Deliberately **not** tracked — these stay English (AGENTS.md §2):

- `ROADMAP.md`, `CHANGELOG.md` — they change on nearly every PR; a translation would be
  stale more often than not, and the freshness gate would fail permanently.
- `docs/adr/`, `docs/rfc/`, `docs/specs/`, `docs/journal/` — the working record of an
  English-language engineering contract, read by contributors who are already working in
  English in the code.
- `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` — instructions to tools, not prose for readers.

Widening the set is a deliberate act: add rows to `translation-status.md` and say why here.

## Freshness is gated, not promised

Every translated page records the **commit SHA of the English source** it was translated
from. `tools/consistency_lint.py`'s `i18n-freshness` check compares that SHA against the
source's history: if the English page moved on, the check fails and CI goes red.

That is the whole point of the design. A translation that silently drifts is worse than no
translation — a reader trusts it and gets a stale answer. Here, drift is a build failure
with the page named.

Only rows marked `translated` are gated. A `pending` row is a known gap, not a lie, so it
costs nothing.

## Adding or updating a translation

1. Copy the English page to `docs/i18n/<code>/<same relative path>`.
2. Translate the prose. Leave code, identifiers, paths, and command output as they are.
3. Record the English source's current commit:

   ```bash
   git log -1 --format=%H -- README.md
   ```

4. In [`translation-status.md`](translation-status.md), set the row's status to
   `` `translated` `` and paste that SHA into the *Source commit* column.
5. Run `python tools/consistency_lint.py` — it must pass before the PR.

When the English page changes afterwards, the gate fails until the translation is updated
and the SHA re-recorded. Updating the SHA without re-translating defeats the gate; do not.

## Status table

Per-page, per-language: [`translation-status.md`](translation-status.md).
