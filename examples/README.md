# Examples

These examples use real Kyrgyz words and phrases, including dictionary-assisted
restoration of `ө`, `ү`, and `ң`:

- `дөңгөлөк` → `dongolok` → `дөңгөлөк`
- `өкмөттүн жаңы дөңгөлөгү` → `okmottun jangy dongologu`
- `үй-бүлө` → `uy-bulo` → `үй-бүлө`
- `мүмкүнчүлүк` → `mumkunchuluk` → `мүмкүнчүлүк`
- `Ысык-Көл облусундагы тоолор` → `Ysyk-Kol oblusundagy toolor`

Run the complete demo from the repository root:

```bash
python -m examples
```

The main implementation is in [`basic.py`](./basic.py). It demonstrates:

- Kyrgyz Cyrillic to ASCII English transliteration with `to_latin`;
- English transliteration back to Kyrgyz with `to_cyrillic`;
- `english_ascii` output using the natural `ө` → `o` spelling;
- natural English output such as `Өмүр бою...` → `Omur boyu...`;
- automatic direction detection with `transliterate`;
- script detection and URL-safe slugs;
- an intentionally lossy `english` example using `Конституциясы`.

For deeper cases, run [`complex_cases.py`](./complex_cases.py):

```bash
python -m examples.complex_cases
```

It covers inflected words such as `dongolokton`, compound phrases, punctuation
and capitalization, ambiguous spellings with and without the dictionary,
custom domain vocabulary, extended ASCII output, and mixed automatic
direction workflows.

For especially dense Kyrgyz text, run
[`very_complex_cases.py`](./very_complex_cases.py):

```bash
python -m examples.very_complex_cases
```

It uses words and sentences with repeated `ң`, `ү`, and `ө`, compares the
dictionary-assisted English output with exact `bgn` output, and demonstrates
adding an inflected form to a copied custom wordlist.

For the supplied personal sentence cases, run
[`custom_cases.py`](./custom_cases.py):

```bash
python -m examples.custom_cases
```

It demonstrates names, punctuation, questions, and application-specific
vocabulary added to a copied `Wordlist`.

The default `english` scheme is designed for keyboards, URLs, filenames, and
messengers, so several Kyrgyz Cyrillic letters share ASCII spellings. Use
`scheme="english_ascii"` when you want ASCII output with `ө` → `o`, `ң` → `n`,
and `ү` → `u`. The legacy `bgn` name is also ASCII-only for compatibility.
Even with the default dictionary, uncommon words and unfamiliar inflections may
need a custom [`Wordlist`](../README.md#свой-список-слов).

The same operations are available from the installed CLI:

```bash
kyrgyz-transliteration "дөңгөлөк"
kyrgyz-transliteration -s english_ascii "Өмүр бою Кыргызстанды сагынам"
kyrgyz-transliteration -d cyrillic "okmottun jangy dongologu"
```
