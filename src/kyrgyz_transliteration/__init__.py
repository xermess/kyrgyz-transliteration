"""Транслитерация кыргызского языка: кириллица <-> английская латиница.

    >>> from kyrgyz_transliteration import to_latin, to_cyrillic, slugify
    >>> to_latin("Кыргыз Республикасы")
    'Kyrgyz Respublikasy'
    >>> to_cyrillic("Kyrgyz Respublikasy")
    'Кыргыз Республикасы'
    >>> slugify("Ысык-Көл")
    'ysyk-kol'

Английская латиница не различает ө и о, ү и у, ң и н, поэтому обратно они
восстанавливаются по списку кыргызских слов — он включён по умолчанию:

    >>> to_latin("дөңгөлөк")
    'dongolok'
    >>> to_cyrillic("dongolok")
    'дөңгөлөк'
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Tuple, Union

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

__version__ = "0.2.0"

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


def _resolve_wordlist(wordlist: WordlistArg) -> Optional[Wordlist]:
    """Какой словарь использовать: ``None``/``True`` — встроенный, ``False`` — никакой.

    Сравнение идёт по тождеству, чтобы пустой :class:`Wordlist` (он ложен как
    пустой контейнер) не был принят за ``False``.
    """
    if wordlist is None or wordlist is True:
        return builtin_wordlist()
    if wordlist is False:
        return None
    return wordlist


def to_latin(text: str, scheme: SchemeArg = DEFAULT_SCHEME) -> str:
    """Перевести кыргызский текст с кириллицы на английскую латиницу.

        >>> to_latin("Манас атанын ак сарайы")
        'Manas atanyn ak sarayy'
        >>> to_latin("Ысык-Көл", scheme="bgn")
        'Ysyk-Köl'
    """
    return apply_table(text, get_scheme(scheme).forward_table())


def to_cyrillic(
    text: str,
    scheme: SchemeArg = DEFAULT_SCHEME,
    wordlist: WordlistArg = None,
) -> str:
    """Перевести кыргызский текст с английской латиницы на кириллицу.

    :param wordlist: чем восстанавливать ө, ү и ң, которых в английской
        латинице нет: ``None`` или ``True`` — встроенным списком частотных
        кыргызских слов, ``False`` — ничем (только правилами схемы), или свой
        :class:`Wordlist`. Слова из словаря восстанавливаются целиком,
        остальные разбираются правилами схемы.

        >>> to_cyrillic("Manas atanyn ak sarayy")
        'Манас атанын ак сарайы'
        >>> to_cyrillic("dongolok")
        'дөңгөлөк'
        >>> to_cyrillic("dongolok", wordlist=False)
        'донголок'
    """
    words = _resolve_wordlist(wordlist)
    if words is not None:
        text = restore_words(text, words)
    return apply_table(text, get_scheme(scheme).reverse_table())


def detect_script(text: str) -> str:
    """Определить письменность текста.

    Возвращает ``"cyrillic"``, ``"latin"``, ``"mixed"`` или ``"unknown"``.

        >>> detect_script("Бишкек")
        'cyrillic'
        >>> detect_script("Bishkek")
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
        'Bishkek'
        >>> transliterate("Bishkek")
        'Бишкек'
        >>> transliterate("dongolok")
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


def slugify(text: str, separator: str = "-", scheme: SchemeArg = DEFAULT_SCHEME) -> str:
    """Сделать из текста ASCII-слаг для URL, файлов и идентификаторов.

        >>> slugify("Ысык-Көл облусу")
        'ysyk-kol-oblusu'
        >>> slugify("Жалал-Абад", separator="_")
        'jalal_abad'
    """
    latin = to_latin(text, scheme).lower()
    latin = unicodedata.normalize("NFKD", latin)
    latin = "".join(char for char in latin if not unicodedata.combining(char))
    slug = re.sub(r"[^a-z0-9]+", lambda _: separator, latin)
    if separator:
        slug = slug.strip(separator)
    return slug


def alphabet_table(scheme: SchemeArg = DEFAULT_SCHEME) -> List[Tuple[str, str]]:
    """Таблица соответствий схемы: список пар (кириллица, латиница).

        >>> alphabet_table()[7]
        ('ж', 'j')
        >>> alphabet_table("bgn")[15]
        ('ң', 'ng')
    """
    mapping: Dict[str, str] = get_scheme(scheme).mapping
    return [(letter, mapping.get(letter, "")) for letter in CYRILLIC_LETTERS]
