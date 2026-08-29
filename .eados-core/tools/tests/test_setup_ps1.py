#!/usr/bin/env python3
"""Behavioral smoke for setup.ps1 — the guided EADOS installer for Windows (PowerShell).

setup.ps1 is the PowerShell-native equivalent of the POSIX setup.sh: one script that is scriptable
via parameters and interactive when asked. Driven through PowerShell (`pwsh`, falling back to
Windows `powershell`), this asserts parity with the POSIX installer: plan resolution (`-PrintPlan`),
argument validation, fail-closed checksum verification (incl. a local `-SumsFile`), additive
no-clobber extraction, and the interactive flow (new = extract + git-init, existing = extract-only)
— all offline via the `-From` seam. SKIPs cleanly when no PowerShell is on PATH (so non-Windows
dev boxes without `pwsh` don't fail); GitHub's ubuntu runners ship `pwsh`, so CI exercises it.

    python .eados-core/tools/tests/test_setup_ps1.py
"""

import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(os.path.dirname(TOOLS))
SETUP_PS1 = os.path.join(REPO_ROOT, "setup", "setup.ps1")

# Which PowerShell to drive. `pwsh` (7.x, cross-platform) by default — but setup.ps1 TARGETS
# Windows, where the default shell is Windows PowerShell 5.1, a different engine with materially
# different behaviour (no `&&`/`||` chain operators, no ternary, `Set-Content` defaulting to the
# ANSI codepage). Testing only under pwsh on a Linux runner therefore proves the script parses and
# runs somewhere other than where its users are. EADOS_PS_EXE lets CI pin the interpreter so the
# 5.1 cell is a real cell rather than a second pwsh run (#318).
PWSH = (shutil.which(os.environ.get("EADOS_PS_EXE", "").strip())
        if os.environ.get("EADOS_PS_EXE", "").strip()
        else (shutil.which("pwsh") or shutil.which("powershell")))
HAVE_GIT = shutil.which("git") is not None


def check(label, cond, failures):
    if not cond:
        failures.append(label)


def run(*args, cwd=None, stdin=""):
    """Run setup.ps1 via PowerShell; return (rc, out, err). Filesystem cases pass cwd + RELATIVE
    paths so tar reads them on Windows (bsdtar) and Linux/pwsh (GNU tar) alike."""
    proc = subprocess.run([PWSH, "-NoProfile", "-File", SETUP_PS1, *args],
                          capture_output=True, text=True, cwd=cwd, input=stdin)
    if os.environ.get("EADOS_PS_VERBOSE", "").strip():
        # The suite reports assertion LABELS, which is unhelpful when a whole class of them fails
        # on a machine you cannot reach. Echo what the installer actually said (#318).
        print(f"--- setup.ps1 {' '.join(map(str, args))} -> rc={proc.returncode}")
        for stream, text in (("out", proc.stdout), ("err", proc.stderr)):
            for line in (text or "").splitlines():
                print(f"    [{stream}] {line}")
    return proc.returncode, proc.stdout, proc.stderr


def make_bundle(path):
    """Write a tiny prefix-less .tar.gz fixture (agent contract + a factory file + a Claude Code
    command adapter, mirroring the real bundle's layout since #239); return sha256 hex."""
    with tarfile.open(path, "w:gz") as tar:
        for name, body in (("AGENTS.md", b"# agent contract\n"),
                           (".eados-core/tools/render.py", b"# render\n"),
                           (".claude/commands/eados/init.md", b"# adapter fixture\n")):
            entry = tarfile.TarInfo(name)
            entry.size = len(body)
            tar.addfile(entry, io.BytesIO(body))
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def make_symlink_bundle(path):
    """A malicious bundle: a symlink whose target escapes the target root, then a file written
    through it. The entry NAMES are innocuous (no '..' / leading '/'), so only a link-type check
    catches it. Return sha256 hex. (issue #129 — tar-slip)"""
    with tarfile.open(path, "w:gz") as tar:
        link = tarfile.TarInfo("pwn")
        link.type = tarfile.SYMTYPE
        link.linkname = "../escaped"
        tar.addfile(link)
        body = b"owned\n"
        through = tarfile.TarInfo("pwn/escaped.txt")
        through.size = len(body)
        tar.addfile(through, io.BytesIO(body))
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main():
    failures = []

    if PWSH is None:
        print("test-setup-ps1: SKIP — no PowerShell (pwsh / powershell) on PATH")
        return 0
    if not os.path.exists(SETUP_PS1):
        print(f"test-setup-ps1: FAIL — setup.ps1 not found at {SETUP_PS1}")
        return 1

    # #318: the checksum is the installer's ONLY integrity control, and it must not depend on
    # cmdlet auto-loading. On a Windows PowerShell 5.1 process whose PSModulePath was set up for
    # pwsh 7 — what a GitHub windows runner hands you, and what any user with pwsh installed can
    # hit — `Get-FileHash` is simply "not recognized". Pull the SHIPPED helper out of setup.ps1
    # with the PowerShell parser (no copy, no regex) and drive it in a process where the cmdlet
    # genuinely raises, so the fallback is proven rather than assumed.
    probe = (
        "$e=$null;$t=$null;"
        f"$a=[System.Management.Automation.Language.Parser]::ParseFile('{SETUP_PS1}',"
        "[ref]$t,[ref]$e);"
        "$f=$a.FindAll({param($n) $n -is "
        "[System.Management.Automation.Language.FunctionDefinitionAst] -and "
        "$n.Name -eq 'Get-Sha256'},$true);"
        "if(-not $f){Write-Output 'MISSING';exit};"
        "Invoke-Expression $f[0].Extent.Text;"
        "$tmp=[System.IO.Path]::GetTempFileName();"
        "[System.IO.File]::WriteAllBytes($tmp,[byte[]](1,2,3));"
        "$ok=(Get-Sha256 $tmp);"
        "function Get-FileHash { throw 'not recognized' };"
        "$broken=(Get-Sha256 $tmp);"
        "Remove-Item $tmp -Force;"
        "Write-Output ($(if($ok -eq $broken -and $ok.Length -eq 64){'SAME'}else{'DIFF'}))"
    )
    p = subprocess.run([PWSH, "-NoProfile", "-Command", probe],
                       capture_output=True, text=True)
    check("setup.ps1 hashes identically with Get-FileHash available and unavailable",
          "SAME" in (p.stdout or ""), failures)

    # -Help
    rc, out, _ = run("-Help")
    check("-Help exits 0", rc == 0, failures)
    check("-Help shows usage + flags", "USAGE" in out and "-Mode" in out and "-PrintPlan" in out,
          failures)

    # plan: latest -> the stable /latest/download/ URL
    rc, out, _ = run("-PrintPlan")
    check("-PrintPlan exits 0", rc == 0, failures)
    check("plan (default) uses the latest-download URL",
          "releases/latest/download/pgs-eados-bundle.tar.gz" in out, failures)
    check("plan (default) is mode existing", "existing" in out, failures)
    check("plan (default) repo is danielPoloWork/pgs-eados",
          "danielPoloWork/pgs-eados" in out, failures)

    # plan: pinned -Ref -> the tagged download URL
    rc, out, _ = run("-PrintPlan", "-Ref", "v2.2.0")
    check("plan -Ref uses the tagged download URL",
          "releases/download/v2.2.0/pgs-eados-bundle.tar.gz" in out, failures)

    # plan: -Mode new -> <Path>/<RepoName>
    rc, out, _ = run("-PrintPlan", "-Mode", "new", "-Path", "/tmp/x", "-RepoName", "proj")
    check("plan -Mode new resolves target <Path>/<RepoName>", "/tmp/x/proj" in out, failures)

    # plan: -Repo override flows into the URL
    rc, out, _ = run("-PrintPlan", "-Repo", "octo/fork")
    check("plan -Repo override flows into the URL", "github.com/octo/fork/" in out, failures)

    # -Mode new without -RepoName -> a clear error
    rc, out, err = run("-Mode", "new", "-NonInteractive")
    check("-Mode new without -RepoName fails", rc != 0, failures)
    check("…with a message naming RepoName", "RepoName" in (err + out), failures)

    with tempfile.TemporaryDirectory() as tmp:
        good_sha = make_bundle(os.path.join(tmp, "bundle.tar.gz"))  # relative "bundle.tar.gz" under cwd
        seq = [0]

        def fresh_target():
            seq[0] += 1
            name = f"t{seq[0]}"
            os.mkdir(os.path.join(tmp, name))
            return name

        # additive success: empty target, checksum pinned
        tgt = fresh_target()
        rc, _, _ = run("-From", "bundle.tar.gz", "-Sha256", good_sha, "-Mode", "existing",
                       "-Path", tgt, "-NonInteractive", cwd=tmp)
        check("additive install into an empty target succeeds", rc == 0, failures)
        check("…extracted the agent contract",
              os.path.exists(os.path.join(tmp, tgt, "AGENTS.md")), failures)
        check("…extracted the factory file",
              os.path.exists(os.path.join(tmp, tgt, ".eados-core", "tools", "render.py")), failures)

        # additive refusal: a pre-existing file is never clobbered (and nothing partial is written)
        tgt = fresh_target()
        with open(os.path.join(tmp, tgt, "AGENTS.md"), "w", encoding="utf-8") as fh:
            fh.write("ORIGINAL")
        rc, out, err = run("-From", "bundle.tar.gz", "-NoVerify", "-Mode", "existing",
                           "-Path", tgt, "-NonInteractive", cwd=tmp)
        check("install refuses to overwrite an existing file", rc != 0, failures)
        check("…names the conflicting file", "AGENTS.md" in (err + out), failures)
        with open(os.path.join(tmp, tgt, "AGENTS.md"), encoding="utf-8") as fh:
            kept = fh.read() == "ORIGINAL"
        check("…leaves the existing file untouched", kept, failures)
        check("…and extracts nothing (no partial write)",
              not os.path.exists(os.path.join(tmp, tgt, ".eados-core", "tools", "render.py")), failures)

        # checksum verification: a wrong -Sha256 fails
        tgt = fresh_target()
        rc, out, err = run("-From", "bundle.tar.gz", "-Sha256", "deadbeef", "-Mode", "existing",
                           "-Path", tgt, "-NonInteractive", cwd=tmp)
        check("a wrong -Sha256 fails (checksum mismatch)", rc != 0, failures)
        check("…with a 'mismatch' message", "mismatch" in (out + err).lower(), failures)

        # fail-closed: no checksum source and no -NoVerify -> refuse, extract nothing
        tgt = fresh_target()
        rc, out, err = run("-From", "bundle.tar.gz", "-Mode", "existing", "-Path", tgt,
                           "-NonInteractive", cwd=tmp)
        check("fail-closed: refuses to extract unverified", rc != 0, failures)
        check("…extracts nothing when unverified",
              not os.path.exists(os.path.join(tmp, tgt, "AGENTS.md")), failures)

        # a missing local bundle -> a clean error
        tgt = fresh_target()
        rc, out, err = run("-From", "nope.tar.gz", "-NoVerify", "-Mode", "existing",
                           "-Path", tgt, "-NonInteractive", cwd=tmp)
        check("a missing -From bundle fails cleanly", rc != 0, failures)
        check("…with a 'not found' message", "not found" in (out + err).lower(), failures)

        # existing mode requires the target dir to already exist
        rc, _, _ = run("-From", "bundle.tar.gz", "-NoVerify", "-Mode", "existing",
                       "-Path", "absent-dir", "-NonInteractive", cwd=tmp)
        check("existing mode requires the target dir to exist", rc != 0, failures)

        # --- tar-slip: reject a bundle carrying a symlink/hardlink entry (issue #129) ---
        evil_sha = make_symlink_bundle(os.path.join(tmp, "evil.tar.gz"))
        tgt = fresh_target()
        rc, out, err = run("-From", "evil.tar.gz", "-Sha256", evil_sha, "-Mode", "existing",
                           "-Path", tgt, "-NonInteractive", cwd=tmp)
        check("rejects a symlink-bearing bundle even when its checksum matches (tar-slip)",
              rc != 0 and "symlink" in (out + err).lower(), failures)
        check("…and extracts nothing through the symlink",
              not os.path.exists(os.path.join(tmp, tgt, "pwn")), failures)
        tgt = fresh_target()
        rc, _, _ = run("-From", "evil.tar.gz", "-NoVerify", "-Mode", "existing",
                       "-Path", tgt, "-NonInteractive", cwd=tmp)
        check("the symlink guard runs even under -NoVerify", rc != 0, failures)

        # --- host adapters (#239): scripted default is opt-in; -WithAdapters places them;
        #     declined adapters neither block on nor touch a colliding user file ---
        adapter_rel = os.path.join(".claude", "commands", "eados", "init.md")
        tgt = fresh_target()
        rc, _, _ = run("-From", "bundle.tar.gz", "-Sha256", good_sha, "-Mode", "existing",
                       "-Path", tgt, "-NonInteractive", cwd=tmp)
        check("scripted default omits the adapters (opt-in)",
              rc == 0 and not os.path.exists(os.path.join(tmp, tgt, ".claude")), failures)

        tgt = fresh_target()
        rc, _, _ = run("-From", "bundle.tar.gz", "-Sha256", good_sha, "-WithAdapters",
                       "-Mode", "existing", "-Path", tgt, "-NonInteractive", cwd=tmp)
        check("-WithAdapters places the Claude Code adapters",
              rc == 0 and os.path.exists(os.path.join(tmp, tgt, adapter_rel)), failures)

        tgt = fresh_target()
        os.makedirs(os.path.join(tmp, tgt, ".claude", "commands", "eados"))
        with open(os.path.join(tmp, tgt, adapter_rel), "w", encoding="utf-8") as fh:
            fh.write("USER FILE")
        rc, _, _ = run("-From", "bundle.tar.gz", "-Sha256", good_sha, "-Mode", "existing",
                       "-Path", tgt, "-NonInteractive", cwd=tmp)
        with open(os.path.join(tmp, tgt, adapter_rel), encoding="utf-8") as fh:
            intact = fh.read() == "USER FILE"
        check("declined adapters ignore a colliding user file (install proceeds, file intact)",
              rc == 0 and intact
              and os.path.exists(os.path.join(tmp, tgt, "AGENTS.md")), failures)
        rc2, out2, err2 = run("-From", "bundle.tar.gz", "-NoVerify", "-WithAdapters",
                              "-Mode", "existing", "-Path", tgt, "-NonInteractive", cwd=tmp)
        check("-WithAdapters still refuses to clobber a user adapter file",
              rc2 != 0 and "init.md" in (out2 + err2), failures)

        rc, out, err = run("-WithAdapters", "-NoAdapters", "-PrintPlan")
        check("-WithAdapters conflicts with -NoAdapters", rc != 0, failures)
        rc, out, _ = run("-PrintPlan")
        check("the plan states the adapters decision", "adapters:" in out, failures)

        # interactive NEW (offline): extract AND git-init
        # stdin sequences: mode, path(/name), the #239 adapters question, then the confirm
        rc, out, err = run("-Interactive", "-NoGh", "-From", "bundle.tar.gz", "-NoVerify",
                           cwd=tmp, stdin="1\nsub\nproj\ny\ny\n")
        target = os.path.join(tmp, "sub", "proj")
        check("interactive new install exits 0", rc == 0, failures)
        check("…extracted the bundle into <parent>/<name>",
              os.path.exists(os.path.join(target, "AGENTS.md")), failures)
        check("…and the adapters (answered yes)",
              os.path.exists(os.path.join(target, adapter_rel)), failures)
        if HAVE_GIT:
            check("…and git-inited the new repo", os.path.isdir(os.path.join(target, ".git")),
                  failures)

        # interactive EXISTING (offline): extract, NO git init, adapters declined
        os.mkdir(os.path.join(tmp, "ex"))
        rc, out, err = run("-Interactive", "-NoGh", "-From", "bundle.tar.gz", "-NoVerify",
                           cwd=tmp, stdin="2\nex\nn\ny\n")
        check("interactive existing install exits 0", rc == 0, failures)
        check("…extracted the bundle into the existing dir",
              os.path.exists(os.path.join(tmp, "ex", "AGENTS.md")), failures)
        check("…without the adapters (answered no)",
              not os.path.exists(os.path.join(tmp, "ex", ".claude")), failures)
        check("…and did NOT git-init an existing repo",
              not os.path.isdir(os.path.join(tmp, "ex", ".git")), failures)

        # interactive abort: answering no writes nothing
        rc, out, err = run("-Interactive", "-DryRun", cwd=tmp, stdin="2\n.\nn\nn\n")
        check("answering 'n' at the confirm aborts (exit 0)", rc == 0, failures)
        check("…with an 'aborted' message", "abort" in (out + err).lower(), failures)

        # --- M9.4: verify against a SHA256SUMS file (the format release.yml publishes) ---
        real = "pgs-eados-bundle.tar.gz"
        real_sha = make_bundle(os.path.join(tmp, real))
        with open(os.path.join(tmp, "SHA256SUMS"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(f"{real_sha}  {real}\n")
            fh.write(f"{'0' * 64} *pgs-eados-bundle.zip\n")   # '*' (binary) form must be stripped
            fh.write(f"{'1' * 64}  setup.ps1\n")

        tgt = fresh_target()
        rc, out, err = run("-From", real, "-SumsFile", "SHA256SUMS", "-Mode", "existing",
                           "-Path", tgt, "-NonInteractive", cwd=tmp)
        check("verify via -SumsFile succeeds (picks the bundle line)", rc == 0, failures)
        check("…extracted the bundle", os.path.exists(os.path.join(tmp, tgt, "AGENTS.md")), failures)

        with open(os.path.join(tmp, "BAD_SUMS"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(f"{'a' * 64}  {real}\n")
        tgt = fresh_target()
        rc, out, err = run("-From", real, "-SumsFile", "BAD_SUMS", "-Mode", "existing",
                           "-Path", tgt, "-NonInteractive", cwd=tmp)
        check("a tampered -SumsFile fails (mismatch)",
              rc != 0 and "mismatch" in (out + err).lower(), failures)

        tgt = fresh_target()
        rc, out, err = run("-From", real, "-SumsFile", "missing-sums", "-Mode", "existing",
                           "-Path", tgt, "-NonInteractive", cwd=tmp)
        check("a missing -SumsFile fails cleanly",
              rc != 0 and "not found" in (out + err).lower(), failures)

    if failures:
        print("test-setup-ps1: FAIL\n")
        for f in failures:
            print(f"  {f}")
        print(f"\n{len(failures)} expectation(s) failed.")
        return 1
    print("test-setup-ps1: OK — plan resolution, arg validation, fail-closed checksum, additive "
          "no-clobber, and interactive new/existing all hold; offline via -From. (parity with the "
          "POSIX installers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
