#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""Author the judged sets over the second corpus — `uv`'s documentation.

    python tools/build_uv_docs_cases.py [--check]

Writes `eval/corpora/uv-docs/eval/{dev,release}.jsonl`, validating every anchor
against a real build first (`mycelium.eval.cases.validate_judged_set`).

**`--check` regenerates and compares instead of writing**, and it exists because
running this file without it used to destroy work. The judgements below are the
sets' only source, so a case added to a committed set by hand is invisible here
and is deleted by the next run. That is not hypothetical: PRs #88 and #90 edited
`dev.jsonl` directly — re-judging `u-0006` and adding `u-0013`..`u-0022` — and
neither edit reached this file, so from 2026-09-08 until it was triggered at
roadmap 5.30 this generator silently reverted ten judged cases and one
re-judgement ([BUG-0026]). The sibling generators were already checked —
`tools/build_ingested_cases.py --check` in CI, `tools/build_eval_cases.py`
by a test — and this one was not, which is why only this one drifted. It is now
a rung of `tools/verify.py` at `code` and a step in CI's `ingest / lanes` job,
beside the carry check it is the upstream half of: checking that the carry still
derives from the source, while the source itself goes unchecked, is the weaker
half of the pair — and it is the half that held while this one drifted.

**Judging provenance, precisely.** These queries and grades were assigned by the
same agent that builds the retriever they measure — that bias is not removed by a
second corpus and this file does not pretend otherwise. What *is* removed is the
other half of it: nobody here wrote the documents being judged. Our own set was
judged by the author of its corpus, so a query could be phrased in the words the
author happened to use; here the phrasing has to be guessed like any reader's
would (ADR-0027).

Judgments were written from the documents' own text, never from retrieval output.
That is a discipline rather than an enforceable rule, so it is recorded where a
reader can weigh it.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mycelium.build import build  # noqa: E402
from mycelium.eval.cases import encode_cases, validate_judged_set, write_cases  # noqa: E402
from mycelium.sdk.types import EvalCase, EvalSlice, RelevantAnchor  # noqa: E402
from mycelium.store import SqliteStore  # noqa: E402

CORPUS = ROOT / "eval" / "corpora" / "uv-docs"

Judgment = tuple[str, str, tuple[EvalSlice, ...], tuple[tuple[str, int], ...], str]

DEV: tuple[Judgment, ...] = (
    (
        "u-0001",
        "UV_CACHE_DIR",
        (EvalSlice.EXACT,),
        (("docs/concepts/cache.md#cache-directory/0", 3),),
        "A literal environment variable name; exact retrieval should be trivial.",
    ),
    (
        "u-0002",
        "where does the cache directory live on Windows",
        (EvalSlice.FACT,),
        (("docs/concepts/cache.md#cache-directory/0", 3),),
        "One specific fact stated in a numbered list, phrased as a reader would ask it.",
    ),
    (
        "u-0003",
        "how do I clear the cache for a single package",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/cache.md#clearing-the-cache/0", 3),
            ("docs/concepts/cache.md#dependency-caching/0", 2),
        ),
        "The answer is a command; the concepts section repeats it in prose.",
    ),
    (
        "u-0004",
        "what is a workspace",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/workspaces.md#/0", 3),),
        "A definitional question whose answer is a document's opening section.",
    ),
    (
        "u-0005",
        "which platforms are tier 1 supported",
        (EvalSlice.FACT,),
        (("docs/reference/policies/platforms.md#/0", 3),),
        "A list-shaped fact in a policy document.",
    ),
    (
        "u-0006",
        "uvx",
        (EvalSlice.SYMBOL,),
        (
            ("docs/guides/tools.md#running-tools/", 3),
            ("docs/concepts/tools.md#the-uv-tool-interface/0", 2),
            ("docs/getting-started/features.md#tools/0", 1),
        ),
        "A bare command name: the symbol slice, and it appears across several "
        "documents. Graded on the convention its siblings follow — the section "
        "that documents the command at 3, the section that frames the interface "
        "at 2, the feature-list entry at 1 (ADR-0062, ADR-0065).",
    ),
    (
        "u-0007",
        "what does resolution mean",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/resolution.md#/0", 3),),
        "The concept the document is named for, defined in its first paragraph.",
    ),
    (
        "u-0008",
        "how are breaking changes versioned",
        (
            EvalSlice.CONCEPTUAL,
            EvalSlice.FACT,
        ),
        (("docs/reference/policies/versioning.md#/0", 3),),
        "A policy stated in prose, asked in words the document does not use verbatim.",
    ),
    (
        "u-0009",
        "dressage piaffe pirouette",
        (EvalSlice.UNANSWERABLE,),
        (),
        "A domain this corpus will never cover; every term verified clean against both retrievers.",
    ),
    (
        "u-0010",
        "escapement tourbillon mainspring",
        (EvalSlice.UNANSWERABLE,),
        (),
        "As u-0009, in a different domain.",
    ),
    (
        "u-0011",
        "how do I run a script that declares its own dependencies",
        (EvalSlice.CONCEPTUAL,),
        (("docs/guides/scripts.md#/", 2),),
        "A guide-shaped question; the opening frames it and later sections answer in detail.",
    ),
    (
        "u-0012",
        "where does uv look for a configuration file",
        (EvalSlice.FACT,),
        (("docs/concepts/configuration-files.md#/", 3),),
        "A search-order fact stated in the document's first section.",
    ),
    (
        "u-0013",
        "UV_PREVIEW",
        (EvalSlice.EXACT,),
        (("docs/concepts/preview.md#enabling-preview-features/0", 3),),
        "An environment variable name. The section that documents it names it "
        "four times; `unicode61` splits it into `uv preview`, which is the same "
        "shape u-0001 already has.",
    ),
    (
        "u-0014",
        "--bare",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/projects/init.md#creating-a-minimal-project/0", 3),
            ("docs/concepts/projects/init.md#/0", 1),
        ),
        "A CLI flag. The section that documents it uses it five times; the "
        "document's own root mentions it once, which is grade 1 for the reason "
        "u-1019 gives - it answers only that the flag exists.",
    ),
    (
        "u-0015",
        "UV_PROJECT_ENVIRONMENT",
        (EvalSlice.EXACT,),
        (("docs/concepts/projects/config.md#project-environment-path/", 3),),
        "An environment variable whose tokens are all common words once split - "
        "the harder end of `exact`, and deliberately kept. Section-scoped: 326 "
        "tokens is one chunk under this setting and may not be under another "
        "(ADR-0043).",
    ),
    (
        "u-0016",
        "uv build",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/projects/build.md#using-uv-build/0", 3),
            ("docs/guides/package.md#building-your-package/0", 2),
            ("docs/concepts/projects/build.md#/0", 1),
        ),
        "The heading of the grade-3 section names the command and its body uses "
        "it eleven times; the guide teaches it in a tutorial step, and the "
        "concept document's root frames building without naming the command.",
    ),
    (
        "u-0017",
        "uv venv",
        (EvalSlice.SYMBOL,),
        (
            ("docs/pip/environments.md#creating-a-virtual-environment/0", 3),
            ("docs/getting-started/features.md#the-pip-interface/0", 1),
        ),
        "The section that documents the command is the one that runs it; the "
        "feature list says only `uv venv: Create a new virtual environment`, "
        "which is grade 1.",
    ),
    (
        "u-0018",
        "uv init",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/projects/init.md#/0", 3),
            ("docs/guides/projects.md#creating-a-new-project/0", 2),
            ("docs/getting-started/features.md#projects/0", 1),
        ),
        "The closest call in this batch: the concept document exists to document "
        'this command ("uv supports creating a project with uv init") while the '
        "guide teaches it as a tutorial step. Three tiers so the judgement does "
        "not hinge on the tie - whichever a retriever prefers, it is credited.",
    ),
    (
        "u-0019",
        "can another tool read the lockfile uv writes",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/concepts/projects/layout.md#the-lockfile/relationship-to-pylock-toml/",
                3,
            ),
            ("docs/concepts/projects/layout.md#the-lockfile/0", 2),
        ),
        "Relates uv's own lockfile to the standardised format: one is "
        "tool-agnostic, the other is not, and uv keeps its own inside the "
        "project. The query names neither `uv.lock` nor `pylock.toml`.",
    ),
    (
        "u-0020",
        "why can uv install into an environment it did not create",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/pip/environments.md#using-arbitrary-python-environments/", 3),
            ("docs/pip/environments.md#discovery-of-python-environments/0", 2),
        ),
        "Two halves in one document: that uv has no dependency on Python and can "
        "target any environment, and the order in which it discovers one. "
        "Section-scoped on the first at 547 tokens (ADR-0043).",
    ),
    (
        "u-0021",
        "what has to be in pyproject.toml before the project can be built",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/build-backend.md#using-the-uv-build-backend/0", 3),
            ("docs/concepts/projects/layout.md#the-pyproject-toml/0", 2),
        ),
        "Relates the build backend to the file that declares it: the grade-3 "
        "section shows the `[build-system]` table that has to be there, the "
        "grade-2 one lists a build system among the file's contents without "
        "showing it.",
    ),
    (
        "u-0022",
        "what decides whether a new project is set up as an application or a library",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/init.md#applications/", 3),
            ("docs/concepts/projects/init.md#libraries/", 2),
        ),
        "The two templates are documented in one section each and the answer is "
        "the contrast between them - applications are the default, libraries need "
        "`--lib` and always require a packaged project. Both section-scoped at "
        "364 and 432 tokens.",
    ),
    (
        "u-0023",
        "why put a dependency in tool.uv.sources rather than just listing it in "
        "project.dependencies",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/projects/dependencies.md#dependency-sources/0", 3),
            ("docs/concepts/projects/dependencies.md#dependency-fields/0", 2),
        ),
        "The sources section gives the rationale: tool.uv.sources adds development-time patterns "
        "the project.dependencies standard cannot express, such as editable installs and relative "
        "paths, and it warns that only uv respects them. The fields section merely frames sources "
        "as one of four dependency fields.",
    ),
    (
        "u-0024",
        "why bother with an editable install while developing a package",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/dependencies.md#editable-dependencies/0", 3),),
        "Explains the mechanism and the motivation: a normal directory install copies sources into "
        "the environment and goes stale on edit, while an editable install writes a .pth link so "
        "the interpreter reads the sources directly; it also names the limitations (backend "
        "support, native modules).",
    ),
    (
        "u-0025",
        "what does it mean for a uv dependency to be virtual",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/dependencies.md#virtual-dependencies/0", 3),),
        "Defines the concept — the dependency itself is not installed as a package but its "
        "dependencies are — and states the conditions: never virtual by default, requires package "
        "= false on a path or workspace source, with the workspace-member example showing anyio "
        "installed but child not.",
    ),
    (
        "u-0026",
        "what does ~= mean in a version constraint",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/dependencies.md#dependency-specifiers/0", 3),),
        "Explains the operator rather than just naming it: ~= matches where the last digit is "
        "equal or higher, so foo ~=1.2 means >=1.2,<2 and foo ~=1.2.3 means >=1.2.3,<1.3, "
        "alongside the other specifier rules.",
    ),
    (
        "u-0027",
        "when should i reach for uv pip instead of uv's project commands",
        (EvalSlice.CONCEPTUAL,),
        (("docs/getting-started/features.md#the-pip-interface/0", 3),),
        "Gives the intended-use answer: the pip interface is for manually managing environments "
        "and packages in legacy workflows or where the high-level commands do not give enough "
        "control, with the caveat that behaviour diverges the further you stray from common "
        "workflows.",
    ),
    (
        "u-0028",
        "why does uv ship python-build-standalone builds instead of official python binaries",
        (EvalSlice.CONCEPTUAL,),
        (("docs/guides/install-python.md#getting-started/0", 3),),
        "The note in this section gives the reason: Python does not publish official distributable "
        "binaries, so uv uses the Astral python-build-standalone distributions.",
    ),
    (
        "u-0029",
        "why doesn't uv write my index password into pyproject.toml when i run uv add",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/authentication/http.md#persistence-of-credentials/0", 3),),
        "Explains the reasoning directly: pyproject.toml and uv.lock are usually committed and "
        "distributed, so uv will not persist index credentials into them, while direct-URL "
        "credentials are persisted because there is no other way to supply them.",
    ),
    (
        "u-0030",
        "should uv.lock be committed to git",
        (EvalSlice.CONCEPTUAL,),
        (("docs/guides/projects.md#project-structure/uv-lock/0", 3),),
        "Answers and justifies: uv.lock is a cross-platform lockfile of exact resolved versions, "
        "it should be checked into version control so installations are consistent and "
        "reproducible across machines, and although it is readable TOML it is uv-managed and "
        "should not be hand-edited.",
    ),
    (
        "u-0031",
        "how do i make uv keep credentials in the macos keychain instead of a plaintext file",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/authentication/http.md#the-uv-credentials-store/0", 3),),
        "The answer is spread across this section's preview note rather than one sentence: that "
        "native storage is still preview, that it maps to Keychain Services on macOS (Credential "
        "Manager on Windows, Secret Service on Linux), that only credentials uv added are "
        "searched, and that UV_PREVIEW_FEATURES=native-auth turns it on. Section-scoped for that "
        "reason.",
    ),
    (
        "u-0032",
        "why aren't my git credentials written into uv.lock when I add a private repo",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/authentication/git.md#persistence-of-credentials/0", 3),),
        "Gives the reasoning: pyproject.toml and uv.lock are usually committed and redistributed, "
        "so writing credentials into them is unsafe.",
    ),
    (
        "u-0033",
        "why do markers make locking harder than installing",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/resolution.md#platform-markers/0", 3),
            ("docs/concepts/resolution.md#universal-resolution/0", 2),
        ),
        "Platform markers states the asymmetry: installing can evaluate the current platform's "
        "markers, but a lockfile built that way only works for developers on the same platform, "
        "which is why universal resolvers exist.",
    ),
    (
        "u-0034",
        "why does uv throw away the upper bound on requires-python",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/reference/internals/resolver.md#requires-python/0", 3),
            ("docs/concepts/resolution.md#universal-resolution/0", 2),
        ),
        "The internals section argues it: you cannot know compatibility with an unreleased Python, "
        "and the bound is circumvented anyway because the resolver backtracks to an older version "
        "that lacks it. The concepts page only states the rule.",
    ),
    (
        "u-0035",
        "why can the same requirements produce a different lockfile on a second run",
        (EvalSlice.CONCEPTUAL,),
        (("docs/reference/internals/resolver.md#forking/0", 3),),
        "Explains the instability: where the resolution splits depends on the order packages are "
        "seen, which depends on preferences from uv.lock, so uv records each fork's markers in the "
        "lockfile to pin the split points.",
    ),
    (
        "u-0036",
        "why does uv assume every wheel of a version has identical metadata",
        (EvalSlice.CONCEPTUAL,),
        (("docs/reference/internals/resolver.md#metadata-consistency/0", 3),),
        "Gives both reasons: without the assumption uv would need one network request per wheel, "
        "and a universal resolver would have to track PEP 508 markers and wheel tags as two "
        "dimensions at once.",
    ),
    (
        "u-0037",
        "how does uv decide which package to solve for next",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/reference/internals/resolver.md#prioritization/0", 3),
            ("docs/reference/internals/resolver.md#resolver/0", 2),
        ),
        "Prioritization gives the ordering - root and URL requirements, then == singletons, then "
        "highly-conflicting packages, then the rest, first-seen within a category - plus the five- "
        "conflict swap heuristic. The overview sketches the same ordering in one bullet.",
    ),
    (
        "u-0038",
        "why does it matter that my library declares lower bounds on its dependencies",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/resolution.md#lower-bounds/0", 3),),
        "Explains the failure mode: without lower bounds the resolver backtracks to ancient "
        "versions that are slow to try, often fail to build, or silently do not work with your "
        "code.",
    ),
    (
        "u-0039",
        "why won't uv let a package from an index point at a url",
        (EvalSlice.CONCEPTUAL,),
        (("docs/reference/internals/resolver.md#url-dependencies/0", 3),),
        "States the two reasons: auditability, so a single-index install never reaches outside the "
        "index, and the fact that URLs could add versions, breaking the incremental resolver's "
        "static-version-set assumption.",
    ),
    (
        "u-0040",
        "why doesn't naming a package in a constraints file pull it in",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/resolution.md#dependency-constraints/0", 3),),
        "Explains the design: a constraint narrows acceptable versions but only takes effect once "
        "the package is already pulled in as a direct or transitive dependency, which is what "
        "makes constraints useful for transitive pins.",
    ),
    (
        "u-0041",
        "why does uv build each package in its own isolated environment",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/config.md#build-isolation/0", 3),),
        "The section opens by explaining that uv builds packages in isolated environments "
        "alongside their declared build dependencies as per PEP 517, and then explains the failure "
        "modes this causes for packages like flash-attn and cchardet - the explanation, not just "
        "the setting.",
    ),
    (
        "u-0042",
        "how does uv decide whether to install my project itself into the environment",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/projects/config.md#build-systems/0", 3),
            ("docs/concepts/projects/config.md#project-packaging/0", 2),
        ),
        "Build systems explains the mechanism: uv uses the presence of a [build-system] table to "
        "decide whether the project contains a package to install, and without one it installs "
        "only the dependencies. Project packaging restates the rule while introducing the "
        "override.",
    ),
    (
        "u-0043",
        "should i disable build isolation or add extra build dependencies",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/config.md#build-isolation/0", 3),),
        "Section-scoped deliberately: the recommendation only makes sense across the whole "
        "section, which states the problem, sets out the two approaches side by side, and then "
        "recommends augmenting because disabling requires build dependencies to be pre-installed "
        "in the project environment.",
    ),
    (
        "u-0044",
        "why doesn't match-runtime work for packages with dynamic metadata",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/concepts/projects/config.md#build-isolation/augmenting-build-dependencies/dynamic-metadata/0",
                3,
            ),
        ),
        "This subsection is the explanation: without static metadata uv must build the package "
        "during resolution, so it cannot yet know which version of the build dependency will end "
        "up installed, which is exactly what match-runtime would need.",
    ),
    (
        "u-0045",
        "why should i make a dedicated jupyter kernel for my project",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/guides/integration/jupyter.md#using-jupyter-within-a-project/creating-a-kernel/0",
                3,
            ),
        ),
        "The section gives the reasoning: a kernel lets the Jupyter server run in one environment "
        "while the notebook runs in the project's, so packages installed from inside the notebook "
        "land in the project environment.",
    ),
    (
        "u-0046",
        "why does uv init set up a build system and a src directory by default",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/projects/init.md#/0", 3),
            ("docs/concepts/projects/config.md#build-systems/0", 2),
        ),
        "The page preamble states the rationale: defining a build system enables packaging "
        "features such as command-line entry points and avoids confusion with the Python import "
        "system, and names --no-package and --bare as the ways out. The build systems section "
        "frames what a build system does.",
    ),
    (
        "u-0047",
        "why cache the uv directory between ci jobs",
        (EvalSlice.CONCEPTUAL,),
        (("docs/guides/integration/gitlab.md#caching/0", 3),),
        "The caching section states the reason - persisting the uv cache between runs improves "
        "performance - and shows the keyed cache plus the prune step that keeps the cache from "
        "growing.",
    ),
    (
        "u-0048",
        "how does inline script metadata let the same script run on a cloud machine",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/guides/integration/coiled.md#running-scripts-on-the-cloud-with-coiled/0", 3),
            ("docs/guides/integration/coiled.md#managing-script-dependencies-with-uv/0", 2),
        ),
        "The cloud section opens with the explanation: inline script metadata makes the script "
        "self-contained, carrying everything needed to run it, which is what makes it portable to "
        "a remote machine. The earlier section frames what that metadata is.",
    ),
    (
        "u-0049",
        "why is it discouraged to keep both uv.lock and requirements.txt",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/export.md#requirements-txt-format/basic-usage/0", 3),),
        "The note in this subsection is the only place the recommendation and its reasoning "
        "appear: uv.lock is more powerful and expresses features requirements.txt cannot, so "
        "exporting one is a sign worth discussing upstream.",
    ),
    (
        "u-0050",
        "if the same setting is in pyproject.toml, an environment variable and on the command "
        "line, which one wins",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/configuration-files.md#/0", 3),),
        "The preamble states the full precedence chain: system < user < project for persistent "
        "files, environment variables above all persistent configuration, and the command line "
        "above both. It also explains that scalars are overridden while arrays are concatenated, "
        "which is the part a reader gets wrong.",
    ),
    (
        "u-0051",
        "why does uv refuse to install a package from pypi once it found it on my private index",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/indexes.md#searching-across-multiple-indexes/0", 3),),
        "The answer is the rationale for the first-index default: limiting candidates to the first "
        "index that has the package prevents dependency-confusion attacks, with the torchtriton "
        "incident cited. The section also lists the unsafe-first-match and unsafe-best-match opt- "
        "outs and why they are called unsafe.",
    ),
    (
        "u-0052",
        "how does uv decide which index to consult first",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/indexes.md#defining-an-index/0", 3),
            ("docs/concepts/indexes.md#index-url-and-extra-index-url/0", 2),
        ),
        "Defining an index states the ordering rule: indexes are consulted in definition order, "
        "command-line indexes outrank configured ones, and the default index is always lowest "
        "priority wherever it appears in the list. The pip-compat section restates the same two "
        "rules for --index-url and --extra-index-url.",
    ),
    (
        "u-0053",
        "how do i keep uv from ever sending credentials to one of my indexes",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/indexes.md#authentication/disabling-authentication/0", 3),
            ("docs/concepts/indexes.md#authentication/using-credential-providers/0", 2),
        ),
        'Disabling authentication documents authenticate = "never", which stops any credential '
        "lookup for that index and errors if credentials are supplied anyway. Using credential "
        'providers earns a 2 because it explains the default search behaviour that "never" is '
        'suppressing, and the opposite "always" setting.',
    ),
    (
        "u-0054",
        "why am i warned about a preview feature when i never enabled preview",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/preview.md#using-preview-features/0", 3),
            ("docs/concepts/preview.md#/0", 2),
        ),
        "This section explains the mechanism: when the behaviour change is gated by user "
        "interaction, using the feature is itself the opt-in, so pointing uv pip install at a "
        "pylock.toml works without configuration but prints a preview warning, which enabling the "
        "feature silences. The page preamble frames preview features as opt-in and why they exist.",
    ),
    (
        "u-0055",
        "why does uv change my lockfile when i only wanted to run a command",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/projects/sync.md#automatic-lock-and-sync/0", 3),
            ("docs/concepts/projects/sync.md#/0", 2),
        ),
        "This section explains that locking and syncing are automatic — uv run locks and syncs "
        "before invoking the command, and lockfile readers such as uv tree update it first — and "
        "gives the three ways out: --locked, --frozen and --no-sync. The page preamble is a 2 for "
        "defining what locking and syncing each mean.",
    ),
    (
        "u-0056",
        "why did uv sync uninstall a package i had installed by hand",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/concepts/projects/sync.md#syncing-the-environment/handling-of-extraneous-packages/0",
                3,
            ),
        ),
        "This section explains the behaviour and its name: uv sync is exact by default and removes "
        "anything absent from the lockfile, --inexact retains those packages, and uv run is "
        "inexact by default with --exact to opt in.",
    ),
    (
        "u-0057",
        "why is it safe to run several uv commands at the same time",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/cache.md#cache-safety/0", 3),),
        "This section gives the reason rather than a value: the cache is thread-safe and append- "
        "only, so concurrent readers and writers are fine, and uv takes a file-based lock on the "
        "target virtual environment during installation. It also carries the caveat that manual "
        "edits to the cache are never safe.",
    ),
    (
        "u-0058",
        "why can two different uv releases share one cache directory",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/cache.md#cache-versioning/0", 3),),
        "The explanation is the bucket versioning scheme: each bucket carries a version, a "
        "breaking format change bumps it, and within a version changes are forwards- and "
        "backwards-compatible, so an incompatible release simply will not read the bucket. The "
        "0.4.12/0.4.13 example is worked through here.",
    ),
    (
        "u-0059",
        "should i install a tool or just run it with uvx",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/tools.md#execution-vs-installation/0", 3),
            ("docs/concepts/tools.md#the-uv-tool-interface/0", 2),
        ),
        "This section exists to answer exactly this trade-off: execution is usually more "
        "appropriate, and installation is for when the tool must be visible to other programs — a "
        "script you do not control, or a Docker image. The interface section frames the two modes "
        "without weighing them.",
    ),
    (
        "u-0060",
        "what happens to the environment uvx creates once the tool exits",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/tools.md#tool-environments/0", 3),),
        "Explains the mechanism: the uvx environment lives in the cache directory and is treated "
        "as disposable — kept only to avoid the overhead of repeated invocations, deleted by uv "
        "cache clean, and recreated automatically if it is gone.",
    ),
    (
        "u-0061",
        "how does uvx decide which version of a tool to run",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/tools.md#tool-versions/0", 3),),
        "Sets out the selection rule: latest on the first invocation, the cached version "
        "afterwards unless a version is requested or the cache is refreshed, and the installed "
        "version once uv tool install has been used — with @latest and --isolated as the escapes.",
    ),
    (
        "u-0062",
        "why does the lambda dockerfile use a multi-stage build",
        (EvalSlice.CONCEPTUAL,),
        (("docs/guides/integration/aws-lambda.md#deploying-a-docker-image/", 3),),
        "Section-scoped deliberately: the rationale is developed across the whole section — the "
        "two-stage plan is stated before the Dockerfile, and the payoff (minimal image size "
        "because the uv binary never reaches the final image, maximal cache reuse because "
        "dependencies install separately from application code) is spelled out after it with a "
        "cached build log.",
    ),
    (
        "u-0063",
        "why put lambda dependencies in a layer instead of in the function package",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/guides/integration/aws-lambda.md#deploying-a-zip-archive/using-a-lambda-layer/0",
                3,
            ),
        ),
        "Explains the motivation before the mechanics: separating dependencies from application "
        "code lets the dependency layer be reused across deployments, improving cold-start "
        "performance for application updates, and it is why --prefix is used instead of --target.",
    ),
    (
        "u-0064",
        "why must keyring and keyrings.codeartifact be installed from somewhere other than "
        "codeartifact",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/guides/integration/aws.md#authenticate-with-keyring-and-keyrings-codeartifact/0",
                3,
            ),
        ),
        "Gives the circularity argument: both packages are required in order to authenticate to "
        "the registry, so they must be pre-installed from another source; it also explains that "
        "the plugin wraps boto3 to mint and refresh short-lived tokens in the system keyring, and "
        "that uv only supports keyring in subprocess mode.",
    ),
    (
        "u-0065",
        "how can i run a uv script directly without typing uv run",
        (EvalSlice.CONCEPTUAL,),
        (("docs/guides/scripts.md#using-a-shebang-to-create-an-executable-file/0", 3),),
        "Explains the mechanism end to end: a '#!/usr/bin/env -S uv run --script' shebang plus "
        "chmod +x makes the file executable from the PATH or the current folder, and inline "
        "dependency metadata still works underneath the shebang.",
    ),
    (
        "u-0066",
        "what does uv's platform tier system mean",
        (EvalSlice.CONCEPTUAL,),
        (("docs/reference/policies/platforms.md#/0", 3),),
        "Explains the scheme rather than a single value: tier 1 is 'guaranteed to work' and "
        "continuously built, tested and developed against; tier 2 is 'guaranteed to build' and "
        "continuously built but not tested; tier 3 is best effort, possibly unbuilt but open to "
        "bug-fix patches. It also notes official binaries and wheels cover tiers 1 and 2.",
    ),
    (
        "u-0067",
        "why would i want uv to use my system's certificate store",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/authentication/certificates.md#system-certificates/0", 3),),
        "Gives the reasoning, not just the switch: uv defaults to bundled Mozilla roots, and you "
        "would want the platform store when you depend on a corporate trust root such as one "
        "required by a mandatory proxy; verification is then delegated to the OS via rustls- "
        "platform-verifier.",
    ),
    (
        "u-0068",
        "why do pytorch versions have a +cpu or +cu130 suffix",
        (EvalSlice.CONCEPTUAL,),
        (("docs/guides/integration/pytorch.md#installing-pytorch/0", 3),),
        "Explains that PyTorch ships a distinct build per accelerator and, absent a standard "
        "mechanism for expressing that, encodes the accelerator in the local version specifier.",
    ),
    (
        "u-0069",
        "why should a pytorch index be marked explicit",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/guides/integration/pytorch.md#using-a-pytorch-index/", 3),
            ("docs/guides/integration/pytorch.md#installing-gpu-enabled-pytorch-extensions/0", 2),
        ),
        "Gives the reason: explicit = true confines the index to torch, torchvision and friends so "
        "generic dependencies like jinja2 still come from PyPI. The GPU-extensions section "
        "restates the rule in one clause for the Astral index.",
    ),
    (
        "u-0070",
        "why does uv insist on a virtual environment when pip does not",
        (EvalSlice.CONCEPTUAL,),
        (("docs/pip/environments.md#/0", 3),),
        "The introduction gives the reasoning — installations' environments should not be "
        "modified, especially OS-managed ones, and a virtual environment is the lightweight "
        "isolation — then states that unlike pip, uv requires one by default.",
    ),
    (
        "u-0071",
        "why does running python -m uv pick a different environment",
        (EvalSlice.CONCEPTUAL,),
        (("docs/pip/environments.md#using-arbitrary-python-environments/0", 3),),
        "Explains that when invoked as `python -m uv`, uv defaults to the parent interpreter's "
        "environment rather than its usual discovery, and warns that this adds startup overhead.",
    ),
    (
        "u-0072",
        "what does installing a package in editable mode actually change",
        (EvalSlice.CONCEPTUAL,),
        (("docs/pip/packages.md#editable-packages/0", 3),),
        "Gives the property that defines editable installs — changes to the source take effect "
        "without reinstalling — and shows -e for the current project and for a project in another "
        "directory.",
    ),
    (
        "u-0073",
        "why should a tool read uv workspace metadata instead of parsing uv.lock",
        (EvalSlice.CONCEPTUAL,),
        (("docs/reference/internals/metadata.md#/0", 3),),
        "Gives the reason for the command's existence: lockfiles are not a stable format uv "
        "guarantees anything about, so tools wanting lockfile information should prefer this "
        "output.",
    ),
    (
        "u-0074",
        "why does the dependency graph contain two versions of the same package",
        (EvalSlice.CONCEPTUAL,),
        (("docs/reference/internals/metadata.md#handling-multiple-versions-of-a-package/", 3),),
        "Names the two causes — platform-specific requirements that conflict, and declared "
        "workspace conflicts — and states the guarantee that a conflict-free selection never "
        "installs two versions.",
    ),
    (
        "u-0075",
        "why do keyring and artifacts-keyring have to come from somewhere other than azure "
        "artifacts",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/guides/integration/azure.md#authenticate-with-keyring-and-artifacts-keyring/0",
                3,
            ),
        ),
        "Explains the bootstrap problem directly: because both packages are required in order to "
        "authenticate to Artifacts, they must be pre-installed from another source, and shows "
        "installing them from public PyPI.",
    ),
    (
        "u-0076",
        "why does uv build a package instead of downloading a wheel",
        (EvalSlice.CONCEPTUAL,),
        (("docs/reference/troubleshooting/build-failures.md#why-does-uv-build-a-package/0", 3),),
        "Explains the two situations: during resolution uv needs metadata for every platform and "
        "builds only after wheels and static sdist metadata both fail; during installation it "
        "builds when no wheel matches the current platform.",
    ),
    (
        "u-0077",
        "who decides which files end up in the wheel uv builds",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/build.md#/0", 3),),
        "The opening admonition explains the division of labour: uv acts only as a build frontend, "
        "choosing the Python version and invoking the backend, while the backend named in [build- "
        "system] determines included files and distribution filenames.",
    ),
    (
        "u-0078",
        "when is a workspace the right way to organize my packages",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/projects/workspaces.md#when-not-to-use-workspaces/0", 3),
            ("docs/concepts/projects/workspaces.md#/0", 2),
        ),
        "The section argues both directions: isolation and separation of concerns, extension- "
        "module and plugin cases, versus conflicting requirements or a wish for per-member "
        "environments, where path dependencies are preferable. The intro only states what a "
        "workspace is.",
    ),
    (
        "u-0079",
        "how can I stop CI from redownloading packages on every run",
        (EvalSlice.CONCEPTUAL,),
        (("docs/guides/integration/github.md#caching/0", 3),),
        "The section is about persisting uv's cache across workflow runs, via setup-uv's enable- "
        "cache or actions/cache keyed on uv.lock with UV_CACHE_DIR, plus the self-hosted runner "
        "caveat.",
    ),
    (
        "u-0080",
        "why does the recommended release workflow build and publish in separate jobs",
        (EvalSlice.CONCEPTUAL,),
        (("docs/guides/integration/github.md#publishing-to-pypi/0", 3),),
        "The admonition explains the split: the publishing job holds the id-token: write "
        "credential and does not share its permissions with the build step, reducing the surface "
        "for supply chain attacks.",
    ),
    (
        "u-0081",
        "why can't keyring itself be installed from artifact registry",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/guides/integration/google.md#authenticate-with-keyring-and-keyrings-google-artifactregistry-auth/0",
                3,
            ),
        ),
        "The section states that because keyring and the plugin are what authenticate to Artifact "
        "Registry, they must be pre-installed from another source, and explains the subprocess- "
        "only support and the PATH requirement.",
    ),
    (
        "u-0082",
        "why does importing a package I installed as a tool fail",
        (EvalSlice.CONCEPTUAL,),
        (("docs/guides/tools.md#installing-tools/0", 3),),
        "The section shows exactly this failure and explains it: unlike uv pip install, a tool "
        "install does not make the modules available in the current environment, and that "
        "isolation is deliberate, to reduce conflicts between tools, scripts and projects.",
    ),
    (
        "u-0083",
        "why doesn't uv pick up my pip.conf or PIP_INDEX_URL",
        (EvalSlice.CONCEPTUAL,),
        (("docs/pip/compatibility.md#configuration-files-and-environment-variables/0", 3),),
        "The section states uv does not read pip-specific configuration or environment variables "
        "and gives five reasons, then points at uv's own variables and uv.toml as the replacement.",
    ),
    (
        "u-0084",
        "why does uv ignore the upper bound on requires-python",
        (EvalSlice.CONCEPTUAL,),
        (("docs/pip/compatibility.md#requires-python-upper-bounds/0", 3),),
        "The section states only lower bounds are considered, with >=3.8, <4 treated as >=3.8, and "
        "explains why: honouring upper bounds makes resolvers backtrack to the first published "
        "version that omits them.",
    ),
    (
        "u-0085",
        "why will uv not move me from python 3.12 to 3.13 automatically",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/python-versions.md#upgrading-python-versions/0", 3),),
        "Gives the reason rather than a value: transparent upgrades are limited to patch releases "
        "because changing minor versions can affect dependency resolution. It also notes upgrades "
        "apply only to uv-managed versions.",
    ),
    (
        "u-0086",
        "how does uv decide which python interpreter to use",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/python-versions.md#discovery-of-python-versions/0", 3),
            ("docs/concepts/python-versions.md#finding-a-python-executable/0", 2),
        ),
        "Explains the search order and the rules applied to it: install dir, then `PATH`, then the "
        "Windows registry and Store; non-executables skipped, each candidate queried for metadata, "
        "first satisfying executable used; newest preferred for managed versions but first- "
        "compatible for system ones. The find section is where a reader can observe the outcome.",
    ),
    (
        "u-0087",
        "why does uv download prebuilt cpython instead of compiling it like pyenv",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/concepts/python-versions.md#managed-python-distributions/cpython-distributions/0",
                3,
            ),
        ),
        "Gives the explanation: Python publishes no official distributable binaries, so uv uses "
        "python-build-standalone; building from source as pyenv does needs preinstalled system "
        "dependencies and producing optimized PGO/LTO builds is very slow.",
    ),
    (
        "u-0088",
        "how does renovate know a repository is managed with uv",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/guides/integration/renovate.md#uv-lock-output/0", 3),
            ("docs/guides/integration/renovate.md#/0", 2),
        ),
        "States the detection rule — Renovate uses the presence of a `uv.lock` file — and what "
        "follows from it: upgrades proposed for project, optional and development dependencies, "
        "with both `pyproject.toml` and `uv.lock` updated. The intro only frames that uv is "
        "supported by Renovate.",
    ),
    (
        "u-0089",
        "when should i not use the uv build backend",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/build-backend.md#choosing-a-build-backend/0", 3),
            ("docs/concepts/build-backend.md#/0", 2),
        ),
        "This section gives the two reasons to pick something else: the uv backend only supports "
        "pure Python code, so extension modules need another backend, and hatchling is suggested "
        "when build scripts or a more flexible layout are required. The intro frames the choice by "
        "noting uv supports all PEP 517 backends.",
    ),
    (
        "u-0090",
        "why do pip-tools projects need one locked requirements file per operating system",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/guides/migration/pip-to-project.md#understanding-pip-workflows/platform-specific-dependencies/0",
                3,
            ),
        ),
        "Explains the cause with a worked example: pip-compile output is only valid on the "
        "platform it was generated on, shown by `colorama` appearing as a `tqdm` dependency on "
        "Windows but not Linux, so each supported platform needs its own lock file.",
    ),
    (
        "u-0091",
        "do i have to anchor include and exclude patterns to the project root",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/concepts/build-backend.md#file-inclusion-and-exclusion/include-and-exclude-syntax/0",
                3,
            ),
            ("docs/concepts/build-backend.md#file-inclusion-and-exclusion/0", 2),
        ),
        "Explains the asymmetry a reader trips over: includes are anchored (`pyproject.toml` "
        "matches only the root one, `src/**` recurses from the root) while excludes are not, so "
        "`__pycache__` matches at any depth unless you prefix a `/`. The parent section supplies "
        "the precedence rule the syntax operates under.",
    ),
    (
        "u-0092",
        "why should uv.lock be committed to version control",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/layout.md#the-lockfile/0", 3),),
        "Gives the reasoning rather than a value: the lockfile holds exact resolved versions, so "
        "checking it in makes installs consistent and reproducible across machines and pins the "
        "exact version set used when deploying.",
    ),
    (
        "u-0093",
        "UV_KEYRING_PROVIDER",
        (EvalSlice.EXACT,),
        (("docs/concepts/authentication/http.md#keyring-providers/0", 3),),
        "This section is where the variable is defined: it explains what a keyring provider is and "
        "states that setting UV_KEYRING_PROVIDER=subprocess (or --keyring-provider subprocess, or "
        "tool.uv.keyring-provider) enables the only supported provider type.",
    ),
    (
        "u-0094",
        "include-group",
        (EvalSlice.EXACT,),
        (("docs/concepts/projects/dependencies.md#development-dependencies/nesting-groups/0", 3),),
        "The nesting section is where include-group is introduced and shown in a [dependency- "
        "groups] table, along with the constraint that an included group's dependencies cannot "
        "conflict with the including group's.",
    ),
    (
        "u-0095",
        "tool.uv.dev-dependencies",
        (EvalSlice.EXACT,),
        (
            (
                "docs/concepts/projects/dependencies.md#development-dependencies/legacy-dev-dependencies/0",
                3,
            ),
        ),
        "Documents the legacy field itself: what it was used for before [dependency-groups] was "
        "standardized, that its contents are combined with dependency-groups.dev, that it will "
        "eventually be removed, and that uv add --dev reuses it when present.",
    ),
    (
        "u-0096",
        "NETRC environment variable",
        (EvalSlice.EXACT,),
        (("docs/concepts/authentication/http.md#netrc-files/0", 3),),
        "The netrc section is the only place that documents NETRC: it says the target .netrc path "
        "is loaded from the NETRC environment variable if defined, falling back to ~/.netrc.",
    ),
    (
        "u-0097",
        "--no-managed-python",
        (EvalSlice.EXACT,),
        (("docs/guides/install-python.md#using-existing-python-versions/0", 3),),
        "The section that documents the flag: it explains uv uses a satisfying system Python with "
        "no configuration, and that --no-managed-python is how you force uv to use the system "
        "Python.",
    ),
    (
        "u-0098",
        "--credential_helper",
        (EvalSlice.EXACT,),
        (("docs/guides/integration/bazel.md#authentication/0", 3),),
        "The Bazel authentication section is the only place documenting this option: Bazel 7 and "
        "newer supports credential helpers via --credential_helper, and it shows the .bazelrc "
        "lines binding hosts to the uv auth helper wrapper.",
    ),
    (
        "u-0099",
        "--upgrade-package",
        (EvalSlice.EXACT,),
        (
            ("docs/guides/projects.md#managing-dependencies/0", 3),
            ("docs/concepts/projects/dependencies.md#changing-dependencies/0", 2),
        ),
        "The projects guide documents the flag: uv lock --upgrade-package requests updates that "
        "package to the latest compatible version while leaving the rest of the lockfile intact. "
        "The changing-dependencies section only mentions it in a note as the way to force a locked "
        "version forward.",
    ),
    (
        "u-0100",
        "UV_NO_HF_TOKEN",
        (EvalSlice.EXACT,),
        (("docs/concepts/authentication/third-party.md#hugging-face-support/0", 3),),
        "This is the section that defines the variable: setting UV_NO_HF_TOKEN=1 disables uv's "
        "automatic Hugging Face authentication.",
    ),
    (
        "u-0101",
        "required-environments",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/resolution.md#required-environments/0", 3),
            ("docs/concepts/resolution.md#common-marker-values/0", 2),
        ),
        "The required-environments section defines the setting and what it forces uv to guarantee; "
        "common marker values only states in a clause that the setting takes PEP 508 markers.",
    ),
    (
        "u-0102",
        "exclude-newer-package",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/resolution.md#reproducible-resolutions/0", 3),
            ("docs/concepts/resolution.md#dependency-cooldowns/0", 2),
        ),
        "Reproducible resolutions defines the option, its per-package syntax and the =false opt- "
        "out; the cooldowns section only reuses the same option with a duration value.",
    ),
    (
        "u-0103",
        "tool.uv.dependency-metadata",
        (EvalSlice.EXACT,),
        (("docs/concepts/resolution.md#dependency-metadata/0", 3),),
        "This is the table's own documentation: why it exists, the chumpy and flash-attn examples, "
        "and which Metadata 2.3 fields uv actually reads from an entry.",
    ),
    (
        "u-0104",
        "exclude-dependencies",
        (EvalSlice.EXACT,),
        (("docs/concepts/resolution.md#dependency-exclusions/0", 3),),
        "The exclusions section is where the exclude-dependencies key is defined, in both its "
        "global form and its package-scoped inline-table form.",
    ),
    (
        "u-0105",
        "upload-time",
        (EvalSlice.EXACT,),
        (("docs/concepts/resolution.md#reproducible-resolutions/0", 3),),
        "The admonition here is what documents this index field: it names PEP 700, says a "
        "distribution lacking upload-time is treated as unavailable, lists the three opt-outs, and "
        "notes PyPI always provides it.",
    ),
    (
        "u-0106",
        "Splitting resolution on",
        (EvalSlice.EXACT,),
        (("docs/reference/internals/resolver.md#forking/0", 3),),
        "This exact log line is documented in the forking tip as the marker to grep for in uv lock "
        "-v output when you want to see where the resolver split.",
    ),
    (
        "u-0107",
        "git+ssh://",
        (EvalSlice.EXACT,),
        (("docs/concepts/authentication/git.md#ssh-authentication/0", 3),),
        "The SSH section is where this URL scheme is defined, with both the plain-host and the "
        "alternate-host-alias forms and the required git username.",
    ),
    (
        "u-0108",
        "prerelease-package",
        (EvalSlice.EXACT,),
        (("docs/concepts/resolution.md#pre-release-handling/0", 3),),
        "Defines the setting in both forms, --prerelease-package foo=allow and the [tool.uv] "
        "table, as the per-package override of the global pre-release strategy.",
    ),
    (
        "u-0109",
        "override-dependencies",
        (EvalSlice.EXACT,),
        (("docs/concepts/resolution.md#dependency-overrides/0", 3),),
        "Names tool.uv.override-dependencies as the pyproject.toml key for overrides and shows "
        "both the plain and the package-scoped inline-table entry forms.",
    ),
    (
        "u-0110",
        "UV_SYSTEM_PYTHON",
        (EvalSlice.EXACT,),
        (("docs/guides/integration/gitlab.md#using-uv-pip/0", 3),),
        "The uv pip section is where UV_SYSTEM_PYTHON is defined for this page: it is the variable "
        "that lets uv pip install into the system environment instead of requiring a virtualenv, "
        "with --no-system given as the opt-out.",
    ),
    (
        "u-0111",
        "UV_NO_MODIFY_PATH=1",
        (EvalSlice.EXACT,),
        (("docs/getting-started/installation.md#upgrading-uv/0", 3),),
        "This section states that uv self update re-runs the installer and can modify shell "
        "profiles, and that setting UV_NO_MODIFY_PATH=1 disables that behavior. It is the only "
        "place the variable is documented.",
    ),
    (
        "u-0112",
        "project.requires-python",
        (EvalSlice.EXACT,),
        (("docs/concepts/projects/config.md#python-version-requirement/0", 3),),
        "This section is where the project.requires-python field is declared and explained: where "
        "it goes in pyproject.toml, that setting it is recommended, and what it controls.",
    ),
    (
        "u-0113",
        "[project.scripts]",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/projects/config.md#entry-points/command-line-interfaces/0", 3),
            ("docs/concepts/projects/config.md#entry-points/0", 1),
        ),
        "The command-line interfaces subsection is the one that documents the [project.scripts] "
        "table, with the module:function syntax and the uv run invocation. The parent entry points "
        "section only names command line interfaces as a bullet in a list, hence grade 1.",
    ),
    (
        "u-0114",
        "uv:package:marker",
        (EvalSlice.EXACT,),
        (("docs/concepts/projects/export.md#cyclonedx-sbom-format/sbom-structure/0", 3),),
        "This subsection lists the custom properties uv adds to SBOM components and is the only "
        "place uv:package:marker is defined, as the environment marker property.",
    ),
    (
        "u-0115",
        "UV_INDEX_INTERNAL_PROXY_PASSWORD",
        (EvalSlice.EXACT,),
        (("docs/concepts/indexes.md#authentication/providing-credentials-directly/0", 3),),
        "This section is where that literal comes from and where the scheme behind it is defined: "
        "UV_INDEX_<NAME>_USERNAME / _PASSWORD, with the index name uppercased and non-alphanumeric "
        "characters replaced by underscores; internal-proxy is the example that produces this "
        "exact name.",
    ),
    (
        "u-0116",
        "UV_PREVIEW_FEATURES",
        (EvalSlice.EXACT,),
        (("docs/concepts/preview.md#enabling-preview-features/0", 3),),
        "This section defines the variable alongside its flag: UV_PREVIEW_FEATURES takes a comma- "
        "separated list, mirroring --preview-features, and sits next to UV_PREVIEW and the "
        "preview-features key in uv.toml / [tool.uv] / PEP 723 metadata.",
    ),
    (
        "u-0117",
        "--no-install-workspace",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/projects/sync.md#partial-installations/0", 3),
            (
                "docs/guides/integration/docker.md#optimizations/intermediate-layers/intermediate-layers-in-workspaces/0",
                2,
            ),
        ),
        "Partial installations is where the flag is defined: it skips every workspace member "
        "including the root project, while still installing their dependencies. The Docker "
        "workspaces subsection is a 2 for showing when to reach for it and pairing it with "
        "--frozen, but it does not define it.",
    ),
    (
        "u-0118",
        "tool.uv.cache-keys",
        (EvalSlice.EXACT,),
        (("docs/concepts/cache.md#dynamic-metadata/0", 3),),
        "This section defines the setting rather than merely mentioning it: it says cache-keys "
        "adds file paths and Git commit hashes to a package's cache key, warns that setting it "
        "replaces the defaults, and shows the file, git, glob, env and dir forms.",
    ),
    (
        "u-0119",
        "UV_INDEX_PRIVATE_REGISTRY_PASSWORD",
        (EvalSlice.EXACT,),
        (("docs/guides/integration/aws.md#authenticate-with-an-aws-access-token/0", 3),),
        "This section is where that variable is defined and its value explained: it carries the "
        "CodeArtifact authorization token, PRIVATE_REGISTRY must match the index name declared in "
        "pyproject.toml, and the paired username variable must be set to aws.",
    ),
    (
        "u-0120",
        "publish-url",
        (EvalSlice.EXACT,),
        (("docs/guides/integration/aws.md#publishing-packages/0", 3),),
        "The publishing section documents the key: it is added to the [[tool.uv.index]] entry so "
        "uv publish --index can target the registry, and it explains that the UV_PUBLISH_URL "
        "alternative is worse because uv cannot then check whether the package was already "
        "published.",
    ),
    (
        "u-0121",
        'package-ecosystem: "uv"',
        (EvalSlice.EXACT,),
        (("docs/guides/integration/dependabot.md#/0", 3),),
        "The page documents this literal: adding the uv package-ecosystem to the updates list in "
        "dependabot.yml is what enables Dependabot to update uv.lock files, and the example shows "
        "the exact YAML it belongs in.",
    ),
    (
        "u-0122",
        "allow-insecure-host",
        (EvalSlice.EXACT,),
        (("docs/concepts/authentication/certificates.md#insecure-hosts/0", 3),),
        "This is the section that documents the option: the pyproject.toml form, the accepted "
        "values (hostname or hostname-port pair), that it only applies to HTTPS, and the warning "
        "about using it outside trusted environments.",
    ),
    (
        "u-0123",
        "exclude-newer",
        (EvalSlice.EXACT,),
        (
            ("docs/guides/scripts.md#improving-reproducibility/0", 3),
            ("docs/guides/integration/dependabot.md#dependency-cooldown/0", 1),
        ),
        "The scripts section defines the field: it goes in the tool.uv table of inline metadata, "
        "limits uv to distributions released before a given RFC 3339 timestamp, and is shown in a "
        "complete example. The Dependabot section only names the option in passing while "
        "recommending a matching cooldown.",
    ),
    (
        "u-0124",
        "VIRTUAL_ENV",
        (EvalSlice.EXACT,),
        (
            ("docs/pip/environments.md#using-arbitrary-python-environments/0", 3),
            ("docs/pip/environments.md#discovery-of-python-environments/0", 2),
        ),
        "This section defines the variable's effect — setting VIRTUAL_ENV=/path/to/venv makes uv "
        "install there, and a directory that is not PEP 405 compliant is ignored. The discovery "
        "section only lists it as the first place searched.",
    ),
    (
        "u-0125",
        "--group",
        (EvalSlice.EXACT,),
        (("docs/pip/packages.md#installing-packages-from-files/0", 3),),
        "The section defining the flag: a bare group name from the current directory's "
        "pyproject.toml, --project to change where groups are sourced from, and per-group "
        "`path:group` syntax.",
    ),
    (
        "u-0126",
        "UV_PUBLISH_URL",
        (EvalSlice.EXACT,),
        (("docs/guides/integration/azure.md#publishing-packages/0", 3),),
        "The publishing section introduces UV_PUBLISH_URL as the way to run uv publish without a "
        "publish-url in pyproject.toml, and gives the caveat that uv then cannot check whether the "
        "package is already published.",
    ),
    (
        "u-0127",
        "workspace_root",
        (EvalSlice.EXACT,),
        (("docs/reference/internals/metadata.md#schema/", 3),),
        "The annotated example is where the field is defined, as the directory the uv.lock can be "
        "found in, alongside the neighbouring top-level fields.",
    ),
    (
        "u-0128",
        "error: command 'gcc' failed: No such file or directory",
        (EvalSlice.EXACT,),
        (
            (
                "docs/reference/troubleshooting/build-failures.md#common-build-failures/command-is-not-found/0",
                3,
            ),
        ),
        "The worked example for a missing command is this exact gcc error, with the fix (install "
        "it via the system package manager) and the tips about clang for uv-managed Pythons and "
        "build-essential.",
    ),
    (
        "u-0129",
        "astral-sh/uv-pre-commit",
        (EvalSlice.EXACT,),
        (("docs/guides/integration/pre-commit.md#/0", 3),),
        "Names astral-sh/uv-pre-commit as the official hook repository and uses it as the `repo` "
        "value in every configuration example, including the `rev` pin.",
    ),
    (
        "u-0130",
        "UV_TORCH_BACKEND",
        (EvalSlice.EXACT,),
        (("docs/guides/integration/pytorch.md#automatic-backend-selection/0", 3),),
        "Documents the variable as the environment-variable form of --torch-backend, with both the "
        "`auto` value and a pinned value such as cu130.",
    ),
    (
        "u-0131",
        "Private :: Do Not Upload",
        (EvalSlice.EXACT,),
        (("docs/concepts/projects/build.md#preventing-publish-to-pypi/0", 3),),
        "This classifier string appears only here, together with what it does (PyPI rejects the "
        "upload) and the limit that it does not affect alternative registries.",
    ),
    (
        "u-0132",
        "tool.uv.workspace",
        (EvalSlice.EXACT,),
        (("docs/concepts/projects/workspaces.md#getting-started/0", 3),),
        "The section documents the table: adding it creates a workspace rooted at that package, "
        "and it takes the required members and optional exclude keys, both lists of globs.",
    ),
    (
        "u-0133",
        "--from",
        (EvalSlice.EXACT,),
        (
            ("docs/guides/tools.md#commands-with-different-package-names/0", 3),
            ("docs/guides/tools.md#requesting-different-sources/0", 2),
        ),
        "The first section introduces --from as the option that runs a command from a package with "
        "a different name (http from httpie); the sources section reuses the same option for git "
        "URLs rather than defining it.",
    ),
    (
        "u-0134",
        "centralized-project-envs",
        (EvalSlice.EXACT,),
        (
            (
                "docs/concepts/projects/layout.md#the-project-environment/centralized-project-environments/0",
                3,
            ),
            ("docs/concepts/projects/layout.md#the-project-environment/0", 2),
        ),
        "This subsection is where the preview feature named by that literal is documented: the "
        "environment moves into the cache, uv tries to keep a `.venv` link, and explicit paths "
        "such as `UV_PROJECT_ENVIRONMENT` or `--active` are exempt. The parent section documents "
        "the default `.venv` behaviour the feature replaces.",
    ),
    (
        "u-0135",
        ".python-version",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/python-versions.md#requesting-a-version/python-version-files/0", 3),
            ("docs/concepts/python-versions.md#project-python-versions/0", 2),
        ),
        "This subsection documents the file itself: how uv searches the working directory and its "
        "parents then the user configuration directory, how `uv python pin` (and `--global`) "
        "creates one, that `--no-config` disables discovery, and that the search stops at project "
        "or workspace boundaries. The project section adds where the file sits relative to "
        "`requires-python`.",
    ),
    (
        "u-0136",
        "python-downloads",
        (EvalSlice.EXACT,),
        (("docs/concepts/python-versions.md#disabling-automatic-python-downloads/0", 3),),
        "This is the section that defines the option: its default `automatic`, the `manual` value "
        "that restricts downloads to `uv python install`, and that it can live in a persistent "
        "configuration file or be overridden with `--no-python-downloads`.",
    ),
    (
        "u-0137",
        "--bump",
        (EvalSlice.EXACT,),
        (("docs/guides/package.md#updating-your-version/0", 3),),
        "Section-scoped deliberately: the option's meaning is spread across this whole section — "
        "the accepted components (major, minor, patch, stable, alpha, beta, rc, post, dev), the "
        "largest-to-smallest ordering when repeated, the `--bump <component>=<value>` form, and "
        "the worked stable-to-prerelease and prerelease-to-stable transitions. No single chunk "
        "carries all of it.",
    ),
    (
        "u-0138",
        "--no-attestations",
        (EvalSlice.EXACT,),
        (
            (
                "docs/guides/package.md#publishing-your-package/uploading-attestations-with-your-package/0",
                3,
            ),
        ),
        "This subsection is where the flag is defined and motivated: uv uploads attestations by "
        "default, some third-party indexes reject uploads containing them, and `--no-attestations` "
        "or `UV_PUBLISH_NO_ATTESTATIONS` turns that default off.",
    ),
    (
        "u-0139",
        "module-name",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/build-backend.md#modules/0", 3),
            ("docs/concepts/build-backend.md#namespace-packages/0", 2),
        ),
        "The Modules section is where `module-name` is defined: it states the default "
        "(`src/<package_name>/__init__.py`), the name-normalization rule, and shows the "
        "`[tool.uv.build-backend]` table where `module-name` and `module-root` are set. Namespace "
        "packages extends the same setting (a `.` in `module-name`, or a list of names) without "
        "defining it.",
    ),
    (
        "u-0140",
        "platform_machine",
        (EvalSlice.EXACT,),
        (("docs/concepts/resolution.md#common-marker-values/0", 3),),
        "Common marker values is the only place `platform_machine` is documented: the table gives "
        "its value on Linux, macOS and Windows for both x86-64 (`'x86_64'`/`'x86_64'`/`'AMD64'`) "
        "and ARM64 (`'aarch64'`/`'arm64'`/`'ARM64'`), and the section says where these values come "
        "from.",
    ),
    (
        "u-0141",
        "--prerelease allow",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/resolution.md#pre-release-handling/0", 3),
            ("docs/pip/compatibility.md#pre-release-compatibility/0", 3),
        ),
        "Both sections state what `--prerelease allow` does — consider pre-releases for every "
        "package without preferring stable candidates first — against the `if-necessary` default, "
        "and contrast it with `disallow` and `explicit`. The text is equivalent in both, so each "
        "documents the flag.",
    ),
    (
        "u-0142",
        "--python-version",
        (EvalSlice.EXACT,),
        (("docs/concepts/resolution.md#platform-specific-resolution/0", 3),),
        "Platform-specific resolution documents `--python-version` for `uv pip compile`: it shows "
        "it paired with `--python-platform` to compile for Python 3.10 on Linux from a Mac, and "
        "states the semantics that matter — under platform-specific resolution the value is the "
        "exact Python version, not a lower bound.",
    ),
    (
        "u-0143",
        "PEP 625",
        (EvalSlice.EXACT,),
        (("docs/concepts/resolution.md#source-distribution/0", 3),),
        "The Source distribution section is the passage that says what PEP 625 specifies — source "
        "distributions must be gzip tarballs (`.tar.gz`) — and states uv's enforcement of it as of "
        "0.12, with `.zip` still accepted for backward compatibility.",
    ),
    (
        "u-0144",
        "ModuleNotFoundError: No module named 'pip'",
        (EvalSlice.EXACT,),
        (
            (
                "docs/reference/troubleshooting/build-failures.md#common-build-failures/module-is-missing-or-cannot-be-imported/0",
                3,
            ),
        ),
        "This is the failure that section is built around: it shows the `chumpy` build emitting "
        "exactly this traceback because the package assumes `pip` is available without declaring "
        "it as a build dependency, and gives the fix (pre-install the build dependencies, then "
        "`--no-build-isolation-package chumpy`).",
    ),
    (
        "u-0145",
        "ModuleNotFoundError: No module named 'distutils'",
        (EvalSlice.EXACT,),
        (
            ("docs/reference/troubleshooting/build-failures.md#recognizing-a-build-failure/0", 3),
            (
                "docs/reference/troubleshooting/build-failures.md#confirming-that-a-build-failure-is-specific-to-uv/0",
                2,
            ),
        ),
        "Recognizing a build failure uses this exact traceback as its worked example and carries "
        "uv's hint explaining it — `distutils` was removed from the standard library in Python "
        "3.12, so constrain `numpy` above 1.19.5. The next section reproduces the same error under "
        "pip to show it is not a uv bug.",
    ),
    (
        "u-0146",
        "fatal error: graphviz/cgraph.h: No such file or directory",
        (EvalSlice.EXACT,),
        (
            (
                "docs/reference/troubleshooting/build-failures.md#common-build-failures/header-or-library-is-missing/0",
                3,
            ),
        ),
        "This is the log excerpt that section reproduces: the `pygraphviz` build failing on a "
        "missing header, with uv's hint about needing a library that provides `graphviz/cgraph.h` "
        "and the resolution (`apt install libgraphviz-dev`, not the `graphviz` package).",
    ),
    (
        "u-0147",
        "XDG_BIN_HOME",
        (EvalSlice.EXACT,),
        (("docs/reference/storage.md#storage-directories/executable-directory/0", 3),),
        "The executable directory subsection is where `XDG_BIN_HOME` is documented: it is the "
        "first entry in the ordered lookup for the directory that should be on the PATH, ahead of "
        "`$XDG_DATA_HOME/../bin` and `$HOME/.local/bin`, with the Windows equivalents.",
    ),
    (
        "u-0148",
        "namespace = true",
        (EvalSlice.EXACT,),
        (("docs/concepts/build-backend.md#namespace-packages/0", 3),),
        "This is the only passage that documents the `namespace = true` option: it says it avoids "
        "declaring each module name for complex namespaces, shows the TOML, warns that it disables "
        "safety checks, and shows combining it with an explicit `module-name` root.",
    ),
    (
        "u-0149",
        "tool.uv.build-backend.wheel-exclude",
        (EvalSlice.EXACT,),
        (("docs/concepts/build-backend.md#file-inclusion-and-exclusion/0", 3),),
        "This section is where `wheel-exclude` is given its meaning: it lists what a wheel build "
        "includes and then states that `source-exclude`, `wheel-exclude` and the default excludes "
        "are removed from that set, and that exclusions take precedence over inclusions.",
    ),
    (
        "u-0150",
        "explicit = true",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/indexes.md#pinning-a-package-to-an-index/0", 3),
            ("docs/concepts/indexes.md#flat-indexes/0", 1),
        ),
        "Pinning a package to an index defines `explicit = true` — it prevents installs from that "
        "index unless a package is pinned to it via `tool.uv.sources` — and covers the `default = "
        "true` plus `explicit = true` combination. The flat-index section only names it as an "
        "example of a supported feature.",
    ),
    (
        "u-0151",
        'format = "flat"',
        (EvalSlice.EXACT,),
        (("docs/concepts/indexes.md#flat-indexes/0", 3),),
        'The "Flat" indexes section is the only place `format = "flat"` appears: it explains '
        "that flat indexes are local directories or HTML pages of wheels and sdists (pip's "
        "`--find-links`) and shows the option in a `[[tool.uv.index]]` entry.",
    ),
    (
        "u-0152",
        "unsafe-best-match",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/indexes.md#searching-across-multiple-indexes/0", 3),
            ("docs/pip/compatibility.md#packages-that-exist-on-multiple-indexes/0", 3),
        ),
        "Both passages enumerate the `--index-strategy` / `UV_INDEX_STRATEGY` values and define "
        "`unsafe-best-match` as selecting the best version across the combined candidate set, "
        "warning it exposes dependency-confusion risk; the pip-compatibility page states the same "
        "definition in the context of pip's behavior, so both genuinely document the literal.",
    ),
    (
        "u-0153",
        "UV_DEFAULT_INDEX",
        (EvalSlice.EXACT,),
        (("docs/concepts/indexes.md#defining-an-index/0", 3),),
        "Defining an index is where `UV_DEFAULT_INDEX` is introduced, as the environment-variable "
        "form of `--default-index`, alongside `UV_INDEX`, and it explains the accepted values (a "
        "URL, a configured name, or `<name>=<url>`) and that the default index is always lowest "
        "priority.",
    ),
    (
        "u-0154",
        "tool.uv.conflicts",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/resolution.md#conflicting-dependencies/", 3),
            ("docs/concepts/projects/config.md#conflicting-dependencies/0", 2),
        ),
        "The resolution section documents the `conflicts` key end to end and the answer is "
        "genuinely spread over both of its chunks: the extra and group forms are in the first, the "
        "workspace `package` key forms in the second. The projects config section frames why "
        "conflicts must be declared without showing the full key.",
    ),
    (
        "u-0155",
        "UV_EXCLUDE_NEWER",
        (EvalSlice.EXACT,),
        (("docs/concepts/resolution.md#reproducible-resolutions/0", 3),),
        "Reproducible resolutions is where `UV_EXCLUDE_NEWER` is documented: it is named as one of "
        "the three ways to disable a cutoff inherited from a lower-priority configuration source "
        "(`--exclude-newer false`, `UV_EXCLUDE_NEWER=false`, or `exclude-newer = false` higher "
        "up), within the section that defines the option's accepted values.",
    ),
    (
        "u-0156",
        "how do i add a dependency that only installs on linux",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/dependencies.md#platform-specific-dependencies/0", 3),),
        "Answers with the exact invocation: uv add \"jax; sys_platform == 'linux'\", and shows the "
        "resulting environment marker in the pyproject.toml dependency entry.",
    ),
    (
        "u-0157",
        "which dependency group does uv install without being asked",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/projects/dependencies.md#development-dependencies/default-groups/0", 3),
            ("docs/concepts/projects/dependencies.md#development-dependencies/0", 2),
        ),
        "The default-groups section states the answer — uv includes the dev group during uv run "
        "and uv sync — and shows how tool.uv.default-groups changes it. The parent section only "
        "frames it, mentioning in a clause that the dev group is synced by default.",
    ),
    (
        "u-0158",
        "can a dependency group need a newer python than the project itself",
        (EvalSlice.FACT,),
        (
            (
                "docs/concepts/projects/dependencies.md#development-dependencies/group-requires-python/0",
                3,
            ),
        ),
        "States that groups must by default match the project's requires-python range, and that a "
        "group needing a different range declares its own requires-python under "
        "[tool.uv.dependency-groups], with a worked example of a project at >=3.10 and a dev group "
        "at >=3.12.",
    ),
    (
        "u-0159",
        "which uv command prints the path to the cache directory",
        (EvalSlice.FACT,),
        (("docs/getting-started/features.md#utility/0", 3),),
        "The utility section is where the state-inspection commands are enumerated with their "
        "effects, and it is the passage that states uv cache dir shows the uv cache directory path "
        "(next to uv tool dir and uv python dir).",
    ),
    (
        "u-0160",
        "where does uv save the credentials it stores",
        (EvalSlice.FACT,),
        (("docs/concepts/authentication/http.md#the-uv-credentials-store/0", 3),),
        "Gives the one stated answer: a plaintext file in uv's state directory, e.g. "
        "~/.local/share/uv/credentials/credentials.toml on Unix, and warns it is not meant to be "
        "edited by hand.",
    ),
    (
        "u-0161",
        "how do i install pypy with uv",
        (EvalSlice.FACT,),
        (("docs/guides/install-python.md#installing-a-specific-version/0", 3),),
        "This section gives the literal answer for an alternative implementation: uv python "
        "install pypy@3.10, alongside the single-version and multi-version forms.",
    ),
    (
        "u-0162",
        "does uv download python by itself if none is installed",
        (EvalSlice.FACT,),
        (
            ("docs/guides/install-python.md#automatic-python-downloads/0", 3),
            ("docs/guides/install-python.md#/0", 2),
        ),
        "The automatic-downloads section states it outright: Python need not be installed "
        "explicitly, uv downloads required versions by default, and even with no version requested "
        "uv venv will install the latest before creating the environment. The page introduction "
        "only frames the same behaviour in a clause.",
    ),
    (
        "u-0163",
        "what is the .python-version file for",
        (EvalSlice.FACT,),
        (("docs/guides/projects.md#project-structure/python-version/0", 3),),
        "States the specific answer: the file holds the project's default Python version and tells "
        "uv which Python to use when creating the project's virtual environment.",
    ),
    (
        "u-0164",
        "how do i let uv pull a private hugging face dataset script",
        (EvalSlice.FACT,),
        (("docs/concepts/authentication/third-party.md#hugging-face-support/0", 3),),
        "States the specific answer: if HF_TOKEN is set, uv propagates it to requests to "
        "huggingface.co, and shows the HF_TOKEN=hf_... uv run <dataset resolve url> invocation for "
        "a private dataset script.",
    ),
    (
        "u-0165",
        "which username do I need in a git+ssh dependency url",
        (EvalSlice.FACT,),
        (("docs/concepts/authentication/git.md#ssh-authentication/0", 3),),
        "States flatly that SSH authentication requires the username git, and shows it in every "
        "git+ssh://git@... example.",
    ),
    (
        "u-0166",
        "do I have to type the extension to run a windows script through uv run",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/run.md#legacy-scripts-on-windows/0", 3),),
        "Answers no, and gives the resolution order uv tries on your behalf: .ps1, then .cmd, then "
        ".bat, with the nuitka example shown both ways.",
    ),
    (
        "u-0167",
        "which signals does uv refuse to forward to the command it runs",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/run.md#signal-handling/0", 3),),
        "Lists the exceptions explicitly - SIGKILL, SIGCHLD, SIGIO and SIGPOLL are not forwarded "
        "on Unix - and adds the separate SIGINT rule.",
    ),
    (
        "u-0168",
        "what is sys_platform on 64-bit windows",
        (EvalSlice.FACT,),
        (("docs/concepts/resolution.md#common-marker-values/0", 3),),
        "The marker table gives 'win32' for Windows and the note answers the 64-bit half directly: "
        "sys_platform is always 'win32' there.",
    ),
    (
        "u-0169",
        "which fields of a dependency-metadata entry does uv actually read",
        (EvalSlice.FACT,),
        (("docs/concepts/resolution.md#dependency-metadata/0", 3),),
        "Names exactly the five fields uv reads out of the Metadata 2.3 entry - name, version, "
        "requires-dist, requires-python, provides-extra - and says version is optional for "
        "registry dependencies.",
    ),
    (
        "u-0170",
        "can I express a dependency cooldown in months",
        (EvalSlice.FACT,),
        (("docs/concepts/resolution.md#dependency-cooldowns/0", 3),),
        "Answers no: calendar units such as months and years are not allowed because their lengths "
        "are inherently inconsistent, unlike hours, days and weeks.",
    ),
    (
        "u-0171",
        "what causes a 401 unauthorized when publishing to artifactory with a token",
        (EvalSlice.FACT,),
        (("docs/guides/integration/jfrog.md#publishing-packages/0", 3),),
        "Gives the cause and the fix: JFrog requires an empty username, but uv sends __token__ as "
        "the username whenever --token or UV_PUBLISH_TOKEN is used.",
    ),
    (
        "u-0172",
        "does a version requested with --with beat the version my project requires",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/run.md#requesting-additional-dependencies/0", 3),),
        "States that the requested version is respected regardless of the project's requirements, "
        "and spells out the httpx==0.24.0 case where the project's pin loses.",
    ),
    (
        "u-0173",
        "which solver implementation does uv build its resolver on",
        (EvalSlice.FACT,),
        (("docs/reference/internals/resolver.md#resolver/0", 3),),
        "Names pubgrub-rs, the Rust implementation of PubGrub, and then walks through the steps uv "
        "runs on top of it.",
    ),
    (
        "u-0174",
        "what rust version do i need to build uv from source",
        (EvalSlice.FACT,),
        (("docs/reference/policies/rust.md#/0", 3),),
        "The Rust support policy states the answer precisely: the minimum is the rust-version key "
        "in Cargo.toml [workspace.package], it may change in any release, and it is never newer "
        "than N-2 stable versions.",
    ),
    (
        "u-0175",
        "which uv crates on crates.io actually promise stability",
        (EvalSlice.FACT,),
        (("docs/reference/policies/versioning.md#crate-versioning/0", 3),),
        "This section names the three crates that follow the uv versioning policy (uv, uv-build, "
        "uv-version) and says the rest give no stability guarantees and are versioned 0.0.x.",
    ),
    (
        "u-0176",
        "where does uv create the project virtual environment by default",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/config.md#project-environment-path/0", 3),),
        "The section states the default path is .venv and describes how a configured relative path "
        "is resolved relative to the workspace root, which is the specific answer to where the "
        "environment lands.",
    ),
    (
        "u-0177",
        "what address does jupyter lab listen on when started through uv run",
        (EvalSlice.FACT,),
        (("docs/guides/integration/jupyter.md#using-jupyter-within-a-project/0", 3),),
        "This section gives the concrete answer: started with uv run --with jupyter jupyter lab, "
        "the server defaults to http://localhost:8888/lab.",
    ),
    (
        "u-0178",
        "install uv with homebrew",
        (EvalSlice.FACT,),
        (("docs/getting-started/installation.md#installation-methods/homebrew/0", 3),),
        "The Homebrew subsection states that uv is in the core Homebrew packages and gives the "
        "brew install uv command - the whole answer sits here.",
    ),
    (
        "u-0179",
        "how do i install a specific older version of uv with the install script",
        (EvalSlice.FACT,),
        (("docs/getting-started/installation.md#installation-methods/standalone-installer/0", 3),),
        "The standalone installer section answers this directly: include the version in the "
        "astral.sh URL, and it shows the pinned-version form for both the sh and the PowerShell "
        "installers.",
    ),
    (
        "u-0180",
        "what do i delete to remove uv from my machine",
        (EvalSlice.FACT,),
        (("docs/getting-started/installation.md#uninstallation/0", 3),),
        "The uninstallation section lists exactly what to remove: the stored data via uv cache "
        "clean and the python and tool directories, then the uv, uvx and uvw binaries under "
        "~/.local/bin.",
    ),
    (
        "u-0181",
        "what happens if i run uv init in a directory that already has a pyproject.toml",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/init.md#target-directory/0", 3),),
        "The target directory section states the outcome: if there is already a pyproject.toml in "
        "the target directory, uv exits with an error.",
    ),
    (
        "u-0182",
        "what formats can uv export a lockfile to",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/projects/export.md#overview-of-export-formats/0", 3),
            ("docs/concepts/projects/export.md#/0", 2),
        ),
        "The overview enumerates the three supported formats (requirements.txt, pylock.toml, "
        "CycloneDX) and the --format flag values for each. The page preamble only frames that uv "
        "export supports multiple output formats.",
    ),
    (
        "u-0183",
        "how do i make torch always install from the pytorch index",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/indexes.md#pinning-a-package-to-an-index/0", 3),
            ("docs/concepts/indexes.md#defining-an-index/0", 2),
        ),
        "The pinning section gives the exact answer with torch as its worked example: a "
        "tool.uv.sources entry naming the index, optionally with explicit = true so nothing else "
        "resolves there. Defining an index is a 2 because the pinned index must first exist as a "
        "[[tool.uv.index]] entry, which that section documents.",
    ),
    (
        "u-0184",
        "what does uv do when an index answers 401 or 403 while it is looking for a package",
        (EvalSlice.FACT,),
        (("docs/concepts/indexes.md#authentication/ignoring-error-codes/0", 3),),
        "The stated answer is here: under the first-index strategy uv stops searching across "
        "indexes on 401 or 403, except that it ignores 403 from the pytorch index; ignore-error- "
        "codes changes which codes are tolerated, and 404 always continues the search and cannot "
        "be overridden.",
    ),
    (
        "u-0185",
        "how do i turn preview features off",
        (EvalSlice.FACT,),
        (("docs/concepts/preview.md#disabling-preview-features/0", 3),),
        "The section states the single answer: the --no-preview option disables preview features.",
    ),
    (
        "u-0186",
        "does uv treat my lockfile as outdated when a dependency publishes a new release",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/sync.md#checking-the-lockfile/0", 3),),
        "The section answers no, in an admonition: uv does not consider a lockfile outdated "
        "because new versions were released; it compares the lockfile against project metadata, so "
        "only a changed dependency or a constraint that now excludes the locked version makes it "
        "stale.",
    ),
    (
        "u-0187",
        "how do i sync every extra a project defines",
        (EvalSlice.FACT,),
        (
            (
                "docs/concepts/projects/sync.md#syncing-the-environment/syncing-optional-dependencies/0",
                3,
            ),
        ),
        "The section states that extras are not synced by default, that --extra includes one, and "
        "that --all-extras enables them all — the specific answer asked for.",
    ),
    (
        "u-0188",
        "how do i clear the cache for a single package instead of the whole thing",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/cache.md#clearing-the-cache/0", 3),
            ("docs/concepts/cache.md#dependency-caching/0", 2),
        ),
        "Clearing the cache states the answer with an example: `uv cache clean ruff` removes all "
        "cache entries for that one package. The dependency-caching section repeats the same "
        "escape hatch in a clause while listing ways out of caching trouble.",
    ),
    (
        "u-0189",
        "what does uv use as the cache key for a git dependency",
        (EvalSlice.FACT,),
        (("docs/concepts/cache.md#dependency-caching/0", 3),),
        "The per-dependency-kind list answers this with one stated value: Git dependencies are "
        "cached on the fully-resolved commit hash, which is also why uv pip compile pins them to a "
        "commit.",
    ),
    (
        "u-0190",
        "where does uv look for its configuration file",
        (EvalSlice.FACT,),
        (("docs/concepts/configuration-files.md#/0", 3),),
        "The page preamble names the search itself: pyproject.toml or uv.toml in the current "
        "directory or nearest parent, plus the user-level (~/.config/uv/uv.toml, "
        "%APPDATA%\\uv\\uv.toml) and system-level (/etc/uv/uv.toml, %PROGRAMDATA%\\uv\\uv.toml) "
        "locations, and the workspace-root rule.",
    ),
    (
        "u-0191",
        "where does uv tool install put the tool",
        (EvalSlice.FACT,),
        (
            ("docs/reference/storage.md#types-of-data/tools/0", 3),
            ("docs/concepts/tools.md#tool-environments/0", 2),
        ),
        "The storage page gives the concrete location — a tools/ subdirectory of the persistent "
        "data directory, e.g. ~/.local/share/uv/tools, with uv tool dir to print it and "
        "UV_TOOL_DIR to change it. The tools concept page only says the environment is created in "
        "the uv tools directory.",
    ),
    (
        "u-0192",
        "how large can a lambda zip archive be",
        (EvalSlice.FACT,),
        (("docs/guides/integration/aws-lambda.md#deploying-a-zip-archive/0", 3),),
        "The opening of the zip section gives the number: zip archives are limited to 250 MB, "
        "which is the constraint that decides between this path and a container image.",
    ),
    (
        "u-0193",
        "what username should i use when authenticating to aws codeartifact",
        (EvalSlice.FACT,),
        (
            ("docs/guides/integration/aws.md#authenticate-with-an-aws-access-token/0", 3),
            (
                "docs/guides/integration/aws.md#authenticate-with-keyring-and-keyrings-codeartifact/0",
                2,
            ),
        ),
        "The token section states the specific answer — the username must be aws or authentication "
        "will fail, with the token in the password field. The keyring section repeats the "
        "constraint for the keyring CLI path without documenting the token scheme.",
    ),
    (
        "u-0194",
        "what happens when i run a .pyw file with uv on windows",
        (EvalSlice.FACT,),
        (("docs/guides/scripts.md#using-gui-scripts/0", 3),),
        "States the specific behaviour: on Windows uv runs a script whose extension is .pyw using "
        "pythonw, with tkinter and PyQt5 examples showing it works with and without extra "
        "dependencies.",
    ),
    (
        "u-0195",
        "what tools is uv's performance compared against",
        (EvalSlice.FACT,),
        (("docs/reference/benchmarks.md#/0", 3),),
        "The benchmarks page gives the answer in one place: uv is benchmarked continually against "
        "its own previous releases and regularly compared with other tools in the space, naming "
        "pip and Poetry, with the results kept in the GitHub repository.",
    ),
    (
        "u-0196",
        "what is the oldest windows version uv supports",
        (EvalSlice.FACT,),
        (("docs/reference/policies/platforms.md#windows-versions/0", 3),),
        "Gives the specific minimum: Windows 10 and Windows Server 2016, following Rust's own tier "
        "1 support.",
    ),
    (
        "u-0197",
        "which versions of macos does uv support",
        (EvalSlice.FACT,),
        (("docs/reference/policies/platforms.md#macos-versions/0", 3),),
        "States the supported floor — macOS 13 (Ventura) and later — plus the caveat that macOS 12 "
        "is known to work if a realpath executable is installed.",
    ),
    (
        "u-0198",
        "can uv read der encoded certificates",
        (EvalSlice.FACT,),
        (("docs/concepts/authentication/certificates.md#custom-certificates/0", 3),),
        "The custom certificates section answers this flatly — 'DER-encoded files are not "
        "supported' — alongside the extensions uv does read (.pem, .crt, .cer) and the fact that "
        "unparseable files in SSL_CERT_DIR are ignored.",
    ),
    (
        "u-0199",
        "can i use --torch-backend with uv add or uv sync",
        (EvalSlice.FACT,),
        (("docs/guides/integration/pytorch.md#automatic-backend-selection/0", 3),),
        "Answers no: the section closes by stating that at present --torch-backend is only "
        "available in the uv pip interface.",
    ),
    (
        "u-0200",
        "where do i get prebuilt flash-attn wheels instead of compiling it",
        (EvalSlice.FACT,),
        (("docs/guides/integration/pytorch.md#installing-gpu-enabled-pytorch-extensions/0", 3),),
        "Names the Astral GPU indexes as the source of pre-built wheels for flash-attn (and "
        "deepspeed, vllm, others) and gives the `uv add flash-attn --index astral-cu128=...` "
        "command.",
    ),
    (
        "u-0201",
        "which platforms get gpu wheels if i just run uv add torch",
        (EvalSlice.FACT,),
        (("docs/guides/integration/pytorch.md#installing-pytorch/0", 3),),
        "States that the default PyPI-sourced configuration yields CPU-only wheels on Windows and "
        "macOS and GPU-accelerated wheels on Linux, targeting CUDA 13.0 as of PyTorch 2.11.0.",
    ),
    (
        "u-0202",
        "what username should i use for azure artifacts when authenticating through keyring",
        (EvalSlice.FACT,),
        (
            (
                "docs/guides/integration/azure.md#authenticate-with-keyring-and-artifacts-keyring/0",
                3,
            ),
        ),
        "States that the keyring CLI requires a username in the URL and that it must be "
        "`VssSessionToken`, and shows setting it via UV_INDEX_PRIVATE_REGISTRY_USERNAME.",
    ),
    (
        "u-0203",
        "in what order does uv look for a virtual environment",
        (EvalSlice.FACT,),
        (("docs/pip/environments.md#discovery-of-python-environments/0", 3),),
        "Gives the ordered list: VIRTUAL_ENV, then CONDA_PREFIX, then a .venv in the current or "
        "nearest parent directory, and says uv prompts to create one if none is found.",
    ),
    (
        "u-0204",
        "how do i install a package from a github branch",
        (EvalSlice.FACT,),
        (("docs/pip/packages.md#installing-a-package/0", 3),),
        "Shows the git+https form with an @ reference and spells out the three variants — tag, "
        "commit hash, and branch (`@main`).",
    ),
    (
        "u-0205",
        "which python versions does uv have tier 1 support for",
        (EvalSlice.FACT,),
        (("docs/reference/policies/python.md#python-versions/0", 3),),
        "Lists 3.10 through 3.14 as Tier 1 and says uv is continuously tested against them.",
    ),
    (
        "u-0206",
        "which pre-commit hook compiles a requirements.in file",
        (EvalSlice.FACT,),
        (("docs/guides/integration/pre-commit.md#/0", 3),),
        "Shows the pip-compile hook with `args: [requirements.in, -o, requirements.txt]`, plus how "
        "to retarget it with `files` and how to declare several entries for several input files.",
    ),
    (
        "u-0207",
        "does logging out of a service invalidate the credentials on the server",
        (EvalSlice.FACT,),
        (("docs/concepts/authentication/cli.md#logging-out-of-a-service/0", 3),),
        "The section's note answers exactly this: credentials are removed from local storage only, "
        "not rendered unusable with the remote server.",
    ),
    (
        "u-0208",
        "where does uv keep the credentials I add with uv auth login",
        (EvalSlice.FACT,),
        (("docs/concepts/authentication/cli.md#configuring-the-storage-backend/0", 3),),
        "The section states credentials are persisted to the uv credentials store, written to a "
        "plaintext file by default, with an encrypted system-native backend available behind a "
        "preview feature.",
    ),
    (
        "u-0209",
        "where do the files from uv build end up",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/build.md#using-uv-build/0", 3),),
        "The section states the built artifacts are placed in a dist/ subdirectory and shows the "
        "resulting wheel and tar.gz filenames.",
    ),
    (
        "u-0210",
        "can one workspace member require a different python version than the others",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/workspaces.md#when-not-to-use-workspaces/0", 3),),
        "The section states workspaces enforce a single requires-python for the whole workspace, "
        "the intersection of all members' values, and that testing a member on an unsupported "
        "version needs uv pip in a separate environment.",
    ),
    (
        "u-0211",
        "which action should I use to install uv in a github workflow",
        (EvalSlice.FACT,),
        (("docs/guides/integration/github.md#installation/0", 3),),
        "The section names the recommended action, astral-sh/setup-uv, says what it does (installs "
        "uv, adds it to PATH, optionally persists the cache) and shows pinning a version.",
    ),
    (
        "u-0212",
        "how do I let my workflow install a dependency from a private github repository",
        (EvalSlice.FACT,),
        (("docs/guides/integration/github.md#private-repos/0", 3),),
        "The section gives the procedure: create a PAT with read access, store it as a repository "
        "secret, then use gh auth login and gh auth setup-git to configure Git's credential "
        "helper.",
    ),
    (
        "u-0213",
        "what username does google artifact registry expect when I pass an access token",
        (EvalSlice.FACT,),
        (
            ("docs/guides/integration/google.md#authenticate-with-a-google-access-token/0", 3),
            (
                "docs/guides/integration/google.md#authenticate-with-keyring-and-keyrings-google-artifactregistry-auth/0",
                2,
            ),
        ),
        "The access-token section states the username must be oauth2accesstoken or authentication "
        "fails, and shows setting it via UV_INDEX_<NAME>_USERNAME. The keyring section restates "
        "the same requirement for the keyring CLI.",
    ),
    (
        "u-0214",
        "how do I run a tool at an older version without installing it",
        (EvalSlice.FACT,),
        (("docs/guides/tools.md#requesting-specific-versions/0", 3),),
        "The section gives command@version and the --from forms for pinned versions and ranges, "
        "and notes the @ syntax accepts only an exact version.",
    ),
    (
        "u-0215",
        "how do i ask uv for a free-threaded python build",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/python-versions.md#free-threaded-python/0", 3),
            ("docs/concepts/python-versions.md#requesting-a-version/0", 2),
        ),
        "Gives the specific request syntax `3.13t` or `3.13+freethreaded`, and states that on 3.13 "
        "it must be explicit while 3.14+ interpreters may be used without it. The request-format "
        "list is where those two spellings are enumerated as general formats.",
    ),
    (
        "u-0216",
        "which python implementations can uv work with",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/python-versions.md#python-implementation-support/0", 3),
            ("docs/concepts/python-versions.md#managed-python-distributions/0", 2),
        ),
        "States the supported set — CPython, PyPy, Pyodide and GraalPy — with the long and short "
        "request names and the note that unsupported implementations fail discovery. The "
        "distributions section is a narrower claim (which ones uv can download) so it only frames "
        "the answer.",
    ),
    (
        "u-0217",
        "how do i get uv to explain why it is doing something",
        (EvalSlice.FACT,),
        (("docs/getting-started/help.md#displaying-verbose-output/0", 3),),
        "Answers with the mechanism: the `-v` flag, repeatable as `-vv` for more verbosity, and "
        "states that the verbose output often includes the reason uv is behaving a certain way.",
    ),
    (
        "u-0218",
        "how do i make renovate update dependencies declared in a pep 723 script header",
        (EvalSlice.FACT,),
        (("docs/guides/integration/renovate.md#inline-script-metadata/0", 3),),
        "Gives the concrete answer: Renovate cannot detect which Python files carry inline script "
        "metadata, so their paths must be listed under `pep723.managerFilePatterns`. It also warns "
        "that the script's lock file is not yet updated automatically.",
    ),
    (
        "u-0219",
        "how do i import requirements-dev into a dependency group",
        (EvalSlice.FACT,),
        (
            (
                "docs/guides/migration/pip-to-project.md#migrating-to-a-uv-project/importing-requirements-files/importing-development-dependency-files/0",
                3,
            ),
            (
                "docs/guides/migration/pip-to-project.md#understanding-pip-workflows/development-dependencies/0",
                2,
            ),
        ),
        "Gives the command `uv add --dev -r requirements-dev.in -c requirements-dev.txt`, the "
        "`sed` workaround for stripping `-r` lines so base requirements do not land in `dev`, and "
        "`--group docs` for other group names. The pip-workflow section is where those `-dev` "
        "files were constructed.",
    ),
    (
        "u-0220",
        "how do i add environment markers to requirements files compiled per platform",
        (EvalSlice.FACT,),
        (
            (
                "docs/guides/migration/pip-to-project.md#migrating-to-a-uv-project/importing-requirements-files/importing-platform-specific-constraints/0",
                3,
            ),
        ),
        "Gives the exact recipe: platform-specific `requirements.txt` files conflict as "
        "constraints because they carry no markers, so re-run `uv pip compile ... --python- "
        "platform windows --no-strip-markers` (varying `--python-platform` and `-o`) before "
        "passing each file with `-c`.",
    ),
    (
        "u-0221",
        "which files does the uv build backend skip by default when packaging",
        (EvalSlice.FACT,),
        (("docs/concepts/build-backend.md#file-inclusion-and-exclusion/0", 3),),
        "States the default exclusions outright — `__pycache__`, `*.pyc` and `*.pyo` — and the "
        "ordering rule that exclusions are applied after inclusions, so they always win.",
    ),
    (
        "u-0222",
        "where does uv create the virtual environment for my project",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/layout.md#the-project-environment/0", 3),),
        "Answers with the specific location: a `.venv` directory next to the `pyproject.toml`, "
        "kept inside the project so editors can find it, and excluded from git by an internal "
        "`.gitignore`.",
    ),
    (
        "u-0223",
        "how are dependency groups different from optional dependencies",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/dependencies.md#development-dependencies/0", 3),
            ("docs/concepts/projects/dependencies.md#optional-dependencies/0", 2),
        ),
        "The development-dependencies section is written as the contrast: unlike optional "
        "dependencies, development dependencies are local-only, excluded from published "
        "requirements, and therefore live outside the [project] table in [dependency-groups]. The "
        "optional-dependencies section supplies the other half — extras exist to be published and "
        "requested with package[extra].",
    ),
    (
        "u-0224",
        "what is the difference between build-system.requires and project.dependencies",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/dependencies.md#build-dependencies/0", 3),
            ("docs/concepts/projects/dependencies.md#project-dependencies/0", 2),
        ),
        "The build-dependencies section defines build requirements as needed to build but not to "
        "run the project, placed in [build-system] requires per PEP 518. The project-dependencies "
        "section states the other side: project.dependencies are what is used when uploading to "
        "PyPI or building a wheel.",
    ),
    (
        "u-0225",
        "how do i install torch from a different index on macos than on linux",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/dependencies.md#dependency-sources/multiple-sources/0", 3),
            (
                "docs/concepts/projects/dependencies.md#dependency-sources/platform-specific-sources/0",
                2,
            ),
        ),
        "The multiple-sources section carries the exact case: a list of sources disambiguated by "
        "markers, including the torch example selecting torch-cpu on Darwin and torch-gpu on Linux "
        "with both indexes marked explicit. The platform-specific-sources section frames the "
        "single-source version of the same marker mechanism.",
    ),
    (
        "u-0226",
        "which existing tools does uv's pip interface stand in for",
        (EvalSlice.RELATIONSHIP,),
        (("docs/getting-started/features.md#the-pip-interface/0", 3),),
        "This section maps uv's commands onto the tools they replace: uv venv for venv and "
        "virtualenv, uv pip for pip and pipdeptree, and uv pip compile / uv pip sync for pip- "
        "tools.",
    ),
    (
        "u-0227",
        "how do i make bazel fetches reuse the credentials i logged into uv with",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/bazel.md#authentication/0", 3),
            ("docs/concepts/authentication/http.md#the-uv-credentials-store/0", 2),
        ),
        "The Bazel section walks the whole bridge between the two tools: uv auth login for the "
        "host, a .bazelrc --credential_helper entry per host, the uv auth helper wrapper script "
        "and chmod +x. The uv credentials store section frames the other side by stating that uv "
        "auth commands read and write that store.",
    ),
    (
        "u-0228",
        "how does uv.lock differ from pyproject.toml",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/projects.md#project-structure/uv-lock/0", 3),
            ("docs/guides/projects.md#project-structure/pyproject-toml/0", 2),
        ),
        "The uv.lock section draws the contrast explicitly — pyproject.toml specifies the "
        "project's broad requirements while the lockfile records the exact resolved versions "
        "installed in the environment. The pyproject.toml section supplies the other side: project "
        "metadata, dependencies and [tool.uv] configuration that you edit.",
    ),
    (
        "u-0229",
        "do i still need to run uv sync if i use uv run",
        (EvalSlice.RELATIONSHIP,),
        (("docs/guides/projects.md#running-commands/0", 3),),
        "This section relates the two commands: uv run re-verifies the lockfile against "
        "pyproject.toml and the environment against the lockfile before every invocation, so "
        "syncing by hand is unnecessary; uv sync plus activating .venv is presented as the manual "
        "alternative for running commands without uv run.",
    ),
    (
        "u-0230",
        "i have a password in the index url and also a netrc entry, which one does uv use",
        (EvalSlice.RELATIONSHIP,),
        (("docs/concepts/authentication/http.md#/0", 3),),
        "The page introduction is the only passage that ranks the credential sources against each "
        "other: URL, then netrc, then the uv credentials store, then a keyring provider, in order "
        "of precedence.",
    ),
    (
        "u-0231",
        "how must my project's requires-python relate to that of its dependencies",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/resolution.md#universal-resolution/0", 3),
            ("docs/reference/internals/resolver.md#requires-python/0", 2),
        ),
        "Universal resolution states the rule as a subset relation and shows the >=3.8 failure it "
        "causes; the internals page restates it as a minimum-version requirement on every "
        "dependency.",
    ),
    (
        "u-0232",
        "what is the difference between environments and required-environments",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/resolution.md#required-environments/0", 3),
            ("docs/concepts/resolution.md#limited-resolution-environments/0", 2),
        ),
        "Required environments carries the comparison itself - environments limits what uv solves "
        "for, required-environments expands what it must support - with the darwin example of "
        "each. The other section documents the limiting half.",
    ),
    (
        "u-0233",
        "how is uv pip sync different from uv pip install",
        (EvalSlice.RELATIONSHIP,),
        (("docs/pip/compile.md#syncing-an-environment/0", 3),),
        "States that uv pip install leaves already-installed packages in place, so the environment "
        "can drift from the lockfile, and that uv pip sync is what makes it match exactly.",
    ),
    (
        "u-0234",
        "how do wheel tags relate to environment markers when uv resolves",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/reference/internals/resolver.md#wheel-tags/0", 3),
            ("docs/reference/internals/resolver.md#marker-and-wheel-tag-filtering/0", 2),
        ),
        "Wheel tags opens on exactly this: uv's resolution is universal over markers but that does "
        "not extend to wheel tags, which is why a torch install can still fail on an uncommon "
        "platform. The filtering section covers the partial mapping uv does maintain.",
    ),
    (
        "u-0235",
        "how does the index name in pyproject.toml determine the environment variable names",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/jfrog.md#authenticate-with-jwt-token/0", 3),
            ("docs/guides/integration/jfrog.md#/0", 2),
        ),
        "The note in this section is what ties them together: PRIVATE_REGISTRY in "
        "UV_INDEX_PRIVATE_REGISTRY_* stands for the index name. The page opening supplies the "
        'matching name = "private-registry" declaration.',
    ),
    (
        "u-0236",
        "how do I declare a conflict between extras of two different workspace members",
        (EvalSlice.RELATIONSHIP,),
        (("docs/concepts/resolution.md#conflicting-dependencies/", 3),),
        "Section-scoped deliberately: the workspace answer builds up across the section, from the "
        "package key paired with extra, through the member-dependencies-versus-extra case, to the "
        "plain member-versus-member case that falls in a later chunk.",
    ),
    (
        "u-0237",
        "how does platform-specific resolution differ from universal resolution",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/resolution.md#platform-specific-resolution/0", 3),
            ("docs/concepts/resolution.md#universal-resolution/0", 2),
        ),
        "The platform-specific section draws the contrast, including that --python-version is an "
        "exact version there rather than a lower bound, and that the project interface offers no "
        "platform-specific mode at all.",
    ),
    (
        "u-0238",
        "if a dependency is both overridden and excluded in the same scope, which one wins",
        (EvalSlice.RELATIONSHIP,),
        (("docs/concepts/resolution.md#dependency-exclusions/0", 3),),
        "Ends with the ruling - in a matching scope the exclusion takes precedence - right after "
        "showing the combined override-plus-exclude idiom for swapping one dependency for another.",
    ),
    (
        "u-0239",
        "how are project.gui-scripts different from project.scripts",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/config.md#entry-points/graphical-user-interfaces/0", 3),
            ("docs/concepts/projects/config.md#entry-points/command-line-interfaces/0", 2),
        ),
        "The GUI subsection is the passage that contrasts the two: it states that they differ only "
        "on Windows, where GUI scripts are wrapped by a GUI executable so they start without a "
        "console, and behave identically elsewhere.",
    ),
    (
        "u-0240",
        "in a notebook, what is the difference between !uv add and !uv pip install",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/guides/integration/jupyter.md#using-jupyter-within-a-project/installing-packages-without-a-kernel/0",
                3,
            ),
            (
                "docs/guides/integration/jupyter.md#using-jupyter-within-a-project/creating-a-kernel/0",
                2,
            ),
        ),
        "This subsection discusses both: without a kernel, !uv add still modifies the project "
        "environment, while !uv pip install lands in Jupyter's own environment and may not survive "
        "the next server start. The kernel subsection contrasts the two under a kernel, where both "
        "reach the project.",
    ),
    (
        "u-0241",
        "is the uv.lock schema version bumped like the cache version",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/reference/policies/versioning.md#lockfile-versioning/0", 3),
            ("docs/reference/policies/versioning.md#cache-versioning/0", 2),
        ),
        "Lockfile versioning states that the uv.lock schema version is public API and only "
        "increments in a minor release; cache versioning states the opposite for cache versions, "
        "which are internal and may change in a minor or patch release. The pair is the answer.",
    ),
    (
        "u-0242",
        "should i export pylock.toml or requirements.txt",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/export.md#overview-of-export-formats/0", 3),
            ("docs/concepts/projects/export.md#requirements-txt-format/0", 2),
            ("docs/concepts/projects/export.md#pylock-toml-format/0", 2),
        ),
        "The overview is the passage that places the two side by side - requirements.txt as the "
        "traditional pip-compatible format, pylock.toml as the PEP 751 standard - which is what a "
        "reader choosing between them needs. The two format sections each add what their own "
        "format is good for.",
    ),
    (
        "u-0243",
        "does uv pip need a virtualenv in ci when the project interface doesn't",
        (EvalSlice.RELATIONSHIP,),
        (("docs/guides/integration/gitlab.md#using-uv-pip/0", 3),),
        "This section answers exactly in those terms: when using the uv pip interface instead of "
        "the uv project interface, uv requires a virtual environment by default, and --system or "
        "UV_SYSTEM_PYTHON is what lifts that requirement.",
    ),
    (
        "u-0244",
        "what's the difference between a uv application project and a library project",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/init.md#/0", 3),
            ("docs/concepts/projects/init.md#libraries/0", 2),
            ("docs/concepts/projects/init.md#applications/0", 2),
        ),
        "The preamble is the passage that names both templates, says application is the default "
        "and --lib selects the other, and states what they share. Each of the two sections then "
        "frames its own half - applications for servers, scripts and CLIs; libraries for code "
        "others consume and always packaged.",
    ),
    (
        "u-0245",
        "how does uv init --no-package change what gets created",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/init.md#creating-a-project-without-a-build-system/0", 3),
            ("docs/concepts/projects/init.md#applications/0", 2),
        ),
        "The no-build-system section spells out the difference against the default: a top-level "
        "main.py instead of a src module, a pyproject.toml with no [build-system] table, and a "
        "project that is not a package and is not installed into the environment. The applications "
        "section supplies the default layout being departed from.",
    ),
    (
        "u-0246",
        "how is required-environments different from environments",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/config.md#required-environments/0", 3),
            ("docs/concepts/projects/config.md#limited-resolution-environments/0", 2),
        ),
        "Required environments is the section that distinguishes them: it marks a platform as one "
        "the project must support and explains this only matters for packages that publish no "
        "source distribution. The other section defines environments as the setting that narrows "
        "the solved platform set instead.",
    ),
    (
        "u-0247",
        "do settings under tool.uv.pip affect uv sync and uv lock too",
        (EvalSlice.RELATIONSHIP,),
        (("docs/concepts/configuration-files.md#configuring-the-pip-interface/0", 3),),
        "This section is about exactly that relation: [tool.uv.pip] applies only inside the uv pip "
        "namespace, while many top-level settings do reach uv pip unless a uv.pip value overrides "
        "them. The index-url example spells out that it would not affect uv sync, uv lock or uv "
        "run.",
    ),
    (
        "u-0248",
        "should i use --refresh or --no-cache",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/cache.md#cache-directory/0", 3),
            ("docs/concepts/cache.md#dependency-caching/0", 2),
        ),
        "The note in the cache-directory section states the comparison outright: --no-cache still "
        "uses a temporary cache for the single invocation, and --refresh should be preferred in "
        "most cases because it updates the cache for later operations without reading from it. The "
        "dependency-caching section supplies the other half by documenting what --refresh actually "
        "revalidates.",
    ),
    (
        "u-0249",
        "is --index-url the same thing as --default-index",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/indexes.md#index-url-and-extra-index-url/0", 3),
            ("docs/concepts/indexes.md#defining-an-index/0", 2),
        ),
        "This section maps the two onto each other explicitly: the pip-style flags behave as "
        "unnamed [[tool.uv.index]] entries, --index-url maps to --default-index and --extra-index- "
        "url to --index, under the same priority rules. Defining an index is a 2 for documenting "
        "--default-index and the default = true entry it corresponds to.",
    ),
    (
        "u-0250",
        "how is a flat index different from a normal pypi style index",
        (EvalSlice.RELATIONSHIP,),
        (("docs/concepts/indexes.md#flat-indexes/0", 3),),
        "This section draws the contrast: ordinary entries are assumed to be PEP 503 Simple "
        "Repository API registries, while a flat index is a local directory or HTML page listing "
        'wheels and sdists, declared with format = "flat" and equivalent to pip\'s --find-links. '
        "It also states that flat indexes support the same features, including pinning.",
    ),
    (
        "u-0251",
        "what is the difference between --locked and --frozen",
        (EvalSlice.RELATIONSHIP,),
        (("docs/concepts/projects/sync.md#automatic-lock-and-sync/0", 3),),
        "Both flags are defined in the same passage and contrasted: --locked errors when the "
        "lockfile is out of date instead of updating it, while --frozen uses the lockfile without "
        "checking it at all. --no-sync is given alongside for the environment-side equivalent.",
    ),
    (
        "u-0252",
        "how does --only-group differ from --only-dev",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/concepts/projects/sync.md#syncing-the-environment/syncing-development-dependencies/0",
                3,
            ),
        ),
        "The passage compares them directly: --only-group has the same semantics as --only-dev in "
        "excluding the project, but additionally excludes default groups. It also states that "
        "exclusions beat inclusions when both --group and --no-group name the same group.",
    ),
    (
        "u-0253",
        "why use --frozen instead of --locked for the first sync in a workspace",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/guides/integration/docker.md#optimizations/intermediate-layers/intermediate-layers-in-workspaces/0",
                3,
            ),
            ("docs/concepts/projects/sync.md#automatic-lock-and-sync/0", 2),
        ),
        "The workspaces subsection gives the reason the two flags are not interchangeable here: uv "
        "cannot assert the lockfile is current without every member's pyproject.toml, which are "
        "not yet copied, so the first sync skips the check with --frozen and the later one "
        "validates with --locked. The sync concept page is a 2 for defining both flags.",
    ),
    (
        "u-0254",
        "what is the difference between running a notebook with uv run marimo edit and uv run "
        "--with marimo",
        (EvalSlice.RELATIONSHIP,),
        (("docs/guides/integration/marimo.md#using-marimo-within-a-project/0", 3),),
        "The section contrasts the two cases in the same passage: with marimo as a project "
        "dependency, uv run marimo edit gives the notebook the project environment; with --with "
        "marimo you can still import project modules, but packages installed from marimo's UI are "
        "not added to the project and may vanish on the next run.",
    ),
    (
        "u-0255",
        "how is uvx different from uv run --with",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/tools.md#relationship-to-uv-run/0", 3),
            ("docs/concepts/tools.md#the-uv-tool-interface/0", 2),
        ),
        "This section states the near-equivalence explicitly and then lists the differences: "
        "--with is inferred from the command name, --no-project is unnecessary because tools are "
        "always isolated, the temporary environment is cached in a dedicated place, and uv tool "
        "run picks up an installed tool where uv run does not.",
    ),
    (
        "u-0256",
        "what is the difference between --with and --with-executables-from",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/tools.md#installing-executables-from-additional-packages/0", 3),
            ("docs/concepts/tools.md#including-additional-dependencies/0", 2),
        ),
        "The --with-executables-from section contrasts the two directly: --with adds packages as "
        "dependencies only, while --with-executables-from also installs their executables into the "
        "tool environment. The --with section documents the option being contrasted against.",
    ),
    (
        "u-0257",
        "does a tool environment respect my project's .python-version file",
        (EvalSlice.RELATIONSHIP,),
        (("docs/concepts/tools.md#python-versions/0", 3),),
        "Answers the interaction directly: tool environments use the same discovery logic as other "
        "uv virtual environments but deliberately ignore non-global requests such as .python- "
        "version files and requires-python, leaving --python as the way to pin one.",
    ),
    (
        "u-0258",
        "how does a fastapi app get adapted to an aws lambda handler",
        (EvalSlice.RELATIONSHIP,),
        (("docs/guides/integration/aws-lambda.md#getting-started/0", 3),),
        "The starting example is where the two are joined: Mangum is described as the library that "
        "adapts ASGI applications to AWS Lambda and API Gateway, and the sample main.py wraps the "
        "FastAPI app as handler = Mangum(app), which is the entrypoint the later deployment steps "
        "reference.",
    ),
    (
        "u-0259",
        "what changes in the deployment package when the project is a uv workspace",
        (EvalSlice.RELATIONSHIP,),
        (("docs/guides/integration/aws-lambda.md#deploying-a-docker-image/workspace-support/", 3),),
        "Section-scoped deliberately: the requirement is stated at the top (local workspace "
        "dependencies must also be included in the deployment package) but the actual answer — a "
        "second RUN that omits --no-emit-workspace and bind-mounts the library so it is copied "
        "into the task root — only appears in the revised Dockerfile at the end.",
    ),
    (
        "u-0260",
        "when should i deploy a lambda as a zip instead of a container image",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/aws-lambda.md#deploying-a-zip-archive/0", 3),
            ("docs/guides/integration/aws-lambda.md#deploying-a-docker-image/0", 2),
        ),
        "The zip section opens by comparing the two: for simple applications zip archives are more "
        "straightforward and efficient than Docker images, at the cost of a 250 MB ceiling. The "
        "Docker section states the case for the image path it is being compared against.",
    ),
    (
        "u-0261",
        "how does dependabot's cooldown setting relate to exclude-newer",
        (EvalSlice.RELATIONSHIP,),
        (("docs/guides/integration/dependabot.md#dependency-cooldown/0", 3),),
        "This section exists to connect the two: if exclude-newer is set, Dependabot's cooldown "
        "should be set to match, or Dependabot will open pull requests whose dependencies uv then "
        "refuses to lock — with the worked example of exclude-newer of 1 week against default- "
        "days: 7.",
    ),
    (
        "u-0262",
        "should i request a script's dependencies with --with or declare them in the script",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/scripts.md#running-a-script-with-dependencies/0", 3),
            ("docs/guides/scripts.md#declaring-script-dependencies/0", 2),
        ),
        "This section weighs the two approaches in the same breath — a project or inline metadata "
        "is generally recommended, but per-invocation --with is supported — and documents --with "
        "with version constraints. The declaring section documents the inline alternative being "
        "compared.",
    ),
    (
        "u-0263",
        "how do i get cuda builds on linux but cpu-only wheels on macos and windows",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/guides/integration/pytorch.md#configuring-accelerators-with-environment-markers/",
                3,
            ),
            ("docs/guides/integration/pytorch.md#using-a-pytorch-index/", 2),
        ),
        "The environment-markers section gives the complete pyproject.toml pairing pytorch-cpu "
        "under `sys_platform != 'linux'` with pytorch-cu130 under `sys_platform == 'linux'`. The "
        "index section supplies the per-accelerator index definitions that configuration depends "
        "on.",
    ),
    (
        "u-0264",
        "how do i let an extra decide whether torch comes from the cpu or the cuda index",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/guides/integration/pytorch.md#configuring-accelerators-with-optional-dependencies/0",
                3,
            ),
        ),
        "Shows the cpu and cu130 optional-dependency groups, the `tool.uv.conflicts` entry that "
        "makes them mutually exclusive, and sources keyed by `extra`, which is exactly the extra- "
        "to-index link asked about.",
    ),
    (
        "u-0265",
        "how do i translate pytorch's recommended pip3 install command into uv",
        (EvalSlice.RELATIONSHIP,),
        (("docs/guides/integration/pytorch.md#the-uv-pip-interface/0", 3),),
        "Sets the pip3 install --index-url command beside its uv form and states the rule "
        "connecting them: replace pip3 with uv pip to get the same workflow.",
    ),
    (
        "u-0266",
        "how is uv pip install --system different from passing --python $(which python)",
        (EvalSlice.RELATIONSHIP,),
        (("docs/pip/environments.md#using-arbitrary-python-environments/0", 3),),
        "States the equivalence and the exception in one place: --system is roughly the same as "
        "--python $(which python), except executables linked to virtual environments are skipped, "
        "and --system makes uv ignore interpreters that are in virtual environments.",
    ),
    (
        "u-0267",
        "does --group read the pyproject.toml i passed to -r",
        (EvalSlice.RELATIONSHIP,),
        (("docs/pip/packages.md#installing-packages-from-files/0", 3),),
        "The note at the end answers exactly this: --group flags do not apply to sources given "
        "with -r or -e, so `-r some/path/pyproject.toml --group foo` sources foo from "
        "./pyproject.toml instead.",
    ),
    (
        "u-0268",
        "how does the node for mypackage[myextra] relate to the node for mypackage",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/reference/internals/metadata.md#/0", 3),
            ("docs/reference/internals/metadata.md#schema/", 2),
        ),
        "States that an extra node always depends on the package node, while a group node does "
        "not, because groups are lists of things you want while working on the package. The "
        "annotated schema repeats the distinction in the commentary on `resolution`.",
    ),
    (
        "u-0269",
        "what does tier 2 support mean compared to tier 1",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/reference/policies/python.md#python-versions/0", 3),
            ("docs/reference/policies/python.md#python-implementations/0", 2),
        ),
        "The versions section defines both terms in contrast — Tier 1 is 'guaranteed to work' and "
        "continuously tested, Tier 2 is 'expected to work' and, for versions, past end-of-life. "
        "The implementations section restates the pair and adds Tier 3, 'should work'.",
    ),
    (
        "u-0270",
        "who builds the python interpreters uv installs for pypy versus cpython",
        (EvalSlice.RELATIONSHIP,),
        (("docs/reference/policies/python.md#python-implementations/0", 3),),
        "Ties the tier to the build provenance: managed CPython builds are maintained by Astral, "
        "while managed builds for the Tier 2 implementations (PyPy, GraalPy, Pyodide) are not.",
    ),
    (
        "u-0271",
        "does uv build the wheel from the source distribution or straight from my project",
        (EvalSlice.RELATIONSHIP,),
        (("docs/concepts/projects/build.md#using-uv-build/0", 3),),
        "The section states uv build first builds a source distribution and then builds the wheel "
        "from that sdist, and gives --sdist --wheel as the way to build both from source.",
    ),
    (
        "u-0272",
        "what do the members of a workspace have in common",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/workspaces.md#/0", 3),
            ("docs/concepts/projects/workspaces.md#workspace-sources/0", 2),
        ),
        "The intro states the relation directly: each package keeps its own pyproject.toml but the "
        "workspace shares one lockfile, and uv lock operates on the whole workspace. The sources "
        "section adds that root-level tool.uv.sources apply to all members.",
    ),
    (
        "u-0273",
        "if a member and the workspace root both declare a source for the same dependency which "
        "one applies",
        (EvalSlice.RELATIONSHIP,),
        (("docs/concepts/projects/workspaces.md#workspace-sources/0", 3),),
        "The section states root definitions apply to all members unless overridden, and its note "
        "adds that a member's tool.uv.sources ignores the root entry for that dependency even when "
        "the member's source is limited by a non-matching marker.",
    ),
    (
        "u-0274",
        "should I set up python with actions/setup-python or uv python install",
        (EvalSlice.RELATIONSHIP,),
        (("docs/guides/integration/github.md#setting-up-python/0", 3),),
        "The section puts the two side by side: uv python install respects the project's pin, "
        "while setup-python can be faster because GitHub caches versions alongside the runner, and "
        "shows python-version-file pointing at .python-version or pyproject.toml.",
    ),
    (
        "u-0275",
        "should I run pytest with uvx or with uv run",
        (EvalSlice.RELATIONSHIP,),
        (("docs/guides/tools.md#running-tools/0", 3),),
        "The section's note compares them for exactly this case: tools that need your project "
        "installed, such as pytest or mypy, want uv run, because uvx runs in an environment "
        "isolated from the project; a flat-layout project is the exception.",
    ),
    (
        "u-0276",
        "why does uv install into .venv when pip installs into the system python",
        (EvalSlice.RELATIONSHIP,),
        (("docs/pip/compatibility.md#virtual-environments-by-default/0", 3),),
        "The section contrasts the two defaults: uv always targets the active or discovered .venv, "
        "pip falls back to a global environment, and uv inverts the default so installing into the "
        "system Python requires --system or --python.",
    ),
    (
        "u-0277",
        "why do package names look different in uv pip list than in pip list",
        (EvalSlice.RELATIONSHIP,),
        (("docs/pip/compatibility.md#package-name-normalization/0", 3),),
        "The section explains the difference and shows it: uv normalizes names to their PEP 503 "
        "forms in all output, while pip preserves the verbatim name from the registry, with a "
        "side-by-side diff of the two listings.",
    ),
    (
        "u-0278",
        "can i use pylock.toml in place of uv.lock",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/layout.md#the-lockfile/relationship-to-pylock-toml/0", 3),
            ("docs/concepts/projects/layout.md#the-lockfile/0", 2),
        ),
        "This subsection is the only place that relates the two formats: some of uv's "
        "functionality cannot be expressed in `pylock.toml`, so the project interface keeps "
        "`uv.lock`, while `pylock.toml` is supported as an export target and in the `uv pip` CLI. "
        "The parent section says what `uv.lock` itself is.",
    ),
    (
        "u-0279",
        "what is the difference between a managed and a system python in uv",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/python-versions.md#managed-and-system-python-installations/0", 3),
            (
                "docs/concepts/python-versions.md#requiring-or-disabling-managed-python-versions/0",
                2,
            ),
        ),
        "Defines the distinction directly — versions uv installed are managed, everything else is "
        "system — and closes the common misreading by saying a pyenv-managed interpreter still "
        "counts as system. The second anchor shows the distinction in use via `--managed-python` "
        "and `--no-managed-python`.",
    ),
    (
        "u-0280",
        "what is the difference between --help and uv help",
        (EvalSlice.RELATIONSHIP,),
        (("docs/getting-started/help.md#help-menus/0", 3),),
        "Contrasts the two directly: `--help` prints a condensed menu while `uv help` prints the "
        "long one, shows both the bare and per-command forms, and notes the long menu is paged "
        "through `less` or `more` and exited with `q`.",
    ),
    (
        "u-0281",
        "what renovate setting should i pair with exclude-newer",
        (EvalSlice.RELATIONSHIP,),
        (("docs/guides/integration/renovate.md#dependency-cooldown/0", 3),),
        "This section exists to relate the two: it recommends setting Renovate's "
        "`minimumReleaseAge` to match uv's `exclude-newer`, otherwise Renovate opens pull requests "
        "uv cannot lock, and shows a `1 week` setting matching a `1 week` `exclude-newer`.",
    ),
    (
        "u-0282",
        "how do i keep my existing pinned versions when importing requirements into uv",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/guides/migration/pip-to-project.md#migrating-to-a-uv-project/importing-requirements-files/0",
                3,
            ),
        ),
        "Names the trap and the fix: importing `requirements.in` with `uv add -r` lets uv resolve "
        "fresh versions, so the locked `requirements.txt` must be passed as constraints with `-c` "
        "for the existing versions to be retained in `uv.lock`.",
    ),
    (
        "u-0283",
        "is the build backend inside the uv executable the same as the uv_build package",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/build-backend.md#bundled-build-backend/0", 3),
            ("docs/concepts/build-backend.md#using-the-uv-build-backend/0", 2),
        ),
        "This is the only passage that relates the two: the `uv` executable carries a copy of the "
        "backend and uses it when its version satisfies the `uv_build` requirement, otherwise it "
        "falls back to the package; other frontends such as `python -m build` always use the "
        "package. The second anchor is where that `uv_build` version requirement is declared.",
    ),
    (
        "u-0284",
        "what does uv.lock record that pyproject.toml does not",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/layout.md#the-lockfile/0", 3),
            ("docs/concepts/projects/layout.md#the-pyproject-toml/0", 2),
        ),
        "The lockfile section draws the contrast explicitly — the `pyproject.toml` specifies broad "
        "requirements, the lockfile the exact resolved versions installed in the environment — and "
        "adds that `uv.lock` is uv-specific and not to be hand-edited. The `pyproject.toml` "
        "section supplies the other half: what that file is for.",
    ),
    (
        "u-0285",
        "uv pip compile --group",
        (EvalSlice.SYMBOL,),
        (("docs/pip/compile.md#locking-requirements/0", 3),),
        "This section introduces the --group flag, its path:group syntax, the --project variant, "
        "and the note that --group always sources from ./pyproject.toml rather than a passed file.",
    ),
    (
        "u-0286",
        "uv pip compile --upgrade-package",
        (EvalSlice.SYMBOL,),
        (("docs/pip/compile.md#upgrading-requirements/0", 3),),
        "The upgrading section is where --upgrade-package is introduced, alongside the pinning "
        "behaviour it exists to defeat and the broader --upgrade flag.",
    ),
    (
        "u-0287",
        "uv pip compile --constraint",
        (EvalSlice.SYMBOL,),
        (("docs/pip/compile.md#adding-constraints/0", 3),),
        "Documents the flag: what a constraints file is, the --constraint invocation, and that uv "
        "also appends constraint-dependencies from the workspace root.",
    ),
    (
        "u-0288",
        "uv pip compile --override",
        (EvalSlice.SYMBOL,),
        (("docs/pip/compile.md#overriding-dependency-versions/0", 3),),
        "Defines overrides files and gives the --override invocation with the worked a/b/c upper- "
        "bound example; no other section in this page documents that flag.",
    ),
    (
        "u-0289",
        "gh auth setup-git",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/authentication/git.md#git-credential-helpers/0", 3),),
        "The credential-helpers section is the only place that says when this command is needed: "
        "after gh auth login --with-token, since the non-interactive login does not configure the "
        "helper itself.",
    ),
    (
        "u-0290",
        "uv add --raw",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/authentication/git.md#persistence-of-credentials/0", 3),),
        "States what --raw does on uv add - it forces uv to persist Git credentials - together "
        "with the recommendation to configure a credential helper instead.",
    ),
    (
        "u-0291",
        "uv run fastapi dev",
        (EvalSlice.SYMBOL,),
        (("docs/guides/integration/fastapi.md#migrating-an-existing-fastapi-project/0", 3),),
        "The migration walkthrough gives this invocation and states its effect: uv resolves and "
        "locks dependencies, creates the virtual environment, then runs the command in it.",
    ),
    (
        "u-0292",
        "uv init --build-backend maturin",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/projects/init.md#projects-with-extension-modules/0", 3),),
        "This section documents --build-backend for extension modules: it names maturin and "
        "scikit-build-core as the supported backends, shows the exact invocation, and notes that "
        "--build-backend implies --package.",
    ),
    (
        "u-0293",
        "uv export --format cyclonedx1.5",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/projects/export.md#cyclonedx-sbom-format/basic-usage/0", 3),
            ("docs/concepts/projects/export.md#cyclonedx-sbom-format/0", 2),
        ),
        "Basic usage gives the exact command and says it emits a JSON-encoded CycloneDX v1.5 "
        "document of the project and its dependencies. The parent section states what the format "
        "is for and that support is in preview.",
    ),
    (
        "u-0294",
        "uv generate-shell-completion",
        (EvalSlice.SYMBOL,),
        (("docs/getting-started/installation.md#shell-autocompletion/0", 3),),
        "The shell autocompletion section is where this subcommand appears and is documented, with "
        "the per-shell eval lines for bash, zsh, fish, elvish and PowerShell.",
    ),
    (
        "u-0295",
        "uv tool run jupyter lab",
        (EvalSlice.SYMBOL,),
        (("docs/guides/integration/jupyter.md#using-jupyter-as-a-standalone-tool/0", 3),),
        "This short section is the one that documents the command, as the way to get an ad hoc "
        "notebook server running in an isolated environment rather than against a project.",
    ),
    (
        "u-0296",
        "uv pip install --system",
        (EvalSlice.SYMBOL,),
        (("docs/guides/integration/docker.md#using-the-pip-interface/installing-a-package/0", 3),),
        "This section documents that invocation: --system installs into the system Python "
        "environment, which is safe in a container, with UV_SYSTEM_PYTHON as the persistent form "
        "and the note that --system must be dropped once a virtual environment is used instead.",
    ),
    (
        "u-0297",
        "uvx marimo edit",
        (EvalSlice.SYMBOL,),
        (
            ("docs/guides/integration/marimo.md#using-marimo-as-a-standalone-tool/0", 3),
            ("docs/guides/integration/marimo.md#/0", 1),
        ),
        "The standalone-tool section documents this invocation: it starts a marimo server in an "
        "isolated environment for ad-hoc use, with or without a notebook path. The page preamble "
        "is only a 1 — it names standalone use in a list of four modes without describing the "
        "command.",
    ),
    (
        "u-0298",
        "uv python dir --bin",
        (EvalSlice.SYMBOL,),
        (("docs/reference/storage.md#types-of-data/python-executables/0", 3),),
        "The Python executables entry documents this exact invocation: it shows the directory "
        "holding the installed Python executables (as opposed to plain uv python dir, which shows "
        "the installation directory), with UV_PYTHON_BIN_DIR to override it.",
    ),
    (
        "u-0299",
        "deactivate",
        (EvalSlice.SYMBOL,),
        (("docs/pip/environments.md#deactivating-an-environment/0", 3),),
        "The section that documents the `deactivate` command as the way to exit a virtual "
        "environment.",
    ),
    (
        "u-0300",
        "uv-lock hook",
        (EvalSlice.SYMBOL,),
        (("docs/guides/integration/pre-commit.md#/0", 3),),
        "Gives the .pre-commit-config.yaml entry with `id: uv-lock` and says what it is for: "
        "keeping uv.lock up to date when pyproject.toml changes.",
    ),
    (
        "u-0301",
        "uv publish --index",
        (EvalSlice.SYMBOL,),
        (("docs/guides/integration/google.md#publishing-packages/0", 3),),
        "This section shows `uv publish --index private-registry` and the publish-url entry that "
        "makes a named index publishable, which is what the --index form refers to.",
    ),
    (
        "u-0302",
        "uv self version",
        (EvalSlice.SYMBOL,),
        (("docs/getting-started/help.md#viewing-the-version/0", 3),),
        "Documents the command and its neighbours: `uv --version` prints the same output, `uv -V` "
        "omits the build commit and date, and before uv 0.7.0 the command was spelled `uv "
        "version`.",
    ),
    (
        "u-0303",
        "uv pip list --format json",
        (EvalSlice.SYMBOL,),
        (
            ("docs/pip/inspection.md#listing-installed-packages/0", 3),
            ("docs/getting-started/features.md#the-pip-interface/0", 1),
        ),
        "The listing section gives the exact invocation `uv pip list --format json` as the way to "
        "get the installed packages in JSON; the features page only names `uv pip list` in a "
        "bullet.",
    ),
    (
        "u-0304",
        "uv run --no-sync",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/projects/sync.md#automatic-lock-and-sync/0", 3),),
        "The automatic lock-and-sync section is where --no-sync is introduced: it shows `uv run "
        "--no-sync ...` and states that it runs the command without checking whether the "
        "environment is up to date.",
    ),
    (
        "u-0305",
        "uv run --exact",
        (EvalSlice.SYMBOL,),
        (
            (
                "docs/concepts/projects/sync.md#syncing-the-environment/handling-of-extraneous-packages/0",
                3,
            ),
        ),
        "This section explains that `uv run` syncs inexactly by default and gives `uv run --exact` "
        "as the way to make it remove packages that are not in the lockfile.",
    ),
    (
        "u-0306",
        "uv sync --no-group",
        (EvalSlice.SYMBOL,),
        (
            (
                "docs/concepts/projects/sync.md#syncing-the-environment/syncing-development-dependencies/0",
                3,
            ),
        ),
        "The development dependencies section lists --no-group among the group options and shows "
        "`uv sync --no-group foo --group foo`, stating that the exclusion wins.",
    ),
    (
        "u-0307",
        "uv sync --extra",
        (EvalSlice.SYMBOL,),
        (
            (
                "docs/concepts/projects/sync.md#syncing-the-environment/syncing-optional-dependencies/0",
                3,
            ),
            ("docs/concepts/projects/dependencies.md#optional-dependencies/0", 2),
        ),
        "The optional dependencies sync section states that extras are not synced by default and "
        "shows `uv sync --extra foo` as the way to include one; the dependencies page explains "
        "what extras are but not this flag.",
    ),
    (
        "u-0308",
        "uv sync --refresh-package",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/cache.md#dependency-caching/0", 3),),
        "The caching escape hatches in this section give `uv sync --refresh-package ruff` and "
        "state that it forces revalidation of cached data for one named dependency rather than all "
        "of them.",
    ),
    (
        "u-0309",
        "uv pip install --group",
        (EvalSlice.SYMBOL,),
        (("docs/pip/packages.md#installing-packages-from-files/0", 3),),
        "This section documents the flag: `uv pip install --group foo` for the current project, "
        "the per-path `pyproject.toml:group` form, and the note that --group does not apply to "
        "sources given with -r or -e.",
    ),
    (
        "u-0310",
        "uv pip install --python",
        (EvalSlice.SYMBOL,),
        (("docs/pip/environments.md#using-arbitrary-python-environments/0", 3),),
        "This section states that `uv pip install --python /path/to/python` installs into the "
        "environment linked to that interpreter, that the option also accepts a virtual "
        "environment root, and when --system is additionally required.",
    ),
    (
        "u-0311",
        "uv init --bare",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/projects/init.md#creating-a-minimal-project/0", 3),),
        "The minimal-project section is the documentation of --bare: it shows `uv init example- "
        "bare --bare` and enumerates what is skipped (version pin, README, source files, git, "
        "extra metadata).",
    ),
    (
        "u-0312",
        "uv tool upgrade --all",
        (EvalSlice.SYMBOL,),
        (
            ("docs/guides/tools.md#upgrading-tools/0", 3),
            ("docs/concepts/tools.md#upgrading-tools/0", 2),
        ),
        "The guide's upgrade section is the only place that shows `uv tool upgrade --all` and says "
        "it upgrades all tools rather than one; the concept section documents `uv tool upgrade` "
        "itself without the --all form.",
    ),
    (
        "u-0313",
        "uv tool install --python",
        (EvalSlice.SYMBOL,),
        (
            ("docs/guides/tools.md#requesting-python-versions/0", 3),
            ("docs/concepts/tools.md#python-versions/0", 2),
        ),
        "That section states the --python option selects the interpreter for tool commands and "
        "shows `uv tool install --python 3.10 ruff`; the concept section only explains that a tool "
        "environment is bound to a Python version.",
    ),
    (
        "u-0314",
        "uv tool install --with-executables-from",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/tools.md#installing-executables-from-additional-packages/0", 3),),
        "This section is the documentation of the option: it gives the invocation, an ansible "
        "example, and states how it differs from --with (it also installs the extra packages' "
        "executables).",
    ),
    (
        "u-0315",
        "uvx --isolated",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/tools.md#tool-versions/0", 3),),
        "The tool versions section introduces `uvx --isolated ruff` and states what it does: "
        "ignore an installed version of the tool without refreshing the cache.",
    ),
    (
        "u-0316",
        "uv python find --system",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/python-versions.md#finding-a-python-executable/0", 3),
            ("docs/getting-started/features.md#python-versions/0", 1),
        ),
        "The section documents `uv python find` and then states that the --system flag makes it "
        "ignore virtual environments, which otherwise take precedence; the features list only "
        "names `uv python find`.",
    ),
    (
        "u-0317",
        "uv python list --all-versions",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/python-versions.md#viewing-available-python-versions/0", 3),
            ("docs/guides/install-python.md#viewing-python-installations/0", 2),
        ),
        "That section says downloads for old patch versions are hidden by default and gives `uv "
        "python list --all-versions` as the way to see them all; the guide only shows the bare `uv "
        "python list`.",
    ),
    (
        "u-0318",
        "uv python install --reinstall",
        (EvalSlice.SYMBOL,),
        (("docs/guides/install-python.md#reinstalling-python/0", 3),),
        "This section exists to document the flag: it shows `uv python install --reinstall`, says "
        "it reinstalls every previously installed version, and explains why that can help even at "
        "the same version.",
    ),
    (
        "u-0319",
        "uv build --sdist",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/projects/build.md#using-uv-build/0", 3),
            ("docs/guides/projects.md#building-distributions/0", 2),
            ("docs/getting-started/features.md#projects/0", 1),
        ),
        "The build concept section states that `uv build --sdist` limits the build to a source "
        "distribution (against --wheel and the default of both); the guide describes `uv build` "
        "without the flags, and the features list only names the command.",
    ),
    (
        "u-0320",
        "uvx --from",
        (EvalSlice.SYMBOL,),
        (
            ("docs/guides/tools.md#commands-with-different-package-names/0", 3),
            ("docs/guides/tools.md#requesting-different-sources/0", 2),
        ),
        "The 'Commands with different package names' section introduces --from as the way to run a "
        "command from a differently-named package, with the httpie/http example. 'Requesting "
        "different sources' shows the same option pointed at Git URLs, framing its wider use.",
    ),
    (
        "u-0321",
        "uv add --optional",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/projects/dependencies.md#optional-dependencies/0", 3),),
        "The optional dependencies section documents '--optional <extra>' as the flag that adds a "
        "requirement to a named extra under [project.optional-dependencies], with the 'uv add "
        "httpx --optional network' example.",
    ),
    (
        "u-0322",
        "uv add --lfs",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/projects/dependencies.md#dependency-sources/git/0", 3),),
        "The Git source section states that Git LFS objects are not fetched by default and shows "
        "'uv add --lfs' writing lfs = true into the tool.uv.sources entry, which is what the flag "
        "does.",
    ),
    (
        "u-0323",
        "uv lock --upgrade",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/projects/sync.md#upgrading-locked-package-versions/0", 3),),
        "This section documents --upgrade as the flag that re-resolves every locked package to the "
        "newest version the project's constraints allow, and notes it also overrides the "
        "preference for a locked Git commit SHA.",
    ),
    (
        "u-0324",
        "uv version --short",
        (EvalSlice.SYMBOL,),
        (("docs/guides/projects.md#viewing-your-version/0", 3),),
        "The 'Viewing your version' section documents --short as the option that prints the bare "
        "version without the package name, contrasting it with plain uv version and --output- "
        "format json.",
    ),
    (
        "u-0325",
        "uvx --with",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/tools.md#including-additional-dependencies/0", 3),
            ("docs/guides/tools.md#commands-with-plugins/0", 2),
        ),
        "The concepts section documents --with for tool execution: repetition, version specifiers, "
        "the -w shorthand, and what happens on conflict. The guide's plugin section only shows one "
        "mkdocs-material invocation.",
    ),
    (
        "u-0326",
        "uv sync --compile-bytecode",
        (EvalSlice.SYMBOL,),
        (("docs/guides/integration/docker.md#optimizations/compiling-bytecode/0", 3),),
        "This section documents --compile-bytecode: it compiles installed sources to .pyc for "
        "faster startup at the cost of install time and image size, and names UV_COMPILE_BYTECODE "
        "as the equivalent environment variable.",
    ),
    (
        "u-0327",
        "uv sync --no-editable",
        (EvalSlice.SYMBOL,),
        (
            ("docs/guides/integration/docker.md#optimizations/non-editable-installs/0", 3),
            ("docs/concepts/projects/sync.md#syncing-the-environment/editable-installation/0", 2),
        ),
        "The Docker section documents --no-editable on uv sync and uv run: it installs the project "
        "without a dependency on the source tree, so a multi-stage build can copy only the virtual "
        "environment. The sync concepts page states the flag opts out of the editable default.",
    ),
    (
        "u-0328",
        "uv tool install --force",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/tools.md#tool-executables/overwriting-executables/0", 3),
            ("docs/concepts/tools.md#tool-executables/0", 2),
        ),
        "The 'Overwriting executables' subsection is the only place --force is documented: "
        "installs normally refuse to replace an executable uv did not install (e.g. one from "
        "pipx), and --force overrides that. The parent section explains what the executable "
        "directory holds.",
    ),
    (
        "u-0329",
        "uv add --dev",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/projects/dependencies.md#development-dependencies/0", 3),
            ("docs/concepts/projects/dependencies.md#adding-dependencies/0", 2),
        ),
        "The development dependencies section documents --dev: it writes the requirement into the "
        "dev group of [dependency-groups], and --dev is equivalent to --group dev. The adding- "
        "dependencies section only lists --dev among the flags that target an alternative table.",
    ),
    (
        "u-0330",
        "uv add --group",
        (EvalSlice.SYMBOL,),
        (
            (
                "docs/concepts/projects/dependencies.md#development-dependencies/dependency-groups/0",
                3,
            ),
        ),
        "This subsection documents --group as the way to put a development dependency into a named "
        "group other than dev, showing 'uv add --group lint ruff' and the resulting [dependency- "
        "groups] table.",
    ),
    (
        "u-0331",
        "what happens when uv finds a lockfile with a newer schema version",
        (EvalSlice.FACT,),
        (("docs/concepts/resolution.md#lockfile-versioning/0", 3),),
        "States the rule directly: a uv that supports schema v1 errors on an existing v1 "
        "lockfile of a greater schema version, and reading an older schema is only "
        "possible when the update was backwards-compatible rather than guaranteed.",
    ),
    (
        "u-0332",
        "where does uv create a project's virtual environment by default",
        (EvalSlice.FACT,),
        (("docs/reference/storage.md#types-of-data/project-virtual-environments/0", 3),),
        "Names the location and the override in one place: `.venv` in the project or "
        "workspace root beside `pyproject.toml`, with `UV_PROJECT_ENVIRONMENT` as the way "
        "to move it.",
    ),
    (
        "u-0333",
        "does uv register managed python installations with the windows registry",
        (EvalSlice.FACT,),
        (("docs/concepts/python-versions.md#registration-in-the-windows-registry/0", 3),),
        "Answers yes and says under which standard - managed installations are registered "
        "as PEP 514 defines, which is what makes them selectable with the `py` launcher.",
    ),
)

RELEASE: tuple[Judgment, ...] = (
    (
        "u-1001",
        "how do I add a package index other than PyPI",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/indexes.md#defining-an-index/", 3),
            ("docs/concepts/indexes.md#/0", 2),
        ),
        "The answer is a configuration table shown in a named section.",
    ),
    (
        "u-1002",
        "is uv a drop-in replacement for pip",
        (EvalSlice.CONCEPTUAL,),
        (("docs/pip/compatibility.md#/0", 3),),
        "A yes-but question the document answers carefully in its opening.",
    ),
    (
        "u-1003",
        "tool.uv.index",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/indexes.md#defining-an-index/", 3),
            ("docs/concepts/indexes.md#/0", 2),
        ),
        "A literal configuration key, documented in one section of the document that "
        "names it twenty-six times. Re-judged at roadmap 5.30: the preamble names the "
        "key in one subordinate clause and says what it is *for*, which is `u-1001`'s "
        "grade for the same passage; the section says what an entry is, which fields "
        "it takes, how indexes are prioritised and what the command line and "
        "environment equivalents are (ADR-0101).",
    ),
    (
        "u-1004",
        "how do I pin one package to a specific index",
        (EvalSlice.FACT,),
        (("docs/concepts/indexes.md#pinning-a-package-to-an-index/", 3),),
        "A task with its own section; the question avoids the section's wording.",
    ),
    (
        "u-1005",
        "what is the difference between a managed and a system Python installation",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/python-versions.md#managed-and-system-python-installations/0", 3),),
        "A distinction the document defines explicitly.",
    ),
    (
        "u-1006",
        "which Python version formats can I request",
        (EvalSlice.FACT,),
        (("docs/concepts/python-versions.md#requesting-a-version/", 3),),
        "A list of accepted formats, asked without the document's noun.",
    ),
    (
        "u-1007",
        "uv tool install",
        (EvalSlice.SYMBOL,),
        (
            ("docs/guides/tools.md#installing-tools/", 3),
            ("docs/concepts/tools.md#the-uv-tool-interface/0", 2),
            ("docs/getting-started/features.md#tools/0", 1),
        ),
        "A command with two homes, and the first judgement named the lesser one "
        "(roadmap 4.34). This corpus vendors no CLI reference, so the command is "
        "*documented* by the guide's `Installing tools` section - what it does, where "
        "the executables land, how it differs from `uv pip install`, the flags - which "
        "is the grade-3 unit its three sibling `symbol` cases all name. Section-scoped "
        "because the answer is spread across the whole of it (ADR-0029). The concepts "
        "page keeps grade 2: it frames the interface and mentions the command in one "
        "sentence, which is more than 'it exists' and less than its documentation. The "
        "feature list is graded 1 on u-1019's precedent - it answers only that the "
        "command exists.",
    ),
    (
        "u-1008",
        "how do I add a dependency to my project",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/dependencies.md#adding-dependencies/", 3),),
        "The commonest task in the corpus. The answer is the section - the command, the "
        "entry it writes, the flags that vary it - so judging one paragraph of it was "
        "judging where the chunker splits (ADR-0029).",
    ),
    (
        "u-1009",
        "why does a single lockfile cover every package in a workspace",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/workspaces.md#/0", 3),
            ("docs/concepts/resolution.md#/0", 1),
        ),
        "Relates two ideas — workspace membership and shared resolution — stated in one place.",
    ),
    (
        "u-1010",
        "what happens to the cache when the format changes between releases",
        (EvalSlice.RELATIONSHIP, EvalSlice.FACT),
        (
            ("docs/concepts/cache.md#cache-versioning/0", 3),
            ("docs/reference/policies/versioning.md#cache-versioning/0", 2),
        ),
        "The same subject in two documents: a concept page and a policy page.",
    ),
    (
        "u-1011",
        "chitin exoskeleton pupation",
        (EvalSlice.UNANSWERABLE,),
        (),
        "A domain this corpus will never cover.",
    ),
    (
        "u-1012",
        "annealing kiln borosilicate gaffer",
        (EvalSlice.UNANSWERABLE,),
        (),
        "As u-1011, in a different domain.",
    ),
    (
        "u-1013",
        "how do I stop uv from using the network at all",
        (EvalSlice.FACT,),
        (("docs/concepts/cache.md#cache-directory/", 1),),
        "A question the corpus answers only partially — a weak-evidence case on purpose.",
    ),
    (
        "u-1014",
        "what does uv do about TLS certificates from a corporate proxy",
        (EvalSlice.FACT,),
        (("docs/concepts/authentication/certificates.md#custom-certificates/0", 3),),
        "A real-world phrasing whose answer sits under a differently-worded heading.",
    ),
    (
        "u-1015",
        "storage directories",
        (EvalSlice.EXACT,),
        (("docs/reference/storage.md#storage-directories/0", 3),),
        "A heading quoted verbatim: the easiest possible lexical case, kept as a floor.",
    ),
    (
        "u-1016",
        "how do I keep credentials out of my shell history when logging in to an index",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/authentication/cli.md#logging-in-to-a-service/", 3),
            ("docs/concepts/authentication/http.md#/0", 1),
        ),
        "A motivation-shaped question; the corpus answers the mechanism, not the motive. "
        "Scoped to the section at 4.12: the stdin recommendation is one paragraph of a "
        "six-chunk section that packing makes a single 204-token chunk, so no chunk "
        "anchor here is true under both settings.",
    ),
    # Nine cases added at roadmap 4.26, to give the thin slices enough judgements
    # to carry a gate (ADR-0052 asks for four). `symbol` takes three of them and
    # `exact` three, because those were the two rows a single case was speaking
    # for; the last three are the relationship and conceptual questions the
    # corpus can honestly be asked. Written from the documents, as every other
    # judgement here was — the passages first, the anchors looked up afterwards.
    (
        "u-1017",
        "uv lock --check",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/projects/sync.md#checking-the-lockfile/0", 3),),
        "A command with a flag, and the section that documents it is named for the "
        "question rather than for the command.",
    ),
    (
        "u-1018",
        "--no-sources",
        (EvalSlice.EXACT,),
        (("docs/concepts/projects/dependencies.md#dependency-sources/disabling-sources/0", 3),),
        "A literal flag. It appears in four documents and is *explained* in one, which is "
        "the discrimination an exact query has to make.",
    ),
    (
        "u-1019",
        "uv python pin",
        (EvalSlice.SYMBOL,),
        (
            (
                "docs/concepts/python-versions.md#requesting-a-version/python-version-files/0",
                3,
            ),
            ("docs/getting-started/features.md#python-versions/0", 1),
        ),
        "The command is named in a feature list and explained under a heading that does "
        "not contain it; the list is graded 1 because it answers only that the command "
        "exists.",
    ),
    (
        "u-1020",
        "free-threaded Python",
        (EvalSlice.EXACT,),
        (("docs/concepts/python-versions.md#free-threaded-python/0", 3),),
        "A term quoted verbatim from its own heading, and one the corpus uses nowhere "
        "else - the counterpart to `storage directories` on the second corpus.",
    ),
    (
        "u-1021",
        "PEP 508",
        (EvalSlice.EXACT,),
        (("docs/concepts/projects/dependencies.md#dependency-specifiers/0", 3),),
        "A standard's number, cited in four documents. Only one says what it *is*, and "
        "the others link it in passing - so a hit anywhere is not an answer.",
    ),
    (
        "u-1022",
        "why is my project environment already up to date when I run a command",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/sync.md#automatic-lock-and-sync/0", 3),
            ("docs/concepts/projects/run.md#/0", 2),
        ),
        "Two documents state the two halves: one that locking and syncing are automatic, "
        "the other that `uv run` ensures the environment is current first. The query uses "
        "neither's noun - it says neither `lock` nor `sync`.",
    ),
    (
        "u-1023",
        "can I adopt part of uv without adopting all of it",
        (EvalSlice.CONCEPTUAL,),
        (("docs/getting-started/features.md#/0", 3),),
        "The answer is one clause of an overview document - the interface breaks into "
        "sections usable independently or together - phrased the way someone deciding "
        "would ask it.",
    ),
    (
        "u-1024",
        "where do I record which Python a project needs, and what reads that",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/concepts/python-versions.md#requesting-a-version/python-version-files/0",
                3,
            ),
            ("docs/concepts/projects/run.md#/0", 1),
        ),
        "A two-part question: the file that records the request, and the commands that "
        "honour it. Graded 1 on the second because it states the mechanism without "
        "naming the file.",
    ),
    (
        "u-1025",
        "uv export",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/projects/sync.md#exporting-the-lockfile/0", 3),),
        "The third `symbol` case, and the one that takes the slice to the four ADR-0052 "
        "enforces on. A command whose section is titled by what it produces.",
    ),
    # --- getting started: the front door, the installer, the feature list ---
    (
        "u-1026",
        "how do I check which version of uv is installed",
        (EvalSlice.FACT,),
        (("docs/getting-started/help.md#viewing-the-version/0", 3),),
        "A fact with three spellings of the command and a note about the one that was "
        "renamed; the section that documents it is the answer.",
    ),
    (
        "u-1027",
        "how do I get uv to explain what it is doing",
        (EvalSlice.FACT,),
        (("docs/getting-started/help.md#displaying-verbose-output/0", 3),),
        "Phrased the way someone debugging asks it, using neither `verbose` nor `-v`.",
    ),
    (
        "u-1028",
        "where do I report a bug in uv",
        (EvalSlice.FACT,),
        (
            ("docs/getting-started/help.md#open-an-issue-on-github/0", 3),
            ("docs/getting-started/help.md#chat-on-discord/0", 1),
        ),
        "The issue tracker is the answer and says to search first; the Discord section "
        "is a place to ask questions rather than to report, which is grade 1's tier.",
    ),
    (
        "u-1029",
        "uv help",
        (EvalSlice.SYMBOL,),
        (("docs/getting-started/help.md#help-menus/0", 3),),
        "A command whose name is also an ordinary word, so a term match is not enough: "
        "the section that documents it separates `--help` from `uv help`.",
    ),
    (
        "u-1030",
        "which existing Python tools does uv set out to replace",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/getting-started/features.md#the-pip-interface/0", 3),
            ("docs/pip/index.md#/0", 2),
        ),
        "The feature list names the replaced tool beside each command - venv and "
        "virtualenv, pip and pipdeptree, pip-tools - where the pip interface's own "
        "preamble only says `drop-in replacement`.",
    ),
    (
        "u-1032",
        "how do I install a particular version of uv with the install script",
        (EvalSlice.FACT,),
        (("docs/getting-started/installation.md#installation-methods/standalone-installer/0", 3),),
        "The answer is a URL shape - the version goes in the path - shown per platform.",
    ),
    (
        "u-1033",
        "do I need a Rust toolchain to install uv",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/getting-started/installation.md#installation-methods/pypi/0", 3),
            ("docs/getting-started/installation.md#installation-methods/cargo/0", 2),
        ),
        "A conditional answer: prebuilt wheels for many platforms, a source build where "
        "there is none - and the one installation method that always needs the "
        "toolchain is a note in its own section.",
    ),
    (
        "u-1034",
        "UV_NO_MODIFY_PATH",
        (EvalSlice.EXACT,),
        (
            ("docs/reference/installer.md#disabling-shell-modifications/0", 3),
            ("docs/getting-started/installation.md#upgrading-uv/0", 2),
        ),
        "The literal appears in two documents: the installer reference documents what it "
        "does, the installation page names it in a tip about self-update (ADR-0101).",
    ),
    (
        "u-1035",
        "UV_INSTALL_DIR",
        (EvalSlice.EXACT,),
        (("docs/reference/installer.md#changing-the-installation-path/0", 3),),
        "A literal with one home, and the section around it states the limit that "
        "surprises people - it moves the binary, not the data.",
    ),
    (
        "u-1036",
        "UV_UNMANAGED_INSTALL",
        (EvalSlice.EXACT,),
        (("docs/reference/installer.md#unmanaged-installations/0", 3),),
        "The CI-shaped variable, documented in one section of one document.",
    ),
    (
        "u-1037",
        "how do I turn on tab completion for uvx",
        (EvalSlice.FACT,),
        (("docs/getting-started/installation.md#shell-autocompletion/0", 3),),
        "Two flag spellings live in this section - `uv generate-shell-completion` and "
        "`uvx --generate-shell-completion` - and the question asks for the second.",
    ),
    (
        "u-1038",
        "how do I remove uv and everything it stored on disk",
        (EvalSlice.FACT,),
        (
            ("docs/getting-started/installation.md#uninstallation/0", 3),
            ("docs/reference/storage.md#storage-directories/0", 1),
        ),
        "An ordered procedure: clear the stored data first, then remove three binaries. "
        "The storage reference is where the procedure points for the locations.",
    ),
    (
        "u-1039",
        "uv self update",
        (EvalSlice.SYMBOL,),
        (
            ("docs/getting-started/installation.md#upgrading-uv/0", 3),
            ("docs/getting-started/features.md#utility/0", 1),
        ),
        "The section that documents the command also states the condition nobody expects "
        "- self-update works only for the standalone installer - against the feature "
        "list's one-line entry (ADR-0062's tiers).",
    ),
    (
        "u-1040",
        "uv cache dir",
        (EvalSlice.SYMBOL,),
        (
            ("docs/reference/storage.md#types-of-data/dependency-cache/0", 3),
            ("docs/concepts/cache.md#cache-directory/0", 2),
            ("docs/getting-started/features.md#utility/0", 1),
        ),
        "The three tiers on one command: the section that documents it, the section that "
        "frames how the directory is chosen, and the feature-list entry.",
    ),
    # --- projects: creating one, and what ends up on disk ---
    (
        "u-1041",
        "what happens if I run uv init where a project already exists",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/init.md#target-directory/0", 3),),
        "An error case, stated in one clause of a section about something else.",
    ),
    (
        "u-1042",
        "why does uv put the code in a src directory",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/projects/init.md#libraries/0", 3),
            ("docs/concepts/projects/init.md#/0", 2),
        ),
        "The reasoning is a note inside the library template - isolation from `python` "
        "invocations in the root - while the document's opening states the preference "
        "without the argument.",
    ),
    (
        "u-1043",
        "how do I start a project with a Rust extension module",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/init.md#projects-with-extension-modules/0", 3),),
        "A fact that is really a choice of backend; the section names the two that can.",
    ),
    (
        "u-1044",
        "--no-package",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/projects/init.md#creating-a-project-without-a-build-system/0", 3),
            ("docs/concepts/projects/init.md#/0", 2),
        ),
        "A flag documented in its own section and named in passing in the opening "
        "paragraph beside its sibling (ADR-0101).",
    ),
    (
        "u-1045",
        "which build backends can uv set up for a new project",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/projects/init.md#libraries/0", 3),
            ("docs/concepts/projects/init.md#projects-with-extension-modules/0", 2),
        ),
        "A seven-item list inside a tip; the extension-module section names the subset "
        "that can build native code, which answers half the question.",
    ),
    (
        "u-1046",
        "should the .venv directory go into version control",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/layout.md#the-project-environment/0", 3),),
        "A recommendation plus the mechanism that enforces it - an internal .gitignore.",
    ),
    (
        "u-1047",
        "why is the lockfile called universal",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/layout.md#the-lockfile/0", 3),),
        "A term the document defines in its own words: every marker, not this machine.",
    ),
    (
        "u-1048",
        "pylock.toml",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/projects/layout.md#the-lockfile/relationship-to-pylock-toml/0", 3),
            ("docs/concepts/projects/export.md#pylock-toml-format/0", 2),
            ("docs/concepts/projects/sync.md#exporting-the-lockfile/0", 1),
        ),
        "A standard's filename in three documents: the section that says what it is and "
        "why uv keeps its own format, the export format's own section, and a list of "
        "export targets that names it.",
    ),
    (
        "u-1049",
        "can I tell uv to stop managing a project's environment",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/layout.md#the-project-environment/0", 3),
            ("docs/concepts/projects/sync.md#automatic-lock-and-sync/0", 2),
        ),
        "The setting is in one document and what it switches off - automatic locking and "
        "syncing - is defined in another.",
    ),
    (
        "u-1050",
        "what does the centralized project environments feature change",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/concepts/projects/layout.md"
                "#the-project-environment/centralized-project-environments/0",
                3,
            ),
            ("docs/concepts/preview.md#/0", 1),
        ),
        "A preview feature with three fallbacks and two exclusions; the preview document "
        "only says what preview means.",
    ),
    (
        "u-1051",
        "why does a library get a py.typed marker when an application does not",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/init.md#libraries/0", 3),
            ("docs/concepts/projects/init.md#applications/0", 2),
        ),
        "Two templates, and the answer is the difference between them: one is built for "
        "consumers to read types from, the other is not distributed.",
    ),
    # --- projects: building a distribution, and exporting the lockfile ---
    (
        "u-1052",
        "how do I build only the wheel and skip the source distribution",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/build.md#using-uv-build/0", 3),),
        "Three flag combinations in one paragraph, and the default order between them.",
    ),
    (
        "u-1053",
        "when I build a project, what does uv decide and what does the backend decide",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/build.md#/0", 3),),
        "The frontend/backend split, stated once in an admonition: uv picks the Python "
        "and invokes; which files ship is the backend's.",
    ),
    (
        "u-1054",
        "how do I keep an internal package from being uploaded to PyPI by mistake",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/build.md#preventing-publish-to-pypi/0", 3),),
        "A classifier plus the caveat that it is not a security control.",
    ),
    (
        "u-1055",
        "--build-constraint",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/projects/build.md#build-constraints/0", 3),
            ("docs/pip/compatibility.md#build-constraints/0", 2),
        ),
        "The literal is in two documents: its own section documents it with a hash "
        "example, and the pip-compatibility page names it to say what `--constraint` "
        "does *not* do (ADR-0101).",
    ),
    (
        "u-1056",
        "how do I get a software bill of materials for my dependencies",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/projects/export.md#cyclonedx-sbom-format/0", 3),
            ("docs/concepts/projects/export.md#cyclonedx-sbom-format/basic-usage/0", 2),
        ),
        "The question never says CycloneDX, which is the only word the section uses.",
    ),
    (
        "u-1057",
        "which custom fields does uv add to the SBOM it writes",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/export.md#cyclonedx-sbom-format/sbom-structure/0", 3),),
        "Two property names in a short subsection, below two others about the format.",
    ),
    (
        "u-1058",
        "is it a good idea to keep both uv.lock and a requirements file",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/export.md#requirements-txt-format/basic-usage/0", 3),),
        "A recommendation hidden in a note under a usage example, and it argues against "
        "the thing the section is showing you how to do.",
    ),
    (
        "u-1059",
        "how do I write an export to a file instead of the terminal",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/export.md#overview-of-export-formats/0", 3),),
        "A default (stdout) and the flag that changes it, in a tip.",
    ),
    (
        "u-1060",
        "which of uv's export formats can another tool install from",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/export.md#overview-of-export-formats/0", 3),
            ("docs/concepts/projects/layout.md#the-lockfile/relationship-to-pylock-toml/0", 2),
        ),
        "The list of formats is in one document; why uv keeps its own format anyway, and "
        "which of the three is tool-agnostic, is argued in another.",
    ),
    # --- projects: configuration, packaging, build isolation ---
    (
        "u-1061",
        "where do I state which Python versions my project supports",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/config.md#python-version-requirement/0", 3),),
        "A field name plus what it decides - allowed syntax and which dependency "
        "versions can be chosen - in a short section.",
    ),
    (
        "u-1062",
        "how do I make my project install a console command",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/projects/config.md#entry-points/command-line-interfaces/0", 3),
            ("docs/concepts/projects/config.md#entry-points/0", 2),
        ),
        "The table and its `module:function` shape; the parent section states the "
        "precondition that a build system must be defined.",
    ),
    (
        "u-1063",
        "what is different about a GUI script on Windows",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/config.md#entry-points/graphical-user-interfaces/0", 3),),
        "The distinction exists on one platform only, which is the whole answer.",
    ),
    (
        "u-1064",
        "project.entry-points",
        (EvalSlice.EXACT,),
        (("docs/concepts/projects/config.md#entry-points/plugin-entry-points/0", 3),),
        "A table name whose section shows both halves - declaring the plugin and "
        "loading it - and the namespacing advice.",
    ),
    (
        "u-1065",
        "how does uv decide whether to install the project itself",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/projects/config.md#build-systems/0", 3),
            ("docs/concepts/projects/config.md#project-packaging/0", 2),
        ),
        "The rule is the presence of a `[build-system]` table; the packaging section "
        "restates it to introduce the override.",
    ),
    (
        "u-1066",
        "tool.uv.package",
        (EvalSlice.EXACT,),
        (("docs/concepts/projects/config.md#project-packaging/0", 3),),
        "A setting with asymmetric behaviour in its two values, documented in one place.",
    ),
    (
        "u-1067",
        "what does uv do with a dependency that declares no build system",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/config.md#build-systems/0", 3),),
        "The legacy fallback, stated in a note: the rule for *your* project is not the "
        "rule for the packages it depends on.",
    ),
    (
        "u-1068",
        "when does my project need to be a package and when is it fine without",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/config.md#project-packaging/0", 3),
            ("docs/concepts/projects/config.md#build-systems/0", 2),
        ),
        "Two lists - you probably need one if, you probably do not if - and the section "
        "that defines what packaging *is* underneath them.",
    ),
    (
        "u-1069",
        "how do I put the project environment somewhere other than .venv",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/config.md#project-environment-path/0", 3),),
        "The variable, how a relative path resolves, and the warning about sharing one "
        "absolute path across projects.",
    ),
    (
        "u-1070",
        "does uv pay attention to an activated virtual environment",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/config.md#project-environment-path/0", 3),),
        "A no with two flags attached, in a note at the end of a section about paths - "
        "and the question names neither `VIRTUAL_ENV` nor `--active`.",
    ),
    (
        "u-1071",
        "why does uv build packages in an isolated environment",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/config.md#build-isolation/0", 3),),
        "A standard's behaviour and the two ways packages break under it.",
    ),
    (
        "u-1072",
        "extra-build-dependencies",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/projects/config.md#build-isolation/augmenting-build-dependencies/0", 3),
            ("docs/concepts/projects/config.md#build-isolation/0", 2),
        ),
        "The setting's own section against the paragraph that introduces it as one of "
        "two approaches (ADR-0101).",
    ),
    (
        "u-1073",
        "match-runtime",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/projects/config.md#build-isolation/augmenting-build-dependencies/0", 3),
            (
                "docs/concepts/projects/config.md"
                "#build-isolation/augmenting-build-dependencies/dynamic-metadata/0",
                2,
            ),
        ),
        "Documented where it is used and qualified where it cannot be used.",
    ),
    (
        "u-1074",
        "why can a build dependency not always be matched to the installed version",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/concepts/projects/config.md"
                "#build-isolation/augmenting-build-dependencies/dynamic-metadata/0",
                3,
            ),
        ),
        "An argument about resolution order: without static metadata the package must "
        "be built before the version it should be built against is known.",
    ),
    (
        "u-1075",
        "how do I tell uv a package's metadata instead of making it build the package",
        (EvalSlice.FACT,),
        (
            (
                "docs/concepts/projects/config.md"
                "#build-isolation/augmenting-build-dependencies/dynamic-metadata/0",
                3,
            ),
        ),
        "The `dependency-metadata` setting, and where to find the values to put in it.",
    ),
    (
        "u-1076",
        "should I disable build isolation or add the missing build dependency",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/config.md#build-isolation/0", 3),
            (
                "docs/concepts/projects/config.md#build-isolation/disabling-build-isolation/0",
                2,
            ),
        ),
        "A recommendation between two approaches, and the section that shows what the "
        "one it argues against actually costs.",
    ),
    (
        "u-1077",
        "no-build-isolation-package",
        (EvalSlice.EXACT,),
        (
            (
                "docs/concepts/projects/config.md#build-isolation/disabling-build-isolation/0",
                3,
            ),
        ),
        "A setting and its command-line twin, with the two-phase install it triggers.",
    ),
    (
        "u-1078",
        "how do I keep build dependencies out of the environment I ship",
        (EvalSlice.FACT,),
        (
            (
                "docs/concepts/projects/config.md#build-isolation/disabling-build-isolation/0",
                3,
            ),
        ),
        "The optional-group trick: sync with the group, then sync without it.",
    ),
    (
        "u-1079",
        "how do I install the project so that source edits are not picked up",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/config.md#editable-mode/0", 3),),
        "A default and the flag that reverses it, with the deployment case it is for.",
    ),
    (
        "u-1080",
        "how do I tell uv that two extras can never be installed together",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/config.md#conflicting-dependencies/0", 3),),
        "A TOML shape with two forms - extras and groups - in one section.",
    ),
    (
        "u-1081",
        "how do I stop the lockfile from solving for platforms we never ship to",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/config.md#limited-resolution-environments/0", 3),),
        "The setting takes environment markers, which is the part a reader has to see.",
    ),
    (
        "u-1082",
        "what is required-environments for, and when does it matter",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/config.md#required-environments/0", 3),),
        "The answer is a condition - it only matters for packages that publish no source "
        "distribution - and the example names one.",
    ),
    # --- projects: declaring dependencies, and where they come from ---
    (
        "u-1083",
        "how do I depend on a specific tag of a git repository",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/dependencies.md#dependency-sources/git/0", 3),),
        "One section carries four reference kinds - tag, branch, rev, subdirectory - and "
        "the question asks for one of them.",
    ),
    (
        "u-1084",
        "subdirectory",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/projects/dependencies.md#dependency-sources/git/0", 3),
            ("docs/concepts/projects/dependencies.md#dependency-sources/url/0", 2),
        ),
        "A key that means the same thing for two source kinds and is shown for one; the "
        "URL section names it in a sentence (ADR-0101).",
    ),
    (
        "u-1085",
        "UV_GIT_LFS",
        (EvalSlice.EXACT,),
        (("docs/concepts/projects/dependencies.md#dependency-sources/git/0", 3),),
        "A variable that only matters when the per-source setting is omitted, which is "
        "stated in the third of three bullets.",
    ),
    (
        "u-1086",
        "how do I depend on a wheel that is already on my disk",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/dependencies.md#dependency-sources/path/0", 3),),
        "The answer covers three shapes - wheel, sdist, directory - and the directory "
        "case carries the warning.",
    ),
    (
        "u-1087",
        "what does it mean to pin a package to an index",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/projects/dependencies.md#dependency-sources/index/0", 3),
            ("docs/concepts/indexes.md#pinning-a-package-to-an-index/0", 2),
        ),
        "The dependency document states the consequence - it will not be downloaded from "
        "other indexes - and the indexes document shows the configuration.",
    ),
    (
        "u-1088",
        "how do I keep an index from being used for anything that does not name it",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/projects/dependencies.md#dependency-sources/index/0", 3),
            ("docs/concepts/indexes.md#defining-an-index/", 2),
        ),
        "The `explicit` flag, and what happens when it is not set - which is the half a "
        "reader gets wrong.",
    ),
    (
        "u-1089",
        "how do I take a dependency from github on macOS and from PyPI everywhere else",
        (EvalSlice.FACT,),
        (
            (
                "docs/concepts/projects/dependencies.md"
                "#dependency-sources/platform-specific-sources/0",
                3,
            ),
            ("docs/concepts/projects/dependencies.md#dependency-sources/multiple-sources/0", 2),
        ),
        "A marker on the source rather than on the dependency, and the section next door "
        "generalises it to a list.",
    ),
    (
        "u-1090",
        "does another packaging tool read tool.uv.sources",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/dependencies.md#dependency-sources/0", 3),),
        "A no, in an admonition, with what it implies for anyone using a second tool.",
    ),
    (
        "u-1091",
        "how do I install a different torch build on Linux than on macOS",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/dependencies.md#dependency-sources/multiple-sources/0", 3),
            ("docs/guides/integration/pytorch.md#using-a-pytorch-index/0", 2),
        ),
        "The mechanism is in the concepts document and the worked example is in a guide; "
        "neither says the other's half.",
    ),
    (
        "u-1092",
        "what is the difference between an extra and a dependency group",
        (EvalSlice.CONCEPTUAL, EvalSlice.RELATIONSHIP),
        (
            ("docs/concepts/projects/dependencies.md#optional-dependencies/0", 3),
            ("docs/concepts/projects/dependencies.md#development-dependencies/0", 3),
        ),
        "Each section defines one half and the answer is the contrast: one is published "
        "with the package, the other is local-only. Both grade 3 because neither alone "
        "answers it.",
    ),
    (
        "u-1093",
        "dependency-groups",
        (EvalSlice.EXACT,),
        (
            (
                "docs/concepts/projects/dependencies.md"
                "#development-dependencies/dependency-groups/0",
                3,
            ),
            ("docs/concepts/projects/dependencies.md#development-dependencies/0", 2),
        ),
        "A standardised table name: the subsection documents how groups are used, the "
        "parent section introduces the table and its special `dev` member.",
    ),
    (
        "u-1094",
        "how do I put a development tool in its own group instead of dev",
        (EvalSlice.FACT,),
        (
            (
                "docs/concepts/projects/dependencies.md"
                "#development-dependencies/dependency-groups/0",
                3,
            ),
        ),
        "The flag and the five options that select groups afterwards.",
    ),
    (
        "u-1095",
        "can one dependency group include another",
        (EvalSlice.FACT,),
        (
            (
                "docs/concepts/projects/dependencies.md#development-dependencies/nesting-groups/0",
                3,
            ),
        ),
        "A yes with a constraint attached, in a 73-token subsection.",
    ),
    (
        "u-1096",
        "which dependency groups are installed when I ask for none",
        (EvalSlice.FACT,),
        (
            (
                "docs/concepts/projects/dependencies.md#development-dependencies/default-groups/0",
                3,
            ),
        ),
        'A default, the setting that changes it, and the `"all"` shorthand.',
    ),
    (
        "u-1097",
        "what if my test dependencies need a newer Python than the project does",
        (EvalSlice.FACT,),
        (
            (
                "docs/concepts/projects/dependencies.md"
                "#development-dependencies/group-requires-python/0",
                3,
            ),
        ),
        "A per-group override of a project-level field, in its own subsection.",
    ),
    (
        "u-1098",
        "what happened to tool.uv.dev-dependencies",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/concepts/projects/dependencies.md"
                "#development-dependencies/legacy-dev-dependencies/0",
                3,
            ),
        ),
        "A superseded field, what it merges with now, and what `uv add --dev` does when "
        "it is still present.",
    ),
    (
        "u-1099",
        "why build a package with sources disabled before publishing it",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/dependencies.md#build-dependencies/0", 3),),
        "A recommendation whose reason is what other build tools will do with the "
        "package, not what uv does.",
    ),
    (
        "u-1100",
        "what does an editable install actually put in the environment",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/dependencies.md#editable-dependencies/0", 3),),
        "A mechanism - a `.pth` link rather than copied files - plus the two limits.",
    ),
    (
        "u-1101",
        "how do I depend on a local directory without installing it as a package",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/dependencies.md#virtual-dependencies/0", 3),),
        "The `package = false` source setting, and the default it overrides.",
    ),
    (
        "u-1102",
        "how do I add a dependency that is only installed on Linux",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/dependencies.md#platform-specific-dependencies/0", 3),),
        "An environment marker on the requirement, shown from the command line.",
    ),
    (
        "u-1103",
        "how do I change the version range of a dependency I already added",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/dependencies.md#changing-dependencies/0", 3),),
        "The answer is the same command again, plus the note that the locked version "
        "does not move unless it has to.",
    ),
    (
        "u-1104",
        "how do I bring the packages in a requirements file into a project",
        (EvalSlice.FACT,),
        (
            (
                "docs/concepts/projects/dependencies.md"
                "#adding-dependencies/importing-dependencies-from-requirements-files/0",
                3,
            ),
            (
                "docs/guides/migration/pip-to-project.md"
                "#migrating-to-a-uv-project/importing-requirements-files/0",
                2,
            ),
        ),
        "One flag, stated in two lines here and worked through in the migration guide.",
    ),
    (
        "u-1105",
        "which table should a dependency go in if only developers need it",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/dependencies.md#dependency-fields/0", 3),
            ("docs/concepts/projects/dependencies.md#development-dependencies/0", 2),
        ),
        "The overview lists four fields and what each is for; the development section is "
        "the one the answer lands on.",
    ),
    (
        "u-1106",
        "what happens to the source entry when I remove a dependency",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/dependencies.md#removing-dependencies/0", 3),),
        "A side effect stated in one sentence, and conditional on nothing else referencing it.",
    ),
    # --- resolution: what the resolver is solving for, and the knobs on it ---
    (
        "u-1107",
        "what is the difference between a direct and a transitive dependency",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/resolution.md#dependencies/0", 3),),
        "Two terms defined in one short section, and the question uses the informal "
        "word for the second.",
    ),
    (
        "u-1108",
        "why does uv solve for platforms I am not on",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/resolution.md#platform-markers/0", 3),
            ("docs/concepts/resolution.md#universal-resolution/0", 2),
        ),
        "The reason is stated where markers are explained - a lockfile made from the "
        "current platform's markers only works there - and named in the section that "
        "follows it.",
    ),
    (
        "u-1109",
        "how do I compile requirements for Linux while working on a Mac",
        (EvalSlice.FACT,),
        (("docs/concepts/resolution.md#platform-specific-resolution/0", 3),),
        "Two options and the caveat that one of them means something different here "
        "than in universal resolution.",
    ),
    (
        "u-1110",
        "what value does sys_platform have on 64-bit Windows",
        (EvalSlice.FACT,),
        (("docs/concepts/resolution.md#common-marker-values/0", 3),),
        "A table plus the note under it, which is the half that catches people out.",
    ),
    (
        "u-1111",
        "does uv pay attention to an upper bound on requires-python",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/resolution.md#universal-resolution/0", 3),),
        "A no, with the argument for it: respecting them produces formally correct and "
        "practically wrong resolutions.",
    ),
    (
        "u-1112",
        "how do I check that my library still works with the oldest versions it allows",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/resolution.md#resolution-strategy/0", 3),
            ("docs/concepts/resolution.md#lower-bounds/0", 2),
        ),
        "The flag is documented with two worked outputs; the lower-bounds section is "
        "where the recommendation to do it lives.",
    ),
    (
        "u-1113",
        "--resolution lowest-direct",
        (EvalSlice.EXACT,),
        (("docs/concepts/resolution.md#resolution-strategy/0", 3),),
        "A literal that differs from its sibling by one word, and the section is where "
        "the difference is stated.",
    ),
    (
        "u-1114",
        "why does uv insist on lower bounds for dependencies",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/resolution.md#lower-bounds/0", 3),),
        "An argument about what a resolver does without them - backtrack to versions "
        "too old to build - rather than a rule.",
    ),
    (
        "u-1115",
        "how do I allow a pre-release for one package but not the rest",
        (EvalSlice.FACT,),
        (("docs/concepts/resolution.md#pre-release-handling/0", 3),),
        "Four modes and a per-package override, in one section.",
    ),
    (
        "u-1116",
        "--fork-strategy",
        (EvalSlice.EXACT,),
        (("docs/concepts/resolution.md#multi-version-resolution/0", 3),),
        "A setting whose two values trade newer versions against fewer of them, shown "
        "with the same package resolved both ways.",
    ),
    (
        "u-1117",
        "why does one package appear twice in my lockfile with different versions",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/resolution.md#multi-version-resolution/0", 3),
            ("docs/concepts/resolution.md#universal-resolution/0", 2),
        ),
        "The answer is a property of universal resolution, explained where the knob "
        "that controls it is documented.",
    ),
    (
        "u-1118",
        "what is the difference between a constraint and an override",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/resolution.md#dependency-constraints/0", 3),
            ("docs/concepts/resolution.md#dependency-overrides/0", 3),
        ),
        "One can only narrow the acceptable versions and the other can widen them; each "
        "section states its own half and the overrides section names the contrast.",
    ),
    (
        "u-1119",
        "how do I override a dependency only for one package that declares it",
        (EvalSlice.FACT,),
        (("docs/concepts/resolution.md#dependency-overrides/0", 3),),
        "The scoped form, its precedence rules and the sources it does not support.",
    ),
    (
        "u-1120",
        "how do I drop a package out of the dependency graph completely",
        (EvalSlice.FACT,),
        (("docs/concepts/resolution.md#dependency-exclusions/0", 3),),
        "A setting with a global and a scoped form, in a section of its own.",
    ),
    (
        "u-1121",
        "how do I swap one dependency for another inside a single package",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/resolution.md#dependency-exclusions/0", 3),
            ("docs/concepts/resolution.md#dependency-overrides/0", 2),
        ),
        "The answer is the two settings used together - and which one wins when they "
        "meet - which only the exclusions section states.",
    ),
    (
        "u-1122",
        "why would I write a package's metadata into pyproject.toml myself",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/resolution.md#dependency-metadata/0", 3),),
        "A performance argument and a portability one: without static metadata the "
        "package has to build on every platform being solved for.",
    ),
    (
        "u-1123",
        "how do I declare that two workspace members conflict",
        (EvalSlice.FACT,),
        (("docs/concepts/resolution.md#conflicting-dependencies/0", 3),),
        "The `package` key, four shapes deep into a long section about extras.",
    ),
    (
        "u-1124",
        "--exclude-newer",
        (EvalSlice.EXACT,),
        (("docs/concepts/resolution.md#reproducible-resolutions/0", 3),),
        "A literal whose section states the one thing a reader gets wrong: the date is "
        "compared against each artifact's upload time, not the release date.",
    ),
    (
        "u-1125",
        "how do I resolve as if it were an earlier date",
        (EvalSlice.FACT,),
        (("docs/concepts/resolution.md#reproducible-resolutions/0", 3),),
        "The same section asked for as a task rather than as a flag name, and the "
        "accepted timestamp formats are the answer's other half.",
    ),
    (
        "u-1126",
        "does uv keep the versions I already have when it resolves again",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/resolution.md#dependency-preferences/0", 3),),
        "A preference rather than a rule, and the two things that override it.",
    ),
    (
        "u-1127",
        "which archive formats count as a source distribution",
        (EvalSlice.FACT,),
        (("docs/concepts/resolution.md#source-distribution/0", 3),),
        "A list-shaped fact in an 88-token section that three other documents link to.",
    ),
    (
        "u-1128",
        "how do required-environments and environments differ",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/resolution.md#required-environments/0", 3),
            ("docs/concepts/resolution.md#limited-resolution-environments/0", 2),
        ),
        "One expands what must be supported and the other reduces what is solved for; "
        "the contrast is stated in the first, and the second defines the half it names.",
    ),
    # --- the cache, and what invalidates it ---
    (
        "u-1129",
        "cache-keys",
        (EvalSlice.EXACT,),
        (("docs/concepts/cache.md#dynamic-metadata/0", 3),),
        "A setting whose section is titled after the problem it solves rather than "
        "after the setting, and which warns that setting it replaces the defaults.",
    ),
    (
        "u-1130",
        "how do I make uv rebuild a package when the git commit changes",
        (EvalSlice.FACT,),
        (("docs/concepts/cache.md#dynamic-metadata/0", 3),),
        "A cache-key entry for commits, among file, glob, env and dir forms.",
    ),
    (
        "u-1131",
        "is it safe to run two uv commands at the same time",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/cache.md#cache-safety/0", 3),),
        "A yes and a never in the same 88-token section: concurrent commands are fine, "
        "editing the cache by hand is not.",
    ),
    (
        "u-1132",
        "what does pruning the cache remove that clearing it does not",
        (EvalSlice.FACT,),
        (("docs/concepts/cache.md#clearing-the-cache/0", 3),),
        "Three commands one section apart, and the answer is the contrast between two of them.",
    ),
    (
        "u-1133",
        "UV_LOCK_TIMEOUT",
        (EvalSlice.EXACT,),
        (("docs/concepts/cache.md#clearing-the-cache/0", 3),),
        "A literal in the last paragraph of a section about something else, with the "
        "default it changes stated beside it.",
    ),
    (
        "u-1134",
        "what should a CI job run at the end to keep its cache worth restoring",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/cache.md#caching-in-continuous-integration/0", 3),
            ("docs/guides/integration/github.md#caching/0", 2),
        ),
        "The concept document argues which artifacts are worth keeping; the guide shows "
        "the step that does it.",
    ),
    (
        "u-1135",
        "why does it matter which filesystem the cache is on",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/cache.md#cache-directory/0", 3),),
        "A performance consequence - links become copies - stated in the last paragraph "
        "of a section about lookup order.",
    ),
    (
        "u-1136",
        "can two different versions of uv share a cache directory",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/cache.md#cache-versioning/0", 3),
            ("docs/reference/policies/versioning.md#cache-versioning/0", 1),
        ),
        "A yes with a qualification about buckets; the policy document only says the "
        "cache version may change in any release.",
    ),
    (
        "u-1137",
        "how do I make uv re-check one package instead of clearing everything",
        (EvalSlice.FACT,),
        (("docs/concepts/cache.md#dependency-caching/0", 3),),
        "Four escape hatches in one list, and the question asks for the narrowest.",
    ),
    # --- tools: running them, installing them, and what that leaves behind ---
    (
        "u-1138",
        "when should I install a tool rather than just run it",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/tools.md#execution-vs-installation/0", 3),),
        "A recommendation with its two exceptions, in 74 tokens.",
    ),
    (
        "u-1139",
        "where does the environment for a tool run with uvx live",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/tools.md#tool-environments/0", 3),
            ("docs/reference/storage.md#types-of-data/tools/0", 2),
        ),
        "The concepts document says which of the two environments is disposable; the "
        "storage reference gives the directory for the other one.",
    ),
    (
        "u-1140",
        "why does uvx keep running an old version of a tool",
        (EvalSlice.FACT,),
        (("docs/concepts/tools.md#tool-versions/0", 3),),
        "Caching behaviour with three ways out - `@latest`, a pruned cache, "
        "`--isolated` - in a long section.",
    ),
    (
        "u-1141",
        "uv tool upgrade",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/tools.md#upgrading-tools/0", 3),),
        "The section that documents the command, including the constraint it respects "
        "from the original install.",
    ),
    (
        "u-1142",
        "what happens if a tool would overwrite an executable that is already there",
        (EvalSlice.FACT,),
        (("docs/concepts/tools.md#tool-executables/overwriting-executables/0", 3),),
        "A 53-token subsection that is the whole answer, under a section about paths.",
    ),
    (
        "u-1143",
        "how do I run a tool with an extra package available to it",
        (EvalSlice.FACT,),
        (("docs/concepts/tools.md#including-additional-dependencies/0", 3),),
        "A flag that is repeated per package, shown with a plugin example.",
    ),
    (
        "u-1144",
        "how is running a tool different from uv run --with",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/tools.md#relationship-to-uv-run/0", 3),
            ("docs/concepts/tools.md#the-uv-tool-interface/0", 2),
        ),
        "A section written to answer exactly this, and the section that defines the "
        "interface it is being compared with.",
    ),
    (
        "u-1145",
        "how do I run a tool under a particular Python version",
        (EvalSlice.FACT,),
        (("docs/concepts/tools.md#python-versions/0", 3),),
        "One option, and what it does to a cached tool environment.",
    ),
    (
        "u-1146",
        "uv tool update-shell",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/tools.md#tool-executables/0", 3),
            ("docs/getting-started/features.md#tools/0", 1),
        ),
        "The command is documented in the section about the executable directory and "
        "listed once in the feature list (ADR-0062's tiers).",
    ),
    # --- locking and syncing ---
    (
        "u-1147",
        "how do I make a command fail instead of quietly updating the lockfile",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/projects/sync.md#automatic-lock-and-sync/0", 3),
            ("docs/concepts/projects/sync.md#checking-the-lockfile/0", 2),
        ),
        "Three flags that sound alike - `--locked`, `--frozen`, `--no-sync` - and the "
        "section next door gives the standalone check.",
    ),
    (
        "u-1148",
        "how do I keep packages that are not in the lockfile when syncing",
        (EvalSlice.FACT,),
        (
            (
                "docs/concepts/projects/sync.md"
                "#syncing-the-environment/handling-of-extraneous-packages/0",
                3,
            ),
        ),
        "One flag, and the fact that two commands default the opposite way.",
    ),
    (
        "u-1149",
        "which commands change the lockfile without being asked to",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/sync.md#automatic-lock-and-sync/0", 3),
            ("docs/concepts/projects/layout.md#the-lockfile/0", 2),
        ),
        "The sync document names the commands; the layout document says the lockfile is "
        "created and updated by them, which is the half that makes it an answer.",
    ),
    (
        "u-1150",
        "how do I install every extra a project declares",
        (EvalSlice.FACT,),
        (
            (
                "docs/concepts/projects/sync.md"
                "#syncing-the-environment/syncing-optional-dependencies/0",
                3,
            ),
        ),
        "A default of none, one flag per extra, and a shorthand for all of them.",
    ),
    (
        "u-1151",
        "if I both include and exclude a dependency group, which one wins",
        (EvalSlice.FACT,),
        (
            (
                "docs/concepts/projects/sync.md"
                "#syncing-the-environment/syncing-development-dependencies/0",
                3,
            ),
        ),
        "A precedence rule at the end of a long section, with the command that shows it.",
    ),
    (
        "u-1152",
        "--no-install-project",
        (EvalSlice.EXACT,),
        (("docs/concepts/projects/sync.md#partial-installations/0", 3),),
        "One of three related flags, in the section that also states the shared rule: "
        "dependencies are still installed.",
    ),
    (
        "u-1153",
        "can uv check my dependencies against known malware",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/sync.md#malware-checks/0", 3),),
        "A preview feature, which database it checks, and what happens on a match.",
    ),
    (
        "u-1154",
        "UV_MALWARE_CHECK",
        (EvalSlice.EXACT,),
        (("docs/concepts/projects/sync.md#malware-checks/0", 3),),
        "The environment form of a setting that appears nowhere else in the corpus.",
    ),
    # --- running commands in a project ---
    (
        "u-1155",
        "how do I run something with an extra dependency just this once",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/run.md#requesting-additional-dependencies/0", 3),),
        "A flag whose section states the part that surprises people: the requested "
        "version wins over the project's own requirement.",
    ),
    (
        "u-1156",
        "does uv pass Ctrl-C through to the command it started",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/run.md#signal-handling/0", 3),),
        "A rule with exceptions on both operating systems, and the question asks it in "
        "the words a user would use rather than in signal names.",
    ),
    (
        "u-1157",
        "which Windows script extensions can uv run execute",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/run.md#legacy-scripts-on-windows/0", 3),),
        "Three extensions, in the order they are tried, in a section nothing links to.",
    ),
    (
        "u-1158",
        "why does a script with inline metadata not see my project's packages",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/projects/run.md#running-scripts/0", 3),
            ("docs/guides/scripts.md#declaring-script-dependencies/0", 2),
        ),
        "The isolation rule is one sentence in the project document; the guide explains "
        "the metadata block it is triggered by.",
    ),
    # --- workspaces ---
    (
        "u-1159",
        "how do I run a command for one member of a workspace",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/workspaces.md#/0", 3),),
        "An option named in the document's opening, where the commands that accept it "
        "are also listed.",
    ),
    (
        "u-1160",
        "when is a workspace the wrong way to organise a repository",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/projects/workspaces.md#when-not-to-use-workspaces/0", 3),),
        "A section that argues against its own document, and names path dependencies as "
        "the alternative.",
    ),
    (
        "u-1161",
        "how do I add a package to an existing workspace",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/workspaces.md#getting-started/0", 3),),
        "A worked sequence: the member's own pyproject, the members list, and the "
        "source entry that points at it.",
    ),
    (
        "u-1162",
        "how does one workspace member depend on another",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/projects/workspaces.md#workspace-sources/0", 3),
            ("docs/concepts/projects/dependencies.md#dependency-sources/workspace-member/0", 2),
        ),
        "The workspace document works the example; the dependency document states the "
        "rule - every member must be stated explicitly, and members are editable.",
    ),
    (
        "u-1163",
        "what directory layouts does uv suggest for a workspace",
        (EvalSlice.FACT,),
        (("docs/concepts/projects/workspaces.md#workspace-layouts/0", 3),),
        "Two shapes, and the note that the root may be a member or not.",
    ),
    # --- Python versions: installing them, finding them, preferring them ---
    (
        "u-1164",
        "uv python install",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/python-versions.md#installing-a-python-version/0", 3),
            ("docs/getting-started/features.md#python-versions/0", 1),
        ),
        "The section that documents the command - five request shapes and the frozen "
        "download list - against the feature list's one line (ADR-0062).",
    ),
    (
        "u-1165",
        "uv python list",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/python-versions.md#viewing-available-python-versions/0", 3),
            ("docs/getting-started/features.md#python-versions/0", 1),
        ),
        "Its own section, with the four flags that widen what the listing shows.",
    ),
    (
        "u-1166",
        "uv python find",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/python-versions.md#finding-a-python-executable/0", 3),
            ("docs/getting-started/features.md#python-versions/0", 1),
        ),
        "Documented with the one behaviour that surprises: a virtual environment takes "
        "precedence over the `PATH`.",
    ),
    (
        "u-1167",
        "uv python upgrade",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/python-versions.md#upgrading-python-versions/0", 3),),
        "A command whose section is mostly about what it will *not* do - minor versions, "
        "PyPy, GraalPy, Pyodide.",
    ),
    (
        "u-1168",
        "uv python dir",
        (EvalSlice.SYMBOL,),
        (
            ("docs/reference/storage.md#types-of-data/python-versions/0", 3),
            ("docs/getting-started/features.md#utility/0", 1),
        ),
        "The storage reference documents it beside the variable that overrides the "
        "directory it prints.",
    ),
    (
        "u-1169",
        "UV_PYTHON_INSTALL_DIR",
        (EvalSlice.EXACT,),
        (
            ("docs/reference/storage.md#types-of-data/python-versions/0", 3),
            ("docs/concepts/python-versions.md#discovery-of-python-versions/0", 2),
        ),
        "The storage reference documents the variable and the warning that comes with "
        "changing it; the discovery list names it as the first place uv looks.",
    ),
    (
        "u-1170",
        "UV_PYTHON_BIN_DIR",
        (EvalSlice.EXACT,),
        (("docs/reference/storage.md#types-of-data/python-executables/0", 3),),
        "The sibling variable, one subsection later, for the executables rather than "
        "the installations.",
    ),
    (
        "u-1171",
        "python-preference",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/python-versions.md#adjusting-python-version-preferences/0", 3),
            (
                "docs/concepts/python-versions.md#requiring-or-disabling-managed-python-versions/0",
                2,
            ),
        ),
        "A setting with four values documented in one section, and pointed at from the "
        "section that gives two of them command-line equivalents.",
    ),
    (
        "u-1172",
        "--managed-python",
        (EvalSlice.EXACT,),
        (
            (
                "docs/concepts/python-versions.md#requiring-or-disabling-managed-python-versions/0",
                3,
            ),
            ("docs/concepts/python-versions.md#adjusting-python-version-preferences/0", 2),
        ),
        "The flag's own section, and the setting section that says which value it is "
        "equivalent to.",
    ),
    (
        "u-1173",
        ".python-versions",
        (EvalSlice.EXACT,),
        (("docs/concepts/python-versions.md#installing-a-python-version/0", 3),),
        "A filename one letter away from a much more common one, mentioned once, and "
        "only the plural form answers this.",
    ),
    (
        "u-1174",
        "why can uv upgrade Python from 3.13.4 to 3.13.5 but not 3.12 to 3.13",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/python-versions.md#upgrading-python-versions/0", 3),),
        "The reason is about dependency resolution, not about Python, which is what "
        "makes it a reasoning question.",
    ),
    (
        "u-1175",
        "how does an existing virtual environment pick up an upgraded Python",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/concepts/python-versions.md#upgrading-python-versions/minor-version-directories/0",
                3,
            ),
            ("docs/concepts/python-versions.md#upgrading-python-versions/0", 2),
        ),
        "A symlink indirection, and the case where it silently does not apply - an "
        "environment created against an exact patch version.",
    ),
    (
        "u-1176",
        "which Python does a project command use if I do not ask for one",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/python-versions.md#project-python-versions/0", 3),
            ("docs/concepts/python-versions.md#discovery-of-python-versions/0", 2),
        ),
        "The project rule - the first version compatible with `requires-python` - and "
        "the discovery order that decides what 'first' means.",
    ),
    (
        "u-1177",
        "will uv use a pre-release Python",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/python-versions.md#python-pre-releases/0", 3),),
        "A conditional no, and the condition is the whole answer.",
    ),
    (
        "u-1178",
        "what is a debug build of Python for, and what does uv do with one",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/python-versions.md#debug-python-variants/0", 3),),
        "The selection rule and the note about stripped symbols, which is the reason "
        "anyone wants one.",
    ),
    (
        "u-1179",
        "how do I see Python downloads for a platform I am not on",
        (EvalSlice.FACT,),
        (("docs/concepts/python-versions.md#viewing-available-python-versions/0", 3),),
        "One flag among four, and the default that hides them.",
    ),
    (
        "u-1180",
        "how do I make uv ignore the active virtual environment when finding Python",
        (EvalSlice.FACT,),
        (("docs/concepts/python-versions.md#finding-a-python-executable/0", 3),),
        "A flag whose name says `system` while the question asks about a virtualenv.",
    ),
    (
        "u-1181",
        "where does uv look for an interpreter, and which one does it settle on",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/python-versions.md#discovery-of-python-versions/0", 3),
            ("docs/pip/environments.md#discovery-of-python-environments/0", 2),
        ),
        "Two discovery orders in two documents - one for installations, one for "
        "environments - and the concepts page says when the second takes over.",
    ),
    (
        "u-1182",
        "how do I get a plain python executable installed rather than python3.12",
        (EvalSlice.FACT,),
        (
            (
                "docs/concepts/python-versions.md"
                "#installing-a-python-version/installing-python-executables/0",
                3,
            ),
        ),
        "An experimental flag, plus the rule about overwriting executables uv does not manage.",
    ),
    (
        "u-1183",
        "why did installing an older patch version not change the python3.12 command",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/concepts/python-versions.md"
                "#installing-a-python-version/installing-python-executables/0",
                3,
            ),
        ),
        "Three commands and their effects, written as a worked example rather than as a "
        "rule - the reader has to read the comments to get the answer.",
    ),
    (
        "u-1184",
        "how do I insist on the GIL-enabled build when both variants are installed",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/python-versions.md#free-threaded-python/0", 3),
            ("docs/concepts/python-versions.md#requesting-a-version/0", 2),
        ),
        "The `+gil` specifier is named in the free-threaded section; the request-format "
        "list is where the shape of such a specifier is defined.",
    ),
    # --- package indexes: priority, credentials, caching, errors ---
    (
        "u-1185",
        "which index does uv consult first when several are configured",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/indexes.md#defining-an-index/", 3),),
        "Two rules that interact - definition order, and the default index always being "
        "lowest - and the second is the one a reader gets wrong.",
    ),
    (
        "u-1186",
        "how do I stop uv from falling back to PyPI",
        (EvalSlice.FACT,),
        (("docs/concepts/indexes.md#defining-an-index/", 3),),
        "A setting on *another* index entry removes PyPI, which is not where anyone looks for it.",
    ),
    (
        "u-1187",
        "UV_INDEX_STRATEGY",
        (EvalSlice.EXACT,),
        (("docs/concepts/indexes.md#searching-across-multiple-indexes/0", 3),),
        "The environment form of the option whose three values are the section's "
        "subject, with the attack the default exists to prevent.",
    ),
    (
        "u-1188",
        "how do I give uv a username and password for a private index without writing "
        "them in a file",
        (EvalSlice.FACT,),
        (("docs/concepts/indexes.md#authentication/providing-credentials-directly/0", 3),),
        "The variable name is derived from the index name by a rule the section states, "
        "which is the part that cannot be guessed.",
    ),
    (
        "u-1189",
        "why does uv try an unauthenticated request first",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/indexes.md#authentication/using-credential-providers/0", 3),
            ("docs/concepts/authentication/http.md#/0", 2),
        ),
        "The order is stated in the indexes document, with the GitLab case that breaks "
        "it; the authentication document frames the provider search it triggers.",
    ),
    (
        "u-1190",
        'authenticate = "always"',
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/indexes.md#authentication/using-credential-providers/0", 3),
            ("docs/concepts/indexes.md#authentication/disabling-authentication/0", 2),
        ),
        "One setting with two values documented in two subsections; the question names "
        "the value that eagerly searches.",
    ),
    (
        "u-1191",
        "how do I keep uv from sending credentials to a particular index",
        (EvalSlice.FACT,),
        (("docs/concepts/indexes.md#authentication/disabling-authentication/0", 3),),
        "The opposite value of the setting above, and what uv does if credentials are "
        "supplied anyway.",
    ),
    (
        "u-1192",
        "ignore-error-codes",
        (EvalSlice.EXACT,),
        (("docs/concepts/indexes.md#authentication/ignoring-error-codes/0", 3),),
        "A setting whose section also states the two codes that stop a search and the "
        "one that never does.",
    ),
    (
        "u-1193",
        "why does uv stop searching other indexes when one returns 403",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/indexes.md#authentication/ignoring-error-codes/0", 3),),
        "A behaviour with a named exception - the pytorch index - which is the detail "
        "that makes the section the answer rather than the setting reference.",
    ),
    (
        "u-1194",
        "cache-control",
        (EvalSlice.EXACT,),
        (("docs/concepts/indexes.md#authentication/customizing-cache-control-headers/0", 3),),
        "A per-index setting with two keys and a recommended pair of values, for the "
        "case where a private index disables caching by accident.",
    ),
    (
        "u-1195",
        "hash-algorithm",
        (EvalSlice.EXACT,),
        (("docs/concepts/indexes.md#authentication/requiring-a-hash-algorithm/0", 3),),
        "A preview-gated setting, and the failure it produces rather than falling back.",
    ),
    (
        "u-1196",
        "how do I use a different exclude-newer cutoff for one index",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/indexes.md#authentication/configuring-exclude-newer-for-an-index/0", 3),
            ("docs/concepts/resolution.md#reproducible-resolutions/0", 2),
        ),
        "The per-index form, including how to switch the cutoff off for an index with "
        "no upload-time metadata; the resolution document defines the setting itself.",
    ),
    (
        "u-1197",
        "how do I use a directory of wheels as an index",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/indexes.md#flat-indexes/0", 3),
            ("docs/concepts/cache.md#dependency-caching/0", 1),
        ),
        'The `format = "flat"` entry, and the pip option it corresponds to; the cache '
        "document mentions such indexes only to say their contents are assumed "
        "immutable.",
    ),
    (
        "u-1198",
        "how do --index-url and --extra-index-url map onto uv's own options",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/indexes.md#index-url-and-extra-index-url/0", 3),
            ("docs/concepts/indexes.md#defining-an-index/", 2),
        ),
        "A compatibility mapping stated in one section, and the priority rules it says "
        "it follows, which are defined in another.",
    ),
    (
        "u-1199",
        "where must a named index be defined for tool.uv.sources to see it",
        (EvalSlice.FACT,),
        (("docs/concepts/indexes.md#pinning-a-package-to-an-index/0", 3),),
        "A restriction in the last paragraph of a section about pinning: the project's "
        "own file, not the command line or user-level configuration.",
    ),
    # --- authentication: the CLI, HTTP credentials, Git, certificates ---
    (
        "u-1200",
        "uv auth login",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/authentication/cli.md#logging-in-to-a-service/", 3),
            ("docs/concepts/authentication/http.md#the-uv-credentials-store/0", 2),
        ),
        "The section that documents the command, including the two things it does not "
        "do - validate the credentials, or use them for Git - against the section that "
        "says where what it writes ends up.",
    ),
    (
        "u-1201",
        "uv auth logout",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/authentication/cli.md#logging-out-of-a-service/0", 3),),
        "A 55-token section whose note is the answer's real content: the credential is "
        "removed locally, not invalidated remotely.",
    ),
    (
        "u-1202",
        "uv auth token",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/authentication/cli.md#showing-credentials-for-a-service/0", 3),),
        "A command whose name collides with the `--token` option of its sibling, so a "
        "term match is not enough to find the right section.",
    ),
    (
        "u-1203",
        "uv auth helper",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/authentication/cli.md#using-credentials-with-external-tools/0", 3),
            ("docs/guides/integration/bazel.md#authentication/0", 2),
        ),
        "A command meant to be called by another program: the concepts page documents "
        "the protocol, the Bazel guide wires it up.",
    ),
    (
        "u-1204",
        "how do I pass a password to uv without it landing in my shell history",
        (EvalSlice.FACT,),
        (("docs/concepts/authentication/cli.md#logging-in-to-a-service/", 3),),
        "The `-` convention for reading a secret from stdin, in a note rather than in "
        "the option list.",
    ),
    (
        "u-1205",
        "where does uv keep the credentials it stores",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/authentication/http.md#the-uv-credentials-store/0", 3),
            ("docs/concepts/authentication/cli.md#configuring-the-storage-backend/0", 2),
        ),
        "A path, the fact that it is plaintext, and the preview feature that replaces "
        "it with the operating system's own store.",
    ),
    (
        "u-1206",
        "in what order does uv look for HTTP credentials",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/authentication/http.md#/0", 3),),
        "A four-item precedence list in a document preamble, which is where a reader "
        "least expects the answer to be.",
    ),
    (
        "u-1207",
        "NETRC",
        (EvalSlice.EXACT,),
        (("docs/concepts/authentication/http.md#netrc-files/0", 3),),
        "A variable whose section states the fallback path when it is unset, and that "
        "reading the file is always on.",
    ),
    (
        "u-1208",
        "--keyring-provider",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/authentication/http.md#keyring-providers/0", 3),
            ("docs/concepts/indexes.md#authentication/using-credential-providers/0", 2),
        ),
        "One supported value and three ways to set it; the indexes document names the "
        "provider search without saying how to turn it on.",
    ),
    (
        "u-1209",
        "does uv remember an index password between commands",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/authentication/http.md#persistence-of-credentials/0", 3),),
        "Cached within one invocation, never across them - and the exception for direct "
        "URLs is the half that matters for safety.",
    ),
    (
        "u-1210",
        "how do I install from a private git repository over SSH",
        (EvalSlice.FACT,),
        (("docs/concepts/authentication/git.md#ssh-authentication/0", 3),),
        "Two URL shapes and the requirement that the username be `git`.",
    ),
    (
        "u-1211",
        "how do I use a personal access token for a private git dependency",
        (EvalSlice.FACT,),
        (("docs/concepts/authentication/git.md#ssh-authentication/http-authentication/0", 3),),
        "Three URL shapes, and the note that the username beside a GitHub token is "
        "arbitrary - which is what a reader is actually unsure about.",
    ),
    (
        "u-1212",
        "--raw",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/authentication/git.md#persistence-of-credentials/0", 3),
            ("docs/concepts/authentication/http.md#persistence-of-credentials/0", 2),
        ),
        "A flag documented in the Git document, in the paragraph that recommends not "
        "using it; the HTTP document states the same rule without the flag.",
    ),
    (
        "u-1213",
        "why does a git dependency work on my machine and fail in CI",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/authentication/git.md#persistence-of-credentials/0", 3),
            ("docs/concepts/authentication/git.md#git-credential-helpers/0", 2),
        ),
        "The answer is a credential helper that exists locally and not on the other "
        "machine; the second section is how to set one up, including the step "
        "`gh auth login --with-token` leaves out.",
    ),
    (
        "u-1214",
        "how do I make uv trust our corporate proxy's certificate",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/authentication/certificates.md#system-certificates/0", 3),
            ("docs/concepts/authentication/certificates.md#custom-certificates/0", 2),
        ),
        "Two routes - the platform's store, or a PEM bundle - in adjacent sections, and "
        "the question describes the situation rather than naming either.",
    ),
    (
        "u-1215",
        "SSL_CERT_DIR",
        (EvalSlice.EXACT,),
        (("docs/concepts/authentication/certificates.md#custom-certificates/0", 3),),
        "A variable whose section carries the rules that decide whether a file in it is "
        "read at all - extensions, symlinks, DER.",
    ),
    (
        "u-1216",
        "which TLS implementation does uv use",
        (EvalSlice.FACT,),
        (("docs/concepts/authentication/certificates.md#tls-backend/0", 3),),
        "A name, a cryptography provider and a list of signature algorithms.",
    ),
    (
        "u-1217",
        "how do I let uv talk to an index with a self-signed certificate",
        (EvalSlice.FACT,),
        (("docs/concepts/authentication/certificates.md#insecure-hosts/0", 3),),
        "An escape hatch with a warning attached, in the section a reader reaches last.",
    ),
    (
        "u-1218",
        "HF_TOKEN",
        (EvalSlice.EXACT,),
        (("docs/concepts/authentication/third-party.md#hugging-face-support/0", 3),),
        "A third-party variable uv propagates automatically, and the variable that "
        "switches that off.",
    ),
    (
        "u-1219",
        "which guides cover authenticating to a hosted private index",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/concepts/authentication/third-party.md"
                "#authentication-with-alternative-package-indexes/0",
                3,
            ),
            ("docs/concepts/indexes.md#authentication/0", 2),
        ),
        "A pointer list in the concepts tree, and the indexes document's own tip "
        "naming the same four providers. The grade-3 anchor is 27 tokens and the "
        "stub lint flags it: kept deliberately, because the four names *are* the "
        "answer - the `## License` case the lint's docstring describes.",
    ),
    # --- configuration files, and the uv build backend ---
    (
        "u-1220",
        "which file wins if a directory has both uv.toml and pyproject.toml",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/configuration-files.md#/0", 3),),
        "A precedence rule in a note, inside a long preamble that also carries the "
        "project/user/system merge order.",
    ),
    (
        "u-1221",
        "--config-file",
        (EvalSlice.EXACT,),
        (("docs/concepts/configuration-files.md#/0", 3),),
        "A flag whose effect is total - it replaces every discovered file, not just the "
        "project's - which is stated in the last line of the section.",
    ),
    (
        "u-1222",
        "UV_ENV_FILE",
        (EvalSlice.EXACT,),
        (("docs/concepts/configuration-files.md#environment-variable-files/0", 3),),
        "A variable with an unusual separator rule for multiple paths, and a second "
        "variable that disables it.",
    ),
    (
        "u-1223",
        "how do I load variables from a .env file when running a command",
        (EvalSlice.FACT,),
        (("docs/concepts/configuration-files.md#environment-variable-files/0", 3),),
        "The flag, the repeat behaviour, and which value wins against the real environment.",
    ),
    (
        "u-1224",
        "does a tool command read the configuration in my project directory",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/configuration-files.md#/0", 3),),
        "A no in a note near the top: `tool` commands are user-level and read only "
        "user- and system-level files.",
    ),
    (
        "u-1225",
        "what does the tool.uv.pip section configure that the top level does not",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/configuration-files.md#configuring-the-pip-interface/0", 3),
            ("docs/concepts/configuration-files.md#/0", 2),
        ),
        "A scoped section with a fallback relationship to the global one; the preamble "
        "is where the file's own precedence rules are defined.",
    ),
    (
        "u-1226",
        "uv_build",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/build-backend.md#using-the-uv-build-backend/0", 3),
            ("docs/concepts/build-backend.md#/0", 2),
            ("docs/concepts/projects/config.md#build-systems/0", 1),
        ),
        "The backend's package name: the section that shows how to declare it, the "
        "preamble that says what it is, and the projects document that mentions it as "
        "the default `uv init` chooses (ADR-0062's tiers).",
    ),
    (
        "u-1227",
        "when is the uv build backend the wrong choice",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/build-backend.md#choosing-a-build-backend/0", 3),),
        "A recommendation that names its own two limits - pure Python only, and build "
        "scripts - and the backend to use instead.",
    ),
    (
        "u-1228",
        "why should the uv_build requirement have an upper bound",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/build-backend.md#using-the-uv-build-backend/0", 3),
            ("docs/reference/policies/versioning.md#/0", 2),
        ),
        "The advice is in a note; the reason it works is the versioning policy the note "
        "links to, where breaking changes are minor releases.",
    ),
    (
        "u-1229",
        "is the build backend inside the uv binary or a separate package",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/build-backend.md#bundled-build-backend/0", 3),),
        "Both, with a rule for which one is used and an exception for other frontends.",
    ),
    (
        "u-1230",
        "module-root",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/build-backend.md#modules/0", 3),
            ("docs/concepts/build-backend.md#file-inclusion-and-exclusion/0", 2),
        ),
        "A setting documented where the default module layout is explained, and "
        "referenced where it decides what goes into a distribution.",
    ),
    (
        "u-1231",
        "how does the build backend turn my package name into a module name",
        (EvalSlice.FACT,),
        (("docs/concepts/build-backend.md#modules/0", 3),),
        "A normalisation rule - lowercase, dots and dashes to underscores - with an "
        "example, in the middle of a section about layout.",
    ),
    (
        "u-1232",
        "how do I package a module into a shared namespace",
        (EvalSlice.FACT,),
        (("docs/concepts/build-backend.md#namespace-packages/0", 3),),
        "A dotted `module-name`, the missing `__init__.py`, and the warning attached to "
        "the shortcut that avoids listing modules.",
    ),
    (
        "u-1233",
        "how do I build a type stub package",
        (EvalSlice.FACT,),
        (("docs/concepts/build-backend.md#stub-packages/0", 3),),
        "Three rules in a short section: the suffix, the suppressed normalisation, and "
        "the `.pyi` file it looks for.",
    ),
    (
        "u-1234",
        "if a file matches both an include and an exclude, which wins",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/build-backend.md#file-inclusion-and-exclusion/0", 3),),
        "A precedence rule stated once, in a section whose bulk is two long lists.",
    ),
    (
        "u-1235",
        "how do I include every file under a directory in the source distribution",
        (EvalSlice.FACT,),
        (
            (
                "docs/concepts/build-backend.md#file-inclusion-and-exclusion/include-and-exclude-syntax/0",
                3,
            ),
            ("docs/concepts/build-backend.md#file-inclusion-and-exclusion/0", 2),
        ),
        "The anchoring rule and the `/**` suffix, in a subsection below the lists that "
        "say which settings take these patterns.",
    ),
    (
        "u-1236",
        "how do I see what the build backend is doing when pip calls it",
        (EvalSlice.FACT,),
        (("docs/concepts/build-backend.md#file-inclusion-and-exclusion/0", 3),),
        "An environment variable in a tip at the end of a long section, and it is the "
        "only place in the corpus that says how to debug the backend under another "
        "frontend.",
    ),
    # --- the pip interface: environments, packages, locking ---
    (
        "u-1237",
        "uv pip list",
        (EvalSlice.SYMBOL,),
        (
            ("docs/pip/inspection.md#listing-installed-packages/0", 3),
            ("docs/getting-started/features.md#the-pip-interface/0", 1),
        ),
        "The section that documents the command, beside its JSON flag and the sibling "
        "that prints requirements format; the feature list names it once.",
    ),
    (
        "u-1238",
        "uv pip freeze",
        (EvalSlice.SYMBOL,),
        (
            ("docs/pip/inspection.md#listing-installed-packages/0", 3),
            ("docs/getting-started/features.md#the-pip-interface/0", 1),
        ),
        "Documented in the same section as `uv pip list`, which is what makes the "
        "discrimination hard: one heading covers two commands.",
    ),
    (
        "u-1239",
        "uv pip show",
        (EvalSlice.SYMBOL,),
        (
            ("docs/pip/inspection.md#inspecting-a-package/0", 3),
            ("docs/getting-started/features.md#the-pip-interface/0", 1),
        ),
        "A 31-token section that is the command's whole documentation.",
    ),
    (
        "u-1240",
        "uv pip check",
        (EvalSlice.SYMBOL,),
        (
            ("docs/pip/inspection.md#verifying-an-environment/0", 3),
            ("docs/pip/compatibility.md#pip-check/0", 2),
            ("docs/getting-started/features.md#the-pip-interface/0", 1),
        ),
        "Its own section says what it is for; the compatibility page says where it "
        "differs from pip's, which is the tier-2 framing.",
    ),
    (
        "u-1241",
        "uv pip sync",
        (EvalSlice.SYMBOL,),
        (
            ("docs/pip/compile.md#syncing-an-environment/0", 3),
            ("docs/pip/compatibility.md#virtual-environments-by-default/0", 2),
        ),
        "The section that documents it states the difference from `uv pip install` - "
        "exact against additive - which is the reason to use it.",
    ),
    (
        "u-1242",
        "uv pip compile",
        (EvalSlice.SYMBOL,),
        (
            ("docs/pip/compile.md#locking-requirements/0", 3),
            ("docs/pip/compatibility.md#pip-compile-defaults/0", 2),
            ("docs/getting-started/features.md#the-pip-interface/0", 1),
        ),
        "Its documentation, the page that lists where its defaults differ from "
        "pip-tools', and the feature list (ADR-0062's three tiers).",
    ),
    (
        "u-1243",
        "uv venv",
        (EvalSlice.SYMBOL,),
        (
            ("docs/pip/environments.md#creating-a-virtual-environment/0", 3),
            ("docs/pip/environments.md#using-a-virtual-environment/0", 2),
        ),
        "The dev set judges this query against the feature list; here it is judged "
        "against the section that documents it and the one that frames what an "
        "environment is for.",
    ),
    (
        "u-1244",
        "how do I install a package from a git branch with the pip interface",
        (EvalSlice.FACT,),
        (("docs/pip/packages.md#installing-a-package/0", 3),),
        "Three reference shapes - tag, commit, branch - at the end of a long list of "
        "install forms.",
    ),
    (
        "u-1245",
        "how do I install a dependency group with uv pip",
        (EvalSlice.FACT,),
        (
            ("docs/pip/packages.md#installing-packages-from-files/0", 3),
            ("docs/pip/compile.md#locking-requirements/0", 2),
        ),
        "A flag that appears in two documents for two commands; the compile section "
        "carries the caveat about which pyproject.toml a group is sourced from.",
    ),
    (
        "u-1246",
        "how do I lock requirements from more than one input file",
        (EvalSlice.FACT,),
        (("docs/pip/compile.md#locking-requirements/0", 3),),
        "One of nine invocation shapes in a single section, including reading from stdin.",
    ),
    (
        "u-1247",
        "why did my compile not upgrade a package that has a newer version",
        (EvalSlice.CONCEPTUAL,),
        (("docs/pip/compile.md#upgrading-requirements/0", 3),),
        "A behaviour shown by a worked example - an existing output file pins - with "
        "the two flags that override it.",
    ),
    (
        "u-1248",
        "what is the difference between a constraint file and an overrides file",
        (EvalSlice.RELATIONSHIP, EvalSlice.CONCEPTUAL),
        (
            ("docs/pip/compile.md#adding-constraints/0", 3),
            ("docs/pip/compile.md#overriding-dependency-versions/0", 3),
        ),
        "Additive against absolute: each section defines its own half and the overrides "
        "section states the contrast, so neither alone is the answer.",
    ),
    (
        "u-1249",
        "build-constraint-dependencies",
        (EvalSlice.EXACT,),
        (
            ("docs/pip/compile.md#adding-build-constraints/0", 3),
            ("docs/concepts/projects/build.md#build-constraints/0", 2),
        ),
        "A workspace-root setting named once, in the section that explains what a build "
        "constraint is; the projects document shows the flag form.",
    ),
    (
        "u-1250",
        "where does uv pip install put packages if no environment is active",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/pip/compatibility.md#virtual-environments-by-default/0", 3),
            ("docs/pip/environments.md#discovery-of-python-environments/0", 2),
        ),
        "The compatibility page states the inverted default and the two opt-outs; the "
        "environments page gives the search order that finds the `.venv`.",
    ),
    (
        "u-1251",
        "how do I install into a Python environment that uv did not create",
        (EvalSlice.FACT,),
        (("docs/pip/environments.md#using-arbitrary-python-environments/0", 3),),
        "A long section about targeting an interpreter by path, and the warnings that "
        "come with targeting a system one.",
    ),
    (
        "u-1252",
        "why does uv require a virtual environment when pip does not",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/pip/environments.md#/0", 3),
            ("docs/pip/compatibility.md#virtual-environments-by-default/0", 2),
        ),
        "The environments preamble argues the practice; the compatibility page states "
        "it as a deliberate difference with an opt-in escape.",
    ),
    (
        "u-1253",
        "how do I activate a uv-created environment in fish",
        (EvalSlice.FACT,),
        (("docs/pip/environments.md#using-a-virtual-environment/0", 3),),
        "A shell-specific activation script in a note, under a section that shows the "
        "POSIX one first.",
    ),
    (
        "u-1254",
        "is the uv pip interface actually running pip",
        (EvalSlice.CONCEPTUAL,),
        (("docs/pip/index.md#/0", 3),),
        "A no, stated in an admonition, together with why the interface is named after "
        "a tool it does not invoke.",
    ),
    (
        "u-1255",
        "where should I declare dependencies if I am not using a project",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/pip/dependencies.md#using-requirements-in/0", 3),
            ("docs/pip/dependencies.md#using-pyproject-toml/0", 2),
        ),
        "Two formats in one document, and the answer is which of them the pip interface "
        "leaves you - including the limitation that groups are not supported there.",
    ),
    # --- the project and packaging guides: the commands a reader meets first ---
    (
        "u-1256",
        "uv add",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/projects/dependencies.md#adding-dependencies/0", 3),
            ("docs/guides/projects.md#managing-dependencies/0", 2),
            ("docs/getting-started/features.md#projects/0", 1),
        ),
        "The concepts section documents it, the guide walks it, the feature list names "
        "it - the three tiers ADR-0062 set out.",
    ),
    (
        "u-1257",
        "uv remove",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/projects/dependencies.md#removing-dependencies/0", 3),
            ("docs/guides/projects.md#managing-dependencies/0", 2),
            ("docs/getting-started/features.md#projects/0", 1),
        ),
        "The same shape as its sibling, and the documenting section is 63 tokens - "
        "short, and still the only place the source-removal rule is stated.",
    ),
    (
        "u-1258",
        "uv sync",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/projects/sync.md#syncing-the-environment/0", 3),
            ("docs/concepts/projects/sync.md#automatic-lock-and-sync/0", 2),
            ("docs/getting-started/features.md#projects/0", 1),
        ),
        "A command most readers meet as something that happens to them; the section "
        "that documents the explicit form is short and easy to rank below the framing.",
    ),
    (
        "u-1259",
        "uv lock",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/projects/sync.md#creating-the-lockfile/0", 3),
            ("docs/concepts/projects/layout.md#the-lockfile/0", 2),
            ("docs/getting-started/features.md#projects/0", 1),
        ),
        "The documenting section is 26 tokens; what the lockfile *is* lives in another "
        "document, which is exactly the discrimination a symbol query has to make.",
    ),
    (
        "u-1260",
        "uv run",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/projects/run.md#/0", 3),
            ("docs/guides/projects.md#running-commands/0", 2),
            ("docs/getting-started/features.md#projects/0", 1),
        ),
        "The command with the most mentions in the corpus, and only one section documents it.",
    ),
    (
        "u-1261",
        "uv build",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/projects/build.md#using-uv-build/0", 3),
            ("docs/guides/package.md#building-your-package/0", 2),
            ("docs/getting-started/features.md#projects/0", 1),
        ),
        "The dev set judges this against the feature list alone; the release judgement "
        "names the section that documents it and the guide that walks it.",
    ),
    (
        "u-1262",
        "uv publish",
        (EvalSlice.SYMBOL,),
        (
            ("docs/guides/package.md#publishing-your-package/0", 3),
            ("docs/getting-started/features.md#projects/0", 1),
        ),
        "A command documented only in a guide - credentials, custom indexes, retries - "
        "with no concepts page of its own.",
    ),
    (
        "u-1263",
        "uv version",
        (EvalSlice.SYMBOL,),
        (
            ("docs/guides/package.md#updating-your-version/0", 3),
            ("docs/guides/projects.md#viewing-your-version/0", 2),
        ),
        "One command, two guides: the publishing guide documents the writing half "
        "(`--bump`, `--dry-run`), the project guide the reading half.",
    ),
    (
        "u-1264",
        "how do I bump my package from a stable version to a beta",
        (EvalSlice.FACT,),
        (("docs/guides/package.md#updating-your-version/0", 3),),
        "A rule about combining two `--bump` components, shown only as worked examples.",
    ),
    (
        "u-1265",
        "UV_PUBLISH_TOKEN",
        (EvalSlice.EXACT,),
        (("docs/guides/package.md#publishing-your-package/0", 3),),
        "One of three credential variables in a paragraph that also says when you need "
        "none of them.",
    ),
    (
        "u-1266",
        "--check-url",
        (EvalSlice.EXACT,),
        (("docs/guides/package.md#publishing-your-package/0", 3),),
        "A flag for the half-finished upload case, and the reason existing files must "
        "match exactly.",
    ),
    (
        "u-1267",
        "how do I publish to a registry other than PyPI",
        (EvalSlice.FACT,),
        (
            ("docs/guides/package.md#publishing-your-package/0", 3),
            ("docs/concepts/indexes.md#defining-an-index/", 2),
        ),
        "A `publish-url` on an index entry, and the index definition it hangs off.",
    ),
    (
        "u-1268",
        "what are attestations and does uv create them",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/guides/package.md#publishing-your-package/uploading-attestations-with-your-package/0",
                3,
            ),
        ),
        "A yes-and-no: uv uploads them and does not generate them, plus the flag for "
        "indexes that reject them.",
    ),
    (
        "u-1269",
        "how do I check that my published package installs cleanly",
        (EvalSlice.FACT,),
        (("docs/guides/package.md#installing-your-package/0", 3),),
        "One command with two flags whose reasons are given: do not install from the "
        "local directory, do not use the cached copy.",
    ),
    (
        "u-1270",
        "what does uv create the first time I run a project command",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/projects.md#project-structure/0", 3),
            ("docs/concepts/projects/layout.md#the-project-environment/0", 2),
        ),
        "The guide lists the files; the concepts document says which of them is created "
        "lazily and by what.",
    ),
    (
        "u-1271",
        "why is uv.lock in my repository but .venv is not",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/projects.md#project-structure/uv-lock/0", 3),
            ("docs/concepts/projects/layout.md#the-project-environment/0", 2),
        ),
        "Two recommendations from two documents, and the answer is the contrast between them.",
    ),
    (
        "u-1272",
        "how do I upgrade one package without touching the rest of the lockfile",
        (EvalSlice.FACT,),
        (
            ("docs/concepts/projects/sync.md#upgrading-locked-package-versions/0", 3),
            ("docs/guides/projects.md#managing-dependencies/0", 2),
        ),
        "The flag is documented in the concepts page with its Git-dependency caveat; "
        "the guide shows the invocation.",
    ),
    (
        "u-1273",
        "does uv run remove packages that are not in the lockfile",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/projects.md#running-commands/0", 3),
            (
                "docs/concepts/projects/sync.md"
                "#syncing-the-environment/handling-of-extraneous-packages/0",
                2,
            ),
        ),
        "The guide states the default in a note and points at the concepts section that "
        "gives the other command's opposite default.",
    ),
    # --- Docker: the guide that touches every concept ---
    (
        "u-1274",
        "what is the difference between uv's distroless and derived Docker images",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/guides/integration/docker.md#getting-started/0", 3),
            ("docs/guides/integration/docker.md#getting-started/available-images/0", 2),
        ),
        "The distinction is drawn in the opening paragraph; the image list is what a "
        "term match will find instead.",
    ),
    (
        "u-1275",
        "how do I get the uv binary into my own Dockerfile",
        (EvalSlice.FACT,),
        (("docs/guides/integration/docker.md#getting-started/installing-uv/0", 3),),
        "Two routes - copy from the distroless image, or run the installer - and the "
        "advice to pin, by tag or by digest.",
    ),
    (
        "u-1276",
        "UV_COMPILE_BYTECODE",
        (EvalSlice.EXACT,),
        (("docs/guides/integration/docker.md#optimizations/compiling-bytecode/0", 3),),
        "The variable form of a flag, with the note that only managed Python versions "
        "get their standard library compiled.",
    ),
    (
        "u-1277",
        "UV_LINK_MODE",
        (EvalSlice.EXACT,),
        (("docs/guides/integration/docker.md#optimizations/caching/0", 3),),
        "A setting named once in the corpus, in a paragraph explaining the warning it "
        "silences when the cache and the target are on different filesystems.",
    ),
    (
        "u-1278",
        "why should dependencies be installed in a separate Docker layer from the project",
        (EvalSlice.CONCEPTUAL,),
        (("docs/guides/integration/docker.md#optimizations/intermediate-layers/0", 3),),
        "An argument about what changes often against what does not, with the flag that "
        "splits them.",
    ),
    (
        "u-1279",
        "why does the workspace Dockerfile use --frozen where the other one uses --locked",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/guides/integration/docker.md"
                "#optimizations/intermediate-layers/intermediate-layers-in-workspaces/0",
                3,
            ),
            ("docs/guides/integration/docker.md#optimizations/intermediate-layers/0", 2),
        ),
        "The answer is the difference between two adjacent examples, and the reason - "
        "uv cannot check the lockfile without every member's pyproject - is stated only "
        "in the second.",
    ),
    (
        "u-1280",
        "how do I keep the container's virtual environment when I bind-mount the project",
        (EvalSlice.FACT,),
        (
            (
                "docs/guides/integration/docker.md"
                "#developing-in-a-container/mounting-the-project-with-docker-run/0",
                3,
            ),
            ("docs/guides/integration/docker.md#developing-in-a-container/0", 2),
        ),
        "An anonymous volume over `.venv`, and the paragraph above it that says why the "
        "image's environment must not be replaced by the host's.",
    ),
    (
        "u-1281",
        "how do I rebuild a container when pyproject.toml changes but sync on source edits",
        (EvalSlice.FACT,),
        (
            (
                "docs/guides/integration/docker.md"
                "#developing-in-a-container/configuring-watch-with-docker-compose/0",
                3,
            ),
        ),
        "Two `watch` actions in one compose file, with the `.venv` exclusion that makes "
        "the first one safe.",
    ),
    (
        "u-1282",
        "how do I make an installed tool runnable inside a container",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/docker.md#getting-started/using-installed-tools/0", 3),
            ("docs/concepts/tools.md#tool-executables/0", 2),
        ),
        "The guide sets the path and names the variable; the concepts document is where "
        "the directory it points at is defined.",
    ),
    (
        "u-1283",
        "should I activate the virtual environment in a Dockerfile or use uv run",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/docker.md#getting-started/using-the-environment/0", 3),
            ("docs/concepts/projects/config.md#project-environment-path/0", 2),
        ),
        "Two options in the guide and a third in the tip - installing into the system "
        "environment instead - which the concepts document defines.",
    ),
    (
        "u-1284",
        "why add .venv to .dockerignore",
        (EvalSlice.CONCEPTUAL,),
        (("docs/guides/integration/docker.md#getting-started/installing-a-project/0", 3),),
        "A platform-dependence argument in an admonition, next to the sync command it protects.",
    ),
    (
        "u-1285",
        "how do I verify that a uv Docker image is the one Astral published",
        (EvalSlice.FACT,),
        (("docs/guides/integration/docker.md#verifying-image-provenance/0", 3),),
        "An attestation check with a named tool, in the last section of a long guide.",
    ),
    # --- scripts, and the commands that only appear with --script ---
    (
        "u-1286",
        "uv add --script",
        (EvalSlice.SYMBOL,),
        (
            ("docs/guides/scripts.md#declaring-script-dependencies/0", 3),
            ("docs/getting-started/features.md#scripts/0", 1),
        ),
        "A command that is a flag on another command; the section that documents it "
        "shows the metadata block it writes.",
    ),
    (
        "u-1287",
        "uv init --script",
        (EvalSlice.SYMBOL,),
        (
            ("docs/guides/scripts.md#creating-a-python-script/0", 3),
            ("docs/concepts/projects/init.md#/0", 1),
        ),
        "Same command name as the project initialiser and a different job; only one "
        "54-token section documents this form.",
    ),
    (
        "u-1288",
        "uv lock --script",
        (EvalSlice.SYMBOL,),
        (
            ("docs/guides/scripts.md#locking-dependencies/0", 3),
            ("docs/concepts/projects/sync.md#creating-the-lockfile/0", 1),
        ),
        "The section states the thing that distinguishes scripts from projects: a "
        "script is never locked automatically.",
    ),
    (
        "u-1289",
        "how do I run a script straight from standard input",
        (EvalSlice.FACT,),
        (("docs/guides/scripts.md#running-a-script-without-dependencies/0", 3),),
        "The `-` form and a here-document example, in a section about the simplest possible case.",
    ),
    (
        "u-1290",
        "--no-project",
        (EvalSlice.EXACT,),
        (
            ("docs/guides/scripts.md#running-a-script-without-dependencies/0", 3),
            ("docs/guides/scripts.md#declaring-script-dependencies/0", 2),
        ),
        "A flag whose placement matters - before the script name - and whose second "
        "section says when it is not needed at all.",
    ),
    (
        "u-1291",
        "does a script with inline metadata use my project's dependencies",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/scripts.md#declaring-script-dependencies/0", 3),
            ("docs/concepts/projects/run.md#running-scripts/0", 2),
        ),
        "A no, stated in an admonition in the guide and as a rule in the concepts "
        "document - and the guide adds that the opt-out flag is unnecessary here.",
    ),
    (
        "u-1292",
        "how do I make a script executable without typing uv run",
        (EvalSlice.FACT,),
        (("docs/guides/scripts.md#using-a-shebang-to-create-an-executable-file/0", 3),),
        "A shebang line whose exact form - `env -S uv run --script` - is the answer.",
    ),
    (
        "u-1293",
        "how do I pin a script's dependencies to a date",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/scripts.md#improving-reproducibility/0", 3),
            ("docs/concepts/resolution.md#reproducible-resolutions/0", 2),
        ),
        "The field goes in the script's own metadata; what it means is defined in the "
        "resolution document.",
    ),
    (
        "u-1294",
        "how do I run a script against a different Python version",
        (EvalSlice.FACT,),
        (("docs/guides/scripts.md#using-different-python-versions/0", 3),),
        "A flag on `uv run`, and the metadata field that does the same thing permanently.",
    ),
    (
        "u-1295",
        "uvw",
        (EvalSlice.SYMBOL,),
        (
            ("docs/guides/scripts.md#using-gui-scripts/0", 3),
            ("docs/getting-started/installation.md#uninstallation/0", 1),
        ),
        "A third binary most readers never notice; the uninstall list is the only other "
        "place in the corpus that names it.",
    ),
    (
        "u-1296",
        "how do I use a private index for a script's dependencies",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/scripts.md#using-alternative-package-indexes/0", 3),
            ("docs/concepts/indexes.md#authentication/0", 2),
        ),
        "The guide shows the option and the metadata it writes, then hands the "
        "authentication half to the indexes document.",
    ),
    # --- tools and Python, as the guides teach them ---
    (
        "u-1297",
        "how do I run a tool whose command name differs from its package name",
        (EvalSlice.FACT,),
        (
            ("docs/guides/tools.md#commands-with-different-package-names/0", 3),
            ("docs/guides/tools.md#running-tools/", 2),
        ),
        "The `--from` option, in a 68-token section; the running-tools section is where "
        "the command it modifies is documented.",
    ),
    (
        "u-1298",
        "how do I run a tool at a specific version",
        (EvalSlice.FACT,),
        (
            ("docs/guides/tools.md#requesting-specific-versions/0", 3),
            ("docs/concepts/tools.md#tool-versions/0", 2),
        ),
        "Two spellings - `package@version` and `--from package==version` - and the "
        "concepts document explains what the cache does with them afterwards.",
    ),
    (
        "u-1299",
        "how do I run a tool with a plugin installed alongside it",
        (EvalSlice.FACT,),
        (
            ("docs/guides/tools.md#commands-with-plugins/0", 3),
            ("docs/concepts/tools.md#including-additional-dependencies/0", 2),
        ),
        "A 35-token section in the guide; the concepts page documents the option it "
        "uses, which is the tier-2 framing.",
    ),
    (
        "u-1300",
        "uv python uninstall",
        (EvalSlice.SYMBOL,),
        (
            ("docs/guides/install-python.md#reinstalling-python/0", 3),
            ("docs/getting-started/features.md#python-versions/0", 1),
        ),
        "The command appears in a section titled after the task it is half of, which is "
        "the discrimination a symbol query has to make.",
    ),
    (
        "u-1301",
        "how do I stop uv from downloading Python without changing a setting",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/install-python.md#automatic-python-downloads/0", 3),
            ("docs/concepts/python-versions.md#disabling-automatic-python-downloads/0", 2),
        ),
        "The guide gives the flag, the concepts page gives the setting and its two "
        "values; the question asks for the first and a retriever will find the second.",
    ),
    (
        "u-1302",
        "how do I use a Python that is already on my machine",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/install-python.md#using-existing-python-versions/0", 3),
            ("docs/concepts/python-versions.md#managed-and-system-python-installations/0", 2),
        ),
        "The guide's answer is a flag; the concepts document supplies the vocabulary "
        "the flag is named after - system against managed.",
    ),
    # --- CI: GitHub, GitLab, pre-commit ---
    (
        "u-1303",
        "how do I install uv in a GitHub Actions workflow",
        (EvalSlice.FACT,),
        (("docs/guides/integration/github.md#installation/0", 3),),
        "An action, and the recommendation to pin it to a version.",
    ),
    (
        "u-1304",
        "UV_PYTHON",
        (EvalSlice.EXACT,),
        (("docs/guides/integration/github.md#multiple-python-versions/0", 3),),
        "A variable named exactly once in the whole corpus, inside a CI guide, as the "
        "fallback for people not using the setup action.",
    ),
    (
        "u-1305",
        "how do I test several Python versions in one GitHub workflow",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/github.md#multiple-python-versions/0", 3),
            ("docs/guides/integration/github.md#setting-up-python/0", 2),
        ),
        "A matrix that has to override the project's own pin, which is what the "
        "preceding section set up - so the two sections answer together.",
    ),
    (
        "u-1306",
        "how do I install a project in CI and then run its tests",
        (EvalSlice.FACT,),
        (("docs/guides/integration/github.md#syncing-and-running/0", 3),),
        "Two steps, and the flags on the first are the part worth copying.",
    ),
    (
        "u-1307",
        "how do I fetch a private git dependency in GitHub Actions",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/github.md#private-repos/0", 3),
            ("docs/concepts/authentication/git.md#git-credential-helpers/0", 2),
        ),
        "The guide gives the workflow step; the authentication document says why the "
        "extra `gh auth setup-git` call is needed when a token is passed in.",
    ),
    (
        "u-1308",
        "how do I publish to PyPI from GitHub Actions without storing a token",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/github.md#publishing-to-pypi/0", 3),
            ("docs/guides/package.md#publishing-your-package/0", 2),
        ),
        "Trusted publishing: the workflow lives in the CI guide, the sentence that says "
        "no credentials are needed lives in the packaging guide.",
    ),
    (
        "u-1309",
        "which uv Docker image should a GitLab job use",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/gitlab.md#using-the-uv-image/0", 3),
            ("docs/guides/integration/docker.md#getting-started/available-images/0", 2),
        ),
        "The GitLab guide composes the tag from three variables and adds the "
        "entrypoint caveat; the image list it draws from is in the Docker guide.",
    ),
    (
        "u-1310",
        "why does a GitLab job need UV_LINK_MODE set to copy",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/gitlab.md#using-the-uv-image/0", 3),
            ("docs/guides/integration/docker.md#optimizations/caching/0", 2),
        ),
        "The reason is a comment in the GitLab snippet - a separate mountpoint, so "
        "hard links fail - and the Docker guide is where the setting is explained.",
    ),
    (
        "u-1311",
        "how do I cache uv between GitLab pipeline runs",
        (EvalSlice.FACT,),
        (("docs/guides/integration/gitlab.md#caching/0", 3),),
        "A cache key built from the lockfile, and the prune step that keeps it small.",
    ),
    (
        "u-1312",
        "how do I make pre-commit keep my lockfile up to date",
        (EvalSlice.FACT,),
        (("docs/guides/integration/pre-commit.md#/0", 3),),
        "One hook id among four in a single document, and the question names the task "
        "rather than the hook.",
    ),
    (
        "u-1313",
        "how do I keep requirements.txt in step with uv.lock automatically",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/pre-commit.md#/0", 3),
            ("docs/concepts/projects/export.md#requirements-txt-format/0", 2),
        ),
        "The hook does it; the export document is what the hook runs, and it is also "
        "where the advice against keeping both files lives.",
    ),
    (
        "u-1314",
        "how do I let Dependabot update a uv lockfile",
        (EvalSlice.FACT,),
        (("docs/guides/integration/dependabot.md#/0", 3),),
        "A configuration block and the ecosystem name, in a short guide.",
    ),
    (
        "u-1315",
        "how do I hold back dependency updates for a few days",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/dependabot.md#dependency-cooldown/0", 3),
            ("docs/concepts/resolution.md#dependency-cooldowns/0", 2),
        ),
        "Two cooldowns with the same purpose in different places: the bot's setting and uv's own.",
    ),
    (
        "u-1316",
        "how do I get Renovate to update inline script metadata",
        (EvalSlice.FACT,),
        (("docs/guides/integration/renovate.md#inline-script-metadata/0", 3),),
        "The bot cannot detect which files carry the metadata, so the answer is the "
        "pattern list that tells it - and the note that the lockfile is not updated.",
    ),
    (
        "u-1317",
        "how do I let Bazel fetch credentials from uv",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/bazel.md#authentication/0", 3),
            ("docs/concepts/authentication/cli.md#using-credentials-with-external-tools/0", 2),
        ),
        "The guide wires up the helper; the concepts page documents the protocol and "
        "the preview flag it needs.",
    ),
    # --- where uv deliberately differs from pip ---
    (
        "u-1318",
        "does uv read pip.conf or PIP_INDEX_URL",
        (EvalSlice.CONCEPTUAL,),
        (("docs/pip/compatibility.md#configuration-files-and-environment-variables/0", 3),),
        "A no with five numbered reasons - a rejected alternative argued out in full, "
        "which is where reasoning questions hide.",
    ),
    (
        "u-1319",
        "why does uv stop at the first index that has a package when pip does not",
        (EvalSlice.RELATIONSHIP, EvalSlice.CONCEPTUAL),
        (
            ("docs/pip/compatibility.md#packages-that-exist-on-multiple-indexes/0", 3),
            ("docs/concepts/indexes.md#searching-across-multiple-indexes/0", 2),
        ),
        "The compatibility page frames it as a difference from pip and the concepts "
        "page states the rule; both name the same attack as the reason.",
    ),
    (
        "u-1320",
        "UV_SKIP_WHEEL_FILENAME_CHECK",
        (EvalSlice.EXACT,),
        (("docs/pip/compatibility.md#wheel-filename-and-metadata-validation/0", 3),),
        "An escape hatch named once, in a section about a check pip does not perform.",
    ),
    (
        "u-1321",
        "why does uv pip list show a different package name than pip list",
        (EvalSlice.CONCEPTUAL,),
        (("docs/pip/compatibility.md#package-name-normalization/0", 3),),
        "Normalisation, shown as a side-by-side diff, with the flag that turns it off.",
    ),
    (
        "u-1322",
        "does --user work with uv pip install",
        (EvalSlice.FACT,),
        (("docs/pip/compatibility.md#user-and-the-user-install-scheme/0", 3),),
        "A no, the recommended alternative, and the pip fallback uv deliberately does "
        "not implement.",
    ),
    (
        "u-1323",
        "why does uv pip compile print to the terminal instead of writing a file",
        (EvalSlice.CONCEPTUAL,),
        (("docs/pip/compatibility.md#pip-compile-defaults/0", 3),),
        "One of three deliberate default changes from pip-tools, each with its flag.",
    ),
    (
        "u-1324",
        "--emit-index-url",
        (EvalSlice.EXACT,),
        (("docs/pip/compatibility.md#pip-compile-defaults/0", 3),),
        "A flag whose behaviour differs from the tool it mimics - uv emits every index "
        "URL, including the default - stated in one clause.",
    ),
    (
        "u-1325",
        "does uv install a package from a URL when --only-binary is set",
        (EvalSlice.CONCEPTUAL,),
        (("docs/pip/compatibility.md#only-binary-enforcement/0", 3),),
        "A yes-except: uv enforces the flag where pip does not, and the exception is "
        "about package names it cannot infer.",
    ),
    (
        "u-1326",
        "does uv compile .pyc files when it installs",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/pip/compatibility.md#bytecode-compilation/0", 3),
            ("docs/guides/integration/docker.md#optimizations/compiling-bytecode/0", 2),
        ),
        "A no by default, the flag, and the guide that recommends turning it on - plus "
        "the warning behaviour nobody expects.",
    ),
    (
        "u-1327",
        "why does uv send credentials before being asked for them",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/pip/compatibility.md#registry-authentication/0", 3),
            ("docs/concepts/authentication/http.md#keyring-providers/0", 2),
        ),
        "The compatibility page states the difference - no waiting for a 401 - and the "
        "authentication page defines the provider it does or does not consult.",
    ),
    (
        "u-1328",
        "can uv install an egg distribution",
        (EvalSlice.FACT,),
        (("docs/pip/compatibility.md#egg-support/0", 3),),
        "A no for installing and a partial yes for everything else, which is the whole "
        "of a short section.",
    ),
    (
        "u-1329",
        "why does changing the order of packages change what uv resolves",
        (EvalSlice.CONCEPTUAL,),
        (("docs/pip/compatibility.md#package-priority/0", 3),),
        "A property of the resolver stated as a difference from pip's priorities, with "
        "a two-command example.",
    ),
    (
        "u-1330",
        "does a project that requires Python 3.13 accept 3.13.0b1",
        (EvalSlice.FACT,),
        (("docs/pip/compatibility.md#requires-python-specifiers/0", 3),),
        "A truncation rule, its consequence, and the admission that it is not strictly PEP 440.",
    ),
    (
        "u-1331",
        "why did my constraint not apply while building a package",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/pip/compatibility.md#build-constraints/0", 3),
            ("docs/pip/compile.md#adding-build-constraints/0", 2),
        ),
        "The compatibility page says constraints do not reach build dependencies; the "
        "compile document is where the setting that does reach them is documented.",
    ),
    (
        "u-1332",
        "how do I install a package whose build dependencies are broken",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/pip/compatibility.md#pep-517-build-isolation/0", 3),
            ("docs/concepts/projects/config.md#build-isolation/disabling-build-isolation/0", 2),
        ),
        "The escape hatch in the pip interface, and the project-level setting that does "
        "the same thing without a two-command dance.",
    ),
    (
        "u-1333",
        "why did uv reject a URL dependency that came from a registry package",
        (EvalSlice.CONCEPTUAL,),
        (("docs/pip/compatibility.md#transitive-url-dependencies/0", 3),),
        "An assumption stated as an assumption, with the workaround - promote it to a "
        "direct dependency.",
    ),
    # --- internals: the resolver, and the metadata command ---
    (
        "u-1334",
        "which solver does uv's resolver use",
        (EvalSlice.FACT,),
        (("docs/reference/internals/resolver.md#resolver/0", 3),),
        "A named algorithm and its Rust implementation, five paragraphs into a document "
        "whose first half argues about SAT.",
    ),
    (
        "u-1335",
        "what decides which package the resolver looks at next",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/reference/internals/resolver.md#prioritization/0", 3),
            ("docs/reference/internals/resolver.md#resolver/0", 2),
        ),
        "The priority order is stated twice at different depths - the walkthrough and "
        "the dedicated section - and only together do they answer why it matters.",
    ),
    (
        "u-1336",
        "what is a fork in uv's resolution",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/reference/internals/resolver.md#forking/0", 3),
            ("docs/concepts/resolution.md#multi-version-resolution/0", 2),
        ),
        "The internals document defines the mechanism; the concepts document is where a "
        "user meets its consequence - one package, several versions, in one lockfile.",
    ),
    (
        "u-1337",
        "resolution-markers",
        (EvalSlice.EXACT,),
        (("docs/reference/internals/resolver.md#forking/0", 3),),
        "A lockfile field named once, in the paragraph explaining why a second "
        "resolution could otherwise find a different answer.",
    ),
    (
        "u-1338",
        "why can a universal resolution still fail to install on my machine",
        (EvalSlice.CONCEPTUAL, EvalSlice.RELATIONSHIP),
        (
            ("docs/reference/internals/resolver.md#wheel-tags/0", 3),
            ("docs/concepts/resolution.md#required-environments/0", 2),
        ),
        "Markers are universal and wheel tags are not; the concepts document is where "
        "the setting that guards against it lives.",
    ),
    (
        "u-1339",
        "why does uv require every wheel of a version to have the same metadata",
        (EvalSlice.CONCEPTUAL,),
        (("docs/reference/internals/resolver.md#metadata-consistency/0", 3),),
        "A performance argument and a correctness one - 73 requests, and the missing "
        "mapping between markers and wheel tags.",
    ),
    (
        "u-1340",
        "uv workspace metadata",
        (EvalSlice.SYMBOL,),
        (("docs/reference/internals/metadata.md#/0", 3),),
        "A command documented in a reference page whose title is a noun phrase, and it "
        "is the recommended way to read what a lockfile encodes.",
    ),
    (
        "u-1341",
        "how do I find a package's extras in the exported workspace metadata",
        (EvalSlice.FACT,),
        (("docs/reference/internals/metadata.md#/0", 3),),
        "Five node kinds and the lookup rule for each; the question asks for one of them.",
    ),
    (
        "u-1342",
        "should another tool read uv.lock directly",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/reference/internals/metadata.md#/0", 3),
            ("docs/concepts/projects/layout.md#the-lockfile/0", 2),
        ),
        "A no from two directions: the lockfile is uv's own format, and there is a "
        "command whose output is meant to be consumed instead.",
    ),
    # --- troubleshooting, notebooks, and the commands left over ---
    (
        "u-1343",
        "how do I tell whether a build failure is uv's fault",
        (EvalSlice.FACT,),
        (
            (
                "docs/reference/troubleshooting/build-failures.md"
                "#confirming-that-a-build-failure-is-specific-to-uv/0",
                3,
            ),
            ("docs/reference/troubleshooting/build-failures.md#recognizing-a-build-failure/0", 2),
        ),
        "A procedure - reproduce it with pip, using the flags that make the comparison "
        "fair - and the section that teaches which part of the output came from uv.",
    ),
    (
        "u-1344",
        "the build backend returned an error",
        (EvalSlice.EXACT,),
        (("docs/reference/troubleshooting/build-failures.md#recognizing-a-build-failure/0", 3),),
        "A quoted error string a reader pastes into a search box; the section is built "
        "around exactly that line and what follows it.",
    ),
    (
        "u-1345",
        "a package says a header or library is missing when it builds",
        (EvalSlice.FACT,),
        (
            (
                "docs/reference/troubleshooting/build-failures.md"
                "#common-build-failures/header-or-library-is-missing/0",
                3,
            ),
        ),
        "One of eight named failure shapes, each with its own remedy, under one heading.",
    ),
    (
        "u-1346",
        "what should I include when reporting a uv bug",
        (EvalSlice.CONCEPTUAL,),
        (
            (
                "docs/reference/troubleshooting/reproducible-examples.md#how-to-write-a-reproducible-example/0",
                3,
            ),
            (
                "docs/reference/troubleshooting/reproducible-examples.md"
                "#why-reproducible-examples-are-important/0",
                2,
            ),
        ),
        "A six-item list of context, and the section before it that says why a "
        "maintainer cannot work without it.",
    ),
    (
        "u-1347",
        "how do I share a reproduction that does not depend on my machine",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/reference/troubleshooting/reproducible-examples.md"
                "#strategies-for-reproducible-examples/docker-image/0",
                3,
            ),
            (
                "docs/reference/troubleshooting/reproducible-examples.md"
                "#strategies-for-reproducible-examples/script/0",
                2,
            ),
        ),
        "Three strategies in one document; the question's phrasing - independent of my "
        "system - is the argument the Docker one makes for itself.",
    ),
    (
        "u-1348",
        "how do I run Jupyter against my project's environment",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/jupyter.md#using-jupyter-within-a-project/0", 3),
            ("docs/concepts/projects/run.md#requesting-additional-dependencies/0", 2),
        ),
        "The guide's answer is `uv run --with`; the concepts section is where that "
        "option is documented, and the guide never explains it.",
    ),
    (
        "u-1349",
        "how do I install packages from inside a notebook",
        (EvalSlice.FACT,),
        (
            (
                "docs/guides/integration/jupyter.md"
                "#using-jupyter-within-a-project/installing-packages-without-a-kernel/0",
                3,
            ),
            (
                "docs/guides/integration/jupyter.md#using-jupyter-within-a-project/creating-a-kernel/0",
                2,
            ),
        ),
        "Two answers in one document, and the guide recommends the other one - which is "
        "what makes the discrimination worth measuring.",
    ),
    (
        "u-1350",
        "uv pip install",
        (EvalSlice.SYMBOL,),
        (
            ("docs/pip/packages.md#installing-a-package/0", 3),
            ("docs/pip/index.md#/0", 2),
            ("docs/getting-started/features.md#the-pip-interface/0", 1),
        ),
        "The most-mentioned command in the corpus: its own section, the interface that "
        "frames it, the feature list that names it.",
    ),
    (
        "u-1351",
        "uv pip uninstall",
        (EvalSlice.SYMBOL,),
        (
            ("docs/pip/packages.md#uninstalling-a-package/0", 3),
            ("docs/getting-started/features.md#the-pip-interface/0", 1),
        ),
        "A 40-token section that is the command's whole documentation, against a "
        "one-line list entry.",
    ),
    (
        "u-1352",
        "uv cache prune",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/cache.md#clearing-the-cache/0", 3),
            ("docs/concepts/cache.md#caching-in-continuous-integration/0", 2),
            ("docs/getting-started/features.md#utility/0", 1),
        ),
        "Documented beside the command it is confused with, framed by the CI section "
        "that gives it its `--ci` flag, listed in the feature table.",
    ),
    (
        "u-1353",
        "uv init --lib",
        (EvalSlice.SYMBOL,),
        (("docs/concepts/projects/init.md#libraries/0", 3),),
        "A flag that selects a template; the section that documents it shows what the "
        "template contains and why.",
    ),
    (
        "u-1354",
        "uv export --script",
        (EvalSlice.SYMBOL,),
        (("docs/guides/scripts.md#locking-dependencies/0", 3),),
        "One of four `--script` forms named in a single paragraph, and the only place "
        "in the corpus that names this one.",
    ),
    (
        "u-1355",
        "uv python pin --global",
        (EvalSlice.SYMBOL,),
        (
            (
                "docs/concepts/python-versions.md#requesting-a-version/python-version-files/0",
                3,
            ),
        ),
        "A flag whose effect is a file in the user configuration directory, documented "
        "in one line beside the project-level form.",
    ),
    (
        "u-1356",
        "UV_TOOL_BIN_DIR",
        (EvalSlice.EXACT,),
        (
            ("docs/reference/storage.md#types-of-data/tool-executables/0", 3),
            ("docs/guides/integration/docker.md#getting-started/available-images/1", 2),
        ),
        "The storage reference documents it; the Docker guide is where a reader meets "
        "it, because the derived images set it.",
    ),
    (
        "u-1357",
        "UV_NO_DEV",
        (EvalSlice.EXACT,),
        (("docs/guides/integration/docker.md#getting-started/installing-a-project/0", 3),),
        "A variable that appears once, in a Dockerfile, with no prose around it - the "
        "hardest shape for a term query to rank.",
    ),
    (
        "u-1358",
        "UV_PYTHON_CACHE_DIR",
        (EvalSlice.EXACT,),
        (("docs/guides/integration/docker.md#optimizations/caching/0", 3),),
        "A variable for a case the cache document never mentions: managed Python "
        "installations are not cached before being installed.",
    ),
    (
        "u-1359",
        "UV_SYSTEM_CERTS",
        (EvalSlice.EXACT,),
        (("docs/concepts/authentication/certificates.md#system-certificates/0", 3),),
        "One of three spellings of the same switch - flag, variable, setting - in the "
        "section that says which verifier it hands over to.",
    ),
    (
        "u-1360",
        "--universal",
        (EvalSlice.EXACT,),
        (
            ("docs/concepts/resolution.md#universal-resolution/0", 3),
            ("docs/pip/compatibility.md#pip-compile-defaults/0", 1),
        ),
        "A flag that brings the project interface's default to the pip interface; the "
        "compatibility page names it among the defaults that differ from pip-tools'.",
    ),
    (
        "u-1361",
        "--python-platform",
        (EvalSlice.EXACT,),
        (("docs/concepts/resolution.md#platform-specific-resolution/0", 3),),
        "A flag documented with the caveat that it cannot express everything a marker "
        "can - the `platform_version` example.",
    ),
    (
        "u-1362",
        "--strip-extras",
        (EvalSlice.EXACT,),
        (("docs/pip/compatibility.md#pip-compile-defaults/0", 3),),
        "A default that differs from pip-tools' today and is scheduled to converge, "
        "stated in one paragraph.",
    ),
    # --- the remaining guides, and the support policies ---
    (
        "u-1363",
        "why is installing PyTorch more complicated than installing another package",
        (EvalSlice.CONCEPTUAL,),
        (("docs/guides/integration/pytorch.md#installing-pytorch/0", 3),),
        "Three packaging facts - a dedicated index, accelerator builds, local version "
        "specifiers - that together are the answer.",
    ),
    (
        "u-1364",
        "how do I install a CPU-only build of torch on Linux and the default elsewhere",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/pytorch.md#using-a-pytorch-index/0", 3),
            (
                "docs/concepts/projects/dependencies.md#dependency-sources/multiple-sources/0",
                2,
            ),
        ),
        "The guide gives the index names and markers; the concepts document is where "
        "the list-of-sources shape it uses is defined.",
    ),
    (
        "u-1365",
        "how do I let uv pick the right accelerator build automatically",
        (EvalSlice.FACT,),
        (("docs/guides/integration/pytorch.md#automatic-backend-selection/0", 3),),
        "One option with a name that does not contain the words a reader would use - "
        "`--torch-backend=auto` for 'detect my GPU'.",
    ),
    (
        "u-1366",
        "how do I install flash-attn or another GPU extension without building it",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/pytorch.md#installing-gpu-enabled-pytorch-extensions/0", 3),
            (
                "docs/concepts/projects/config.md#build-isolation/augmenting-build-dependencies/0",
                2,
            ),
        ),
        "The guide points at prebuilt wheels on a dedicated index; the concepts "
        "document is the route for when there is no wheel, and each is a poor answer "
        "to the other's question.",
    ),
    (
        "u-1367",
        "how do I move a FastAPI application to uv",
        (EvalSlice.FACT,),
        (("docs/guides/integration/fastapi.md#migrating-an-existing-fastapi-project/0", 3),),
        "A worked migration: the file layout, the init command, and the dependency "
        "that has to be added by hand.",
    ),
    (
        "u-1368",
        "how do I deploy a FastAPI application built with uv",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/fastapi.md#deployment/0", 3),
            ("docs/guides/integration/docker.md#getting-started/installing-a-project/0", 2),
        ),
        "The FastAPI guide's Dockerfile is a specialisation of the Docker guide's, and "
        "the question does not say Docker.",
    ),
    (
        "u-1369",
        "how do I package a project for AWS Lambda",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/aws-lambda.md#deploying-a-zip-archive/0", 3),
            ("docs/guides/integration/aws-lambda.md#deploying-a-docker-image/0", 2),
        ),
        "Two deployment shapes in one guide; the zip route is the one that needs the "
        "platform and Python version pinned at install time.",
    ),
    (
        "u-1370",
        "how do I share a Lambda layer between functions",
        (EvalSlice.FACT,),
        (
            (
                "docs/guides/integration/aws-lambda.md"
                "#deploying-a-zip-archive/using-a-lambda-layer/0",
                3,
            ),
        ),
        "A long subsection whose answer is a directory layout the runtime expects.",
    ),
    (
        "u-1371",
        "how do I run a marimo notebook as a script",
        (EvalSlice.FACT,),
        (("docs/guides/integration/marimo.md#running-marimo-notebooks-as-scripts/0", 3),),
        "A 64-token section, and the question's wording is its heading - the easy case "
        "kept deliberately, as a floor.",
    ),
    (
        "u-1372",
        "how do I use inline script metadata in a marimo notebook",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/marimo.md#using-marimo-with-inline-script-metadata/0", 3),
            ("docs/guides/scripts.md#declaring-script-dependencies/0", 2),
        ),
        "The guide shows the sandbox flag that writes the metadata; the scripts guide "
        "is where the format is defined.",
    ),
    (
        "u-1373",
        "how do I run a script on cloud hardware with its dependencies",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/coiled.md#running-scripts-on-the-cloud-with-coiled/0", 3),
            ("docs/guides/integration/coiled.md#managing-script-dependencies-with-uv/0", 2),
        ),
        "Two halves of one workflow in one guide: the decorator that sends the function "
        "to a VM, and the metadata that tells uv what to install there.",
    ),
    (
        "u-1374",
        "which Python versions does uv guarantee to work with",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/reference/policies/python.md#python-versions/0", 3),
            ("docs/reference/policies/platforms.md#/0", 2),
        ),
        "The Python policy borrows the platform policy's tier vocabulary, and only the "
        "second says what a tier promises.",
    ),
    (
        "u-1375",
        "which Python implementations can uv install",
        (EvalSlice.FACT,),
        (
            ("docs/reference/policies/python.md#python-implementations/0", 3),
            ("docs/concepts/python-versions.md#python-implementation-support/0", 2),
        ),
        "A policy list and a concepts section that says what support means for each - "
        "the same four names, two different claims.",
    ),
    (
        "u-1376",
        "what Rust version does building uv from source need",
        (EvalSlice.FACT,),
        (("docs/reference/policies/rust.md#/0", 3),),
        "A policy document of one section, and the answer is not a number: it names "
        "the key the number lives in and the N-2 bound on how old it may be.",
    ),
    (
        "u-1377",
        "how do I convert a requirements.txt workflow into a uv project",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/guides/migration/pip-to-project.md"
                "#migrating-to-a-uv-project/importing-requirements-files/0",
                3,
            ),
            (
                "docs/guides/migration/pip-to-project.md"
                "#understanding-pip-workflows/requirements-files/0",
                2,
            ),
        ),
        "The migration guide is written as a before and after; the answer is the after, "
        "and the before is what a term query matches.",
    ),
    (
        "u-1378",
        "how do development dependencies change when I migrate off pip",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/guides/migration/pip-to-project.md"
                "#migrating-to-a-uv-project/importing-requirements-files/importing-development-dependency-files/0",
                3,
            ),
            (
                "docs/guides/migration/pip-to-project.md"
                "#understanding-pip-workflows/development-dependencies/0",
                2,
            ),
        ),
        "A `requirements-dev.txt` becomes a dependency group; each half is a section, "
        "and they are four headings apart.",
    ),
    (
        "u-1379",
        "where did my project's virtual environment go after migrating",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/guides/migration/pip-to-project.md#migrating-to-a-uv-project/project-environments/0",
                3,
            ),
            ("docs/concepts/projects/layout.md#the-project-environment/0", 2),
        ),
        "The guide says uv manages it for you; the concepts document says where it is "
        "and what not to do to it.",
    ),
    (
        "u-1380",
        "what do uv's benchmarks measure",
        (EvalSlice.CONCEPTUAL,),
        (("docs/reference/benchmarks.md#/0", 3),),
        "A 42-token pointer page - the honest answer is that the numbers live outside "
        "this corpus, and a retriever should still find the page that says so.",
    ),
    # --- hosted indexes, preview, and the last of the commands ---
    (
        "u-1381",
        "how do I install from Azure Artifacts with a personal access token",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/azure.md#authenticate-with-an-azure-access-token/0", 3),
            ("docs/concepts/indexes.md#authentication/providing-credentials-directly/0", 2),
        ),
        "The guide gives the two variables with a dummy username; the concepts document "
        "is where the rule that derives their names from the index name lives.",
    ),
    (
        "u-1382",
        "how do I publish a package to AWS CodeArtifact",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/guides/integration/aws.md#publishing-packages/0", 3),
            ("docs/guides/package.md#publishing-your-package/0", 2),
        ),
        "The guide adds a `publish-url` and the credentials; the packaging guide is "
        "what it defers to for the command itself.",
    ),
    (
        "u-1383",
        "how do I authenticate to Google Artifact Registry with keyring",
        (EvalSlice.RELATIONSHIP,),
        (
            (
                "docs/guides/integration/google.md"
                "#authenticate-with-keyring-and-keyrings-google-artifactregistry-auth/0",
                3,
            ),
            ("docs/concepts/authentication/http.md#keyring-providers/0", 2),
        ),
        "The guide installs the plugin and sets the provider; the concepts document "
        "says what a keyring provider is and that only one kind is supported.",
    ),
    (
        "u-1384",
        "how do I use a JFrog JWT token with uv",
        (EvalSlice.FACT,),
        (("docs/guides/integration/jfrog.md#authenticate-with-jwt-token/0", 3),),
        "A 45-token section whose content is two exports, one of which sets an empty "
        "username - the detail that makes it work.",
    ),
    (
        "u-1385",
        "UV_PUBLISH_USERNAME",
        (EvalSlice.EXACT,),
        (
            ("docs/guides/package.md#publishing-your-package/0", 3),
            ("docs/guides/integration/aws.md#publishing-packages/0", 2),
        ),
        "A variable named in the packaging guide's credential paragraph and used in "
        "anger by one integration guide (ADR-0101).",
    ),
    (
        "u-1386",
        "UV_TOOL_DIR",
        (EvalSlice.EXACT,),
        (
            ("docs/reference/storage.md#types-of-data/tools/0", 3),
            ("docs/concepts/tools.md#tool-environments/0", 2),
        ),
        "The storage reference documents the override; the tools concept page is where "
        "the directory it changes is introduced.",
    ),
    (
        "u-1387",
        "SSL_CERT_FILE",
        (EvalSlice.EXACT,),
        (("docs/concepts/authentication/certificates.md#custom-certificates/0", 3),),
        "One of two variables in the section, and the one that takes a bundle rather "
        "than a directory.",
    ),
    (
        "u-1388",
        "--no-binary",
        (EvalSlice.EXACT,),
        (
            ("docs/pip/compatibility.md#no-binary-enforcement/0", 3),
            ("docs/pip/compatibility.md#only-binary-enforcement/0", 2),
        ),
        "Two flags one word apart, documented in adjacent sections; the question names "
        "the one whose section also states what uv still reuses from the cache.",
    ),
    (
        "u-1389",
        "--all-groups",
        (EvalSlice.EXACT,),
        (
            (
                "docs/concepts/projects/sync.md"
                "#syncing-the-environment/syncing-development-dependencies/0",
                3,
            ),
            (
                "docs/concepts/projects/dependencies.md"
                "#development-dependencies/dependency-groups/0",
                2,
            ),
        ),
        "A flag listed among five siblings in the sync document, and named again where "
        "groups themselves are defined.",
    ),
    (
        "u-1390",
        "uv tool run",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/tools.md#the-uv-tool-interface/0", 3),
            ("docs/guides/tools.md#running-tools/", 2),
            ("docs/getting-started/features.md#tools/0", 1),
        ),
        "The long form of `uvx`: the section that defines the equivalence, the guide "
        "that walks it, the feature list that names both.",
    ),
    (
        "u-1391",
        "uv cache clean",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/cache.md#clearing-the-cache/0", 3),
            ("docs/concepts/tools.md#tool-environments/0", 2),
            ("docs/getting-started/features.md#utility/0", 1),
        ),
        "Documented in the cache document; the tools document is where its most "
        "surprising effect - a disposable tool environment disappears - is stated.",
    ),
    (
        "u-1392",
        "uv tool dir",
        (EvalSlice.SYMBOL,),
        (
            ("docs/reference/storage.md#types-of-data/tools/0", 3),
            ("docs/getting-started/features.md#utility/0", 1),
        ),
        "A command whose whole documentation is one line of a storage subsection.",
    ),
    (
        "u-1393",
        "uv tree --script",
        (EvalSlice.SYMBOL,),
        (("docs/guides/scripts.md#locking-dependencies/0", 3),),
        "Named once, in the list of commands that reuse a script's lockfile.",
    ),
    (
        "u-1394",
        "uv build --package",
        (EvalSlice.SYMBOL,),
        (
            ("docs/guides/package.md#building-your-package/0", 3),
            ("docs/concepts/projects/build.md#using-uv-build/0", 2),
        ),
        "The workspace form of the build command, named in the guide and absent from "
        "the concepts section that documents everything else about it.",
    ),
    (
        "u-1395",
        "what does it mean for a feature to be in preview",
        (EvalSlice.CONCEPTUAL,),
        (
            ("docs/concepts/preview.md#/0", 3),
            ("docs/concepts/preview.md#using-preview-features/0", 2),
        ),
        "A definition in 32 tokens, and the section that says how a preview feature "
        "behaves before you turn it on.",
    ),
    (
        "u-1396",
        "what happens if I enable a preview feature that does not exist",
        (EvalSlice.CONCEPTUAL,),
        (("docs/concepts/preview.md#enabling-preview-features/0", 3),),
        "A warning rather than an error, and the reason - backwards compatibility - in "
        "the last line of a long section about syntax.",
    ),
    (
        "u-1397",
        "UV_NO_CACHE",
        (EvalSlice.EXACT,),
        (
            ("docs/guides/integration/docker.md#optimizations/caching/0", 3),
            ("docs/concepts/cache.md#cache-directory/0", 2),
        ),
        "The variable is named in the Docker guide, where not mounting a cache is the "
        "case for it; the cache document explains what `--no-cache` still does.",
    ),
    (
        "u-1398",
        "how do I keep a tool's environment when I clear the cache",
        (EvalSlice.RELATIONSHIP,),
        (
            ("docs/concepts/tools.md#tool-environments/0", 3),
            ("docs/concepts/cache.md#clearing-the-cache/0", 2),
        ),
        "The answer is to install the tool rather than run it, which only the tools "
        "document says; the cache document says what clearing removes.",
    ),
    # --- command forms the corpus documents but the feature list does not ---
    (
        "u-1399",
        "uv pip install -e",
        (EvalSlice.SYMBOL,),
        (
            ("docs/pip/packages.md#editable-packages/0", 3),
            ("docs/concepts/projects/dependencies.md#editable-dependencies/0", 2),
        ),
        "A flag that makes a different command: the pip document shows both forms, the "
        "concepts document explains what an editable install actually is.",
    ),
    (
        "u-1400",
        "uv run --with",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/projects/run.md#requesting-additional-dependencies/0", 3),
            ("docs/guides/scripts.md#running-a-script-with-dependencies/0", 2),
        ),
        "One option documented twice for two audiences - a project command and a script "
        "invocation - and only the first is its documentation.",
    ),
    (
        "u-1401",
        "uv sync --inexact",
        (EvalSlice.SYMBOL,),
        (
            (
                "docs/concepts/projects/sync.md"
                "#syncing-the-environment/handling-of-extraneous-packages/0",
                3,
            ),
        ),
        "A flag whose section exists to contrast it with the opposite default on another command.",
    ),
    (
        "u-1402",
        "uv lock --upgrade-package",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/projects/sync.md#upgrading-locked-package-versions/0", 3),
            ("docs/guides/projects.md#managing-dependencies/0", 2),
        ),
        "The section that documents it also states the Git-dependency behaviour nobody "
        "expects; the guide just shows the line.",
    ),
    (
        "u-1403",
        "uv venv --python",
        (EvalSlice.SYMBOL,),
        (
            ("docs/pip/environments.md#creating-a-virtual-environment/0", 3),
            ("docs/concepts/python-versions.md#requesting-a-version/0", 2),
        ),
        "A command plus a request format: the environments document documents the "
        "command, the Python document defines what the value may look like.",
    ),
    (
        "u-1404",
        "uv cache prune --ci",
        (EvalSlice.SYMBOL,),
        (
            ("docs/concepts/cache.md#caching-in-continuous-integration/0", 3),
            ("docs/guides/integration/github.md#caching/0", 2),
        ),
        "A flag that only exists for one situation, documented where that situation is "
        "argued and used where it is configured.",
    ),
    (
        "u-1405",
        "uv python install --default",
        (EvalSlice.SYMBOL,),
        (
            (
                "docs/concepts/python-versions.md"
                "#installing-a-python-version/installing-python-executables/0",
                3,
            ),
        ),
        "An experimental flag named once, in the subsection about which executables "
        "land on the PATH.",
    ),
)


def cases_of(judgments: tuple[Judgment, ...]) -> tuple[EvalCase, ...]:
    return tuple(
        EvalCase(
            case_id=case_id,
            query=query,
            slices=slices,
            relevant=tuple(
                RelevantAnchor(anchor=anchor, grade=grade) for anchor, grade in relevant
            ),
            answerable=bool(relevant),
            note=note,
        )
        for case_id, query, slices, relevant, note in judgments
    )


def main() -> int:
    check_only = "--check" in sys.argv[1:]
    if not (CORPUS / "docs").is_dir():
        print(f"the vendored corpus is missing: {CORPUS / 'docs'}")
        return 1

    dev, release = cases_of(DEV), cases_of(RELEASE)
    # Clean for the reason [BUG-0018] records: this corpus is compiled in place,
    # so an incremental build would validate the judgements against whatever
    # chunking the local store already held.
    build(CORPUS, clean=True, pin_identity=False)  # a committed corpus (ADR-0046)
    with SqliteStore.open(CORPUS, read_only=True) as store:
        errors, warnings = validate_judged_set(dev + release, store)

    for warning in warnings:
        print(f"  warning: {warning}")

    if errors:
        print("The judged set does not hold against the corpus:")
        for error in errors:
            print(f"  {error}")
        return 1

    destination = CORPUS / "eval"
    summary = f"{len(dev)} dev and {len(release)} release cases"

    if check_only:
        # A judged set its own generator no longer reproduces is the defect, not
        # a reason to regenerate quietly: the file on disk may be the only copy
        # of a judgement somebody wrote ([BUG-0026]).
        differences = [
            (destination / f"{name}.jsonl").relative_to(ROOT).as_posix()
            for name, cases in (("dev", dev), ("release", release))
            if encode_cases(cases)
            != (
                (destination / f"{name}.jsonl").read_text(encoding="utf-8")
                if (destination / f"{name}.jsonl").is_file()
                else ""
            )
        ]
        print(summary)
        if differences:
            print("the judged sets do not reproduce from this tree:")
            for relative in differences:
                print(f"  {relative}")
            print(
                "a case edited into the set by hand is invisible to this file and the "
                "next run deletes it; move the judgement into DEV/RELEASE above, then "
                "re-run `python tools/build_uv_docs_cases.py` and review the diff"
            )
            return 1
        print("judged sets reproduce byte-for-byte")
        return 0

    destination.mkdir(parents=True, exist_ok=True)
    write_cases(destination / "dev.jsonl", dev)
    write_cases(destination / "release.jsonl", release)
    print(f"wrote {summary} to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
