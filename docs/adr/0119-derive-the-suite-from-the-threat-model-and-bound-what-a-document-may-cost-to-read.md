# ADR-0119: Derive the suite from the threat model, and bound what a document may cost to read

- **Status:** Accepted
- **Date:** 2026-09-17
- **Deciders:** security-auditor role (the `/eados security` sub-mode), acting through the
  tech-lead delivery agent, per RFC-0001 / spec 06 §Phase 4; the owner resolves the register
- **Related:** [ADR-0033](0033-keep-the-original-and-bound-the-hostile.md) (the ingest lane's
  cost bounds, which the authored lane now shares), [ADR-0037](0037-record-what-was-refused-and-redact-what-was-found.md)
  (the secret scan whose one rule was quadratic), [ADR-0110](0110-drop-the-markup-and-keep-the-words-on-evidence-a-placeholder-cannot-forge.md)
  (why hidden-by-renderer text is a residual and not a bug), [ADR-0114](0114-freeze-the-five-contracts-as-goldens-and-publish-the-promise-before-the-tag-that-binds-it.md)
  (the envelope and the error fields a document cannot forge are the frozen tool contract),
  [ADR-0118](0118-make-a-deferral-name-the-condition-that-ends-it.md) (a control that is a
  sentence is what this ADR is about, one level down), [ADR-0053](0053-report-on-the-corpus-we-author-and-gate-on-the-one-we-do-not.md)
  (why the injection corpus is not an eval gate); spec 02 §8, spec 04 §6 (amended here),
  spec 06 §Phase 4 and §5 (R8); D-017; roadmap 3.7, 6.3, 6.17

## Context

Roadmap 6.3 asks for a *security review pass: a threat-model-derived test suite including
the injection corpus*. Spec 06 §Phase 4 makes "zero critical findings open from security
review" an exit gate, and risk R8 names the injection corpus a release gate. Before this item:

**The threat model was fifteen boundaries of sentences.** Each STRIDE row names a control,
and whether a test stood behind it was a matter of reading the test tree with the model open
beside it. Walked that way once, five controls had nothing behind them — the pandoc
`--sandbox` and timeout claimed since 4.1 among them — three boundaries were still marked
*(design)* four milestones after their controls shipped, one row still rested on "private
repo today" (void since 6.16), and a duplicated B14 row sat outside the table.

**The injection corpus was three documents inline in a test.** Spec 04 §6 asks for adversarial
documents "in the eval corpus" with "the harness" asserting verbatim return; the judged
`injection` slice has one case and checks that the *doctrine* is findable, and
`tests/test_injection.py` checked three attack shapes against a temporary corpus, saying in
its own docstring that the full suite was 6.3's.

**Nothing had measured what a document may cost to read.** The ingest lane bounds an
acquired source at 64 MiB, refuses an archive from its header and a markup tree from its
depth (ADR-0033). The authored lane, which compiles the same Markdown through the same
adapter and receives every projection the ingest lane writes, bounded nothing. The review
probed, in subprocesses with hard timeouts, what a hostile file, query or export could make
the compiler and the server spend:

| probe | result |
|---|---|
| nine lines of YAML aliases in frontmatter (387 million leaves as shared references) | `build` did not return in 90 s; `safe_load` alone took 6 ms — the expansion is walked downstream |
| 40 KB of asterisks (emphasis nested ten thousand deep) | `RecursionError` from the syntax-tree builder; the build quarantined it by a catch-all in 13 s, `mycelium ingest` died with a traceback |
| 20 000 PEM headers, 640 KB, no footers | `scan_text` did not finish in 60 s; every other rule scanned a megabyte of its worst case in under a second |
| a 190 KB query of 20 000 terms | 57 s inside the single-threaded stdio server (5 000 terms: 2.7 s) |
| 100 000 nested brackets to `chats import` | `RecursionError` out of `json.loads`, caught by nobody |
| nine hidden-text shapes | HTML comments and link titles reach neither KIR nor index; `<div hidden>` text and Unicode tricks are indexed verbatim |
| FTS5 syntax, SQL, a 200 KB token, a bidi override, in the query | matched as words or ignored, in milliseconds |

## Decision

**The suite is derived from the model, mechanically, in both directions.** A test file that
holds a boundary declares it at module level — `pytestmark = pytest.mark.boundary("B4")`,
a list where it holds several — so `pytest -m boundary` *is* the threat-model-derived suite.
`tests/test_threat_model.py` checks the derivation is whole: every boundary the model declares
is held by at least one test file or excused there by name with its reason (B3, the vendored
bundle, whose control is the review of its diffs); every marker names a declared boundary; the
marker is registered so a misspelt one fails; a file that claims a boundary has tests in it.
Thirty-seven existing files were marked on the review's reading and four new ones carry their
own. The model gains §4, which says this and gives the reading at 6.3; the test, not the
table, is the authority.

**The injection corpus is a fixture corpus asserted by the suite, not by the eval harness —
a recorded deviation from spec 04 §6.** `tests/fixtures/injection/` holds twenty-three
authored documents, one attack class each — an instruction in prose, in a heading, in a
callout, in a title, in alt text; a fenced tool call; an envelope spoof; a fake citation; an
HTML comment and a hidden block; zero-width joins, a bidi override, a homoglyph; a
frontmatter-shaped status forgery in the body and a real one in frontmatter; a duplicate
identity; references outside the tree; a forged `mycelium_search` symbol; a credential in
prose; and the small forms of the alias bomb and the emphasis run. `attacks.json` declares
each with its payload, the word a query finds it by, the fields the payload may appear in,
and whether the build indexes or quarantines it; `make_corpus.py` regenerates both. The
suite asserts, per document, that a served payload comes back verbatim and *only* inside its
allowed fields; that the envelope, identity, status and graph are the server's whatever the
document says; that a channel a reader cannot see is not indexed; and that a document built
to cost unbounded time is refused by name inside a budget. Two residuals are declared rather
than discovered, and a test pins the list so a third is a decision. The eval corpus stays
what it is, because an attack document in the documentation corpus moves every retrieval
number for no gain, and nDCG cannot express "returned verbatim" (ADR-0053's rule: gate on
what a metric can say).

**A document's cost to read is bounded in both lanes, at the point the cost is incurred.**
Frontmatter is loaded through a `SafeLoader` subclass that refuses YAML aliases — the profile
has no use for them — under a 64 KiB block ceiling, so a block is bounded before a field is
read (BUG-0027). The adapter measures the token stream's deepest nesting before the syntax
tree is built and refuses a document past `MAX_NESTING`, markdown-it's own `maxNesting` of
100 (the deepest document in the three corpora nests six), as a `MarkdownError` both lanes
quarantine; a guard behind it turns a `RecursionError` from the tree builder into the same
typed error (BUG-0029). An authored document over the file connector's 64 MiB is quarantined
instead of read whole. Every secret rule is linear: a rule may carry a `closer`, and the PEM
rule matches its header and extends forward once to the footer or the last line that could
sit inside a key — so a truncated key flags and redacts where before it matched nothing,
while a header with nothing under it flags nothing, because that is documentation of a key
and this repository's own ledger quotes one (BUG-0028). The chats readers and the segmenter type a `RecursionError` out of `json.loads`
as the refusal it is (BUG-0030). Each bound is held by a test at the size that used to break
it.

**What the review leaves open, it leaves open by name.** The unbounded query is filed as
roadmap 6.17 rather than capped here, because a cap on the terms a query contributes is a
retrieval change with gates of its own, and a security PR is the wrong place to move a
ranking (register F11, low, the threat-model row ⚠️). Text a renderer would hide is an
accepted residual (F12): closing it means the compiler guessing at CSS. A credential in an
*authored* document is served verbatim by design — the scan runs at ingestion, the authored
tree is the user's Git content — and the corpus asserts both that and that the same document
ingested is redacted.

**No finding is critical and no advisory is opened.** All four defects are denial-of-service
shapes against a local, single-user compiler and server, on input the operator chose to
compile or import; none damages data or crosses a trust boundary. The M6 exit gate holds.

## Alternatives Considered

- **Put the injection corpus in `eval/` and score it through the harness, as spec 04 §6
  reads.** Rejected. The harness's metrics rank chunks; none can express "returned verbatim
  inside a typed field", so a gate on them would pass an elided payload and fail a verbatim
  one that ranked low. And adding twenty-three attack documents to a documentation corpus
  moves every judged number for reasons that have nothing to do with retrieval. The spec's
  intent — asserted, not hoped — is met by the suite; the location is the deviation, and it
  is recorded in spec 04 §6.
- **Keep the boundary→test map as a table in the model, by hand.** Rejected. That is the
  shape that drifted: a sentence about tests is as unverified as a sentence about controls.
  The marker puts the claim in the file it is about, and the meta-test reads both sides.
- **Catch `RecursionError` in the ingest pipeline's per-document handler and stop there.**
  Rejected as the control, kept as the guard. A catch-all names the interpreter, not the
  document's fault, and the build already had one and still spent thirteen seconds per file.
  The bound — depth measured before the tree is built — is the control; the guard behind it
  is for a shape the measure does not model.
- **Bound the frontmatter block's size and leave aliases alone.** Rejected: the bomb is three
  hundred bytes. Size bounds the parse; only refusing the expansion bounds the walk.
- **Make the PEM regex's body bounded (`{0,N}`) instead of extending in code.** Rejected: still
  quadratic in the number of headers, merely with a smaller constant, and a truncated key
  still matches nothing.
- **Cap the query's term count in this PR, since the probe found it.** Rejected on ordering,
  not on merit: `mycelium.store` is a tuning path, the cap changes what a long query returns,
  and that decision belongs under the retrieval gates as its own item (6.17).
- **Drop hidden-by-renderer text (`hidden`, `display:none`) from the index.** Rejected: the
  compiler would be interpreting presentation it does not render, and ADR-0110 chose to keep
  words for fidelity on evidence. Declared as a residual the corpus asserts, so the trade is
  visible and reversible.

## Consequences

- **`pytest -m boundary` exists** and `tests/test_threat_model.py` fails when a declared
  boundary loses its last test or a marker names a boundary that does not exist. Adding a
  boundary to the model without a marked test fails the suite, which is the point.
- **Four defects fixed, one control added, one item filed.** BUG-0027 to BUG-0030 are `fixed`
  in the ledger with 0.6.0 as `fixed-in`; the authored byte ceiling is new; 6.17 carries the
  query cap with its measurement.
- **The verification mode is `retrieval`**, because `src/mycelium/markdown/` is a tuning path
  (roadmap 5.40). Nothing in ranking moved: a well-formed document parses exactly as before,
  and gate G6's golden is byte-identical. The gates run anyway, which is what a tuning path
  means.
- **Behaviour changes, all at the edge of malformed input:** a frontmatter block using a YAML
  alias, or over 64 KiB, is now refused where it used to hang; a document nesting past 100
  levels is refused where it used to crash or stall; an authored document over 64 MiB is
  quarantined where it used to be read; a truncated PEM key is flagged and redacted where it
  used to pass; `chats import` reports bracket soup where it used to die. No well-formed
  document in the three corpora is affected, and the ingested corpus reproduces byte for byte.
- **The threat model is corrected where it undersold the product** (B6, B8, the repudiation
  and promotion rows, the B1 spam row) and extended where the review found new rows; a
  duplicated row is removed. Its header records the revision; §3 lists both registers; §4 is
  new.
- **A limitation, stated.** The probes were shaped by the reviewer's reading of each control;
  they are not a fuzzer, and a shape nobody thought of is not bounded by a test nobody wrote.
  What the derivation guarantees is narrower and real: a boundary the model declares has a
  test that claims it, and a control that loses its test is visible.

## References

- Spec: `.draft-specs/02-architecture.md` §8; `.draft-specs/04-retrieval-and-evaluation.md`
  §6 (amended here); `.draft-specs/06-roadmap-and-governance.md` §Phase 4, §5 R8.
- The register: `docs/security/audit-2026-09-17-review-pass.md`. The model:
  `docs/security/threat-model.md` §4. The corpus: `tests/fixtures/injection/`.
- Re-runnable: `uv run pytest -m boundary -q`; `uv run pytest tests/test_threat_model.py
  tests/test_injection.py tests/test_security_controls.py -q`.
