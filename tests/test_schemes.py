# -*- coding: utf-8 -*-
import re

import pytest

from kyrgyz_transliteration import (
    CYRILLIC_LETTERS,
    DEFAULT_SCHEME,
    SCHEMES,
    Scheme,
    UnknownSchemeError,
    alphabet_table,
    get_scheme,
    list_schemes,
    register_scheme,
)


@pytest.mark.parametrize("scheme", list(SCHEMES.values()), ids=list(SCHEMES))
def test_every_letter_is_mapped(scheme):
    assert scheme.missing_letters() == []


def test_alphabet_is_36_letters():
    assert len(CYRILLIC_LETTERS) == 36
    assert len(set(CYRILLIC_LETTERS)) == 36


@pytest.mark.parametrize("scheme", list(SCHEMES.values()), ids=list(SCHEMES))
def test_alphabet_table_covers_scheme(scheme):
    table = alphabet_table(scheme)
    assert len(table) == 36
    assert [cyr for cyr, _ in table] == list(CYRILLIC_LETTERS)


def test_default_scheme_is_english():
    assert DEFAULT_SCHEME == "english"
    assert get_scheme() is SCHEMES["english"]


def test_english_writes_the_special_letters_with_plain_english_ones():
    mapping = SCHEMES["english"].mapping
    assert (mapping["ң"], mapping["ө"], mapping["ү"]) == ("n", "o", "u")
    assert (mapping["ж"], mapping["ч"], mapping["ш"]) == ("j", "ch", "sh")


def test_bgn_compatibility_scheme_is_ascii_only():
    mapping = SCHEMES["bgn"].mapping
    assert (mapping["ң"], mapping["ө"], mapping["ү"]) == ("n", "o", "u")


def test_english_ascii_keeps_special_letters_without_diacritics():
    mapping = SCHEMES["english_ascii"].mapping
    assert (mapping["ң"], mapping["ө"], mapping["ү"]) == ("n", "o", "u")
    assert "".join(mapping.values()).isascii()


def test_scheme_rejects_non_english_output_letters():
    with pytest.raises(ValueError, match="English ASCII"):
        Scheme(name="invalid", title="Invalid", mapping={"а": "ö"})


def test_no_scheme_uses_a_non_english_alphabet():
    # ı, ş, ç, ğ, ñ — турецкие; ž, ô, ù, ņ, â — научные. Ни тех, ни других.
    forbidden = set("ışçğñžščŝôùņèëûâ")
    for scheme in list_schemes():
        assert not forbidden & set("".join(scheme.mapping.values()))
        assert all(
            re.fullmatch(r"[A-Za-z]*", value)
            for value in scheme.mapping.values()
        )


def test_get_scheme_accepts_object_and_is_case_insensitive():
    assert get_scheme("ENGLISH") is SCHEMES["english"]
    assert get_scheme(SCHEMES["bgn"]) is SCHEMES["bgn"]


def test_unknown_scheme_lists_alternatives():
    with pytest.raises(UnknownSchemeError) as info:
        get_scheme("turkic")
    assert "english" in info.value.args[0]
    assert "bgn" in info.value.args[0]


def test_register_custom_scheme():
    custom = Scheme(
        name="test-minimal",
        title="Тестовая схема",
        mapping=dict(SCHEMES["english"].mapping, ж="zh", ө="oe", ү="ue", ң="ng"),
    )
    try:
        register_scheme(custom)
        assert get_scheme("test-minimal") is custom
        assert custom in list_schemes()
        with pytest.raises(ValueError):
            register_scheme(custom)
        register_scheme(custom, overwrite=True)
    finally:
        SCHEMES.pop("test-minimal", None)


def test_custom_scheme_can_override_letter_case():
    # Регистровые исключения — общий механизм движка, он же нужен своим схемам.
    custom = Scheme(
        name="test-case",
        title="Схема с регистровым исключением",
        mapping=dict(SCHEMES["english"].mapping),
        latin_upper={"i": "I."},
        latin_lower={"I.": "i"},
    )
    from kyrgyz_transliteration import apply_table

    assert apply_table("Иш", custom.forward_table()) == "I.sh"
