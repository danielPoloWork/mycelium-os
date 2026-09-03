# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The Porter stemmer (roadmap 4.19, ADR-0048).

An in-repo implementation of a published algorithm invites one question — is it the
algorithm, or a transcription of it — and the answer here is not "read the code". SQLite
ships the same algorithm in C, and
:func:`test_agrees_with_sqlites_own_porter_tokenizer` stems every word of a real corpus
both ways and requires them to agree. That is the load-bearing test; the tables below are
for reading, so a failure says *which rule* broke rather than only that something did.
"""

import re
import sqlite3
from pathlib import Path

import pytest

from mycelium.store.stemming import stem, stem_text

CORPUS = Path(__file__).parent / "fixtures" / "determinism" / "knowledge"
_WORD = re.compile(r"[A-Za-z]{3,}")


# ---------------------------------------------------------------------------
# The rules, one row at a time
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        # The inflections roadmap 4.17 found the index could not match.
        ("signs", "sign"),
        ("signed", "sign"),
        ("signing", "sign"),
        ("contribution", "contribut"),
        ("contributed", "contribut"),
        ("contributing", "contribut"),
        # Step 1a — plurals.
        ("caresses", "caress"),
        ("ponies", "poni"),
        ("ties", "ti"),
        ("caress", "caress"),
        ("cats", "cat"),
        # Step 1b — past and progressive, and the stems they break.
        ("feed", "feed"),
        ("agreed", "agre"),
        ("plastered", "plaster"),
        ("bled", "bled"),
        ("motoring", "motor"),
        ("sing", "sing"),
        ("conflated", "conflat"),
        ("troubled", "troubl"),
        ("sized", "size"),
        ("hopping", "hop"),
        ("falling", "fall"),
        ("hissing", "hiss"),
        ("filing", "file"),
        # Step 1c — terminal y.
        ("happy", "happi"),
        ("sky", "sky"),
        # Steps 2 and 3 — derivational suffixes.
        ("relational", "relat"),
        ("conditional", "condit"),
        ("valenci", "valenc"),
        ("digitizer", "digit"),
        ("vietnamization", "vietnam"),
        ("predication", "predic"),
        ("operator", "oper"),
        ("feudalism", "feudal"),
        ("decisiveness", "decis"),
        ("hopefulness", "hope"),
        ("callousness", "callous"),
        ("analogousli", "analog"),
        ("triplicate", "triplic"),
        ("formative", "form"),
        ("formalize", "formal"),
        ("electriciti", "electr"),
        ("hopeful", "hope"),
        ("goodness", "good"),
        # Step 4 — the suffix goes when what is left is long enough.
        ("revival", "reviv"),
        ("allowance", "allow"),
        ("inference", "infer"),
        ("airliner", "airlin"),
        ("gyroscopic", "gyroscop"),
        ("adjustable", "adjust"),
        ("defensible", "defens"),
        ("irritant", "irrit"),
        ("replacement", "replac"),
        ("adjustment", "adjust"),
        ("dependent", "depend"),
        ("adoption", "adopt"),
        ("homologou", "homolog"),
        ("communism", "commun"),
        ("activate", "activ"),
        ("angulariti", "angular"),
        ("homologous", "homolog"),
        ("effective", "effect"),
        ("bowdlerize", "bowdler"),
        # Step 5 — the trailing e and the doubled l.
        ("probate", "probat"),
        ("rate", "rate"),
        ("cease", "ceas"),
        ("controll", "control"),
        ("roll", "roll"),
    ],
)
def test_the_published_rules(word: str, expected: str) -> None:
    assert stem(word) == expected


def test_a_short_word_is_left_alone() -> None:
    # Porter's own guard. Without it `is` becomes `i`, which would collide with
    # every loop variable in every code block this project indexes.
    for word in ("a", "is", "as", "os", "on"):
        assert stem(word) == word


def test_a_non_ascii_token_survives() -> None:
    # `μs` is a unit this project's own benchmarks use. The algorithm has nothing
    # to say about it and must therefore say nothing.
    assert stem("μs") == "μs"
    assert stem("naïve") == "naïv"


def test_stem_text_folds_case_the_way_the_index_does() -> None:
    # `unicode61` folds case on both sides, so a stem that did not would match
    # nothing on a capitalised word.
    assert stem_text(["Signed", "SIGNS", "signing"]) == ["sign", "sign", "sign"]
    assert stem_text([]) == []


# ---------------------------------------------------------------------------
# The check that matters: agreement with the C implementation
# ---------------------------------------------------------------------------


def _sqlite_stems(words: list[str]) -> dict[str, str]:
    """What SQLite's own `porter` tokenizer reduces each word to."""
    memory = sqlite3.connect(":memory:")
    memory.execute("CREATE VIRTUAL TABLE probe USING fts5(t, tokenize='porter unicode61')")
    memory.executemany("INSERT INTO probe(t) VALUES(?)", [(word,) for word in words])
    memory.execute("CREATE VIRTUAL TABLE probe_v USING fts5vocab(probe, 'instance')")
    found: dict[str, str] = {}
    for term, rowid, _column, _offset in memory.execute(
        "SELECT term, doc, col, offset FROM probe_v"
    ):
        found[words[int(rowid) - 1]] = str(term)
    return found


def _corpus_vocabulary() -> list[str]:
    """Every distinct alphabetic word in the committed determinism corpus."""
    words: set[str] = set()
    for path in sorted(CORPUS.rglob("*.md")):
        words.update(match.group(0).lower() for match in _WORD.finditer(path.read_text("utf-8")))
    return sorted(words)


def test_agrees_with_sqlites_own_porter_tokenizer() -> None:
    """Both implementations of Porter (1980), over a real vocabulary.

    SQLite's is the reference: it is C, it is vetted, and it is already in the
    process. Agreement over a corpus is a far stronger statement than agreement
    over a table someone chose, because nobody chose these words.
    """
    vocabulary = _corpus_vocabulary()
    assert len(vocabulary) > 200, "the fixture corpus should carry a real vocabulary"

    theirs = _sqlite_stems(vocabulary)
    disagreements = {
        word: (stem(word), theirs[word]) for word in vocabulary if stem(word) != theirs[word]
    }
    assert disagreements == {}


def test_the_one_place_the_two_implementations_part() -> None:
    """SQLite's porter is byte-oriented; ours is not, and that is the difference.

    `μs` ends in an `s` as far as bytes are concerned, so SQLite's step 1a strips
    it and the unit becomes the letter mu. Ours sees a two-character word and
    leaves it alone. Recorded as a test rather than a footnote because the
    corpus check above would otherwise have to carry an unexplained exception —
    and because ours is the behaviour a reader would want.
    """
    assert _sqlite_stems(["μs"])["μs"] == "μ"
    assert stem("μs") == "μs"
