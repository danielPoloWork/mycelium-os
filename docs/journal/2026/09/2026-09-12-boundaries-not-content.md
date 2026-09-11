# 2026-09-12 — boundaries, not content (roadmap 5.16)

- **Session scope:** roadmap 5.16 — doc 08 §6's fourth import row: optional LLM-assisted
  segmentation for a paste with no turn labels.
- **PR:** #115 (`feat/llm-segmentation`). Follows #114, merged as `dda2fe4`.
- **Milestone 5:** 5.16 done. Nothing new filed.
- **ADR:** [ADR-0088](../../../adr/0088-let-a-model-propose-line-numbers-and-slice-the-paste-ourselves.md).

## The shape that makes the promise hold

Doc 08 §6 says the segmenter *"may propose boundaries/roles only — content stays verbatim"*.
There are two ways to read that. One is a rule the implementation must obey and somebody must
check: let the model return the segmented text, then compare it against the source. The other
is a shape in which the rule cannot be broken: ask for line numbers, and slice the text here.

The second is the only one worth building. A comparison against a model's output is a string
diff against something that had every opportunity to normalise whitespace, fix a typo, or drop
a blank line — and each of those would be a defensible-looking failure that a reviewer would be
tempted to tolerate. A model that is never asked for text cannot return any. The test I like
best in this item passes an invented `content` key beside a legitimate boundary and asserts the
invention does not reach the record; it passes because there is nowhere for it to go.

That is ADR-0035's rule applied one layer down. The synthesis lane lets an LLM write *because*
the citations can be checked. Here the output is small enough that checking is not the
mechanism — narrowness is.

## The question the item did not ask

5.16 named three things to build: a provider call, a prompt returning boundaries and roles, and
a refusal path for a proposal that does not partition. It did not mention egress, and egress is
where the interesting half was.

Doc 08 §6 has a security paragraph, and it is precise about two places: a secret is redacted in
the *projection and the index*, and kept in the *record* unless the operator says otherwise,
because the record is the archive. It says nothing about a third place, because until this item
there was no third place. An unlabelled paste is exactly the input most likely to hold a
credential — somebody copied a terminal session out of a chat window — and segmentation would
have sent it to a provider verbatim.

So the paste is scanned and redacted before the request, while the record is sliced from the
original. That works only because the core's redaction replaces a finding **in place**, which
keeps the line numbering the model is answering about — and I checked rather than assumed,
which is the part that paid. One rule does not behave that way: `private-key-block` matches
across lines, and redacting an 8-line paste holding an RSA key gives back 5. Every index after
the key would have named the wrong line.

I considered padding the placeholder with blank lines to restore the count. It would work. I
rejected it because it is a second redaction implementation, living in a module, diverging from
the core's, in order to rescue the one case where the right answer is to stop. A paste with a
private key in it is not sent. The index guard and the security instinct arrived at the same
rule from opposite directions, which is usually a sign the rule is right.

## A sentence that was true when it was written

The `pasted` reader emitted its own warning: *"no turn labels found in the paste: it is
archived as a single fragment."* Correct in 5.5, and false the moment something could turn that
fragment into turns after the reader had spoken. An import that had just produced three
messages would have reported producing one.

A reader cannot know — it runs before the decision. So the sentence moved to the archive, which
runs after, and the reader now sets a typed `unsegmented` flag and says nothing. The flag is a
field rather than a `meta` string because the archive asks the question on every import, and an
answer parsed out of prose is an answer nobody pinned.

Two README sentences had aged the same way, and one of them was mine. *"Nothing here touches
the network, ever"* was true until 5.15 put a distillation lane in this module yesterday, and I
left it standing while adding the section that contradicted it. Both READMEs now say the
default touches no network and name the two opt-in lanes that do. Worth writing down: I added
the paragraph that falsified the claim and did not re-read the claim, in the same file, in the
same session.

## Lesson

A specification's security paragraph is written about the places that existed when it was
written. This item added a third — bytes leaving the machine — and the spec had nothing to say
about it, not because the doctrine is silent but because the case had not come up. When a
feature creates a new kind of movement for data, the question to ask is not *what does the spec
say about this* but *what would it have said*.
