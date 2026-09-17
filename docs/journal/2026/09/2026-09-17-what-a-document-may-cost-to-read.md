# 2026-09-17 — what a document may cost to read (roadmap 6.3)

- **Session scope:** roadmap 6.3 — the security review pass, the threat-model-derived test
  suite and the injection corpus.
- **PR:** `feat/security-review-pass`, following #153 (merged as `916974b`).
- **Milestone 6:** 6.1, 6.2, 6.6, 6.11, 6.16 delivered before this session; 6.3 delivered
  here; 6.17 filed.
- **Records it produces:** [ADR-0119](../../../adr/0119-derive-the-suite-from-the-threat-model-and-bound-what-a-document-may-cost-to-read.md),
  the register [`audit-2026-09-17-review-pass.md`](../../../security/audit-2026-09-17-review-pass.md),
  BUG-0027 to BUG-0030.

## What "review pass" turned out to mean

Two things, and the second was the one that produced findings. The first was a walk: every
boundary in the threat model, its controls traced to the code that implements them and to
the tests that hold them. That found sentences — five controls with nothing behind them,
three boundaries still marked *(design)* four milestones after they went live, a STRIDE row
still resting on "private repo today", a duplicated row outside the table. Real, but the
kind of finding a careful reader produces.

The second was measurement. The question was not *is this control present* but *what can
one document make the compiler spend*, and the way to ask it was to write the document and
time the compiler, in a subprocess with a hard timeout so that a hang is a number and not a
stuck session. Nine lines of YAML: the build did not come back in ninety seconds. Forty
kilobytes of asterisks: a `RecursionError`, quarantined by luck in one lane and fatal in the
other. Twenty thousand PEM headers: the secret scan did not come back in sixty. A hundred
thousand brackets: `chats import` died with a traceback. None of these needed cleverness;
each needed someone to try.

## The alias bomb, and where the time went

`yaml.safe_load` took six milliseconds on the bomb, which is what made it worth isolating:
PyYAML builds an aliased structure as shared references, so the parse is cheap and the
387 million leaves exist only to whoever *walks* the result. Two walkers do — pydantic
validating `properties`, and `canonical_json` over the mapping — and each timed out alone.
The fix therefore belongs at the loader, not downstream: refuse aliases outright, because
the profile has no use for them, and cap the block at 64 KiB so that even the literal form
is bounded. Fixing the walkers would have fixed two of the walkers.

## Shape, at fixture size and at scale

The injection corpus holds the *shape* of each attack — a nine-line bomb, four thousand
asterisks — and `tests/test_security_controls.py` holds the megabytes, generated at test
time. The corpus proves the doctrine on twenty-three documents in one build under a budget;
the controls file proves each bound at the size that used to break it. Committing the large
forms would have been a repository full of asterisks for no gain.

Three of the corpus's assertions were wrong on the first run, and each was my picture of the
product rather than the product: an embed is served as its target words, not its syntax; a
document's own id legitimately appears in every URI, so it is not a "hidden channel"; and
the meta-test matched the marker literal inside its own docstring. The corpus was right and
the reviewer's expectations were what got corrected, which is the order it should be.

## The derivation, made mechanical

The model now names its tests. Not in a table maintained by hand — that is the shape that
had drifted — but in the test files themselves: `pytestmark = pytest.mark.boundary("B4")`,
and a meta-test that reads both sides. Thirty-seven existing files were marked on the
review's reading, four new ones carry their own, B3 is excused by name, and `pytest -m
boundary` is now a thing one can run. A boundary that loses its last test fails the suite;
a marker that names no boundary fails it too.

## What was left open, on purpose

A 190 KB query holds the server for 57 s. The cap is a retrieval change — `mycelium.store`
is a tuning path, the cap changes what a long query returns — and a security PR is the wrong
place to move a ranking. Filed as 6.17 with its measurement, low severity, and the threat
model's row marked ⚠️ until it lands. And text a renderer would hide is indexed as the words
it is, which ADR-0110 chose for fidelity; the review declares it a residual the corpus asserts
rather than closing it by having the compiler guess at CSS.

## Lesson

A control that is a sentence costs nothing to write and nothing to lose, and this repository
had at least five of them. The two things that changed that are cheap and mechanical: a
marker on the test that holds the control, and a probe that asks the product what a hostile
input costs rather than reading the code to decide it cannot cost much. Every defect this
review found was in a path the code's author had bounded *in the other lane*.
