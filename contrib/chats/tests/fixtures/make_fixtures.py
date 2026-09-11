"""Regenerate the JSON export fixtures.

    python contrib/chats/tests/fixtures/make_fixtures.py

Committed beside the fixtures it writes, for the reason `tests/fixtures/ingest`
keeps its own generator: a fixture nobody can rebuild is a fixture nobody dares
change. The ChatGPT export in particular is a *node graph*, and a graph written
out by hand is a graph nobody re-reads.

The three Markdown and text fixtures are hand-written and stay that way — they
are what a human actually pastes, and generating them would lose the point.
"""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def node(node_id, parent, children, message=None):
    return {"id": node_id, "parent": parent, "children": children, "message": message}


def message(node_id, role, text, *, created=None, model=None, extra=None):
    body = {
        "id": node_id,
        "author": {"role": role, "name": None, "metadata": {}},
        "create_time": created,
        "content": {"content_type": "text", "parts": [text]},
        "status": "finished_successfully",
        "metadata": {"model_slug": model} if model else {},
    }
    if extra:
        body.update(extra)
    return body


# --- ChatGPT: two conversations, one with an abandoned edit branch --------------------------
chatgpt = [
    {
        "title": "Webhook retry design",
        "create_time": 1785000000.0,
        "update_time": 1785000120.0,
        "conversation_id": "c-webhook-1",
        "current_node": "n4",
        "moderation_results": [],
        "plugin_ids": None,
        "mapping": {
            "root": node("root", None, ["n1"]),
            "n1": node(
                "n1",
                "root",
                ["n2", "n2-abandoned"],
                message(
                    "n1",
                    "user",
                    "How should webhook retries back off?",
                    created=1785000005.0,
                ),
            ),
            "n2": node(
                "n2",
                "n1",
                ["n3"],
                message(
                    "n2",
                    "assistant",
                    "Exponential backoff with a ceiling.\n\n"
                    "## Attempt schedule\n\n"
                    "| attempt | delay |\n|---|---|\n| 1 | 1s |\n| 2 | 2s |\n\n"
                    "After the fifth attempt, quarantine the message rather than dropping it.",
                    created=1785000030.0,
                    model="gpt-5",
                ),
            ),
            "n2-abandoned": node(
                "n2-abandoned",
                "n1",
                [],
                message(
                    "n2-abandoned",
                    "assistant",
                    "Linear backoff is simpler.",
                    created=1785000025.0,
                    model="gpt-5",
                ),
            ),
            "n3": node(
                "n3",
                "n2",
                ["n4"],
                message(
                    "n3", "user", "Does the ceiling apply per connector?", created=1785000060.0
                ),
            ),
            "n4": node(
                "n4",
                "n3",
                [],
                message(
                    "n4",
                    "assistant",
                    "A connector may lower the ceiling, never raise it past the build's budget.",
                    created=1785000090.0,
                    model="gpt-5",
                    extra={"weight": 1.0},
                ),
            ),
        },
    },
    {
        "title": "Multimodal note",
        "create_time": 1785100000.0,
        "conversation_id": "c-multimodal-2",
        "current_node": "m2",
        "mapping": {
            "m-root": node("m-root", None, ["m1"]),
            "m1": node(
                "m1",
                "m-root",
                ["m2"],
                {
                    "id": "m1",
                    "author": {"role": "user"},
                    "create_time": 1785100005.0,
                    "content": {
                        "content_type": "multimodal_text",
                        "parts": [
                            "What does this diagram show?",
                            {"asset_pointer": "file-service://file-abc", "size_bytes": 20481},
                        ],
                    },
                },
            ),
            "m2": node(
                "m2",
                "m1",
                [],
                message(
                    "m2",
                    "assistant",
                    "The stage DAG: discover, parse, chunk, extract, embed, index, manifest.",
                    created=1785100030.0,
                    model="gpt-5",
                ),
            ),
        },
    },
]

# --- Claude: one conversation, both body shapes, an attachment, a secret --------------------
claude = [
    {
        "uuid": "9f0c1d2e-claude-export",
        "name": "Anchor stability",
        "created_at": "2026-07-31T09:02:11.482913Z",
        "updated_at": "2026-07-31T09:14:02.117640Z",
        "account": {"uuid": "acct-1"},
        "chat_messages": [
            {
                "uuid": "m-1",
                "sender": "human",
                "created_at": "2026-07-31T09:02:11.482913Z",
                "updated_at": "2026-07-31T09:02:11.482913Z",
                "text": "Do citations survive a file being renamed?",
                "attachments": [],
                "files": [],
            },
            {
                "uuid": "m-2",
                "sender": "assistant",
                "created_at": "2026-07-31T09:02:40.001000Z",
                "updated_at": "2026-07-31T09:02:40.001000Z",
                "content": [
                    {
                        "type": "text",
                        "text": "Yes. A citation keys on `doc_id`, not on the path, so a "
                        "rename or a promotion from candidate/ to verified/ leaves it valid.",
                    },
                    {"type": "thinking", "thinking": "Checking the identity rules."},
                ],
            },
            {
                "uuid": "m-3",
                "sender": "human",
                "created_at": "2026-07-31T09:10:00.000000Z",
                "text": "Here is the config I am using, with the key redacted later:\n\n"
                "export MYCELIUM_TOKEN=ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8",
                "attachments": [{"file_name": "mycelium.toml", "file_size": 412}],
            },
            {
                "uuid": "m-4",
                "sender": "assistant",
                "created_at": "2026-07-31T09:11:30.000000Z",
                "content": [{"type": "text", "text": "Rotate that token: it is now in an export."}],
            },
        ],
    }
]

# --- A shape no built-in reader knows, for the generic mapper ------------------------------
generic = {
    "threads": [
        {
            "subject": "Retention windows",
            "history": [
                {"speaker": "me", "body": "Does retention delete the archive?", "at": 1785200000},
                {
                    "speaker": "bot",
                    "body": "No. It leaves the index; the record stays unless you --purge.",
                    "at": 1785200060,
                },
            ],
            "thread_id": "t-77",
        }
    ]
}

for name, payload in (
    ("chatgpt-export.json", chatgpt),
    ("claude-export.json", claude),
    ("generic-export.json", generic),
):
    path = OUT / name
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print("wrote", path.name, path.stat().st_size, "bytes")
