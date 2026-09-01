# 2026-09-01 — the third verb, and the one copy (roadmap 4.6)

- **Session scope:** roadmap 4.6 — quarantine path and secret scanning (`redact_secrets`),
  spec 02 §5 and §8, D-017.
- **PR:** #56 (`feat/ingest-quarantine-and-secret-scan`). Follows #55 (4.5), merged as
  `2301b83`.
- **Milestone 4:** 4.1–4.6 done; 4.7, 4.8 and 4.9 open.

## The item was two features because it is one sentence

Quarantine and secret scanning look unrelated on the roadmap line. They are the same
question asked at two ends: *what happens to a document that should not simply pass
through*. One is a document the lane cannot accept; the other is a document it can accept
but not verbatim. Both had to answer it without crying wolf, and that constraint decided
almost every design choice below.

## Spec 02 §5 asks for three verbs and we had two

*"Recorded, skipped, and reported."* Since 4.1 `mycelium ingest` skipped and reported: each
source on its own, a warning, exit 1. Recording was missing, and it is the verb with the
half-life. An operator ingests a directory, three warnings scroll past, and an hour later
there is no way to answer which three.

The irritating part is that the answer already existed. ADR-0033 made ingestion store the
acquired original **before** it tries to parse it, and said in its own words that the reason
was "so a refused file can still be examined (roadmap 4.6)". The bytes were in custody the
whole time and nothing pointed at them. So a refusal now writes one record naming the stage,
the reason, and that digest — which is the difference between *quarantined* and a politer
word for *dropped*.

## The stage is a type, because a sentence is not a classifier

The first draft read the stage off the error message: `"loses "` meant the loss budget,
`"exceeds"` meant a guard. It worked, and it was wrong — a classifier that reads prose is one
reworded message away from silently mislabelling, and no test would catch it, because the
test would be written against the same sentences.

So `GuardError` and `LossBudgetError` were split out of `ParseError` as **subclasses**. Every
existing handler is untouched (they all catch `ParseError`), the classification became an
`isinstance` ladder, and the taxonomy in `mycelium.ingest.errors` now says out loud what it
had been implying. Eight lines.

Running it against the hostile fixtures then surfaced a fifth stage nobody had planned:
`UnsupportedMediaTypeError` was landing as `acquire`, and the bytes had been perfectly
acquirable — what failed was *dispatch*, and the remedy is a configuration edit rather than
anything to do with the file. Five stages, five different operator actions.

## Warn, not fail

`doctor` reports the quarantine as a **warning**. That is a deliberate refusal to be strict:
a quarantined source is the system working exactly as designed, and a health check that goes
red because one PDF is a scan is a health check an operator stops running. The same instinct
kept a `mycelium quarantine` command out of spec 05 §1's table — reporting belongs to
`doctor`, and the one action that cannot happen by itself is `--forget`, a flag on the
command that already takes sources.

## The secret scan: what it deliberately does not do

Eleven rules, each anchored on a structure that does not occur in prose — a vendor's fixed
key prefix, PEM armour, credentials in a URL's authority. **No entropy heuristic**, and that
is the whole design rather than an omission. High-entropy scanning fires on base64 images,
digests, UUIDs and minified code, all of which this project's own corpora are full of, and a
scanner that flags healthy documents is one that gets switched off inside a week — which is
strictly worse than not shipping it.

The negative corpus is therefore this repository's own `docs/` tree, asserted clean by a
test. That has a pleasing consequence: documenting the scanner cannot contain a
live-looking credential, so the dogfooding is enforced rather than intended. Writing the ADR
under that constraint is how I know it works.

What it costs is stated in the README rather than implied away: a bare password or a
home-grown token goes through unflagged, and **this is not a substitute for a secret scanner
on the repository**.

## One copy, in the one place that has to have it

Redaction happens **before the KIR is stored**, and that ordering is the load-bearing
decision. It fixes where the credential lives: the tier-1 original holds it verbatim, because
that is what a citation is checked against and destroying it destroys the evidence; every
derived artifact — the KIR blob, the projection, the chunks, the index, an export bundle —
carries `[redacted: <rule-id>]`. Redacting at projection time would have been simpler and
would have meant choosing which outputs to clean and remembering that list forever.

The residual is real and now recorded in the threat model: `.mycelium/` is gitignored so the
credential never reaches a clone, but an operator who needs it gone from a machine has to
delete the original and accept losing the evidence behind that document's citations.

**Flagging is the observation; redaction is the action.** `redact_secrets = false` turns off
the second, never the first — an operator who wants the verbatim text should not silently
also lose the record that a credential is in it. The flags reach `Document.secret_flags`
through the custody record, which is ADR-0034's mechanism used a third time: one frontmatter
key, every other fact read back from the evidence's own record, so nothing can drift.

Two small things fell out of the URL rule while testing it. It first redacted the entire URL,
host included — protection at the cost of the one part of the line a reader needs to know
what the credential was *for*. It now takes the userinfo only. And `scan_kir` returns a clean
document *identically* rather than merely equally, so the overwhelming majority of ingestions
pay nothing for a check that found nothing.

## What this closes

`[ingest]` is honoured in full: `redact_secrets` was the last accepted-and-inert key, so
ADR-0014's promise is discharged for that section and `eval` is the only unhonoured section
left. The threat model's B4 boundary now has every control it was modelled with.

**No golden re-bless** this time — `redact_secrets` was already in the config digest, and a
document with no credentials is returned untouched.
