# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The planner: which generators a query needs, and why (spec 04 §2, roadmap 5.11).

Spec 04 §2 asks for *"a small, deterministic, logged rule set — not a model
call"*, prints the rules as a table, and adds one obligation that outlived every
milestone since: *"Every response's `explain` includes the chosen plan and why
(matched rule), so planner behavior is auditable and debuggable rather than
folkloric."* Until this module the plan reported by `mycelium_explain` was the
name of the configured profile, which is not a plan and has no rule behind it.

**The plan narrows; the configuration decides.** This is the load-bearing rule
and it is the reason a planner can be added to a query path whose defaults were
all set by measurement. A plan may *withhold* a generator the configuration
enabled; it may never *enable* one the configuration disabled. Gate G2 decided
the vector leg's default, and two ablations decided the graph and symbol legs'
(ADR-0017, ADR-0075, ADR-0080) — a router that could switch a leg on would
overturn three measured verdicts with a regex. It is the same direction of
safety `_serve_only` applies to the serving policy: narrow, never widen.

**What is routed, and what is not, is a measurement rather than a reading**
(ADR-0083):

- **The graph leg is routed.** Expansion on every query pays its cost on all
  cases and offers its benefit on few, and routing recovers the difference: the
  overall regression an operator pays for turning it on falls from 0.0–4.1 % to
  0.0–1.6 % across the six judged sets.
- **The symbol leg is routed, and the routing is where it always was.** The leg
  already tested each query token for identifier-likeness and asked the store
  nothing when none passed; that test is this module's `identifier` rule, moved
  to where a plan can report it. Behaviour is identical by construction.
- **The vector leg is not routed, and the refusal is measured.** Spec 04 §2's
  first row ends *"vector as backfill"*, which reads as a licence to withhold the
  vector leg from identifier queries — and hybrid's one losing slice at gate G2
  was `exact`, which is where the identifier queries are (ADR-0017). Measured, it
  is the wrong way round: withholding costs uv/dev 5.2 points of hybrid's gain
  and turns `exact` from +9.7 % to −0.5 %, and uv/release's `exact` from −1.6 %
  to −9.0 %. The vector leg *helps* identifier queries on these corpora.

**Signals are independent; the rules are reported in the spec's order.** Spec 04
§2's table reads as first-match-wins, and first-match-wins would mean a query
that both names an identifier and asks a relationship question silently loses
its symbol lookup — a behaviour nobody measured and nobody wants. So every rule
that matches is recorded, and the generators a plan asks for are the union of
what the matched rules ask for. On the 133 judged case-instances no query matches
two rules, so the difference is untested by the corpora and is a design choice
made in the safe direction rather than a measured one.

**The relationship rule's recall is poor, it is stated rather than improved, and
that is deliberate.** Spec 04 §2 names two phrasings — *"what depends on…"*,
*"related to…"* — and :data:`RELATIONSHIP_PHRASES` generalises them to the verb
family they belong to and no further. Measured against the judged `relationship`
slice it reaches **3 of 22** case-instances at 100 % precision. A wider list
reaches 13 of 22 at 72 % — and it was written by reading the queries it had to
catch, which is fitting the router to the benchmark (D-010), so it is reported in
ADR-0083 and refused. The honest consequence is that the phrase list is a weak
signal and `--related` is the reliable one: the caller knows what kind of
question they are asking, and spec 04 §2 puts their flag in the same cell as the
phrasing for exactly that reason.
"""

import re
from dataclasses import dataclass
from typing import Final

from mycelium.symbols import identifier_like

__all__ = [
    "GENERATORS",
    "GRAPH",
    "LEXICAL",
    "RELATIONSHIP_PHRASES",
    "SYMBOL",
    "VECTOR",
    "Plan",
    "plan_query",
]

LEXICAL: Final = "lexical"
VECTOR: Final = "vector"
GRAPH: Final = "graph"
SYMBOL: Final = "symbol"

GENERATORS: Final = (LEXICAL, VECTOR, SYMBOL, GRAPH)
"""Every generator a plan can name, in the order :func:`mycelium.retrieval.search`
runs them. Named here so the planner and the query path cannot disagree about
what a leg is called — the two halves of one decision."""

RELATIONSHIP_PHRASES: Final = (
    "depends on",
    "depend on",
    "depends upon",
    "depend upon",
    "related to",
    "relate to",
    "relates to",
    "relationship between",
    "connected to",
    "linked to",
    "refers to",
    "refer to",
    "what uses",
    "who uses",
    "what reads",
    "what writes",
    "what calls",
)
"""Phrasings that route a query to graph expansion (spec 04 §2).

The spec prints two — *"what depends on…"* and *"related to…"* — and this is
that pair generalised to its verb family: the dependency verbs in both voices,
and the inverse-dependency question *"what uses/reads/writes/calls X"*, which is
what *"what depends on"* asks with the arrow turned round. It stops there.

The membership is an English fact about a phrasing, in the same sense
:data:`mycelium.retrieval.STOPWORDS` is an English fact about function words —
not a tuning parameter, and not a list to extend whenever a query is missed.
What it costs is stated in ADR-0083 and in this module's docstring: 3 of 22
judged relationship case-instances, at 100 % precision. Extending it until the
slice is covered is how a router gets fitted to a benchmark."""

_TOKEN: Final = re.compile(r"[A-Za-z0-9_./:+-]+")
"""How the planner cuts a query into candidate names.

The same expression the symbol leg used before this module existed, and
deliberately not the lexical leg's word boundary, which splits `uv.lock` into
`uv` and `lock`: the two halves of a name are not the name (ADR-0080)."""

_QUOTE: Final = re.compile(r"\"[^\"]+\"|'[^']+'")
"""A quoted phrase — spec 04 §2's other identifier-shaped signal."""


@dataclass(frozen=True, slots=True)
class Plan:
    """What a query asks for, and which rule said so (spec 04 §2)."""

    rules: tuple[str, ...]
    """Every rule that matched, in the spec's table order. Never empty: the
    natural-language rule is the default and matches whatever the others do
    not."""

    generators: frozenset[str]
    """The generators these rules ask for — a *request*, not a decision. What
    actually runs is this set narrowed by the configuration, which is the rule
    this module exists to keep (see the module docstring)."""

    why: str
    """One operator-facing sentence, for `explain`. Says what was recognised in
    the query, not what the ranking then did with it."""

    def asks_for(self, generator: str) -> bool:
        """Whether the plan requests `generator`."""
        return generator in self.generators

    def as_dict(self) -> dict[str, object]:
        return {
            "rules": list(self.rules),
            "generators": sorted(self.generators),
            "why": self.why,
        }


def _relationship_phrase(query: str) -> str | None:
    low = query.casefold()
    return next((phrase for phrase in RELATIONSHIP_PHRASES if phrase in low), None)


def _identifier_tokens(query: str) -> tuple[str, ...]:
    return tuple(token for token in _TOKEN.findall(query) if identifier_like(token))


def plan_query(query: str, *, related: bool = False) -> Plan:
    """Classify `query` against spec 04 §2's table. Pure, and cheap by design.

    `related` is the caller's own `--related` signal, which the spec puts in the
    same cell as the relationship phrasing. It is the reliable half of that cell:
    a phrase list reaches 3 of 22 judged relationship queries and the caller
    reaches all of the ones they mean.

    Two costs, both bounded: one substring scan of a casefolded query against a
    seventeen-entry tuple, and one regex over its tokens. No store access, no
    model, no I/O — so a plan can be computed before deciding whether a leg is
    worth opening a connection for.
    """
    rules: list[str] = []
    generators: set[str] = {LEXICAL}
    reasons: list[str] = []

    names = _identifier_tokens(query)
    quoted = _QUOTE.search(query)
    if names or quoted:
        rules.append("identifier")
        generators.update({SYMBOL, VECTOR})
        found = ", ".join(names) if names else (quoted.group(0) if quoted else "")
        reasons.append(
            f"identifier-like token ({found}): exact lookup in the symbol table, "
            "and the lexical leg searches the token as written"
        )

    phrase = _relationship_phrase(query)
    if related or phrase is not None:
        rules.append("relationship")
        generators.update({GRAPH, VECTOR})
        reasons.append(
            "asked for with --related: one hop over the typed edges from the fused seeds"
            if phrase is None
            else f"relationship phrasing ({phrase!r}): one hop over the typed edges "
            "from the fused seeds"
        )

    if not rules:
        rules.append("natural-language")
        generators.add(VECTOR)
        reasons.append("a natural-language question: lexical and vector candidates, fused by RRF")

    return Plan(rules=tuple(rules), generators=frozenset(generators), why="; ".join(reasons))
