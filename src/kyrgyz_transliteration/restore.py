"""Восстановление кыргызских слов из английской латиницы.

В английском алфавите нет ни ө, ни ү, ни ң: схема `english` пишет их как o, u
и n, и по такой записи выбрать между «дөңгөлөк» и «донголок» нельзя — оба
слова подчиняются гармонии гласных. Единственный надёжный способ — словарь.
(Все встроенные схемы пишут только английскими ASCII-буквами; `bgn` сохранён
как совместимое имя старой схемы.)

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
    "builtin_names",
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
NAME_TRIGRAM_MIN_SCORE = 0.72
NAME_TRIGRAM_MIN_MARGIN = 0.08

# Сведение допустимых латинских вариантов к ASCII.
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

        >>> ascii_key("donggolok")
        'donggolok'
        >>> ascii_key("Kyrgyz")
        'kyrgyz'
        >>> ascii_key("Chuy")
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


def _trigrams(key: str) -> Set[str]:
    """Return character trigrams with word-boundary markers."""
    padded = "^^" + key + "$$"
    return {padded[index : index + 3] for index in range(len(padded) - 2)}


def _trigram_similarity(left: str, right: str) -> float:
    """Dice similarity for two sets of boundary-aware character trigrams."""
    left_grams = _trigrams(left)
    right_grams = _trigrams(right)
    if not left_grams or not right_grams:
        return 0.0
    return 2.0 * len(left_grams & right_grams) / (len(left_grams) + len(right_grams))


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
        self._trigram_words: Set[str] = set()
        self._trigram_index: Dict[str, Set[str]] = {}
        self._name_index: Optional["Wordlist"] = None
        self.add(words)

    def add(
        self,
        words: Iterable[str],
        *,
        preferred: bool = False,
        trigram: bool = False,
    ) -> "Wordlist":
        """Добавить слова (кириллицей). Возвращает сам словарь.

        :param preferred: закрепить за словом его ключи, отобрав их у обычных
            слов. Так задаётся более частотное чтение неоднозначной латиницы
            (``uy`` -> «үй», а не «уй»). Порядок добавления при этом не важен;
            если на один ключ претендуют два предпочтительных слова, ключ
            снова становится неоднозначным.
        :param trigram: добавить слово в индекс нечёткого поиска имён.
        """
        for word in words:
            word = word.strip()
            if not word:
                continue
            self._words.add(word)
            if trigram:
                self._add_trigram_word(word)
            if preferred:
                self._preferred_words.add(word)
            for key in self._keys(word):
                if key:
                    self._claim(key, word, preferred)
            self._add_voiced_stem(word)
        return self

    def _add_trigram_word(self, word: str) -> None:
        self._trigram_words.add(word)
        for key in self._keys(word):
            for trigram in _trigrams(key):
                self._trigram_index.setdefault(trigram, set()).add(word)

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
        twin._trigram_words = set(self._trigram_words)
        twin._trigram_index = {
            trigram: set(words) for trigram, words in self._trigram_index.items()
        }
        twin._name_index = self._name_index
        return twin

    def merge(self, other: "Wordlist") -> "Wordlist":
        """Добавить слова другого словаря вместе с его предпочтительными чтениями."""
        self.add(
            (word for word in other.words() if word not in other._preferred_words),
            trigram=False,
        )
        self.add(other.preferred(), preferred=True, trigram=False)
        for word in other._trigram_words:
            self._add_trigram_word(word)
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
        normalized = ascii_key(key)
        form = self._forms.get(normalized)
        if form is not None:
            return form
        if self._name_index is not None and normalized not in self._forms:
            return self._name_index.lookup(normalized)
        return None

    def lookup_regular(self, key: str) -> Optional[str]:
        """Look up only the regular word index, excluding names."""
        return self._forms.get(ascii_key(key))

    def attach_name_index(self, names: "Wordlist") -> "Wordlist":
        """Attach a separate name index without merging its collision-prone keys."""
        self._name_index = names
        return self

    def lookup_trigram(
        self,
        key: str,
        *,
        min_score: float = NAME_TRIGRAM_MIN_SCORE,
        min_margin: float = NAME_TRIGRAM_MIN_MARGIN,
    ) -> Optional[str]:
        """Найти близкое имя по перекрытию символьных триграмм.

        Нечёткий поиск ограничен словами, добавленными с ``trigram=True``.
        Возвращается только однозначный лучший кандидат; это предотвращает
        случайную замену обычных слов или похожих имён.
        """
        normalized = ascii_key(key)
        if self._name_index is not None and not self._trigram_words:
            return self._name_index.lookup_trigram(
                normalized,
                min_score=min_score,
                min_margin=min_margin,
            )
        if len(normalized) < 3 or not self._trigram_words:
            return None

        candidates: Set[str] = set()
        for trigram in _trigrams(normalized):
            candidates.update(self._trigram_index.get(trigram, ()))
        if not candidates:
            return None

        ranked = sorted(
            (
                (_trigram_similarity(normalized, candidate_key), word)
                for word in candidates
                for candidate_key in self._keys(word)
            ),
            reverse=True,
        )
        if not ranked or ranked[0][0] < min_score:
            return None
        best_score = ranked[0][0]
        best_words = {word for score, word in ranked if score == best_score}
        if len(best_words) != 1:
            return None
        next_score = max(
            (score for score, word in ranked if word not in best_words),
            default=0.0,
        )
        if best_score - next_score < min_margin:
            return None
        return next(iter(best_words))

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
_BUILTIN_NAMES: Optional[Wordlist] = None


def _resource_text(filename: str) -> str:
    try:
        from importlib.resources import files

        return files("kyrgyz_transliteration.data").joinpath(filename).read_text(
            encoding="utf-8"
        )
    except (ImportError, AttributeError):  # pragma: no cover - Python < 3.9
        import os

        path = os.path.join(os.path.dirname(__file__), "data", filename)
        with open(path, encoding="utf-8") as handle:
            return handle.read()


def builtin_names() -> Wordlist:
    """Return the curated Kyrgyz name and surname index.

    The returned object is cached and must not be mutated in place. Use
    :meth:`Wordlist.copy` before adding application-specific names.
    """
    global _BUILTIN_NAMES
    if _BUILTIN_NAMES is None:
        _BUILTIN_NAMES = Wordlist.from_text(_resource_text("kyrgyz_names.txt"))
        _BUILTIN_NAMES.add(_BUILTIN_NAMES.words(), trigram=True)
    return _BUILTIN_NAMES


def builtin_wordlist() -> Wordlist:
    """Встроенный список частотных кыргызских слов (кешируется).

        >>> len(builtin_wordlist()) > 200
        True
        >>> builtin_wordlist().lookup("dongolok")
        'дөңгөлөк'
    """
    global _BUILTIN
    if _BUILTIN is None:
        _BUILTIN = Wordlist.from_text(_resource_text("kyrgyz_frequent.txt"))
        _BUILTIN.attach_name_index(builtin_names())
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

    form = (
        wordlist.lookup(key)
        if token[:1].isupper()
        else wordlist.lookup_regular(key)
    )
    if form is None and token[:1].isupper():
        form = wordlist.lookup_trigram(key)

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
