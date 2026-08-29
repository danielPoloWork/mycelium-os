#!/usr/bin/env python3
"""yamlmini — EADOS's dependency-free YAML loader (extracted from render.py, #166).

Every gate tool (render, eados_lint, eados, doctor, phase_runner, autotune, traceability, …)
parses its data through this ONE module, so the parser under every gate can no longer be
perturbed by renderer changes (and vice versa). `render.load_yaml` remains a re-export, so
callers are unchanged.

Supported subset (validated against PyYAML by tools/tests/test_loader.py): block/flow mappings
and sequences — including a SEQUENCE-ROOT document (#315), which used to load as an empty dict —
block-style mapping items, double-quoted scalars WITH escapes
(\\n \\t \\r \\0 \\" \\\\ \\/), single-quoted scalars with '' escaping, `|` (clip) and `|-`
(strip) block scalars, and int / true / false / null / ~ literals.

Deliberate deviations from YAML 1.1, kept because they are safer for a manifest:
  * yes/no/on/off are NOT booleans (avoids the "Norway problem"); only true/false are.
    The same applies to a bare KEY (`on:` stays the string "on", where YAML 1.1 makes it True).
  * unquoted decimals/exponents stay strings (versions like 1.22 are not coerced).
  * ISO dates stay strings — `2026-07-26` is "2026-07-26", not a datetime.date. Every consumer
    here compares, sorts or renders these as text, and a date object would have to be turned back
    into a string on the way out; keeping one representation end to end removes that round trip.
  * mapping KEYS are never type-coerced: a bare `123:` is the string "123", where YAML 1.1 makes
    it the integer 123. A quoted key is unquoted (`"foo":` -> foo), which is not a deviation but
    the rule; only the coercion is skipped, consistently with the scalar rules above.

A single leading UTF-8 BOM is stripped (utf-8-sig semantics, PyYAML-compatible) — Windows
editors and PowerShell 5.1's `Out-File -Encoding utf8` write one, and it is not content.

Anything outside the subset fails LOUDLY (ADR-0006/0008: reject, never guess). That includes
the two #153 silent-truncation constructs — a quoted scalar that does not close on its line,
and a flow collection left open at end-of-line — which used to truncate everything after them,
plus folded `>` block scalars (`>`/`>-`/`>+`), which used to drop their body and keep the bare
`">"` as the value (#194) — use a literal block scalar (|), which is byte-exact here.
Out of scope (rejected or best-effort, never byte-identical): `|+` keep-chomping, anchors,
tags, and multi-document streams.
"""

import re


def _strip_comment(text):
    out, q, i = [], None, 0
    while i < len(text):
        c = text[i]
        if q:
            out.append(c)
            # Inside a double-quoted scalar a backslash escapes the next char, so an
            # escaped quote (\") must not be read as closing the string.
            if c == "\\" and q == '"' and i + 1 < len(text):
                out.append(text[i + 1])
                i += 2
                continue
            if c == q:
                q = None
        elif c in "\"'":
            q = c
            out.append(c)
        elif c == "#" and (i == 0 or text[i - 1] == " "):
            break
        else:
            out.append(c)
        i += 1
    return "".join(out).rstrip()


def _split_top(text, sep=","):
    parts, depth, q, buf, i = [], 0, None, [], 0
    while i < len(text):
        c = text[i]
        if q:
            buf.append(c)
            if c == "\\" and q == '"' and i + 1 < len(text):
                buf.append(text[i + 1])     # escaped char: never a separator or quote-close
                i += 2
                continue
            if c == q:
                q = None
        elif c in "\"'":
            q = c
            buf.append(c)
        elif c in "[{":
            depth += 1
            buf.append(c)
        elif c in "]}":
            depth -= 1
            buf.append(c)
        elif c == sep and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(c)
        i += 1
    if buf:
        parts.append("".join(buf))
    return parts


# Recognised escapes in a YAML double-quoted scalar (the subset a manifest needs).
_DQ_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0",
               '"': '"', "\\": "\\", "/": "/", " ": " "}


def _unescape_double(body):
    """Apply double-quoted YAML escapes; an unknown \\x degrades to the literal x."""
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            out.append(_DQ_ESCAPES.get(nxt, nxt))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _scalar(s):
    s = s.strip()
    if s == "":
        return ""
    if s[0] == "[" and s[-1] == "]":
        inner = s[1:-1].strip()
        return [_scalar(x) for x in _split_top(inner)] if inner else []
    if s[0] == "{" and s[-1] == "}":
        inner, d = s[1:-1].strip(), {}
        if inner:
            for pair in _split_top(inner):
                k, _, v = pair.partition(":")
                d[k.strip()] = _scalar(v.strip())
        return d
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return _unescape_double(s[1:-1])
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1].replace("''", "'")     # YAML single-quote escaping: '' -> '
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", s):
        # A leading-zero integer (e.g. a ZIP/year like "08540") would lose the zero if
        # coerced — keep it a string, consistent with "unquoted decimals stay strings".
        if re.fullmatch(r"-?0\d+", s):
            return s
        return int(s)
    return s


def _split_key(text):
    """`(raw_key, value)` for a block-mapping line, or None when the line is not a mapping entry.

    YAML's own rule, which the old `partition(":")` and the old `[A-Za-z0-9_]+:` probe both only
    approximated: the key ends at the first ':' that is **followed by a space or end-of-line** and
    lies **outside** any quoted scalar or flow collection. So a ':' inside a URL, a quoted string
    or a `{...}` flow map is not a separator, while `a:b: c` splits after `a:b` (#316).
    """
    depth, quote, i = 0, None, 0
    while i < len(text):
        c = text[i]
        if quote:
            if quote == '"' and c == "\\":
                i += 2
                continue
            if c == quote:
                if quote == "'" and i + 1 < len(text) and text[i + 1] == "'":
                    i += 2                       # '' inside single quotes is an escaped quote
                    continue
                quote = None
        elif c in "\"'":
            quote = c
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        elif c == ":" and depth == 0 and (i + 1 == len(text) or text[i + 1] == " "):
            return text[:i].strip(), text[i + 1:].strip()
        i += 1
    return None


def _key_text(raw):
    """A mapping key as YAML reads it: a quoted key loses its quotes and escapes; a plain key is
    used verbatim. Keys are deliberately NOT type-coerced — a bare `123:` stays the string "123",
    the same no-coercion rule this loader applies to scalars."""
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        return _unescape_double(raw[1:-1])
    if len(raw) >= 2 and raw[0] == "'" and raw[-1] == "'":
        return raw[1:-1].replace("''", "'")
    return raw


_DOC_MARKERS = ("---", "...")


def _value_of(content):
    """The scalar/value part of one comment-stripped line: past any `- ` item dashes, and past
    the `key:` when the line is a mapping entry (a colon followed by a space or end-of-line —
    a colon inside a plain scalar, like a URL port, is not a key separator)."""
    v = content.strip()
    while v.startswith("- "):
        v = v[2:].lstrip()
    key, sep, rest = v.partition(":")
    if sep and (rest == "" or rest.startswith(" ")) and ":" not in key and '"' not in key \
            and "'" not in key and "[" not in key and "{" not in key:
        v = rest.strip()
    return v


def _open_at_eol(value):
    """Which #153 truncation construct `value` leaves open at end-of-line: 'quote' for a quoted
    scalar that never closes, 'flow' for an unclosed [ / { collection, None when the line is
    whole. Escape-aware ('' in single quotes, \\ in double quotes)."""
    if not value:
        return None
    if value[0] in "\"'":
        q, i = value[0], 1
        while i < len(value):
            c = value[i]
            if q == '"' and c == "\\":
                i += 2
                continue
            if c == q:
                if q == "'" and i + 1 < len(value) and value[i + 1] == "'":
                    i += 2                     # '' inside single quotes is an escaped quote
                    continue
                return None                    # the quote closes on its own line — whole
            i += 1
        return "quote"
    if value[0] in "[{":
        depth, q, i = 0, None, 0
        while i < len(value):
            c = value[i]
            if q:
                if q == '"' and c == "\\":
                    i += 2
                    continue
                if c == q:
                    q = None
            elif c in "\"'":
                q = c
            elif c in "[{":
                depth += 1
            elif c in "]}":
                depth -= 1
            i += 1
        if q is not None:
            return "quote"                     # a quoted entry inside the flow never closes
        if depth > 0:
            return "flow"
    return None


def _reject_unsupported(text):
    """Fail loudly on constructs outside the supported subset rather than mis-parsing them.

    A single leading `---` document-start marker is tolerated (idiomatic, single-document);
    any *later* `---`/`...` marks a multi-document stream (out of scope) and a tab in the
    indentation is invalid YAML. #166 adds the two #153 silent-truncation constructs: a quoted
    scalar that opens but does not close on its line (the loader does not fold multi-line
    quoted scalars) and a flow collection ([ / {) left open at end-of-line (the loader does not
    read wrapped flow collections) — both used to truncate everything after them. Literal
    block-scalar bodies (|) are exempt from the line checks; folded `>` scalars are rejected
    outright (#194) — parse_map cannot fold them, so it would keep the bare ">" and drop the body.
    """
    seen_content = False
    lines = text.split("\n")
    i, n = 0, len(lines)
    while i < n:
        num, raw = i + 1, lines[i]
        i += 1
        s = raw.strip()
        if s in _DOC_MARKERS:
            if seen_content or s == "...":
                raise ValueError(
                    f"line {num}: multi-document streams / '...' end markers are not supported; "
                    "the manifest must be a single YAML document"
                )
            continue  # a leading '---' document-start is fine
        lead = raw[: len(raw) - len(raw.lstrip())]
        if "\t" in lead:
            raise ValueError(f"line {num}: tab indentation is not valid YAML — use spaces")
        if not s or s.startswith("#"):
            continue
        seen_content = True
        value = _value_of(_strip_comment(s))
        marker = value.rstrip()
        if marker in (">", ">-", ">+"):
            # Folded `>` scalars are legal YAML but out of the subset: parse_map has no `>`
            # branch, so the body below would be skipped here and the bare ">" kept as the
            # value — the #153 silent-truncation class, live in this repo's own profiles (#194).
            # Reject loudly; a literal block scalar (|) is byte-exact and needs no folding.
            raise ValueError(
                f"line {num}: folded block scalars ('>', '>-', '>+') are not supported — the "
                "loader does not fold them and used to silently drop the body (#194); use a "
                "literal block scalar (|) instead"
            )
        if marker in ("|", "|-", "|+"):
            # A block-scalar body is literal content — skip it (blank or deeper-indented lines).
            base = len(raw) - len(raw.lstrip(" "))
            while i < n and (not lines[i].strip()
                             or len(lines[i]) - len(lines[i].lstrip(" ")) > base):
                i += 1
            continue
        if s == "-" or (s.startswith("-") and not s.startswith("- ") and not s[1:].strip()):
            # A sequence item whose value lives on the FOLLOWING lines ("-" alone). parse_list
            # only recognises "- <content>", so parse_map used to swallow the dash as a KEY and
            # produce {'-': {...}} instead of a list — the #153 silent-misparse class again,
            # found while fixing #315. Reject loudly; the inline form ("- key: value") is read
            # correctly and is what every shipped file already uses.
            raise ValueError(
                f"line {num}: a block sequence item must carry its first key on the dash line "
                "('- key: value') — a bare '-' with the value on the following lines is not "
                "supported and used to parse as a mapping key named '-' (#315)"
            )
        construct = _open_at_eol(value)
        if construct == "quote":
            raise ValueError(
                f"line {num}: a quoted scalar must open and close on the same line — the loader "
                "does not fold multi-line quoted scalars, and used to silently truncate here "
                "(#153); keep it single-line or use a block scalar (|)"
            )
        if construct == "flow":
            raise ValueError(
                f"line {num}: a flow collection ([...] / {{...}}) must close on the same line — "
                "the loader does not read wrapped flow collections, and used to silently "
                "truncate here (#153); keep it single-line or use a block sequence (- items)"
            )


def load_yaml(text):
    # A leading U+FEFF — the UTF-8 BOM as decoded text, written by Windows Notepad and
    # PowerShell 5.1's `Out-File -Encoding utf8` — is a byte-order artifact, not content.
    # Strip exactly one, matching utf-8-sig / PyYAML (differentially pinned in test_loader).
    # Left in place it glued itself to the first key (U+FEFF + 'identity') and produced a
    # confusing unknown-top-level-section error plus phantom missing-field reports.
    if text.startswith(chr(0xFEFF)):
        text = text[1:]
    _reject_unsupported(text)   # loud failure outside the subset, not silent guessing
    lines = text.split("\n")
    n = len(lines)
    pos = [0]

    def indent_of(line):
        return len(line) - len(line.lstrip(" "))

    def skip_blanks():
        # Comments, blank lines, and a tolerated leading '---' (validated by
        # _reject_unsupported, which rejects any non-leading marker) are not content.
        while pos[0] < n:
            s = lines[pos[0]].strip()
            if s and not s.startswith("#") and s != "---":
                return
            pos[0] += 1

    def parse_block_scalar(parent_indent, chomp=""):
        collected, base = [], None
        while pos[0] < n:
            line = lines[pos[0]]
            if line.strip() == "":
                collected.append("")
                pos[0] += 1
                continue
            if indent_of(line) <= parent_indent:
                break
            if base is None:
                base = indent_of(line)
            # Never slice into real content: if a later line is less-indented than the
            # first, dedent only by what it actually has.
            collected.append(line[min(base, indent_of(line)):])
            pos[0] += 1
        if chomp == "+":                       # keep: preserve trailing blank lines as-is
            return ("\n".join(collected) + "\n") if collected else ""
        while collected and collected[-1] == "":   # clip/strip both drop trailing blanks
            collected.pop()
        if not collected:
            return ""
        body = "\n".join(collected)
        return body if chomp == "-" else body + "\n"   # strip: no final newline; clip: one

    def parse_map(indent, first_line=None):
        # `first_line` lets a block-style sequence item ("- key: value") feed its dash-stripped
        # first line in without rewriting the shared `lines` buffer (the parser no longer
        # mutates its own input). Subsequent iterations read normally from the buffer.
        result = {}
        while True:
            skip_blanks()
            if pos[0] >= n:
                break
            line = first_line if first_line is not None else lines[pos[0]]
            first_line = None
            ind = indent_of(line)
            if ind != indent or line.strip().startswith("- "):
                break
            split = _split_key(_strip_comment(line.strip()))
            if split is None:
                # A line in mapping context that carries no `key:` — malformed YAML (PyYAML
                # rejects it too). `partition(":")` used to invent a key from the whole line.
                raise ValueError(
                    f"line {pos[0] + 1}: expected a 'key: value' mapping entry, got "
                    f"{line.strip()[:60]!r}"
                )
            key, val = _key_text(split[0]), split[1]
            pos[0] += 1
            if val in ("|", "|-", "|+"):
                result[key] = parse_block_scalar(indent, val[1:])  # "" clip, "-" strip, "+" keep
            elif val == "":
                skip_blanks()
                if pos[0] < n:
                    nxt = lines[pos[0]]
                    nind = indent_of(nxt)
                    is_item = nxt.strip().startswith("- ")
                    if is_item and nind == indent:
                        # YAML permits a block sequence at the SAME indent as its key;
                        # accept it instead of silently treating the key as null.
                        result[key] = parse_list(indent)
                    elif nind > indent:
                        result[key] = parse_list(nind) if is_item else parse_map(nind)
                    else:
                        result[key] = None
                else:
                    result[key] = None
            else:
                result[key] = _scalar(val)
        return result

    def parse_list(indent):
        items = []
        while True:
            skip_blanks()
            if pos[0] >= n:
                break
            line = lines[pos[0]]
            if indent_of(line) != indent or not line.strip().startswith("- "):
                break
            after_dash = line[indent + 1:]                       # everything past the '-'
            key_col = indent + 1 + (len(after_dash) - len(after_dash.lstrip(" ")))
            content = line[key_col:]
            if _split_key(_strip_comment(content)) is not None:
                # Block-style mapping item ("- key: value" + aligned continuation lines).
                # Feed the dash-stripped first line to parse_map (no buffer mutation).
                #
                # This probe used to be `[A-Za-z0-9_]+\s*:`, which missed any first key carrying a
                # hyphen, a dot, a space or quotes — the item then fell through to _scalar and
                # became a STRING, and parse_list broke on the next line, silently dropping every
                # continuation (#316). Only the FIRST key was ever charset-restricted, so merely
                # reordering two keys inside an item changed the parse. `_split_key` applies YAML's
                # real rule instead of a charset guess.
                items.append(parse_map(key_col, first_line=" " * key_col + content))
            else:
                items.append(_scalar(_strip_comment(content.strip())))
                pos[0] += 1
        return items

    skip_blanks()
    if pos[0] < n and lines[pos[0]].strip().startswith("- "):
        # A SEQUENCE-ROOT document. parse_map breaks on the first `- ` item and returned {} —
        # silently discarding the whole file (#315). It was live on learning/lessons.yaml, whose
        # consumers each grew their own textual parser to work around it; supporting the root
        # here is what lets them collapse back onto this one loader.
        return parse_list(indent_of(lines[pos[0]]))
    return parse_map(0)
