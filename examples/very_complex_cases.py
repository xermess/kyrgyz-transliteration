"""Very complex Kyrgyz transliteration cases.

Run from the repository root:

    python -m examples.very_complex_cases

The examples deliberately contain many ``ң``, ``ү``, and ``ө`` letters in the
same words and sentences. All Latin output is restricted to English ASCII
letters.
"""

from __future__ import annotations

from kyrgyz_transliteration import (
    builtin_wordlist,
    to_cyrillic,
    to_latin,
)


WORDS = (
    "көңүлдүү",
    "мүмкүнчүлүктөр",
    "өнүгүү",
    "өзгөчө",
    "көчөлөрүбүздөн",
    "дүйнөбүздүн",
    "жөнөкөйлөштүрүү",
)

SENTENCES = (
    "Көңүлдүү мүмкүнчүлүктөр өнүгүүгө жол ачат.",
    "Өзгөчө түшүнүктөрдү дүйнөбүздүн келечеги үчүн изилдейбиз.",
    "Мүмкүнчүлүктөрүбүз көбөйгөн сайын өнүгүүбүз күчөйт.",
)


def show_dense_words() -> None:
    """Convert individual words containing several special Kyrgyz letters."""
    print("Dense words with ң, ү, and ө")
    for word in WORDS:
        english = to_latin(word)
        restored = to_cyrillic(english)
        bgn = to_latin(word, scheme="bgn")
        exact = to_cyrillic(bgn, scheme="bgn")
        print(f"  {word}")
        print(f"    english: {english} -> {restored}")
        print(f"    bgn-compatible: {bgn} -> {exact}")
        assert bgn.isascii()


def show_dense_sentences() -> None:
    """Compare two ASCII-compatible schemes on dense sentences."""
    print("\nDense sentences")
    for sentence in SENTENCES:
        english = to_latin(sentence)
        bgn = to_latin(sentence, scheme="bgn")
        print(f"  {sentence}")
        print(f"    english: {english}")
        print(f"    bgn-compatible: {bgn}")
        assert bgn.isascii()


def show_custom_inflection() -> None:
    """Teach the dictionary an inflected form that is not built in."""
    latin = "Janylyktardy korgondor konulsuz bolboyt"
    built_in = to_cyrillic(latin)
    custom = builtin_wordlist().copy().add(["көргөндөр"])
    restored = to_cyrillic(latin, wordlist=custom)
    print("\nCustom inflected vocabulary")
    print(f"  source:   {latin}")
    print(f"  built-in: {built_in}")
    print(f"  custom:   {restored}")
    assert restored == "Жаңылыктарды көргөндөр көңүлсүз болбойт"


def main() -> None:
    """Run all very complex examples."""
    show_dense_words()
    show_dense_sentences()
    show_custom_inflection()


if __name__ == "__main__":
    main()
