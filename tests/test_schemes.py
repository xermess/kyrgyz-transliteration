# -*- coding: utf-8 -*-
import pytest

from kyrgyz_transliteration import (
    CYRILLIC_LETTERS,
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


def test_iso9_is_one_to_one():
    values = [lat for lat in SCHEMES["iso9"].mapping.values()]
    assert len(set(values)) == len(values)
    assert not SCHEMES["iso9"].lossy


def test_get_scheme_accepts_object_and_is_case_insensitive():
    assert get_scheme("TURKIC") is SCHEMES["turkic"]
    assert get_scheme(SCHEMES["bgn"]) is SCHEMES["bgn"]


def test_unknown_scheme_lists_alternatives():
    with pytest.raises(UnknownSchemeError) as info:
        get_scheme("klingon")
    assert "turkic" in info.value.args[0]


def test_register_custom_scheme():
    custom = Scheme(
        name="test-minimal",
        title="Тестовая схема",
        mapping=dict(SCHEMES["ascii"].mapping, ж="zh", ө="oe", ү="ue", ң="ng"),
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
