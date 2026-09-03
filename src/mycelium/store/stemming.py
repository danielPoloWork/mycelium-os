# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Daniel Polo
"""The Porter stemmer, in-repo, so the lexical index can match inflections.

FTS5's `unicode61` tokenizer does no stemming, so `signs` does not match `signed`
and `contributed` does not match `contribution` — a query that inflects a word
differently from the document simply misses it (roadmap 4.17 found one judged
case reaching its answer through a single weak word for exactly this reason).

SQLite ships a `porter` tokenizer that would fix that, and it is *not* what this
module is for. Replacing the tokenizer replaces the surface form: the index then
holds only stems, so a literal match loses its edge over an inflected one, which
ADR-0044 measured as a large overall win with one slice paying for it. Expansion
needs the stem *beside* the surface form in the same index — and for that the
stems have to exist in Python, at index time and at query time, which is this
module.

**Porter (1980), not Porter2.** The choice is not a preference: SQLite's own
`porter` tokenizer implements the 1980 algorithm, and agreeing with it is what
lets the implementation be *checked* against a vetted one rather than against a
transcription of the paper — see
`tests/test_store_stemming.py::test_agrees_with_sqlites_own_porter_tokenizer`,
which stems every term of the real corpus both ways.

The algorithm is deliberately mechanical and known-imperfect: it maps `sign` and
`signed` together but leaves `contribution` and `contributed` apart on some
inputs, and it produces non-words (`generalization` → `gener`). None of that
matters here. A stem is an index key, never shown to anyone, and its only job is
to make two spellings of one word collide more often than two words collide.
"""

from typing import Final

__all__ = ["stem", "stem_text"]

_VOWELS: Final = frozenset("aeiou")

_STEP2: Final = (
    ("ational", "ate"),
    ("tional", "tion"),
    ("enci", "ence"),
    ("anci", "ance"),
    ("izer", "ize"),
    ("bli", "ble"),
    ("alli", "al"),
    ("entli", "ent"),
    ("eli", "e"),
    ("ousli", "ous"),
    ("ization", "ize"),
    ("ation", "ate"),
    ("ator", "ate"),
    ("alism", "al"),
    ("iveness", "ive"),
    ("fulness", "ful"),
    ("ousness", "ous"),
    ("aliti", "al"),
    ("iviti", "ive"),
    ("biliti", "ble"),
    ("logi", "log"),
)
_STEP3: Final = (
    ("icate", "ic"),
    ("ative", ""),
    ("alize", "al"),
    ("iciti", "ic"),
    ("ical", "ic"),
    ("ful", ""),
    ("ness", ""),
)
_STEP4: Final = (
    "al",
    "ance",
    "ence",
    "er",
    "ic",
    "able",
    "ible",
    "ant",
    "ement",
    "ment",
    "ent",
    "ion",
    "ou",
    "ism",
    "ate",
    "iti",
    "ous",
    "ive",
    "ize",
)


def _is_consonant(word: str, index: int) -> bool:
    """Whether `word[index]` is a consonant — `y` depends on what precedes it."""
    letter = word[index]
    if letter in _VOWELS:
        return False
    if letter != "y":
        return True
    return index == 0 or not _is_consonant(word, index - 1)


def _measure(stem: str) -> int:
    """Porter's *m*: how many vowel-consonant sequences `stem` contains."""
    count = 0
    previous_was_vowel = False
    for index in range(len(stem)):
        vowel = not _is_consonant(stem, index)
        if previous_was_vowel and not vowel:
            count += 1
        previous_was_vowel = vowel
    return count


def _has_vowel(stem: str) -> bool:
    return any(not _is_consonant(stem, index) for index in range(len(stem)))


def _ends_double_consonant(stem: str) -> bool:
    return len(stem) >= 2 and stem[-1] == stem[-2] and _is_consonant(stem, len(stem) - 1)


def _ends_cvc(stem: str) -> bool:
    """Consonant-vowel-consonant, where the final consonant is not w, x or y."""
    if len(stem) < 3:
        return False
    return (
        _is_consonant(stem, len(stem) - 3)
        and not _is_consonant(stem, len(stem) - 2)
        and _is_consonant(stem, len(stem) - 1)
        and stem[-1] not in "wxy"
    )


def _replace(word: str, suffix: str, replacement: str, *, minimum: int) -> str | None:
    """Swap `suffix` for `replacement` when the remaining stem measures > `minimum`."""
    if not word.endswith(suffix):
        return None
    stem = word[: len(word) - len(suffix)]
    if _measure(stem) <= minimum:
        return word  # the rule matched and its condition refused it: stop here
    return stem + replacement


def _step1a(word: str) -> str:
    if word.endswith("sses"):
        return word[:-2]
    if word.endswith("ies"):
        return word[:-2]
    if word.endswith("ss"):
        return word
    if word.endswith("s"):
        return word[:-1]
    return word


def _step1b(word: str) -> str:
    if word.endswith("eed"):
        stem = word[:-3]
        return stem + "ee" if _measure(stem) > 0 else word
    for suffix in ("ed", "ing"):
        if word.endswith(suffix):
            stem = word[: len(word) - len(suffix)]
            if not _has_vowel(stem):
                return word
            return _step1b_cleanup(stem)
    return word


def _step1b_cleanup(stem: str) -> str:
    """The second half of step 1b: restore a stem the suffix removal broke."""
    if stem.endswith(("at", "bl", "iz")):
        return stem + "e"
    if _ends_double_consonant(stem) and not stem.endswith(("l", "s", "z")):
        return stem[:-1]
    if _measure(stem) == 1 and _ends_cvc(stem):
        return stem + "e"
    return stem


def _step1c(word: str) -> str:
    if word.endswith("y") and _has_vowel(word[:-1]):
        return word[:-1] + "i"
    return word


def _step2(word: str) -> str:
    for suffix, replacement in _STEP2:
        result = _replace(word, suffix, replacement, minimum=0)
        if result is not None:
            return result
    return word


def _step3(word: str) -> str:
    for suffix, replacement in _STEP3:
        result = _replace(word, suffix, replacement, minimum=0)
        if result is not None:
            return result
    return word


def _step4(word: str) -> str:
    for suffix in _STEP4:
        if not word.endswith(suffix):
            continue
        stem = word[: len(word) - len(suffix)]
        if suffix in {"ion"} and not stem.endswith(("s", "t")):
            return word
        return stem if _measure(stem) > 1 else word
    return word


def _step5a(word: str) -> str:
    if not word.endswith("e"):
        return word
    stem = word[:-1]
    measure = _measure(stem)
    if measure > 1 or (measure == 1 and not _ends_cvc(stem)):
        return stem
    return word


def _step5b(word: str) -> str:
    if word.endswith("ll") and _measure(word[:-1]) > 1:
        return word[:-1]
    return word


def stem(word: str) -> str:
    """Reduce one already-lowercased word to its Porter stem.

    Words of two letters or fewer come back unchanged, as the algorithm
    specifies: there is nothing left to remove, and `is` → `i` would collide with
    every identifier called `i`.
    """
    if len(word) <= 2:
        return word
    result = _step1c(_step1b(_step1a(word)))
    result = _step4(_step3(_step2(result)))
    return _step5b(_step5a(result))


def stem_text(terms: list[str]) -> list[str]:
    """Stem a token list, lowercasing on the way in.

    Tokens are lowercased here rather than by the caller because the index and
    the query must fold case identically, and `unicode61` already folds it on
    both sides — a stem that did not would match nothing on a capitalised word.
    """
    return [stem(term.lower()) for term in terms]
