# -*- coding: utf-8 -*-
import io
import sys

from kyrgyz_transliteration.cli import main


def run(argv, stdin=None, monkeypatch=None, capsys=None):
    if stdin is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    code = main(argv)
    out, err = capsys.readouterr()
    return code, out, err


def test_text_argument(capsys, monkeypatch):
    code, out, _ = run(["Кыргыз Республикасы"], capsys=capsys, monkeypatch=monkeypatch)
    assert code == 0
    assert out == "Kırgız Respublikası\n"


def test_scheme_and_direction(capsys, monkeypatch):
    code, out, _ = run(["-s", "bgn", "Ысык-Көл"], capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "Ysyk-Köl\n")
    code, out, _ = run(
        ["-d", "cyrillic", "Kırgız"], capsys=capsys, monkeypatch=monkeypatch
    )
    assert (code, out) == (0, "Кыргыз\n")


def test_stdin(capsys, monkeypatch):
    code, out, _ = run([], stdin="Бишкек\n", capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "Bişkek\n")


def test_slug_and_detect(capsys, monkeypatch):
    code, out, _ = run(["--slug", "Ысык-Көл"], capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "ysyk-kol\n")
    code, out, _ = run(["--detect", "Бишкек"], capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "cyrillic\n")


def test_list_and_table(capsys, monkeypatch):
    code, out, _ = run(["--list"], capsys=capsys, monkeypatch=monkeypatch)
    assert code == 0
    assert "turkic" in out and "iso9" in out
    code, out, _ = run(["--table", "bgn"], capsys=capsys, monkeypatch=monkeypatch)
    assert code == 0
    assert "ж j" in out


def test_unknown_scheme_exits_with_error(capsys, monkeypatch):
    code, _, err = run(["-s", "nope", "тест"], capsys=capsys, monkeypatch=monkeypatch)
    assert code == 2
    assert "nope" in err


def test_empty_stdin(capsys, monkeypatch):
    code, _, err = run([], stdin="", capsys=capsys, monkeypatch=monkeypatch)
    assert code == 2
    assert "usage" in err.lower()


def test_builtin_wordlist_flag(capsys, monkeypatch):
    code, out, _ = run(["-w", "dongolok kocho jok"], capsys=capsys, monkeypatch=monkeypatch)
    assert (code, out) == (0, "дөңгөлөк көчө жок\n")


def test_wordlist_file(capsys, monkeypatch, tmp_path):
    path = tmp_path / "words.txt"
    path.write_text("# свои слова\nкөпөлөк\n", encoding="utf-8")
    code, out, _ = run(
        ["--wordlist", str(path), "kopolokton dongolok"],
        capsys=capsys,
        monkeypatch=monkeypatch,
    )
    assert (code, out) == (0, "көпөлөктөн дөңгөлөк\n")


def test_missing_wordlist_file_exits_with_error(capsys, monkeypatch):
    code, _, err = run(
        ["--wordlist", "/nope/words.txt", "dongolok"], capsys=capsys, monkeypatch=monkeypatch
    )
    assert code == 2
    assert "words.txt" in err
