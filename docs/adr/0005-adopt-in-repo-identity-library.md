# ADR-0005: Implement the identity library in-repo, with an injectable monotonic ULID factory

- **Status:** Accepted
- **Date:** 2026-08-29
- **Deciders:** tech-lead (EADOS delivery agent), per RFC-0001 / spec 03 §§1–2
- **Related:** [ADR-0004](0004-adopt-pydantic-v2-record-contracts.md); spec 03 §§1–2
  (`.draft-specs/03-data-model.md`); architecture §10 (five stable contracts); D-008,
  D-021, D-028; roadmap 2.3; [BUG-0004](../bugs/2026/08/BUG-0004-ulid-pattern-admits-overflow.md)

## Context

Roadmap 2.3 turns spec 03 §§1–2 from validated *shapes* (ADR-0004) into *constructors*:
canonical hashing, ULID minting, heading slugs, anchors, citation URIs, and the reference
forms edges are built from. Identity rules are the first of the five contracts that freeze
at 1.0 (architecture §10), and every downstream guarantee leans on them — build keys and
dirty detection are digests (D-008), citations survive folder moves because they key on
`doc_id` (D-021), and byte-identical rebuilds (G6) are only possible if two representations
of the same content hash identically.

The spec fixes the rules but not their implementation, and four questions have no derivable
answer: whether ULIDs come from a dependency or from this repository; how far
normalization goes before hashing; how a multi-segment heading path and its ordinal share
one string unambiguously; and how to spell the citation URI's optional line range, which
the spec writes *after* the fragment — where RFC 3986 puts no query at all.

## Decision

Implement identity in-repo as `mycelium.sdk.identity` — a single module of pure functions
plus one stateful class — and take no dependency for it.

- **ULIDs are ours.** ~60 lines of Crockford base32 over a 48-bit millisecond timestamp and
  80 bits of randomness. `UlidFactory` mints monotonically: within one millisecond it
  increments the previous randomness rather than redrawing, and it holds the last
  millisecond if the clock steps backwards, so lexicographic order always equals mint
  order. Its `clock` and `entropy` are constructor-injected (Dependency Injection), and
  `new` serializes on a lock (Monitor Object) because build stages run in bounded
  parallelism and the invariant is a read-modify-write.
- **Text normalization** is NFC, LF line endings, per-line trailing whitespace stripped,
  trailing blank lines removed, and a leading BOM dropped. Leading blank lines are
  content and survive. The function is idempotent, and `digest_text` normalizes before
  hashing; `digest_bytes` never normalizes, because CAS custody of an acquired original
  must hash the bytes that arrived.
- **Canonical JSON** applies exactly the four rules §1 lists — sorted keys, UTF-8, no
  insignificant whitespace, integral floats emitted as integers — plus rejection of
  non-finite numbers, which JSON cannot express. Payload strings are *not* NFC-folded:
  §1 scopes that rule to text hashing, and rewriting strings would make the digest
  disagree with the data a consumer reads back.
- **Anchor grammar**: heading slugs join with `/`, and the ordinal is always the final
  segment, so `roadmap.md#2026/12/3` parses unambiguously even when a heading slugs to
  digits. An empty slug path (`doc.md#/0`) is the lawful form for content before the first
  heading. Slugs are NFKC-folded, case-folded, alphanumerics preserved, everything else
  collapsed to `-`; non-Latin scripts are kept rather than transliterated, since the
  corpus is multilingual (D-028) and stripping would collapse every CJK heading onto one
  slug. A heading with no alphanumerics slugs to `section`.
- **Citation URIs** are built and parsed in exactly the spec's form,
  `mycelium://<doc_id>#<path>/<ordinal>?lines=a-b` — query *after* fragment. The
  specification is the design of record; a citation is an opaque token this project both
  mints and resolves, so internal consistency with the spec beats conformance to a
  component order no third party parses.
- Failures raise `IdentityError`, a `ValueError` subclass — identity failures are argument
  failures, which the CLI's usage exit code (2) already covers.

Writing the constructors against the contracts surfaced [BUG-0004](../bugs/2026/08/BUG-0004-ulid-pattern-admits-overflow.md):
the `Ulid` pattern accepted 130-bit overflows. It is tightened to `^[0-7][…]{25}$` here, so
the validator and the decoder accept exactly the same set.

## Alternatives Considered

- **A ULID dependency (`python-ulid`, `ulid-py`)** — battle-tested, one less thing to own.
  Rejected: the encoding is 60 lines of spec-fixed arithmetic, but the *policy* around it
  is not — monotonic-within-millisecond behavior, backwards-clock handling, and an
  injectable clock/entropy for deterministic tests are exactly what this project needs
  and what libraries differ on. A frozen 1.0 contract should not be able to change because
  a transitive dependency changed its tie-breaking. The alphabet also has to agree,
  character for character, with a pattern we already own.
- **UUIDv7 instead of ULID** — same time-ordered property, stdlib-adjacent, and RFC 9562
  standard. Rejected: the spec says ULID (§2), the 26-character Crockford form is
  human-readable in citations and paths in a way hyphenated hex is not, and the deviation
  would buy nothing.
- **Transliterating slugs to ASCII** (`unidecode`-style) — prettier URLs on Latin corpora.
  Rejected: it needs a dependency, is lossy and language-dependent, and would make every
  Japanese or Chinese heading slug to the same empty string (D-028).
- **Hash-suffixed slugs** (`event-bus-9c41`) to guarantee uniqueness — would remove the
  chunker's sibling-collision problem entirely. Rejected: it destroys the property the
  spec buys with anchors — that they are *readable and stable* across edits — and
  collision handling belongs to the chunker (2.5), which alone knows the sibling set.
- **RFC 3986 component order** (`mycelium://doc?lines=a-b#anchor`) for citations.
  Rejected: it contradicts the design of record, and the RFC's ordering earns nothing here
  because no generic URI parser consumes these tokens. Revisit only if citations are ever
  handed to third-party URI machinery.
- **NFC-folding strings inside canonical JSON** — would make JSON digests as
  representation-insensitive as text digests. Rejected: it silently rewrites payload data,
  so the digest would no longer certify the bytes a consumer reads back.

## Consequences

- No new dependency; the runtime closure stays at pydantic alone.
- The identity grammars live in one module, so freezing them at 1.0 is a review of ~400
  lines, and plugins that build anchors go through the same code the engine does.
- `UlidFactory` is stateful and lock-guarded: it is cheap, but it is a serialization point
  if a future build mints ULIDs in an inner loop. Per-worker factories are the escape
  hatch — ids stay unique because randomness differs, only the global ordering weakens.
- `ulid_timestamp` raises `IdentityError` beyond year 9999: the 48-bit ULID range exceeds
  `datetime.max`, and the alternative (a platform-dependent `OSError` on Windows) is worse.
- Monotonic minting can exhaust a millisecond's randomness in principle (2^80 ids); it
  raises rather than silently wrapping into a duplicate id.
- The tightened `Ulid` pattern is a contract change, but a strictly narrowing one on an
  unreleased contract — no data or artifact exists that it invalidates.
- Testing: the rules are stated as properties (idempotence, digest-invariance under line
  endings/composition/key order, order-equals-time, parser round-trips) rather than
  examples, because these are universally-quantified claims. Cross-layer assertions
  validate constructed values against the ADR-0004 record contracts, so the two modules
  cannot drift apart again unnoticed.

## References

- Spec: `.draft-specs/03-data-model.md` §§1–2 · `.draft-specs/02-architecture.md` §10
- [ULID specification](https://github.com/ulid/spec) — monotonic mode, Crockford base32
- Patterns: Monitor Object, Dependency Injection (`docs/patterns/README.md`)
- [BUG-0004](../bugs/2026/08/BUG-0004-ulid-pattern-admits-overflow.md)
