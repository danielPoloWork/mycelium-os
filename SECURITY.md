# Security Policy

## Supported versions

Until `mycelium-os` reaches `v1.0.0`, only the latest released minor line receives
security fixes. After `1.0.0`, the supported window is defined in
[`docs/workflow/maintenance.md`](docs/workflow/maintenance.md).

| Version | Supported |
|---------|-----------|
| latest released `0.x` | ✅ |
| older `0.x` | ❌ |

## Reporting a vulnerability

**Do not open a public issue or PR for a security problem.** Report it privately via
[GitHub private vulnerability reporting](https://docs.github.com/code-security/security-advisories)
on this repository (**Security** tab → *Report a vulnerability*), to `danielPoloWork`.

> **Interim, as of 2026-09-15.** That form is **not yet enabled on this repository**, so a
> reporter who is not a collaborator cannot submit it. Enabling it is a repository setting
> and is pending with the maintainer (risk register
> [F3](docs/security/audit-2026-08-29-bootstrap.md), re-rated `medium` at roadmap 6.16).
>
> Until it is on, and **without describing the problem anywhere public**: open an issue whose
> entire content is *"I have a security report and need a private channel"*, or contact
> `danielPoloWork` through the address on their GitHub profile. Do not put the vulnerability,
> a reproduction, or an affected version in that issue — the request for a channel is all it
> should contain. This paragraph disappears the day the setting is enabled.

Please include:

- the affected version(s) and platform/toolchain;
- a minimal reproduction (a failing test is ideal);
- the observed impact and, if known, the root cause.

## Response targets

From **v1.0.0**, a report rated **critical** is acknowledged within **24 hours** and fixed or
mitigated within **7 days** — the targets spec 06 §4 adopts at the point where a published
compatibility promise makes them honest. Before v1.0.0, and for every other severity, reports
are triaged by severity on a best-effort basis; this is a single-maintainer project, and a
target it could not keep would be worse than none.

## What to expect

1. **Acknowledgement** of the report, within the targets above.
2. **Triage & fix under embargo** on a private branch / draft advisory; the SemVer level of
   the fix is assessed by the decision tree in
   [`docs/workflow/maintenance.md`](docs/workflow/maintenance.md).
3. **Coordinated release**: the fix ships, then the advisory is published. The fix is
   recorded in `CHANGELOG.md` under a **Security** entry with the advisory / CVE reference.
4. **Backport** to every still-supported release line.

Thank you for reporting responsibly.
