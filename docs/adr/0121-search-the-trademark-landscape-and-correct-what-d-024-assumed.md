# ADR-0121: Search the trademark landscape, and correct what D-024 assumed

- **Status:** Accepted
- **Date:** 2026-09-17
- **Deciders:** tech-lead (EADOS delivery agent); the brand decision is the maintainer's,
  per this item's own routing (`owner call`) and the Interaction Contract §12.4
- **Related:** [D-018](../../.draft-specs/00-verdict-and-decisions.md),
  [D-024](../../.draft-specs/00-verdict-and-decisions.md) (the naming decision this
  corrects one claim of), `.draft-specs/01-product-strategy.md` §9; roadmap 6.5

## Context

Roadmap 6.5: *"Trademark search + brand decision before the public branding push"*,
routed `owner call` — the item's own signal that its second half is not an engineering
decision. Product strategy §9 recorded the name decision (D-024, 2026-07-31: **Mycelium**,
everywhere, one name) and flagged a trademark search as a pre-1.0-launch task, noting in
passing that *"the unrelated 'Mycelium' Bitcoin-wallet brand exists in a different
trademark class."* That claim is checked here, and it does not hold.

**What this search is, and what it is not.** It is a landscape scan built from public web
search results — USPTO filings surfaced through Justia and Trademarkia, one IP Australia
record, and open-source/package-namespace checks — read on 2026-09-17. It is **not** a
live query against USPTO TESS, EUIPO or the WIPO Global Brand Database (none of which this
environment can query directly), and it is **not** a clearance opinion: a real one reads
the full prosecution history of each mark, checks likelihood-of-confusion factors a
paralegal or attorney is trained to weigh, and covers jurisdictions and coordinated
classes a keyword search does not surface. USPTO's own guidance says exactly this — supplement
a self-search with counsel before relying on it. What follows is evidence for the
maintainer's decision, not the decision.

## What was found

| Mark / owner | Jurisdiction, status | Goods / services | Relevance |
|---|---|---|---|
| **MYCELIUM** — MRD X-Change GmbH, US Reg. **6352173** (filed 2020-06-25, registered 2021-05-18) | USPTO, **live** | Nice Class **009**: "downloadable computer software for use as a cryptocurrency wallet"; the well-known Mycelium Bitcoin Wallet | **Same class as ours** (009, downloadable software). Product strategy §9's "different trademark class" is wrong — it is the same class, a narrower and different specific good (a crypto wallet, not a knowledge compiler). Likelihood of confusion turns on relatedness of the actual goods and the buying public, which a search cannot weigh; an attorney can. |
| **mycelium** — Eliza Weisman (`hawkw`), GitHub, active | No trademark found; common-law / community use | An open-source Rust "operating system", literally described that way | Not a legal trademark issue on the evidence found, but a **real practical collision**: another well-known project in the systems/developer-tooling space already answers to "mycelium … operating system" in search results and in the Rust community this project's plugin ecosystem may want to recruit from. |
| **MYCELIUM** — Mycelium Software Inc., US Serial **98295090** (filed 2023-12-01) | USPTO, filing found; **status not confirmed** by this search | Class 009 (as filed): downloadable / mobile-app software for creating, viewing, editing and publishing digital content | Adjacent (content software), not developer tooling; a live registration here would still sit in the same class. |
| **MYCELIUM** — Mycelium Ventures Pty Ltd, IP Australia App. **2172629** (filed 2021-04-29) | Australia only | Mixed: venture-capital/fintech services **and** "computer software design", "development of software", "hosting of software as a service (SaaS)" | Different jurisdiction (AU, not US); goods list includes software development/SaaS services, which overlaps this project's eventual commercial surface if one is ever offered there. |
| MYCELIUM CAFE / COLLECTION / mushroom marks — Mycelium Enterprises LLC | USPTO | Food service, jewelry, agricultural/mycology products | **Not relevant** — unrelated goods, no software class. |
| MYCELIUM SWISH — Mycelium S.A. (Swiss); MYCELIUM — Hanwha Investment & Securities (Korea); MYCELIUM GEAR | USPTO / other | Payments, financial investment services, unrelated goods | **Not relevant** on the goods found. |

**What was not found:** a registered mark for "Mycelium OS", "MyceliumOS", or "Mycelium
LABS" in any register searched; nothing on PyPI, npm or GitHub org names beyond what
D-024 already checked (`mycelium` on PyPI held by an unrelated abandoned package since
2019, PEP 541 transfer pending).

## Decision

**Three things are decided here.**

1. **Product strategy §9's characterization is corrected.** The MRD X-Change GmbH mark is
   in the *same* Nice class as this project's own software, not a different one. The
   sentence is rewritten below to state the actual relationship — same class, different
   specific goods — rather than a comfortable approximation.
2. **No filing, no rename, no identifier change happens as a result of this item.** D-024's
   rationale for the name stands on its own terms: a live founder site, Discord and logo
   already carry Mycelium brand equity, and the package is already published to PyPI as
   `mycelium-os` (roadmap 6.11) with real installs possible from the day it merged. A
   landscape scan is not grounds to unwind a decision three milestones of shipped work sit
   on top of, and this ADR does not attempt to.
3. **The brand decision, put to the maintainer with this evidence, is: proceed as-is.**
   The project ships under Mycelium / `mycelium-os` exactly as D-024 already decided, with
   no defensive filing of its own for now. The landscape above is not treated as blocking
   because nothing found is a live registration for a knowledge compiler or developer tool,
   and D-024's sunk-cost rationale (live founder site, Discord, logo, a published PyPI
   package) stands. **This is not a closed question — it is a decision to revisit before any
   commercial or paid branding push**, which is the moment a real clearance search or a
   narrower claim (e.g. never asserting the bare word "Mycelium" alone) becomes worth its
   cost. Recorded here rather than only in the roadmap so a later session finds the
   reasoning, not just the checkbox.

## Alternatives Considered

- **Treat the search as clearance and close the item.** Rejected: nothing in this
  environment can perform the query TESS, EUIPO or WIPO's databases actually run, and
  reporting a web-search summary as a clearance opinion would be a claim this session
  cannot back — the opposite of calibrated confidence (§12.1).
- **Recommend a rename now, given the crowded landscape.** Rejected as a decision I could
  make: D-024 was an explicit owner decision with its own accepted rationale, three
  milestones of tooling (`mycelium.toml`, `mycelium://`, `mycelium_*` MCP tools,
  `mycelium.plugins`) are built on the name, and the package is already live on PyPI. A
  rename is exactly the kind of consequence-heavy, hard-to-reverse call this project's
  contract reserves for the maintainer.
- **Leave §9's mischaracterization alone since the owner already accepted the risk.** Rejected:
  the owner accepted a *specific* factual claim ("different class"), which was wrong. Holding
  a claim only while the evidence supports it, and conceding when it does not, applies here
  even though the underlying decision (D-024) is not being reopened.

## Consequences

- **`.draft-specs/01-product-strategy.md` §9** is corrected in this PR: the trademark
  sentence now states the actual relationship to the Bitcoin-wallet mark and records that
  the pre-1.0 search happened, with this ADR as the citation. D-024's decision text in
  `.draft-specs/00-verdict-and-decisions.md` is unchanged — it made no claim about the
  trademark class, so nothing there was wrong.
- **Roadmap 6.5 closes on this PR.** Both halves of the item are delivered: the search, and
  the maintainer's decision (proceed as-is, revisit before a commercial or paid push) taken
  against it in the same conversation this ADR records.
- **A live, same-class US registration exists for a well-known product this project shares
  no goods with, and the decision is to ship anyway.** That is a risk knowingly carried, not
  one resolved — the trigger for revisiting it is named above rather than left implicit.
- **A real clearance search, if a future push wants to file a trademark application of our
  own, is unpriced by this ADR.** It would need a US trademark attorney or search firm,
  cover Class 009 and Class 042 at minimum, and probably the EU and Australia given this
  project's actual users. Filed as the trigger this ADR names, not as a task today.

## References

- USPTO, *Federal trademark searching*: a self-search is a starting point, not a
  substitute for professional clearance — https://www.uspto.gov/trademarks/search/federal-trademark-searching
- MYCELIUM, MRD X-Change GmbH, US Reg. 6352173 / Serial 90021585 —
  https://trademarks.justia.com/900/21/mycelium-90021585.html
- `hawkw/mycelium` — https://github.com/hawkw/mycelium
- MYCELIUM, Mycelium Software Inc., US Serial 98295090 (filed 2023-12-01) — surfaced via
  https://trademarks.justia.com/owners/mycelium-software-inc-5721200/
- MYCELIUM, Mycelium Ventures Pty Ltd, IP Australia Application 2172629 —
  https://www.trademarkelite.com/australia/trademark/trademark-detail/2172629/MYCELIUM
- `.draft-specs/01-product-strategy.md` §9 (D-024, amended here); roadmap 6.5.
