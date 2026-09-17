# 2026-09-17 — a landscape scan is not a clearance (roadmap 6.5)

- **Session scope:** roadmap 6.5 — the trademark search and brand decision, routed
  `owner call`.
- **PR:** `chore/trademark-search-6-5`, following #146.
- **Milestone 6:** 6.5 delivered. Open: 6.7–6.10, 6.12–6.15, 6.17–6.23.
- **Decision it records:** [ADR-0121](../../../adr/0121-search-the-trademark-landscape-and-correct-what-d-024-assumed.md).

## What the item actually asked for

Two things bundled under one size-S item: a trademark search, and a brand decision before
"the public branding push." The route (`owner call`) said which half was not mine to
close, and the Interaction Contract's §12.4 says the same thing in general terms: a claim
follows the evidence, a decision follows the maintainer.

## What the search found, and what it is not

A web-search landscape scan — Justia and Trademarkia surfacing USPTO filings, one IP
Australia record — read on 2026-09-17. Not a TESS, EUIPO or WIPO live query, and not an
attorney's clearance opinion; USPTO's own guidance says a self-search wants professional
supplementing before anyone relies on it, and this ADR says so rather than dressing a
web search up as more than it is.

Four things worth the record:

- **MRD X-Change GmbH's Mycelium Bitcoin Wallet** (US Reg. 6352173) is registered in Class
  009 — the *same* class as this project's own downloadable software. Product strategy §9
  had called it "a different trademark class" since D-024, and that was wrong: same class,
  different specific goods (a crypto wallet, not a knowledge compiler). Corrected in this
  PR, not reopened as a decision — D-024 itself made no claim about the class, so nothing
  D-024 decided was wrong, only a sentence describing it.
- **`hawkw/mycelium`** is a real, active open-source Rust project describing itself as an
  operating system. No trademark claim found, but a genuine practical collision in exactly
  the systems/developer-tooling audience this project's plugin ecosystem wants to reach.
- Two further software-adjacent filings (Mycelium Software Inc., US, mobile content apps;
  Mycelium Ventures Pty Ltd, Australia, fintech/SaaS) sit near but not on this project's
  actual goods.
- Several more (Mycelium Enterprises LLC's food/agriculture marks, Mycelium S.A.'s Swiss
  payment mark, Hanwha's Korean investment mark) are not relevant on the goods found.

None of the four is a registration for a knowledge compiler or a developer tool.

## The decision, asked and answered in one turn

Put to the maintainer with the table above, in Italian per how this session runs: proceed
as-is, no filing, revisit before a commercial or paid push. The maintainer chose exactly
that — the option this session flagged as the low-cost default given D-024's sunk brand
equity (a live founder site, Discord, logo, and — since roadmap 6.11 — a published PyPI
package with real installs possible from the day it merged).

## What changed, and what did not

`.draft-specs/01-product-strategy.md` §9 now states the actual relationship to the
Bitcoin-wallet mark. Nothing else moved: no filing, no rename, no identifier touched.
ADR-0121 records the decision's own trigger for revisiting it — a commercial or paid
branding push, or a decision to file a trademark of our own, either of which needs a real
attorney and a search this session could not perform.

## Lesson

A search that cannot query the databases it names should say so in the same breath as its
findings, not in a footnote — and a decision an item's own routing marks as the
maintainer's should be asked plainly, with the evidence in hand, rather than assumed from
the sunk cost that makes one answer likely.
