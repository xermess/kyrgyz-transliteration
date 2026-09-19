# -*- coding: utf-8 -*-
import re

import pytest

from kyrgyz_transliteration import Table, apply_table


def test_contextual_marker_changes_reading():
    table = Table(
        mapping={"y": "ы", "\ue000": "й", "a": "а"},
        contextual=((re.compile(r"(?<=a)y"), "\ue000"),),
    )
    assert apply_table("ay ya", table) == "ай ыа"


def test_contextual_rule_must_preserve_length():
    table = Table(mapping={"a": "а"}, contextual=((re.compile(r"a"), "aa"),))
    with pytest.raises(ValueError):
        apply_table("a", table)


def test_unknown_characters_pass_through():
    table = Table(mapping={"а": "a"})
    assert apply_table("а→ب 42", table) == "a→ب 42"


def test_empty_text():
    assert apply_table("", Table(mapping={"а": "a"})) == ""


def test_word_initial_has_priority():
    table = Table(mapping={"e": "е", "k": "к", "l": "л"}, word_initial={"e": "э"})
    assert apply_table("el kel", table) == "эл кел"
