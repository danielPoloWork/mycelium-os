# Risk register — security review pass (2026-09-17, roadmap 6.3)

- **Auditor:** security-auditor role (the `/eados security` sub-mode of `/eados audit`),
  acting through the delivery agent; the owner resolves.
- **Change under audit:** the repository at `main` = `916974b` (after PR #153), the state
  Milestone 6's security review pass was asked to walk — every trust boundary of the
  [threat model](threat-model.md) against the code that implements its controls and the
  tests that hold them, plus the injection corpus spec 04 §6 asks for.
- **Method:** boundary walk (B1–B15) with each control traced to code and to a test; then
  **measurement** — probes of what a hostile document, query or export can make the compiler
  or the server *spend*, run in subprocesses with hard timeouts. Every probe that found
  something is now a test (`tests/test_security_controls.py`, `tests/test_injection.py`,
  `contrib/chats/tests/test_hostile_input.py`); the probes themselves were not committed.
- **Decision record:** [ADR-0119](../adr/0119-derive-the-suite-from-the-threat-model-and-bound-what-a-document-may-cost-to-read.md).
- **Finding numbers** continue the bootstrap register's (F1–F5), like bug ids: one sequence
  across registers, so `F2` means one thing in `check_repo_settings.py` and in prose.

## Findings

| # | Severity | Component | Finding · realistic impact | Mitigation · status |
|---|---|---|---|---|
| F6 | **medium** (confirmed defect) | `mycelium.markdown.frontmatter` — B4, both lanes | Nine lines of YAML aliases in frontmatter describe 387 million leaves; `safe_load` builds them in 6 ms as shared references and everything that walks the result — pydantic's validation of `properties`, the canonical JSON a digest is taken over — walks the expansion. `mycelium build` on a two-document corpus had not returned after 90 s, with nothing to say which file. One authored or ingested file stalls the compiler; nothing is damaged. | **Fixed here**: a `SafeLoader` subclass refuses aliases, and a block over 64 KiB is refused before it is parsed; both quarantine per document. [BUG-0027](../bugs/2026/09/BUG-0027-a-yaml-alias-bomb-in-frontmatter-stalls-the-build.md). Held at scale by `test_a_yaml_alias_bomb_is_refused_by_name_in_milliseconds`, at fixture size by the corpus |
| F7 | **medium** (confirmed defect) | `mycelium.ingest.secrets` — B4/B11/B15 | The `private-key-block` rule was header, lazy body, footer in one regex. A header with no footer scans to the end of the text and fails, once per header: 20 000 headers in 640 KB had not finished after 60 s. The scan runs on every ingested document, every imported conversation and every paste the segmenter sends. A second defect rode on the first: a key with a truncated footer matched nothing and went into the tree unflagged. | **Fixed here**: a rule may carry a `closer`; the PEM rule matches its header and extends forward once. 20 000 truncated keys scan in under a second and each flags with its body redacted; 20 000 lone headers scan in the same time and none flags, because a header with nothing under it is documentation — this repository's own ledger quotes one. [BUG-0028](../bugs/2026/09/BUG-0028-the-private-key-secret-rule-scans-quadratically.md) |
| F8 | **medium** (confirmed defect) | `mycelium.markdown.adapter` — B4, both lanes | Forty kilobytes of asterisks nest emphasis ten thousand levels; markdown-it parses it and building the syntax tree recurses past the interpreter's limit. The build caught the `RecursionError` in its per-document catch-all — 13 s, with the interpreter's error as the quarantine reason — and `mycelium ingest` did not catch it at all: exit 1, a traceback, no quarantine record. | **Fixed here**: the token tree's depth is measured before it is built and refused past `MAX_NESTING` (100, the parser's own number; the deepest real document nests six) as a `MarkdownError`, with a guard behind it for a shape the measure does not model. Both lanes quarantine by name in milliseconds. [BUG-0029](../bugs/2026/09/BUG-0029-a-long-emphasis-run-recurses-past-the-interpreter-limit.md) |
| F9 | **low** (confirmed defect) | `mycelium_chats.readers`, `mycelium_chats.segment` — B15/B10 | `json.loads` raises `RecursionError` on a hundred thousand nested brackets, which is not the `ValueError` every reader and the segmenter catch, so `mycelium chats import` died with a traceback instead of reporting the input as unreadable. Nothing written. | **Fixed here**: typed as `ReaderError` / `SegmentationError`; `pasted` declines to claim bracket soup. [BUG-0030](../bugs/2026/09/BUG-0030-deeply-nested-json-crashes-chats-import.md) |
| F10 | **low** (missing control) | `mycelium.build.orchestrator` — B4, authored lane | The file connector bounds an ingested source at 64 MiB; an authored document had no ceiling and was read whole into memory before anything asked its size. D-017 declares the user's own documents untrusted content, so the asymmetry was a gap rather than a choice. | **Fixed here**: `MAX_SOURCE_BYTES` = the connector's ceiling; a larger document is quarantined by name and the build carries on |
| F11 | **low** (open, filed) | `mycelium.mcp.tools`, `mycelium.store` — B6 | The query is unbounded. Twenty thousand terms (190 KB) hold the single-threaded stdio server for 57 s; five thousand take 2.7 s; the growth is superlinear in the term count. Every other call waits meanwhile. A local, single-user client can only stall itself, and an agent pasting a document as a query is the realistic case. | **Not fixed here, by decision**: a cap on the terms a query contributes is a retrieval change and belongs under the evaluation gates, not inside a security PR. Filed as roadmap **6.17**. Until then the threat-model row is ⚠️ |
| F12 | **info** (accepted residual) | the Markdown profile — B6/B11 | Since ADR-0110 the profile drops markup and keeps words, so text a *renderer* would hide — `<div hidden>…</div>`, a `display:none` span — is indexed and served as prose, verbatim, with the notice. A human reading the rendered page never sees it; the agent sees exactly what the index holds. HTML comments and link titles are *not* indexed, so the two channels that carry no visible words at all are already closed. | **Accepted**: closing the rest means the compiler guessing at CSS, which it cannot do honestly. Declared in the injection corpus (`hidden-html-block`) so the suite asserts the current behaviour and a change to it is a decision. A `mycelium doctor` warning for hidden-attribute markup is a possible future control, not a promise |
| F13 | **info** (model drift) | `docs/security/threat-model.md` | Three boundaries were still marked *(design)* four milestones after their controls shipped (B6 since 2.9, B8's only crossing since 3.3, the repudiation and promotion rows since 2.7 and 4.5), one row still rested on "private repo today", and a duplicated B14 row sat outside the table. The model described a smaller product than the one that existed, in the direction that undersells the controls. | **Corrected here**, and §4 makes the model name its tests so the next drift is caught by a test rather than a reading |
| F14 | **info** (untested control) | `mycelium.ingest.parsers.pandoc` — B9 | The model claimed since 4.1 that pandoc runs `--sandbox`, over stdin, with a fixed argument vector and a timeout. All four were true in the code and none had a test; a refactor could have dropped `--sandbox` without a red run. | **Test added** (`test_pandoc_runs_sandboxed_over_stdin_with_a_timeout_and_no_shell`); the same walk found four more sentence-only controls, all now under `-m boundary` |

## What the walk found sound

Every other boundary held under measurement, and the findings above are the exceptions:

- **B4 acquisition** resolves before it checks containment, reads under a byte ceiling, and
  refuses archives from their own header; the hostile suite's nine files each fail as one
  typed refusal inside a five-second budget.
- **B5/B10** send evidence to a model quoted under a standing data-not-instructions rule, and
  the citation contract no prompt can relax stands behind it; the judge is fail-closed.
- **B6** returns twenty-one attack payloads verbatim and inside their typed fields only, and
  quotes the two the profile drops nowhere. FTS5 syntax, SQL fragments, a 200 KB token and a
  bidi override in the *query* are matched as words or ignored, in milliseconds.
- **B7** pins resolution and refuses a shadowed id; **B12** re-hashes on every read; **B13**
  refuses a narrowed mode by name; **B14** bounds a fence at 256 KiB and its binding by pin.
- **B15** takes an export into custody before it writes anything and scans it for secrets on
  the way to the projection.
- The hidden-text probe confirmed ADR-0110's control from the other side: an HTML comment's
  words reach neither the KIR nor the index.

## Verdicts

- **No critical finding is open.** The four defects are denial-of-service shapes against a
  local, single-user compiler and server, on input the operator chose to compile or import;
  none damages data, none crosses a trust boundary, and all four are fixed in this change.
  Milestone 6's exit gate *"zero critical security findings open"* holds. (`certain` — every
  finding above is reproduced by a committed test.)
- **No vulnerability requiring an advisory.** No draft advisory opened. (`certain` — the
  impact analysis per finding.)
- **The injection corpus exists**, and the doctrine it asserts held before the corpus did:
  no served payload leaked out of its typed fields on any of the twenty-three documents.
  (`certain` — `tests/test_injection.py`.)
- **Secret hygiene:** unchanged since the bootstrap audit; the scan's own negative corpus is
  this repository's `docs/` tree, still asserted clean. (`certain` — `test_ingest_secrets.py`.)
- **What this pass did not do**, stated: no dependency audit (Dependabot's weekly run is the
  standing control, ADR-0117's SBOM the inventory), no fuzzing beyond the shaped probes above,
  and no review of the docs site's deployment, which does not exist yet (6.14).

## Evidence trail

Probes (subprocess-bounded, not committed): a YAML alias bomb through `build` (timeout at
90 s; `safe_load` alone 6 ms; `canonical_json` of the loaded mapping timeout at 30 s) ·
ten pathological Markdown shapes through the adapter (one `RecursionError`, the rest under
10 s, a 25 MB nested list included) · queries of 100 to 20 000 terms and four syntactic
shapes through `handle_search` and `handle_explain` (57 s at 20 000) · eight shaped inputs
through `scan_text` (one timeout at 60 s) · nine hidden-text shapes through the adapter and a
build · the emphasis run through `build`, `mycelium ingest` and the chats readers · deep JSON
through `reader_for`. Each committed as the test named in its finding. Boundary walk: this
file's §"What the walk found sound" against `threat-model.md` §1–§2 and the tests now
marked under `-m boundary` (`tests/test_threat_model.py` holds the derivation).
