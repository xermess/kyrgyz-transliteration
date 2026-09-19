# -*- coding: utf-8 -*-
import pytest

from kyrgyz_transliteration import (
    Wordlist,
    ascii_key,
    builtin_wordlist,
    restore_words,
    to_cyrillic,
    transliterate,
)


@pytest.mark.parametrize(
    "word,key",
    [
        ("döñgölök", "donggolok"),
        ("Kırgız", "kirgiz"),
        ("İş", "ish"),
        ("Çüy", "chuy"),
        ("kıtaʺ", "kita"),
    ],
)
def test_ascii_key(word, key):
    assert ascii_key(word) == key


def test_wordlist_indexes_all_typing_variants():
    words = Wordlist(["дөңгөлөк", "жаңылык"])
    for typed in ("dongolok", "donggolok", "döñgölök", "DONGOLOK"):
        assert words.lookup(typed) == "дөңгөлөк"
    for typed in ("jangylyk", "jangilik", "zhangylyk", "cañılık"):
        assert words.lookup(typed) == "жаңылык"


def test_ambiguous_key_is_not_used():
    words = Wordlist(["кол", "көл"])
    assert words.lookup("kol") is None
    assert words.ambiguous_keys() == ["kol"]
    assert len(words) == 2


def test_wordlist_container_protocol():
    words = Wordlist(["мектеп"])
    assert "mektep" in words
    assert "dongolok" not in words
    assert words.words() == ["мектеп"]


def test_wordlist_from_file(tmp_path):
    path = tmp_path / "words.txt"
    path.write_text("# комментарий\n\nдөңгөлөк\nкөйгөй\n", encoding="utf-8")
    words = Wordlist.from_file(str(path))
    assert len(words) == 2
    assert words.lookup("koygoy") == "көйгөй"


def test_restore_words_keeps_unknown_words_and_punctuation():
    words = Wordlist(["дөңгөлөк"])
    assert restore_words("Dongolok, kompyuter!", words) == "Дөңгөлөк, kompyuter!"


def test_restore_words_keeps_case():
    words = Wordlist(["көчө"])
    assert restore_words("kocho Kocho KOCHO", words) == "көчө Көчө КӨЧӨ"


def test_restore_words_ignores_cyrillic_input():
    assert restore_words("Дөңгөлөк жок", builtin_wordlist()) == "Дөңгөлөк жок"


@pytest.mark.parametrize(
    "typed,expected",
    [
        ("dongolokton", "дөңгөлөктөн"),
        ("dongolokko", "дөңгөлөккө"),
        ("dongolokchu", "дөңгөлөкчү"),
        ("okmottun", "өкмөттүн"),
        ("duinodo", "дүйнөдө"),
        ("mektepte", "мектепте"),
        ("bishkekten", "бишкектен"),
    ],
)
def test_stem_lookup_with_vowel_harmony(typed, expected):
    assert restore_words(typed, builtin_wordlist()) == expected


def test_stem_lookup_respects_min_stem():
    words = Wordlist(["көчө"], min_stem=10)
    assert restore_words("kochodo", words) == "kochodo"
    assert restore_words("kochodo", Wordlist(["көчө"], min_stem=4)) == "көчөдө"


def test_builtin_wordlist_is_cached_and_useful():
    assert builtin_wordlist() is builtin_wordlist()
    assert len(builtin_wordlist()) > 200
    assert builtin_wordlist().lookup("mumkunchuluk") == "мүмкүнчүлүк"


@pytest.mark.parametrize(
    "typed,expected",
    [
        ("dongolok", "дөңгөлөк"),
        ("jonokoy", "жөнөкөй"),
        ("omur", "өмүр"),
        ("kenesh", "кеңеш"),
        ("tushunuk", "түшүнүк"),
        ("kirgiz", "кыргыз"),
        ("kyrgyz", "кыргыз"),
    ],
)
def test_to_cyrillic_with_builtin_wordlist(typed, expected):
    assert to_cyrillic(typed, wordlist=True) == expected
    assert to_cyrillic(typed) != expected or typed == expected


def test_wordlist_does_not_break_correct_latin():
    assert to_cyrillic("döñgölök jañılık", wordlist=True) == "дөңгөлөк жаңылык"
    assert to_cyrillic("Kırgız Respublikası", wordlist=True) == "Кыргыз Республикасы"


def test_transliterate_passes_wordlist_only_to_cyrillic():
    assert transliterate("dongolok", wordlist=True) == "дөңгөлөк"
    assert transliterate("дөңгөлөк", wordlist=True) == "döñgölök"


def test_wordlist_can_be_extended():
    words = Wordlist(builtin_wordlist().words()).add(["көпөлөк"])
    assert restore_words("kopolokton", words) == "көпөлөктөн"
    assert "kopolok" not in builtin_wordlist()
