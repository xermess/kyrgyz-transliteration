"""Консольная утилита ``kyrgyz-translit``."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional, Sequence

from . import (
    DEFAULT_SCHEME,
    Wordlist,
    __version__,
    alphabet_table,
    builtin_wordlist,
    detect_script,
    get_scheme,
    list_schemes,
    slugify,
    transliterate,
)
from .schemes import UnknownSchemeError

__all__ = ["main", "build_parser"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kyrgyz-translit",
        description="Транслитерация кыргызского текста: кириллица <-> латиница.",
        epilog="Без аргумента TEXT текст читается со стандартного ввода.",
    )
    parser.add_argument("text", nargs="*", help="текст для транслитерации")
    parser.add_argument(
        "-s",
        "--scheme",
        default=DEFAULT_SCHEME,
        help="схема транслитерации (по умолчанию: {0})".format(DEFAULT_SCHEME),
    )
    parser.add_argument(
        "-d",
        "--direction",
        choices=("auto", "latin", "cyrillic"),
        default="auto",
        help="направление преобразования (по умолчанию: auto)",
    )
    parser.add_argument(
        "-w",
        "--words",
        action="store_true",
        help=(
            "для латиницы без диакритики: восстанавливать слова по встроенному "
            "списку частотных кыргызских слов"
        ),
    )
    parser.add_argument(
        "--wordlist",
        metavar="FILE",
        help=(
            "то же, но со своим списком слов (одно слово в строке, кириллицей); "
            "встроенный список тоже используется"
        ),
    )
    parser.add_argument(
        "--slug", action="store_true", help="вывести ASCII-слаг вместо транслитерации"
    )
    parser.add_argument(
        "--detect", action="store_true", help="определить письменность и выйти"
    )
    parser.add_argument(
        "-l", "--list", action="store_true", help="показать доступные схемы"
    )
    parser.add_argument(
        "--table",
        metavar="SCHEME",
        nargs="?",
        const=DEFAULT_SCHEME,
        help="показать таблицу соответствий схемы",
    )
    parser.add_argument("-V", "--version", action="version", version=__version__)
    return parser


def _print_schemes(stream) -> None:
    width = max(len(scheme.name) for scheme in list_schemes())
    for scheme in list_schemes():
        mark = " (с потерями)" if scheme.lossy else ""
        stream.write("{0}  {1}{2}\n".format(scheme.name.ljust(width), scheme.title, mark))
        if scheme.notes:
            stream.write("{0}  {1}\n".format(" " * width, scheme.notes))


def _print_table(name: str, stream) -> None:
    scheme = get_scheme(name)
    stream.write("{0} — {1}\n".format(scheme.name, scheme.title))
    pairs = ["{0} {1}".format(cyr, lat or "-") for cyr, lat in alphabet_table(scheme)]
    for start in range(0, len(pairs), 6):
        stream.write("  " + "   ".join(cell.ljust(6) for cell in pairs[start : start + 6]).rstrip() + "\n")


def _read_input(text_args: Sequence[str], stdin) -> str:
    if text_args:
        return " ".join(text_args)
    return stdin.read()


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.list:
            _print_schemes(sys.stdout)
            return 0
        if args.table is not None:
            _print_table(args.table, sys.stdout)
            return 0

        get_scheme(args.scheme)  # проверяем имя схемы до чтения ввода
        text = _read_input(args.text, sys.stdin)
        if not text:
            parser.print_usage(sys.stderr)
            return 2

        if args.detect:
            sys.stdout.write(detect_script(text.strip()) + "\n")
            return 0
        if args.slug:
            sys.stdout.write(slugify(text.strip()) + "\n")
            return 0

        wordlist = None
        if args.words or args.wordlist:
            wordlist = Wordlist(builtin_wordlist().words())
            if args.wordlist:
                wordlist.add(Wordlist.from_file(args.wordlist).words())

        keep_newline = text.endswith("\n")
        result = transliterate(text.rstrip("\n"), args.scheme, args.direction, wordlist)
        sys.stdout.write(result + ("\n" if keep_newline or args.text else ""))
        return 0
    except UnknownSchemeError as error:
        sys.stderr.write("ошибка: {0}\n".format(error.args[0]))
        return 2
    except OSError as error:
        sys.stderr.write("ошибка: {0}\n".format(error))
        return 2
    except BrokenPipeError:  # pragma: no cover - зависит от окружения
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
