"""Движок транслитерации.

Одна функция :func:`apply_table` умеет применять любую подготовленную таблицу
замен (:class:`Table`) в любом направлении: кириллица -> латиница или обратно.
Движок жадный (longest match first) и сам восстанавливает регистр, включая
многосимвольные замены вроде ``ё -> yo`` и аббревиатуры в верхнем регистре.

Неоднозначные буквы разбираются контекстными правилами (:attr:`Table.contextual`):
правило помечает символ служебным маркером, а маркер уже переводится таблицей.
Правило обязано сохранять длину текста: контекст задаётся проверками вида
``(?<=...)`` и ``(?=...)``, а замена — маркером той же длины, что и совпадение.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Pattern, Tuple

__all__ = ["Table", "apply_table", "match_case"]

_WORD_RE = re.compile(r"[^\W\d_]+")


@dataclass
class Table:
    """Подготовленная таблица замен для одного направления.

    :param mapping: последовательность символов источника (в нижнем регистре)
        -> результат.
    :param word_initial: замены, действующие только в начале слова; имеют
        приоритет над :attr:`mapping`.
    :param upper: как переводить символы результата в верхний регистр, если
        стандартного ``str.upper()`` недостаточно (например ``i -> İ``).
    :param fold: как приводить символы источника к нижнему регистру, если
        стандартного ``str.lower()`` недостаточно (например ``I -> ı``).
    :param contextual: правила ``(шаблон, маркер)``, которые до основного
        прохода помечают неоднозначные символы; маркеры должны быть описаны в
        :attr:`mapping`.
    """

    mapping: Dict[str, str]
    word_initial: Dict[str, str] = field(default_factory=dict)
    upper: Dict[str, str] = field(default_factory=dict)
    fold: Dict[str, str] = field(default_factory=dict)
    contextual: Tuple[Tuple[Pattern, str], ...] = ()
    max_len: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        lengths = [len(key) for key in self.mapping]
        lengths += [len(key) for key in self.word_initial]
        self.max_len = max(lengths) if lengths else 0


def _fold(text: str, fold: Dict[str, str]) -> str:
    """Регистронезависимая копия текста той же длины, что и исходный."""
    chars: List[str] = []
    for char in text:
        if char in fold:
            chars.append(fold[char])
            continue
        lowered = char.lower()
        # ``str.lower()`` для отдельных символов (например 'İ') может вернуть
        # два символа и сбить нумерацию — такие символы оставляем как есть.
        chars.append(lowered if len(lowered) == 1 else char)
    return "".join(chars)


def _upper(text: str, upper: Dict[str, str]) -> str:
    return "".join(upper.get(char, char.upper()) for char in text)


def _capitalize(text: str, upper: Dict[str, str]) -> str:
    if not text:
        return text
    return _upper(text[0], upper) + text[1:]


def _apply_contextual(folded: str, table: Table) -> str:
    """Расставить маркеры контекстных правил, не меняя длину текста."""
    for pattern, marker in table.contextual:
        marked = pattern.sub(marker, folded)
        if len(marked) != len(folded):
            raise ValueError(
                "контекстное правило {0!r} изменило длину текста: "
                "замена должна быть той же длины, что и совпадение".format(pattern.pattern)
            )
        folded = marked
    return folded


def match_case(
    original: str,
    replacement: str,
    upper: Optional[Dict[str, str]] = None,
    all_caps: bool = False,
) -> str:
    """Привести ``replacement`` к регистру исходного фрагмента ``original``.

    :param upper: регистровые исключения (например ``{"i": "İ"}``).
    :param all_caps: считать фрагмент частью слова, набранного КАПСОМ.
    """
    upper = upper or {}
    letters = [char for char in original if char.isalpha()]
    if not letters or not letters[0].isupper():
        return replacement
    if all_caps or (len(letters) > 1 and all(char.isupper() for char in letters)):
        return _upper(replacement, upper)
    return _capitalize(replacement, upper)


def _caps_lock_flags(text: str) -> List[bool]:
    """Для каждой позиции: входит ли она в слово, набранное КАПСОМ."""
    flags = [False] * len(text)
    for match in _WORD_RE.finditer(text):
        letters = [char for char in match.group() if char.isalpha()]
        if len(letters) > 1 and all(char.isupper() for char in letters):
            flags[match.start() : match.end()] = [True] * (match.end() - match.start())
    return flags


def apply_table(text: str, table: Table) -> str:
    """Применить таблицу замен к тексту, сохранив регистр и всё остальное."""
    if not text:
        return ""

    folded = _apply_contextual(_fold(text, table.fold), table)
    caps_lock = _caps_lock_flags(text)
    result: List[str] = []
    index = 0
    length = len(text)

    while index < length:
        at_word_start = index == 0 or not text[index - 1].isalpha()
        source = replacement = None
        window = min(table.max_len, length - index)
        for size in range(window, 0, -1):
            chunk = folded[index : index + size]
            if at_word_start and chunk in table.word_initial:
                source, replacement = chunk, table.word_initial[chunk]
                break
            if chunk in table.mapping:
                source, replacement = chunk, table.mapping[chunk]
                break

        if source is None:
            result.append(text[index])
            index += 1
            continue

        if replacement:
            original = text[index : index + len(source)]
            result.append(
                match_case(original, replacement, table.upper, all_caps=caps_lock[index])
            )

        index += len(source)

    return "".join(result)
