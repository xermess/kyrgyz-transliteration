# -*- coding: utf-8 -*-
import pytest

from kyrgyz_transliteration import (
    SCHEMES,
    detect_script,
    slugify,
    to_cyrillic,
    to_latin,
    transliterate,
)

WORDS = [
    "кыргыз",
    "республика",
    "ысык-көл",
    "жалал-абад",
    "манас",
    "бишкек",
    "таң",
    "күн",
    "өмүр",
    "сүйүү",
    "жаңылык",
    "чүкө",
    "шамал",
    "ыңгайлуу",
    "мүмкүнчүлүк",
]


@pytest.mark.parametrize("word", WORDS)
def test_iso9_round_trip_is_exact(word):
    assert to_cyrillic(to_latin(word, "iso9"), "iso9") == word


@pytest.mark.parametrize("word", WORDS)
def test_turkic_round_trip_is_exact_for_kyrgyz_words(word):
    assert to_cyrillic(to_latin(word, "turkic"), "turkic") == word


@pytest.mark.parametrize("scheme", list(SCHEMES), ids=list(SCHEMES))
def test_non_letters_pass_through(scheme):
    text = "Бишкек, 2026-жыл: 100% — «ок»!"
    result = to_latin(text, scheme)
    for token in ("2026", "100%", "«", "»", "!", ":", ","):
        assert token in result


def test_turkic_defaults():
    assert to_latin("Кыргыз Республикасы") == "Kırgız Respublikası"
    assert to_latin("жаңы жыл") == "cañı cıl"
    assert to_latin("Чүй облусу") == "Çüy oblusu"


def test_bgn_examples():
    assert to_latin("Кыргыз Республикасы", "bgn") == "Kyrgyz Respublikasy"
    assert to_latin("Ысык-Көл", "bgn") == "Ysyk-Köl"
    assert to_latin("Ёлка", "bgn") == "Yolka"
    assert to_latin("Ош шаары", "bgn") == "Osh shaary"


def test_ascii_examples():
    assert to_latin("Ысык-Көл", "ascii") == "Ysyk-Kol"
    assert to_latin("Жалал-Абад", "ascii") == "Jalal-Abad"
    assert to_latin("өмүр", "ascii") == "omur"


def test_case_is_preserved():
    assert to_latin("Жол") == "Col"
    assert to_latin("ЖОЛ") == "COL"
    assert to_latin("Ёлка", "iso9") == "Ëlka"
    assert to_latin("ЁЛКА", "ascii") == "YOLKA"
    assert to_latin("Ёлка", "ascii") == "Yolka"
    assert to_latin("КЫРГЫЗ ЭЛИ") == "KIRGIZ ELİ"
    assert to_cyrillic("KIRGIZ") == "КЫРГЫЗ"
    assert to_cyrillic("Kırgız") == "Кыргыз"


def test_single_letter_word_is_capitalized_not_shouted():
    assert to_latin("Я жаздым", "ascii") == "Ya jazdym"


def test_turkic_dotted_capital_i():
    assert to_latin("Иш") == "İş"
    assert to_cyrillic("İş") == "Иш"
    assert to_cyrillic("IŞ") == "ЫШ"


def test_soft_and_hard_signs_are_dropped_in_latin_schemes():
    assert to_latin("альбом", "ascii") == "albom"
    assert to_latin("подъезд", "turkic") == "podezd"


def test_digraphs_win_over_single_letters():
    assert to_cyrillic("şçı", "turkic") == "щы"
    assert to_cyrillic("shchi", "bgn") == "щи"
    assert to_cyrillic("yurt", "ascii") == "юрт"


def test_latin_extras_are_understood():
    assert to_cyrillic("qwerty", "ascii") == "кверты"


def test_empty_input():
    assert to_latin("") == ""
    assert to_cyrillic("") == ""
    assert slugify("") == ""


def test_detect_script():
    assert detect_script("Бишкек") == "cyrillic"
    assert detect_script("Bişkek") == "latin"
    assert detect_script("Бишкек Bishkek") == "mixed"
    assert detect_script("2026!") == "unknown"


def test_transliterate_auto_direction():
    assert transliterate("Бишкек") == "Bişkek"
    assert transliterate("Bişkek") == "Бишкек"
    assert transliterate("2026") == "2026"
    assert transliterate("Бишкек", direction="cyrillic") == "Бишкек"
    with pytest.raises(ValueError):
        transliterate("Бишкек", direction="sideways")


def test_slugify():
    assert slugify("Ысык-Көл облусу") == "ysyk-kol-oblusu"
    assert slugify("Жалал-Абад", separator="_") == "jalal_abad"
    assert slugify("  Манас   атанын  ") == "manas-atanyn"
    assert slugify("Бишкек 2026") == "bishkek-2026"
    assert slugify("Чүй", separator="") == "chuy"


def test_multiline_text_keeps_line_breaks():
    text = "Кыргыз\nРеспубликасы\n"
    assert to_latin(text) == "Kırgız\nRespublikası\n"


@pytest.mark.parametrize(
    "latin,cyrillic",
    [
        ("Ysyk-Köl", "Ысык-Көл"),
        ("oy-toy", "ой-той"),
        ("ayyl", "айыл"),
        ("myyzam", "мыйзам"),
        ("kyyyn", "кыйын"),
        ("biyik", "бийик"),
        ("kyyuu", "кыюу"),
        ("sayakat", "саякат"),
        ("Kyrgyz Respublikasy", "Кыргыз Республикасы"),
    ],
)
def test_bgn_reverse_resolves_y(latin, cyrillic):
    assert to_cyrillic(latin, "bgn") == cyrillic


@pytest.mark.parametrize("scheme", ["turkic", "bgn", "ascii"])
def test_reverse_ts_after_vowel_is_te_plus_se(scheme):
    assert to_cyrillic(to_latin("айтса кетсе", scheme), scheme) == "айтса кетсе"
    assert to_cyrillic(to_latin("концерт цирк", scheme), scheme) == "концерт цирк"


@pytest.mark.parametrize("scheme", ["turkic", "bgn", "ascii"])
def test_word_initial_e_becomes_reversed_e(scheme):
    assert to_cyrillic(to_latin("эл эмгек эски", scheme), scheme) == "эл эмгек эски"
    assert to_cyrillic(to_latin("мектеп", scheme), scheme) == "мектеп"


def test_ascii_reverse_tolerates_diacritics_of_other_schemes():
    assert to_cyrillic("Ysyk-Köl", "ascii") == "Ысык-Көл"
    assert to_cyrillic("çüy", "ascii") == "чүй"


SENTENCE = "Кыргыз Республикасынын Жогорку Кеңеши"


@pytest.mark.parametrize("scheme", ["turkic", "bgn", "iso9"])
def test_sentence_round_trip(scheme):
    assert to_cyrillic(to_latin(SENTENCE, scheme), scheme) == SENTENCE


WORDS_CORPUS = (
    "айыл кыйын айтса кетсе концерт цирк ай ой үй кыз ырыс ысык-көл тайыз жайыл "
    "сайын аяк оюн саякат бийик мыйзам ыйлады тийет кыюу бай той сарай май жыл "
    "жылдыз кыргыз республика бишкек нарын талас баткен жалал-абад чүй таң күн "
    "өмүр сүйүү жаңылык чүкө шамал ыңгайлуу мүмкүнчүлүк мектеп китеп эже байке "
    "сиңди кыздар эмгек өлкө шаар манас семетей сейтек жийде тоо суу асман эчки "
    "эрте эми экен жер эл тил сөз үн ый айт кел жакшы чоң кичине узун кыска эски"
).split()


@pytest.mark.parametrize("scheme", ["turkic", "bgn", "iso9"])
def test_corpus_round_trip(scheme):
    broken = [
        word for word in WORDS_CORPUS if to_cyrillic(to_latin(word, scheme), scheme) != word
    ]
    assert broken == []
