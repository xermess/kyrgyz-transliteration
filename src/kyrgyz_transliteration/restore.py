"""Восстановление кыргызских слов из латиницы, набранной без диакритики.

Схемы `turkic` и `bgn` обратимы, только если латиница написана полностью:
``döñgölök`` -> ``дөңгөлөк``. Но люди пишут ``dongolok``, а по такой записи
выбрать между «дөңгөлөк» и «донголок» нельзя — оба слова подчиняются гармонии
гласных. Единственный надёжный способ — словарь.

:class:`Wordlist` индексирует кыргызские слова по «сплющенному» ASCII-ключу
(``дөңгөлөк`` -> ``dongolok``, ``donggolok``). При разборе латиницы слово
ищется в словаре: нашлось ровно одно — берём его, иначе слово разбирается
обычными правилами схемы. Если точного совпадения нет, ищется самая длинная
основа из словаря, а к оставшемуся суффиксу применяется гармония гласных
(``dongolokton`` -> ``дөңгөлөктөн``).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .core import Table, apply_table, match_case
from .schemes import get_scheme

__all__ = [
    "Wordlist",
    "ascii_key",
    "builtin_wordlist",
    "restore_words",
]

_WORD_RE = re.compile(r"[^\W\d_]+")

# Варианты ASCII-записи каждой кыргызской буквы: так их набирают на практике.
# Из них строятся все ключи слова (ө и ү без диакритики неотличимы от о и у,
# ң пишут и как n, и как ng, ж — как j, zh или c).
_KEY_VARIANTS = {
    "а": ("a",), "б": ("b",), "в": ("v",), "г": ("g",), "д": ("d",),
    "е": ("e",), "ё": ("yo", "e"), "ж": ("j", "zh", "c"), "з": ("z",),
    "и": ("i",), "й": ("y", "i"), "к": ("k",), "л": ("l",), "м": ("m",),
    "н": ("n",), "ң": ("n", "ng"), "о": ("o",), "ө": ("o", "oe"), "п": ("p",),
    "р": ("r",), "с": ("s",), "т": ("t",), "у": ("u",), "ү": ("u", "ue"),
    "ф": ("f",), "х": ("h", "kh"), "ц": ("ts",), "ч": ("ch",), "ш": ("sh",),
    "щ": ("shch",), "ъ": ("",), "ы": ("y", "i"), "ь": ("",), "э": ("e",),
    "ю": ("yu",), "я": ("ya",),
}

#: Ограничение на число ключей одного слова.
MAX_KEYS_PER_WORD = 64

# Сведение латиницы всех схем к ASCII.
_FOLD = {
    "ı": "i", "ş": "sh", "ç": "ch", "ñ": "ng", "ö": "o", "ü": "u", "ğ": "g",
    "ž": "zh", "š": "sh", "č": "ch", "ŝ": "shch", "ô": "o", "ù": "u",
    "ņ": "ng", "è": "e", "ë": "yo", "û": "yu", "â": "ya", "ʺ": "", "ʹ": "",
    "ʼ": "", "ʻ": "", "'": "", "’": "",
}

_FRONT_VOWELS = "еёиөүэ"
_BACK_VOWELS = "аоуы"
_FRONT_HARMONY = {"о": "ө", "у": "ү", "О": "Ө", "У": "Ү"}
_BACK_HARMONY = {"и": "ы", "И": "Ы"}

#: Минимальная длина основы при поиске по началу слова.
DEFAULT_MIN_STEM = 4

_SUFFIX_TABLE: Optional[Table] = None


def _suffix_table() -> Table:
    """Таблица для разбора суффикса: ASCII-схема плюс латиница других схем.

    Суффикс приходит из того же небрежного текста, что и основа, поэтому
    читать его алфавитом запрошенной схемы нельзя: в `turkic` «ch» — это
    «ц + х», а человек имел в виду «ч».
    """
    global _SUFFIX_TABLE
    if _SUFFIX_TABLE is None:
        base = get_scheme("ascii").reverse_table()
        mapping = dict(base.mapping)
        mapping.setdefault("c", "ж")
        _SUFFIX_TABLE = Table(
            mapping=mapping,
            fold=dict(base.fold),
            contextual=tuple(base.contextual),
        )
    return _SUFFIX_TABLE


def ascii_key(word: str) -> str:
    """ASCII-ключ слова: нижний регистр, без диакритики и апострофов.

        >>> ascii_key("döñgölök")
        'donggolok'
        >>> ascii_key("Kırgız")
        'kirgiz'
        >>> ascii_key("İş")
        'ish'
    """
    key, _ = _key_with_offsets(word)
    return key


def _strip_marks(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _key_with_offsets(word: str) -> Tuple[str, List[int]]:
    """ASCII-ключ и длина ключа после каждого символа исходного слова.

    Длины нужны, чтобы по границе основы в ключе найти границу в самом слове:
    один символ может дать два (``ñ`` -> ``ng``).
    """
    chars: List[str] = []
    offsets = [0]
    for char in word:
        lowered = char.lower()
        if len(lowered) != 1:  # 'İ'.lower() — это два символа
            lowered = _strip_marks(lowered) or char
        folded = _FOLD[lowered] if lowered in _FOLD else _strip_marks(lowered)
        chars.append(folded)
        offsets.append(offsets[-1] + len(folded))
    return "".join(chars), offsets


class Wordlist:
    """Словарь кыргызских слов, проиндексированный по ASCII-ключам.

    Слова задаются кириллицей. Ключ, на который претендуют два разных слова
    (``кол`` и ``көл`` -> ``kol``), считается неоднозначным и не используется:
    такое слово останется как набрано.

        >>> words = Wordlist(["дөңгөлөк", "түшүнүк"])
        >>> words.lookup("dongolok")
        'дөңгөлөк'
        >>> words.lookup("tushunuk")
        'түшүнүк'
        >>> words.lookup("kompyuter") is None
        True
    """

    def __init__(
        self,
        words: Iterable[str] = (),
        *,
        min_stem: int = DEFAULT_MIN_STEM,
    ) -> None:
        self.min_stem = min_stem
        self._forms: Dict[str, Optional[str]] = {}
        self._words: Set[str] = set()
        self.add(words)

    def add(self, words: Iterable[str]) -> "Wordlist":
        """Добавить слова (кириллицей). Возвращает сам словарь."""
        for word in words:
            word = word.strip()
            if not word:
                continue
            self._words.add(word)
            for key in self._keys(word):
                if not key:
                    continue
                if key in self._forms and self._forms[key] != word:
                    self._forms[key] = None  # неоднозначный ключ
                else:
                    self._forms[key] = word
        return self

    @staticmethod
    def _keys(word: str) -> Set[str]:
        """Все ASCII-записи слова, которые может набрать человек."""
        keys = [""]
        for char in word.lower():
            variants = _KEY_VARIANTS.get(char)
            if variants is None:
                folded = ascii_key(char)
                variants = (folded,) if folded else ("",)
            keys = [key + variant for key in keys for variant in variants]
            if len(keys) > MAX_KEYS_PER_WORD:
                keys = keys[:MAX_KEYS_PER_WORD]
        return {key for key in keys if key}

    @classmethod
    def from_file(cls, path: str, *, min_stem: int = DEFAULT_MIN_STEM) -> "Wordlist":
        """Прочитать список слов из файла: одно слово в строке, ``#`` — комментарий."""
        with open(path, encoding="utf-8") as handle:
            words = _parse_words(handle.read())
        return cls(words, min_stem=min_stem)

    def lookup(self, key: str) -> Optional[str]:
        """Слово по ASCII-ключу или ``None``, если его нет или ключ неоднозначен."""
        return self._forms.get(ascii_key(key))

    def lookup_stem(self, key: str) -> Optional[Tuple[str, int]]:
        """Самая длинная однозначная основа: ``(слово, длина ключа основы)``."""
        for size in range(len(key) - 1, self.min_stem - 1, -1):
            form = self._forms.get(key[:size])
            if form is not None:
                return form, size
        return None

    def ambiguous_keys(self) -> List[str]:
        """Ключи, на которые претендует больше одного слова."""
        return sorted(key for key, form in self._forms.items() if form is None)

    def words(self) -> List[str]:
        """Все слова словаря."""
        return sorted(self._words)

    def __len__(self) -> int:
        return len(self._words)

    def __contains__(self, word: str) -> bool:
        return self.lookup(word) is not None

    def __repr__(self) -> str:  # pragma: no cover - для отладки
        return "Wordlist({0} слов, {1} ключей)".format(len(self._words), len(self._forms))


def _parse_words(text: str) -> List[str]:
    """Разобрать список слов: одно слово в строке, ``#`` — комментарий."""
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


_BUILTIN: Optional[Wordlist] = None


def builtin_wordlist() -> Wordlist:
    """Встроенный список частотных кыргызских слов (кешируется).

        >>> len(builtin_wordlist()) > 200
        True
        >>> builtin_wordlist().lookup("dongolok")
        'дөңгөлөк'
    """
    global _BUILTIN
    if _BUILTIN is None:
        try:
            from importlib.resources import files

            source = files("kyrgyz_transliteration.data").joinpath("kyrgyz_frequent.txt")
            text = source.read_text(encoding="utf-8")
        except (ImportError, AttributeError):  # pragma: no cover - Python < 3.9
            import os

            path = os.path.join(os.path.dirname(__file__), "data", "kyrgyz_frequent.txt")
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        _BUILTIN = Wordlist(_parse_words(text))
    return _BUILTIN


def _harmonize(suffix: str, stem: str) -> str:
    """Согласовать гласные суффикса с основой (гармония гласных)."""
    last = ""
    for char in reversed(stem.lower()):
        if char in _FRONT_VOWELS or char in _BACK_VOWELS:
            last = char
            break
    if not last:
        return suffix
    table = _FRONT_HARMONY if last in _FRONT_VOWELS else _BACK_HARMONY
    return "".join(table.get(char, char) for char in suffix)


def restore_words(text: str, wordlist: Wordlist) -> str:
    """Заменить латинские слова на кириллические по словарю.

    Слова, которых в словаре нет, остаются как есть — их разберёт обычная
    транслитерация (:func:`kyrgyz_transliteration.to_cyrillic` делает это сама,
    если передать ей ``wordlist``).

        >>> restore_words("Dongolok jok", builtin_wordlist())
        'Дөңгөлөк жок'
        >>> restore_words("dongolokton", builtin_wordlist())
        'дөңгөлөктөн'
    """
    result: List[str] = []
    position = 0

    for match in _WORD_RE.finditer(text):
        token = match.group()
        replacement = _restore_token(token, wordlist)
        if replacement is None:
            continue
        result.append(text[position : match.start()])
        result.append(replacement)
        position = match.end()

    result.append(text[position:])
    return "".join(result)


def _restore_token(token: str, wordlist: Wordlist) -> Optional[str]:
    """Кириллическое написание слова по словарю или ``None``, если не нашлось."""
    key, offsets = _key_with_offsets(token)
    if not key.isascii() or not key.isalpha():
        return None

    form = wordlist.lookup(key)
    if form is not None:
        return match_case(token, form, all_caps=_is_caps(token))

    found = wordlist.lookup_stem(key)
    if found is None:
        return None
    stem, size = found
    try:
        split = offsets.index(size)
    except ValueError:  # граница основы попала внутрь диграфа
        return None
    suffix = apply_table(token[split:], _suffix_table())
    return match_case(token, stem + _harmonize(suffix, stem), all_caps=_is_caps(token))


def _is_caps(token: str) -> bool:
    letters = [char for char in token if char.isalpha()]
    return len(letters) > 1 and all(char.isupper() for char in letters)
