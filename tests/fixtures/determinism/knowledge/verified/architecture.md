---
mycelium_id: 01KDVDNA010000000000000001
title: Architecture
collection: core-docs
tags: [architecture, event-bus]
aliases: [Arch]
---

# Architecture

Mycelium OS compiles a repository's knowledge into a deterministic, versioned substrate.
The compiler is a stage DAG: discover, parse, chunk, index, publish. See [[retries]] for
the delivery guarantees and [[multilingual]] for the corpus profile. #architecture

## Event Bus

The event bus routes messages between components without a broker. Every message carries
its originating snapshot, so a consumer can tell whether it is reading current state.

### Delivery

Delivery is at-least-once within a build, and exactly-once across a published snapshot.
The distinction matters for consumers that keep their own state.

## Event Bus

A second section with the same heading, which the chunker must disambiguate rather than
collide with. See the [specification](https://example.invalid/spec) for the rules.

> Structure replaces overlap: a heading path says where you are better than the previous
> paragraph repeated.

- Stages are pure functions of their declared inputs.
- Build keys are digests over those inputs.
- A rebuild with unchanged inputs produces unchanged outputs.
