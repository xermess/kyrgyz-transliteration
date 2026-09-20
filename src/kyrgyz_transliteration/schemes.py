"""Схемы транслитерации кыргызского языка: кириллица <-> английская латиница.

Библиотека работает только с английским алфавитом: кыргызский текст
записывается буквами ``a-z``, которые англоязычный читатель прочитает близко к
оригиналу. Турецких (``ı ş ç ğ ñ``) и научных (``ž ô ù ņ â``) алфавитов здесь
нет — они дают другое чтение и не являются английскими.

Каждая схема — это таблица «кириллица -> латиница» плюс немного метаданных.
Обратная таблица («латиница -> кириллица») строится автоматически: при
конфликтах побеждает буква, объявленная раньше (например ``й`` и ``ы`` обе
дают ``y``, обратно ``y`` читается как ``й``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Pattern, Tuple

from .core import Table

__all__ = [
    "CYRILLIC_LETTERS",
    "MARKER_SHORT_I",
    "MARKER_TE",
    "DEFAULT_SCHEME",
    "SCHEMES",
    "Scheme",
    "UnknownSchemeError",
    "get_scheme",
    "list_schemes",
    "register_scheme",
]

#: Кыргызский алфавит (36 букв) в алфавитном порядке.
CYRILLIC_LETTERS = "абвгдеёжзийклмнңоөпрстуүфхцчшщъыьэюя"

#: Схема, используемая по умолчанию.
DEFAULT_SCHEME = "english"

# Служебные маркеры контекстных правил (см. core._apply_contextual).
MARKER_SHORT_I = ""  # y, который читается как «й»
MARKER_TE = ""  # t в сочетании «тс», которое не является «ц»

_VOWELS = "aeiouöü"

# «ts» после гласной — почти всегда стык «т» + «с» (айтса, кетсе), а не «ц».
# Правило идёт первым, пока «y» ещё не заменён маркером.
_TS_IS_TE_SE = (re.compile(r"(?<=[" + _VOWELS + r"y])t(?=s)"), MARKER_TE)

# «й» и «ы» пишутся одной буквой «y», поэтому разбираются по позиции:
# «yyy» — это ы+й+ы (кыйын), «yy» после гласной — й+ы (айыл), а не после
# гласной — ы+й (мыйзам, но не кыюу = ы+ю), «y» перед узкой гласной — й
# (бийик), «y» между гласной и согласной — й (ай, ой, той), в остальных
# случаях — ы (Ысык, кыз).
_Y_RULES = (
    _TS_IS_TE_SE,
    (re.compile(r"yyy"), "y" + MARKER_SHORT_I + "y"),
    (re.compile(r"(?<=[" + _VOWELS + r"])yy"), MARKER_SHORT_I + "y"),
    (re.compile(r"(?<![" + _VOWELS + r"])yy(?![aou])"), "y" + MARKER_SHORT_I),
    (re.compile(r"(?<=[" + _VOWELS + r"])y(?=[eiöü])"), MARKER_SHORT_I),
    (re.compile(r"(?<=[" + _VOWELS + r"])y(?![" + _VOWELS + r"y])"), MARKER_SHORT_I),
)

# Читать библиотека умеет больше, чем пишет: в присланном тексте попадаются
# ө и ү с диакритикой (в том числе из BGN/PCGN) и апострофы вместо ъ и ь.
_TOLERANT = {"ö": "ө", "ü": "ү", "ʺ": "ъ", "ʼ": "ь", "ʻ": "ь"}

# Латинские буквы, которых нет в схемах, но которые встречаются в текстах
# (заимствования, бренды). Нужны только для обратного направления.
_LATIN_EXTRAS = {"q": "к", "w": "в", "x": "кс"}


class UnknownSchemeError(KeyError):
    """Запрошена незарегистрированная схема транслитерации."""


@dataclass
class Scheme:
    """Схема транслитерации.

    :param name: короткое имя, по которому схема запрашивается.
    :param title: человекочитаемое описание.
    :param mapping: кириллица (нижний регистр) -> латиница.
    :param word_initial: замены только для начала слова.
    :param reverse_mapping: правки для обратной таблицы (латиница -> кириллица).
    :param reverse_word_initial: замены латиница -> кириллица только для начала
        слова (``e -> э``).
    :param reverse_skip: латинские последовательности, которые не надо брать
        в обратную таблицу автоматически.
    :param latin_upper: регистровые исключения латиницы.
    :param latin_lower: обратные регистровые исключения.
    :param forward_contextual: контекстные правила для прямого направления.
    :param reverse_contextual: контекстные правила для обратного направления.
    :param lossy: ``True``, если преобразование в латиницу необратимо.
    :param notes: примечания для документации и CLI.
    """

    name: str
    title: str
    mapping: Dict[str, str]
    word_initial: Dict[str, str] = field(default_factory=dict)
    reverse_mapping: Dict[str, str] = field(default_factory=dict)
    reverse_word_initial: Dict[str, str] = field(default_factory=dict)
    reverse_skip: Tuple[str, ...] = ()
    latin_upper: Dict[str, str] = field(default_factory=dict)
    latin_lower: Dict[str, str] = field(default_factory=dict)
    forward_contextual: Tuple[Tuple[Pattern, str], ...] = ()
    reverse_contextual: Tuple[Tuple[Pattern, str], ...] = ()
    lossy: bool = False
    notes: str = ""
    _forward: Optional[Table] = field(default=None, init=False, repr=False, compare=False)
    _reverse: Optional[Table] = field(default=None, init=False, repr=False, compare=False)

    def forward_table(self) -> Table:
        """Таблица «кириллица -> латиница»."""
        if self._forward is None:
            self._forward = Table(
                mapping=dict(self.mapping),
                word_initial=dict(self.word_initial),
                upper=dict(self.latin_upper),
                contextual=tuple(self.forward_contextual),
            )
        return self._forward

    def reverse_table(self) -> Table:
        """Таблица «латиница -> кириллица»."""
        if self._reverse is None:
            mapping: Dict[str, str] = {}
            for cyrillic, latin in self.mapping.items():
                if not latin or latin in self.reverse_skip:
                    continue
                mapping.setdefault(latin.lower(), cyrillic)
            for latin, cyrillic in _LATIN_EXTRAS.items():
                mapping.setdefault(latin, cyrillic)
            mapping.update({k.lower(): v for k, v in self.reverse_mapping.items()})

            word_initial: Dict[str, str] = {}
            for cyrillic, latin in self.word_initial.items():
                if latin:
                    word_initial.setdefault(latin.lower(), cyrillic)
            word_initial.update({k.lower(): v for k, v in self.reverse_word_initial.items()})

            self._reverse = Table(
                mapping=mapping,
                word_initial=word_initial,
                fold=dict(self.latin_lower),
                contextual=tuple(self.reverse_contextual),
            )
        return self._reverse

    def missing_letters(self) -> List[str]:
        """Буквы кыргызского алфавита, которых нет в таблице схемы."""
        return [letter for letter in CYRILLIC_LETTERS if letter not in self.mapping]


def _scheme(name: str, title: str, mapping: Dict[str, str], **kwargs: object) -> Scheme:
    return Scheme(name=name, title=title, mapping=mapping, **kwargs)  # type: ignore[arg-type]


# --- English ----------------------------------------------------------------

_ENGLISH = _scheme(
    "english",
    "Английская латиница — так кыргызы пишут латиницей в жизни",
    {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
        "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "ң": "n", "о": "o", "ө": "o", "п": "p", "р": "r", "с": "s",
        "т": "t", "у": "u", "ү": "u", "ф": "f", "х": "kh", "ц": "ts",
        "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "",
        "э": "e", "ю": "yu", "я": "ya",
    },
    reverse_mapping=dict(_TOLERANT, y="ы", **{MARKER_SHORT_I: "й", MARKER_TE: "т"}),
    reverse_word_initial={"e": "э"},
    reverse_contextual=_Y_RULES,
    lossy=True,
    notes=(
        "Только буквы a-z: ң -> n, ө -> o, ү -> u, ж -> j, х -> kh. Обратно "
        "ө, ү и ң по одной латинице не вычисляются, поэтому to_cyrillic() "
        "восстанавливает их по списку кыргызских слов."
    ),
)

# --- BGN/PCGN ---------------------------------------------------------------

_BGN = _scheme(
    "bgn",
    "BGN/PCGN — англоязычный стандарт романизации (карты, паспорта, пресса)",
    {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
        "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "ң": "ng", "о": "o", "ө": "ö", "п": "p", "р": "r", "с": "s",
        "т": "t", "у": "u", "ү": "ü", "ф": "f", "х": "kh", "ц": "ts",
        "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "ʺ", "ы": "y", "ь": "ʼ",
        "э": "e", "ю": "yu", "я": "ya",
    },
    reverse_mapping={"y": "ы", MARKER_SHORT_I: "й", MARKER_TE: "т"},
    reverse_word_initial={"e": "э"},
    reverse_contextual=_Y_RULES,
    lossy=True,
    notes=(
        "Тот же английский алфавит, но ө, ү и ң пишутся точно (ö, ü, ng), "
        "поэтому текст читается обратно без словаря. й и ы обе дают y: "
        "обратно y — это й между гласной и согласной (ay -> ай) и ы в "
        "остальных случаях (Ysyk -> Ысык), начальное e — это э (el -> эл)."
    ),
)

SCHEMES: Dict[str, Scheme] = {scheme.name: scheme for scheme in (_ENGLISH, _BGN)}


def get_scheme(scheme: "str | Scheme" = DEFAULT_SCHEME) -> Scheme:
    """Вернуть схему по имени (или саму схему, если передан объект)."""
    if isinstance(scheme, Scheme):
        return scheme
    try:
        return SCHEMES[scheme.lower()]
    except KeyError:
        known = ", ".join(sorted(SCHEMES))
        raise UnknownSchemeError(
            "неизвестная схема {0!r}; доступны: {1}".format(scheme, known)
        ) from None


def register_scheme(scheme: Scheme, *, overwrite: bool = False) -> Scheme:
    """Зарегистрировать свою схему, чтобы обращаться к ней по имени."""
    if not overwrite and scheme.name in SCHEMES:
        raise ValueError("схема {0!r} уже зарегистрирована".format(scheme.name))
    SCHEMES[scheme.name] = scheme
    return scheme


def list_schemes() -> List[Scheme]:
    """Все зарегистрированные схемы."""
    return list(SCHEMES.values())
