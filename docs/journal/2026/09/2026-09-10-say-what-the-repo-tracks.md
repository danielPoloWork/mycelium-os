# 2026-09-10 — the merge that was refused one directory too deep (roadmap 5.8)

- **Session scope:** a maintainer report — "refusing to merge unrelated histories", right after
  the v0.4.0 release — that turned out to be a working-directory slip, and the repository audit
  it prompted (roadmap 5.8; AGENTS.md §4, §13).
- **PR:** #97 (`chore/say-what-the-repo-tracks`). Follows #96 (the v0.4.0 cut), merged as
  `5a99abe`.
- **Milestone 5:** 5.8 done. Nothing else in M5 has started.

## The error was real, and the repository was fine

`main` and `origin/main` were the same commit with the same root, and every fast-forward in the
reflog had gone through. The refusal came from `.mycelium-os-legacy/`, a gitignored clone of the
superseded implementation made on 2026-07-31 — the day the owner renamed that GitHub repository
to `mycelium-os-legacy` and gave its name to this one (D-024). The clone's remote URL was never
updated, so today it resolves to *this* repository, whose history starts on 2026-08-29 and shares
no commit with the clone's. `git merge-base` there returns nothing. A routine
`checkout main && pull`, run one directory too deep, was refused — correctly, and before it
touched a file.

Nothing was at risk. The legacy history is intact on GitHub under its new name, tip for tip, and
the clone itself was clean. The repair is one `git remote set-url` to the renamed repository, or
deleting a folder that `mycelium.toml` already excludes from the corpus as "kept for salvage
only". Proposed to the maintainer, not applied: the folder is theirs.

How the sync got there is the more useful half. The agent shell keeps its working directory
between commands, so a `cd` made for one inspection outlived it — and the same slip reproduced
itself during the diagnosis, in the session that was diagnosing it. The rule that follows is
mechanical: address the repository as `git -C <root>`, never `cd` below it. §4 now says so, next
to the folder that taught it.

## What a clone contains, checked against what the contract says

The maintainer's second question was the right one: of the dot-directories in the tree, what
belongs on GitHub, and what would a colleague need? Tracked: `.github/`, the vendored
`.eados-core/` bundle (306 files), `.draft-specs/` (the specification every ADR cites by
section), and `.claude/commands/eados/`. Not tracked and regenerable by one command each:
`.venv/` (618 MB), `.mycelium/` (57 MB — this repository's own compiled store), `.hypothesis/`,
`.benchmarks/`. Not tracked and archival: the legacy clone. Everything development needs is in
the clone; the setup is `uv sync --all-extras --dev`, plus pandoc for the ingest lane.

Checking that list against `AGENTS.md` found the contract disagreeing with the tree in two
places. §13 said three times that the `.eados-core/` bundle and the host command tree are *not
committed* — the EADOS rendered default — while `.gitignore` carries a dated owner decision
(PR #1, 2026-08-29) to track both, with its reasons. Two documents both authoritative, one of
them wrong, and the wrong one is the file every agent is told to read first. §4 still drew the
`src/main/python/…` tree that ADR-0003 superseded, and named none of `.draft-specs/`,
`.eados-core/`, `.claude/` or `eval/`.

Two smaller findings. `.benchmarks/` had no ignore rule, so the first `--benchmark-autosave`
would have surfaced as untracked noise. And `.claudeignore`, written on 2026-09-04 to keep
`.venv/`, the legacy clone and `.draft-specs/` out of the agent's context, was never added —
which prompted the question of what it does. Checked against the Claude Code documentation: it
is not a mechanism the product documents. The documented ones are `.gitignore` respect, which
already covers two of the three paths, and `permissions.deny` rules in `.claude/settings.json`.

## What changed, and what did not

§4 now says what a clone contains and, in one paragraph, what it deliberately does not and how
each absence is regenerated. §13 states the deviation instead of contradicting it: the bundle
and the Claude Code tree are tracked here by owner decision; every other host still generates
its own. `.benchmarks/` is ignored.

Not changed: `.claudeignore`. It stays untracked and is referred to the owner rather than
committed, for two reasons that compound. Committing a file the host does not read would
enshrine a no-op in the tree the contract describes. And the one path it names that
`.gitignore` does not already cover is `.draft-specs/` — the directory the ADRs point *into* by
section — so the working equivalent, a deny rule in a tracked `settings.json`, would keep every
agent from following those pointers. Whether that trade is wanted is a decision, not a repair.

Not changed either: the ADRs that still mention `src/main/python/`. ADR-0002 records the layout
that was chosen and ADR-0003 the one that superseded it; a record that rewrote its own history
would be worth less than one that shows the change.

One observation from verifying it, noted rather than filed. `verify.py` derived `full` for a
change with no Python in it, because it classifies by suffix and a root dotfile such as
`.gitignore` has none — so the safe direction won and the whole ladder ran, seventeen gates,
all green. That is the tool doing what ADR-0055 asks of it when in doubt; whether root dotfiles
deserve a rule of their own is a one-line question for whoever next touches the classifier.

## Lesson

A contract that describes the tree is only as good as the last time someone compared the two,
and nobody compares them from inside: the people who know the decision stop reading the
paragraph that contradicts it. The comparison came from a question asked from outside — "what
would a colleague need?" — which is the reader the file is for.
