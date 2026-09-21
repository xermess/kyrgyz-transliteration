"""Custom sentence examples supplied by a Kyrgyz speaker.

Run from the repository root:

    python -m examples.custom_cases

The examples use the built-in dictionary plus two application-specific words
that are not currently in the bundled list: ``өлчөп`` and ``өзүмдү``.
"""

from __future__ import annotations

from kyrgyz_transliteration import builtin_wordlist, to_cyrillic, to_latin


CASES = (
    (
        "Menin atym Alibek, jeti olchop bir kesemin.",
        "Менин атым Алибек, жети өлчөп бир кесемин.",
    ),
    (
        "Oorchuluktarga chydabay ichip kettim",
        "Оорчулуктарга чыдабай ичип кеттим",
    ),
    (
        "Suluu kyzdar menen taanyshkym kelet.",
        "Сулуу кыздар менен таанышкым келет.",
    ),
    (
        "Ozumdu ayabay jaman sezip atam.",
        "Өзүмдү аябай жаман сезип атам.",
    ),
    (
        "Nurdoolot Rysbaev degen kim?",
        "Нурдөөлөт Рысбаев деген ким?",
    ),
)


def main() -> None:
    """Restore the supplied Latin sentences and show the reverse direction."""
    words = builtin_wordlist().copy().add(["өлчөп", "өзүмдү"])
    print("Custom Kyrgyz sentence cases")
    for latin, expected in CASES:
        kyrgyz = to_cyrillic(latin, wordlist=words)
        english = to_latin(kyrgyz)
        print(f"  {latin}")
        print(f"    -> {kyrgyz}")
        print(f"    -> {english}")
        assert kyrgyz == expected


if __name__ == "__main__":
    main()
