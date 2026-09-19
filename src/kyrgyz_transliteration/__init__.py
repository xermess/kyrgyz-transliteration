"""Транслитерация кыргызского языка: кириллица <-> латиница.

    >>> from kyrgyz_transliteration import to_latin, to_cyrillic, slugify
    >>> to_latin("Кыргыз Республикасы")
    'Kırgız Respublikası'
    >>> to_cyrillic("Kırgız Respublikası")
    'Кыргыз Республикасы'
    >>> slugify("Ысык-Көл")
    'ysyk-kol'
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Tuple, Union

from .core import Table, apply_table, match_case
from .restore import (
    Wordlist,
    ascii_key,
    builtin_wordlist,
    restore_words,
)
from .schemes import (
    CYRILLIC_LETTERS,
    DEFAULT_SCHEME,
    SCHEMES,
    Scheme,
    UnknownSchemeError,
    get_scheme,
    list_schemes,
    register_scheme,
)

__version__ = "0.1.0"

__all__ = [
    "CYRILLIC_LETTERS",
    "DEFAULT_SCHEME",
    "SCHEMES",
    "Scheme",
    "Table",
    "UnknownSchemeError",
    "Wordlist",
    "alphabet_table",
    "apply_table",
    "ascii_key",
    "builtin_wordlist",
    "detect_script",
    "get_scheme",
    "list_schemes",
    "match_case",
    "register_scheme",
    "restore_words",
    "slugify",
    "to_cyrillic",
    "to_latin",
    "transliterate",
    "__version__",
]

SchemeArg = Union[str, Scheme]
WordlistArg = Union[None, bool, Wordlist]

_CYRILLIC_RE = re.compile(r"[Ѐ-ԯ]")
_LATIN_RE = re.compile(r"[A-Za-zÀ-ɏ]")

# Сведение латиницы с диакритикой к ASCII (для slugify).
_ASCII_FOLD = {
    "ı": "i", "ş": "s", "ç": "c", "ğ": "g", "ñ": "n", "ö": "o", "ü": "u",
    "ž": "z", "š": "s", "č": "c", "ŝ": "s", "ô": "o", "ù": "u", "ņ": "n",
    "è": "e", "ë": "e", "û": "u", "â": "a",
}


def to_latin(text: str, scheme: SchemeArg = DEFAULT_SCHEME) -> str:
    """Перевести кыргызский текст с кириллицы на латиницу.

        >>> to_latin("Манас атанын ак сарайы")
        'Manas atanın ak sarayı'
        >>> to_latin("Манас", scheme="bgn")
        'Manas'
    """
    return apply_table(text, get_scheme(scheme).forward_table())


def to_cyrillic(
    text: str,
    scheme: SchemeArg = DEFAULT_SCHEME,
    wordlist: WordlistArg = None,
) -> str:
    """Перевести кыргызский текст с латиницы на кириллицу.

    :param wordlist: словарь для латиницы, набранной без диакритики
        (:class:`Wordlist`), или ``True`` — взять встроенный список слов. Слова
        из словаря восстанавливаются целиком, остальные разбираются правилами
        схемы.

        >>> to_cyrillic("Manas atanın ak sarayı")
        'Манас атанын ак сарайы'
        >>> to_cyrillic("dongolok")
        'донголок'
        >>> to_cyrillic("dongolok", wordlist=True)
        'дөңгөлөк'
    """
    if wordlist:
        if wordlist is True:
            wordlist = builtin_wordlist()
        text = restore_words(text, wordlist)
    return apply_table(text, get_scheme(scheme).reverse_table())


def detect_script(text: str) -> str:
    """Определить письменность текста.

    Возвращает ``"cyrillic"``, ``"latin"``, ``"mixed"`` или ``"unknown"``.

        >>> detect_script("Бишкек")
        'cyrillic'
        >>> detect_script("Bişkek")
        'latin'
        >>> detect_script("2026")
        'unknown'
    """
    cyrillic = len(_CYRILLIC_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    if not cyrillic and not latin:
        return "unknown"
    if cyrillic and latin:
        minority = min(cyrillic, latin) / float(cyrillic + latin)
        if minority > 0.25:
            return "mixed"
    return "cyrillic" if cyrillic >= latin else "latin"


def transliterate(
    text: str,
    scheme: SchemeArg = DEFAULT_SCHEME,
    direction: str = "auto",
    wordlist: WordlistArg = None,
) -> str:
    """Транслитерировать текст в заданном направлении.

    :param direction: ``"latin"``, ``"cyrillic"`` или ``"auto"`` — в последнем
        случае направление выбирается по преобладающей письменности.
    :param wordlist: см. :func:`to_cyrillic`; используется только при переводе
        на кириллицу.

        >>> transliterate("Бишкек")
        'Bişkek'
        >>> transliterate("Bişkek")
        'Бишкек'
        >>> transliterate("dongolok", wordlist=True)
        'дөңгөлөк'
    """
    if direction == "latin":
        return to_latin(text, scheme)
    if direction == "cyrillic":
        return to_cyrillic(text, scheme, wordlist)
    if direction != "auto":
        raise ValueError(
            "direction должен быть 'auto', 'latin' или 'cyrillic', получено {0!r}".format(direction)
        )
    cyrillic = len(_CYRILLIC_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    if cyrillic == 0 and latin == 0:
        return text
    if cyrillic >= latin:
        return to_latin(text, scheme)
    return to_cyrillic(text, scheme, wordlist)


def slugify(text: str, separator: str = "-", scheme: SchemeArg = "ascii") -> str:
    """Сделать из текста ASCII-слаг для URL, файлов и идентификаторов.

        >>> slugify("Ысык-Көл облусу")
        'ysyk-kol-oblusu'
        >>> slugify("Жалал-Абад", separator="_")
        'jalal_abad'
    """
    latin = to_latin(text, scheme).lower()
    latin = "".join(_ASCII_FOLD.get(char, char) for char in latin)
    latin = unicodedata.normalize("NFKD", latin)
    latin = "".join(char for char in latin if not unicodedata.combining(char))
    slug = re.sub(r"[^a-z0-9]+", lambda _: separator, latin)
    if separator:
        slug = slug.strip(separator)
    return slug


def alphabet_table(scheme: SchemeArg = DEFAULT_SCHEME) -> List[Tuple[str, str]]:
    """Таблица соответствий схемы: список пар (кириллица, латиница).

        >>> alphabet_table("bgn")[7]
        ('ж', 'j')
    """
    mapping: Dict[str, str] = get_scheme(scheme).mapping
    return [(letter, mapping.get(letter, "")) for letter in CYRILLIC_LETTERS]
