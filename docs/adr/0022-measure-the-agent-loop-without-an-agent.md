# ADR-0022: Measure the agent loop without an agent, and say what that leaves out

- **Status:** Accepted
- **Date:** 2026-08-31
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 04 §7.4
- **Related:** [ADR-0013](0013-adopt-the-evaluation-harness.md) (the harness and the grep
  baseline), [ADR-0021](0021-scope-the-corpus-and-gate-the-evaluation.md) (the corpus these
  tasks are scored over), [ADR-0017](0017-adopt-the-local-embedder-and-hybrid-retrieval.md)
  (the retrieval the tasks consume); spec 04 §7.4; D-010, D-013, D-017; roadmap 3.7

## Context

D-010 is unusually blunt about the standard: *"The baseline to beat is not only BM25 — it
is the agent's built-in grep/glob/read."* Spec 04 §7.4 turns that into an asset: at least
twenty realistic tasks, run *agent-with-Mycelium-MCP against agent-with-grep-only*, scoring
task success, wall time, and tokens consumed — qualitative pre-1.0, a quantified gate at
1.0.

Read literally, that needs a model in the loop. A model needs a key, a budget, and a
network, and it answers differently every run. None of those belongs in a suite that must
run offline, on three platforms, in CI, as part of a gate (D-013, D-017). Waiting for 1.0
to measure anything was the other option, and it would leave the product's central claim —
that compiled knowledge beats grepping — unmeasured for the whole of v1.

## Decision

**Measure the substrate both loops consume, not the loop.** For each task, both strategies
assemble the context an agent would be handed, and the suite reports what arrived and what
it cost:

- **Mycelium** issues one search and takes budgeted, cited passages.
- **grep** does what an agent without an index does: scan for the task's terms, then *read
  the matching files whole*, because a grep hit is a line number and a line number is not
  context.

That second sentence is the comparison. In a small corpus both strategies usually *find* the
evidence; what differs is how much text the model must be handed to see it.

**Task success is "the required evidence was in what the agent received".** Each task
carries the anchors any correct answer rests on, judged by reading the document — not by
asking a retriever what it liked, which would score the retriever against itself. That
condition is *necessary and not sufficient*: the model still has to read what it was given
and answer correctly, and this suite cannot tell whether it would.

**The tasks are data, validated like the judged cases.** `tools/build_agent_tasks.py` holds
them, every required anchor is checked against a real build before the file is written, and
a task citing an anchor the corpus lacks cannot be committed. The same heading-stub lint as
the case builder applies, and it caught four of these tasks pointing at section headings
that carried none of the answer.

**Three task shapes, because spec 04 §7.4 names two and the graph adds a third:** `answer`
a question from the corpus, `locate` where something is defined, `relate` two documents to
each other. Twenty-two tasks ship: twelve, six, four.

**The suite reports; it does not gate.** Pre-1.0 the spec asks for qualitative scoring, and
a gate on a number this indirect would be a gate on the wrong thing. CI runs it so the
numbers are in every build's log, and the quantified gate arrives at 1.0 with the loop it
is actually about.

**`AgentTask` deliberately does not live in `mycelium.sdk.types`.** The SDK is the surface
that freezes at 1.0 (roadmap 6.1). This format will change the day a model joins the loop
and success becomes an answer rather than a retrieval check; a harness asset that is going
to change does not belong in a contract that must not.

## Alternatives Considered

- **Run a real agent behind an API key.** Rejected for v1: it puts a paid, networked,
  non-deterministic dependency inside a release gate, against D-013 and D-017, and makes
  the suite unrunnable for a contributor without a key. Revisited at 1.0, where §7.4 puts it.
- **Score with a local model instead.** Rejected: the local model this project ships is a
  384-dimension embedder, not something that can judge an answer. Adding a generative model
  to make the benchmark work would be a large dependency serving the benchmark alone.
- **Count only whether the evidence was found, and ignore tokens.** Rejected: in a corpus
  this small both strategies find most things, so the interesting difference — and the one
  the product's positioning rests on — is the cost of the context, not its presence.
- **Let grep return line matches without reading files.** Rejected as unfair in the
  product's favour: an agent cannot answer from a line number, so a loop that stops there is
  not the incumbent, it is a strawman.
- **Derive the tasks automatically from the judged cases.** Rejected: a task is phrased the
  way someone actually asks, and reusing case queries verbatim would measure the same thing
  twice. Anchors already judged *are* reused, which is different — if an anchor answers the
  question, it is the evidence for the task.

## Consequences

- **The first numbers, on this repository's own corpus** (69 documents, 568 chunks,
  22 tasks): Mycelium put the required evidence in front of the model on **64 %** of tasks
  against grep's **27 %**, at **2 165 mean tokens** against **4 333** — half the context —
  and a p95 of **13 ms** against **129 ms**.
- **The failures are informative and stay visible.** Eight tasks fail for Mycelium, and at
  least one for a reason worth fixing rather than hiding: a task asking about the "licence"
  misses a corpus that spells it "license", because there is no stemming in the lexical path.
  That is a product finding the suite exists to produce.
- **A ceiling, stated plainly:** these numbers say what reached the model, never what the
  model did with it. A retrieval that hands over the right passage in a confusing order can
  score 100 % here and still lose the task. Nothing in this suite should be quoted as a
  task-success rate without that sentence attached.
- **The corpus is small and self-hosting**, so the absolute numbers move easily; the
  comparison between two strategies over the *same* corpus is the part that carries weight.
- **CI runs the suite on every push**, which also means it is exercised on three platforms
  and cannot rot quietly.

## References

- Spec: `.draft-specs/04-retrieval-and-evaluation.md` §7.4 (the grep baseline and the
  agent-task suite), §7.2 (metrics), §7.6 (corpus plan)
- Decision log: D-010 (the incumbent, and not fixing the benchmark), D-013 (offline by
  default), D-017 (no unrequested network calls)
- Assets: `eval/tasks.jsonl`, `tools/build_agent_tasks.py`; tests:
  `tests/test_agent_tasks.py`
