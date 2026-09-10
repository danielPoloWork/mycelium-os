# Mycelium Chats

A local archive of your conversations with chatbots, compiled into your vault as
citable, searchable knowledge.

Significant knowledge lives inside conversations — decisions, designs, research — and it
evaporates: locked in provider silos, unsearchable across tools, deletable by a vendor.
This module archives those conversations **locally**, in a canonical format any tool can
read, and projects them into `knowledge/` so `mycelium_search` finds them like any other
document.

It is the first **module** for [Mycelium OS](https://github.com/danielPoloWork/mycelium-os)
(D-025), and the specification it implements is
[`.draft-specs/08-module-chats.md`](../../.draft-specs/08-module-chats.md).

## Install and enable

```bash
pip install mycelium-chats
```

Then name it in your repository's `mycelium.toml` — installing a module does not activate
it, and nothing changes about what your repository compiles until you say so:

```toml
[modules]
enabled = ["chats"]

[chats]
default_project = "personal"   # so --project becomes optional
timezone = "UTC"               # pin it, or archive paths follow the machine
retention_months = 24          # older conversations stay archived, leave the index
redact_in_record = false       # secrets are always redacted in the projection
```

## Use it

```bash
mycelium chats import conversations.json --project research   # a provider export
mycelium chats import transcript.md --project research        # a Markdown transcript
pbpaste | mycelium chats import - --project research          # a paste, from stdin
mycelium chats list                                           # newest first
mycelium chats show 7f3a2b                                    # a unique id prefix will do
mycelium chats export 7f3a2b --format openai                  # port it elsewhere
mycelium chats resume 7f3a2b --budget-tokens 4000             # carry on in any chatbot
mycelium chats delete 7f3a2b                                  # record, projection, index
mycelium build                                                # index the projections
```

Every read command takes `--json`, exits 0/1/2 (ok / failed / usage), and honours
`NO_COLOR` — the core's conventions, because a module that printed its own way would make
`mycelium` two CLIs wearing one name.

## What it reads

| Input | Reader | Structure |
|---|---|---|
| ChatGPT `conversations.json` | `chatgpt` | Read from the node tree, following the branch you last saw; abandoned edit branches are kept as fragments |
| Claude `conversations.json` | `claude` | Read from `chat_messages`, in order |
| Any JSON export | `generic` | Read through `[chats.mapping]` field paths — the escape hatch |
| Markdown transcript | `transcript` | Read from `> [!user]`, `## User` or `User:` markers |
| A pasted conversation | `pasted` | Read from `You said:` labels; **unlabelled text is kept whole rather than guessed at** |

`--provider` pins a reader; without it the input is sniffed, most specific first.

## What it promises

Four invariants, and the tests are named after them:

1. **Content is verbatim.** No rewriting, no cleanup, no summarising — ever.
2. **Structure may be inferred; content may not.** When boundaries are guessed the record
   says `structure_inferred`, every guessed message says `meta.inferred`, and the
   projection says so in prose. An unlabelled paste gets **no** invented speakers.
3. **Unknown provider fields are preserved**, not dropped: whatever the schema has no
   field for lands in `meta`, verbatim.
4. **The original is kept** in tier-1 custody under its own digest, so the archive is
   re-derivable and every quotation has something behind it.

And two consequences worth knowing. An import is **idempotent**: `conv_id` is derived from
the original's content digest, so importing the same export twice produces the same files
and no diff. And **nothing here touches the network**, ever.

## Two files per conversation

```text
chats/research/2026/07/2026-07-30-webhook-retry-design-4k9f2a.chat.jsonl   ← canonical
knowledge/evidence/chats/research/2026/07/2026-07-30-webhook-retry-design-4k9f2a.md
```

The record is JSONL — one message per line, append-friendly, greppable, lossless, and
already the shape every chatbot API consumes. The Markdown is the derived view the
compiler indexes: one heading and one Obsidian callout per message, so a citation
resolves to a conversation *and a message*, and `--collection chats/research` filters to
one project.

One canonical form, one derived view — the same doctrine the rest of the system uses for
ingested evidence.

## Licence

Apache-2.0, with the repository it lives in.
