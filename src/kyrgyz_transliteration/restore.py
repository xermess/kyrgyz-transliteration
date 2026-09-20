"""Восстановление кыргызских слов из английской латиницы.

В английском алфавите нет ни ө, ни ү, ни ң: схема `english` пишет их как o, u
и n, и по такой записи выбрать между «дөңгөлөк» и «донголок» нельзя — оба
слова подчиняются гармонии гласных. Единственный надёжный способ — словарь.
(Схема `bgn` пишет их отдельно — ö, ü, ng — и читается обратно без словаря.)

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
from .schemes import DEFAULT_SCHEME, get_scheme

__all__ = [
    "Wordlist",
    "ascii_key",
    "builtin_wordlist",
    "restore_words",
]

# Слово вместе с дефисами внутри: «Ысык-Көл» и «үй-бүлө» стоит искать в
# словаре целиком — по отдельности «көл» от «кол» не отличить.
_WORD_RE = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")

# Варианты латинской записи каждой кыргызской буквы: так их набирают на
# практике. Из них строятся все ключи слова — ө и ү неотличимы от о и у, ң
# пишут и как n, и как ng, ы и й — и как y, и как i, ж — как j или zh.
_KEY_VARIANTS = {
    "а": ("a",), "б": ("b",), "в": ("v",), "г": ("g",), "д": ("d",),
    "е": ("e",), "ё": ("yo", "e"), "ж": ("j", "zh"), "з": ("z",),
    "и": ("i",), "й": ("y", "i"), "к": ("k",), "л": ("l",), "м": ("m",),
    "н": ("n",), "ң": ("n", "ng"), "о": ("o",), "ө": ("o", "oe"), "п": ("p",),
    "р": ("r",), "с": ("s",), "т": ("t",), "у": ("u",), "ү": ("u", "ue"),
    "ф": ("f",), "х": ("h", "kh"), "ц": ("ts",), "ч": ("ch",), "ш": ("sh",),
    "щ": ("shch",), "ъ": ("",), "ы": ("y", "i"), "ь": ("",), "э": ("e",),
    "ю": ("yu",), "я": ("ya",),
}

#: Ограничение на число ключей одного слова.
MAX_KEYS_PER_WORD = 64

# Сведение латиницы схем к ASCII: ö и ü из BGN/PCGN и знаки ъ и ь.
_FOLD = {
    "ö": "o", "ü": "u", "ʺ": "", "ʹ": "", "ʼ": "", "ʻ": "", "'": "", "’": "",
}

# Конечный согласный основы озвончается перед гласным окончанием:
# китеп -> китеби, эшик -> эшиги, дөңгөлөк -> дөңгөлөгү. Такие основы
# заводятся в словаре отдельно, иначе окончание не отделить.
_FINAL_VOICING = {"к": "г", "п": "б"}

_FRONT_VOWELS = "еёиөүэ"
_BACK_VOWELS = "аоуы"
_FRONT_HARMONY = {"о": "ө", "у": "ү", "О": "Ө", "У": "Ү"}
_BACK_HARMONY = {"и": "ы", "И": "Ы"}

#: Минимальная длина основы при поиске по началу слова.
DEFAULT_MIN_STEM = 4

_SUFFIX_TABLE: Optional[Table] = None


def _suffix_table() -> Table:
    """Таблица для разбора суффикса — обратная таблица схемы по умолчанию.

    От неё отличается только одним: правила начала слова не применяются.
    Суффикс стоит в конце слова, поэтому его «e» — это «е», а не «э»
    (``mektepte`` -> «мектепте», а не «мектептэ»).
    """
    global _SUFFIX_TABLE
    if _SUFFIX_TABLE is None:
        base = get_scheme(DEFAULT_SCHEME).reverse_table()
        _SUFFIX_TABLE = Table(
            mapping=dict(base.mapping),
            fold=dict(base.fold),
            contextual=tuple(base.contextual),
        )
    return _SUFFIX_TABLE


def ascii_key(word: str) -> str:
    """ASCII-ключ слова: нижний регистр, без диакритики и апострофов.

        >>> ascii_key("dönggölök")
        'donggolok'
        >>> ascii_key("Kyrgyz")
        'kyrgyz'
        >>> ascii_key("Chüy")
        'chuy'
    """
    key, _ = _key_with_offsets(word)
    return key


def _strip_marks(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _key_with_offsets(word: str) -> Tuple[str, List[int]]:
    """ASCII-ключ и длина ключа после каждого символа исходного слова.

    Длины нужны, чтобы по границе основы в ключе найти границу в самом слове:
    один символ может дать два (лигатура ``ﬁ`` -> ``fi``) или ни одного
    (апостроф вместо ъ и ь).
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
    такое слово разберётся обычными правилами схемы.

        >>> words = Wordlist(["дөңгөлөк", "түшүнүк"])
        >>> words.lookup("dongolok")
        'дөңгөлөк'
        >>> words.lookup("tushunuk")
        'түшүнүк'
        >>> words.lookup("kompyuter") is None
        True

    Спор за ключ можно решить, добавив более частотное слово как
    предпочтительное: ``уй`` и ``үй`` оба пишутся ``uy``, но «үй» встречается
    несравнимо чаще, и без такой пометки ү потерялось бы.

        >>> pair = Wordlist(["уй"]).add(["үй"], preferred=True)
        >>> pair.lookup("uy")
        'үй'
        >>> pair.ambiguous_keys()
        []
    """

    def __init__(
        self,
        words: Iterable[str] = (),
        *,
        min_stem: int = DEFAULT_MIN_STEM,
    ) -> None:
        self.min_stem = min_stem
        self._forms: Dict[str, Optional[str]] = {}
        self._stems: Dict[str, Optional[str]] = {}
        self._pinned_keys: Set[str] = set()
        self._preferred_words: Set[str] = set()
        self._words: Set[str] = set()
        self.add(words)

    def add(self, words: Iterable[str], *, preferred: bool = False) -> "Wordlist":
        """Добавить слова (кириллицей). Возвращает сам словарь.

        :param preferred: закрепить за словом его ключи, отобрав их у обычных
            слов. Так задаётся более частотное чтение неоднозначной латиницы
            (``uy`` -> «үй», а не «уй»). Порядок добавления при этом не важен;
            если на один ключ претендуют два предпочтительных слова, ключ
            снова становится неоднозначным.
        """
        for word in words:
            word = word.strip()
            if not word:
                continue
            self._words.add(word)
            if preferred:
                self._preferred_words.add(word)
            for key in self._keys(word):
                if key:
                    self._claim(key, word, preferred)
            self._add_voiced_stem(word)
        return self

    def _add_voiced_stem(self, word: str) -> None:
        """Завести озвончённую основу слова: китеп -> китеб, эшик -> эшиг.

        Она нужна только для поиска по началу слова: сама по себе такая
        основа словом не является, поэтому в общий индекс не попадает.
        """
        voiced = _FINAL_VOICING.get(word[-1:].lower())
        if voiced is None:
            return
        stem = word[:-1] + voiced
        for key in self._keys(stem):
            if key and self._stems.get(key, stem) != stem:
                self._stems[key] = None  # основу делят два слова
            elif key:
                self._stems[key] = stem

    def _claim(self, key: str, word: str, preferred: bool) -> None:
        """Записать ключ за словом с учётом уже занятых и закреплённых ключей."""
        taken = self._forms.get(key, word) != word  # на ключ претендует другое слово
        if preferred:
            self._forms[key] = None if taken and key in self._pinned_keys else word
            self._pinned_keys.add(key)
        elif key not in self._pinned_keys:
            self._forms[key] = None if taken else word

    def copy(self) -> "Wordlist":
        """Независимая копия словаря — вместе с предпочтительными словами.

            >>> mine = builtin_wordlist().copy().add(["көпөлөк"])
            >>> mine.lookup("kopolok")
            'көпөлөк'
            >>> "kopolok" in builtin_wordlist()
            False
        """
        twin = Wordlist(min_stem=self.min_stem)
        twin._forms = dict(self._forms)
        twin._stems = dict(self._stems)
        twin._pinned_keys = set(self._pinned_keys)
        twin._preferred_words = set(self._preferred_words)
        twin._words = set(self._words)
        return twin

    def merge(self, other: "Wordlist") -> "Wordlist":
        """Добавить слова другого словаря вместе с его предпочтительными чтениями."""
        self.add(word for word in other.words() if word not in other._preferred_words)
        self.add(other.preferred(), preferred=True)
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
        """Прочитать список слов из файла: одно слово в строке, ``#`` — комментарий.

        Строка, начинающаяся со звёздочки (``*үй``), задаёт предпочтительное
        чтение — см. :meth:`add`.
        """
        with open(path, encoding="utf-8") as handle:
            return cls.from_text(handle.read(), min_stem=min_stem)

    @classmethod
    def from_text(cls, text: str, *, min_stem: int = DEFAULT_MIN_STEM) -> "Wordlist":
        """То же, что :meth:`from_file`, но список слов уже прочитан в строку."""
        words = cls(min_stem=min_stem)
        parsed = _parse_words(text)
        words.add(word for word, preferred in parsed if not preferred)
        words.add((word for word, preferred in parsed if preferred), preferred=True)
        return words

    def lookup(self, key: str) -> Optional[str]:
        """Слово по ASCII-ключу или ``None``, если его нет или ключ неоднозначен."""
        return self._forms.get(ascii_key(key))

    def lookup_stem(self, key: str) -> Optional[Tuple[str, int]]:
        """Самая длинная однозначная основа: ``(основа, длина ключа основы)``.

        Основой может быть как само слово (``дөңгөлөк`` в ``dongolokton``),
        так и его озвончённая форма (``дөңгөлөг`` в ``dongologu``).
        """
        for size in range(len(key) - 1, self.min_stem - 1, -1):
            head = key[:size]
            form = self._forms.get(head)
            if form is None:
                form = self._stems.get(head)
            if form is not None:
                return form, size
        return None

    def ambiguous_keys(self) -> List[str]:
        """Ключи, на которые претендует больше одного слова."""
        return sorted(key for key, form in self._forms.items() if form is None)

    def words(self) -> List[str]:
        """Все слова словаря."""
        return sorted(self._words)

    def preferred(self) -> List[str]:
        """Слова, помеченные как предпочтительное чтение неоднозначной латиницы."""
        return sorted(self._preferred_words)

    def __len__(self) -> int:
        return len(self._words)

    def __contains__(self, word: str) -> bool:
        return self.lookup(word) is not None

    def __repr__(self) -> str:  # pragma: no cover - для отладки
        return "Wordlist({0} слов, {1} ключей)".format(len(self._words), len(self._forms))


def _parse_words(text: str) -> List[Tuple[str, bool]]:
    r"""Разобрать список слов в пары ``(слово, предпочтительное ли)``.

    Одно слово в строке, ``#`` — комментарий, ``*`` в начале строки помечает
    предпочтительное чтение неоднозначного ключа (см. :meth:`Wordlist.add`).

        >>> _parse_words("# дом\nуй\n*үй\n")
        [('уй', False), ('үй', True)]
    """
    words = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        preferred = line.startswith("*")
        word = line.lstrip("*").strip()
        if word:
            words.append((word, preferred))
    return words


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
        _BUILTIN = Wordlist.from_text(text)
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


def _restore_compound(token: str, wordlist: Wordlist) -> Optional[str]:
    """Разобрать составное слово по частям, если целиком его в словаре нет.

    Части, которых в словаре тоже нет, остаются латиницей — их разберут
    правила схемы (``uy-bulo`` -> «үй-бүлө», ``ata-ene`` -> ``ata-ene``).
    """
    parts = token.split("-")
    restored = [_restore_token(part, wordlist) for part in parts]
    if all(form is None for form in restored):
        return None
    return "-".join(
        part if form is None else form for part, form in zip(parts, restored)
    )


def restore_words(text: str, wordlist: Wordlist) -> str:
    """Заменить латинские слова на кириллические по словарю.

    Слова, которых в словаре нет, остаются как есть — их разберёт обычная
    транслитерация (:func:`kyrgyz_transliteration.to_cyrillic` делает это сама:
    словарь у неё включён по умолчанию).

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
        if replacement is None and "-" in token:
            replacement = _restore_compound(token, wordlist)
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
    if not key.isascii() or not key.replace("-", "").isalpha():
        return None

    form = wordlist.lookup(key)
    if form is not None:
        return _match_case(token, form)

    found = wordlist.lookup_stem(key)
    if found is None:
        return None
    stem, size = found
    try:
        split = offsets.index(size)
    except ValueError:  # граница основы попала внутрь диграфа
        return None
    suffix = apply_table(token[split:], _suffix_table())
    return _match_case(token, stem + _harmonize(suffix, stem))


def _match_case(token: str, form: str) -> str:
    """Привести слово к регистру набранного — у составных слов по частям.

    «Ysyk-Kol» — это «Ысык-Көл», а не «Ысык-көл»: с прописной каждая часть.
    """
    caps = _is_caps(token)
    parts, forms = token.split("-"), form.split("-")
    if len(parts) != len(forms):
        return match_case(token, form, all_caps=caps)
    return "-".join(
        match_case(part, piece, all_caps=caps) for part, piece in zip(parts, forms)
    )


def _is_caps(token: str) -> bool:
    letters = [char for char in token if char.isalpha()]
    return len(letters) > 1 and all(char.isupper() for char in letters)
