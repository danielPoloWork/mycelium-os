# Language-Fit Advisory

During intake the architect does not just accept the requested language — it assesses whether
that language **fits the domain** described in the spec, and if a clearly more appropriate one
exists, it **surfaces a reasoned recommendation**. The maintainer always makes the final call
(agent advises, human decides); the chosen language is recorded in the manifest either way.

## When to raise it

- **Raise it** only on a *clear* mismatch (e.g. "a real-time firmware in Python", "an HFT
  engine in PHP", "a data-science pipeline in C"). Give at most **1–2 alternatives**, each with
  a one-line *why*, then ask the maintainer to confirm or override.
- **Do not raise it** for a reasonable choice. If the language is a sensible fit, state "good
  fit for this domain" in one line and move on — no second-guessing, no nagging.
- The recommendation is about *fit*, never about taste. Record the maintainer's decision; if
  they keep a sub-optimal language deliberately, note the rationale and proceed without friction.

## Where each language excels (the basis for the advice)

| Language | Sweet spot |
|---|---|
| **C** | Embedded/firmware, OS/kernel/drivers, real-time, tiny-footprint, C-ABI libraries, interpreters |
| **C++** | High-performance systems, game engines, low-latency/HFT, audio/video, native libs with tight resource control |
| **C#** | .NET enterprise apps & backends, Windows/desktop, Unity game scripting, cross-platform via .NET |
| **VB (VB.NET)** | Legacy/maintenance .NET & Office-adjacent line-of-business apps (rarely the choice for greenfield) |
| **Python** | Data science / ML / AI, scripting & automation, backends (FastAPI/Django), glue, fast prototyping |
| **Java** | Large enterprise backends, Android, big-data (Spark/Kafka), long-lived JVM systems |
| **JavaScript** | Browser frontend, quick Node scripts, broad ecosystem (prefer TypeScript for non-trivial apps) |
| **TypeScript** | Typed frontend (React/Angular/Vue), Node/Deno backends, full-stack, large JS codebases |
| **PHP** | Web backends & CMS (WordPress, Laravel/Symfony), shared-hosting web apps |
| **Go** | Cloud-native services, CLIs, networking, concurrency-heavy backends, DevOps/container tooling |
| **Rust** | Memory-safe systems, performance- *and* safety-critical code, WASM, CLIs, embedded |
| **Lua** | Embedded scripting (games, Redis, Neovim, OpenResty/nginx, Roblox), lightweight extensions/config |
| **Kotlin** | Android, modern JVM backends, Kotlin Multiplatform, a safer Java |
| **Scala** | Big-data (Spark), functional/typed JVM systems, data pipelines |
| **Swift** | Apple platforms (iOS/macOS), and server-side Swift |
| **Dart** | Flutter cross-platform apps (mobile/web/desktop), Dart CLIs |
| **Ruby** | Web apps (Rails), scripting, DevOps tooling, rapid product development |
| **COBOL** | Mainframe/business batch & transaction systems — legacy maintenance & modernization (GnuCOBOL) |
| **Pascal** | Legacy desktop/embedded (Free Pascal/Delphi), maintenance of existing Pascal codebases |
| **SQL** | Relational data: schema, queries, migrations, stored procedures, analytics — usually a *component*, not the primary language |
| **CSS** | Styling / design systems — a *supporting layer* of a web frontend, not a standalone program |
| **HTML** | Markup / structure / static sites & templates — a *supporting layer*, not a program |

## Domain → strong fits (quick reference)

| Domain | First choices |
|---|---|
| Embedded / firmware / real-time | C, Rust, C++ |
| OS / drivers / kernel | C, Rust, C++ |
| High-performance / low-latency / games | C++, Rust, C |
| Cloud-native microservices / CLIs / DevOps | Go, Rust, Java, Kotlin, Ruby |
| Data / ML / AI | Python (Scala/Java for big-data pipelines) |
| Web backend | Go, Java, Kotlin, C#, Python, Ruby, PHP, TypeScript (Node) |
| Web frontend | TypeScript (with HTML/CSS), JavaScript |
| Mobile apps | Kotlin (Android), Swift (iOS), Dart/Flutter (cross-platform) |
| Desktop / Windows / enterprise LOB | C#, Java (VB only for legacy) |
| Embedded scripting / plugins / extensions | Lua, Python |
| Relational data / analytics | SQL (as a component of a larger project) |
| Mainframe / legacy modernization | COBOL, Pascal (maintenance & migration) |
| Safety-critical / WASM | Rust |

## SQL, CSS, HTML — a caveat

These are **supporting technologies**, not primary application languages, and EADOS's project
model (build/test/lint, a version constant, a namespaced source tree) does not map cleanly onto
them. In practice they appear *inside* a project (the web service whose frontend is HTML/CSS/JS;
the backend that owns the SQL schema). When a maintainer names one of these as the *primary*
language, treat it as a fit question: clarify the actual deliverable (a database/schema project?
a design-system? a static site?) and either (a) pick the primary language it really belongs to
and record these as secondary components, or (b) proceed with an adapted profile if it genuinely
is a standalone artifact (e.g. a published CSS design-system or a SQL migration package).

## Output

A one-line fit verdict per project ("good fit" or "consider X because Y — your call"), the
maintainer's final decision, and — when the decision was non-obvious — a
[lesson](../learning/README.md) so future runs in the same domain start from it.
