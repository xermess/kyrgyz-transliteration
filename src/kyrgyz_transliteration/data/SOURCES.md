# Bundled corpus sources

## `kyrgyz_names.txt`

This is a curated supplement of Kyrgyz given names and surnames used to improve
restoration of ASCII input. It is not a complete list of Kyrgyz names and does
not claim to be an official registry. The library keeps this corpus in a
separate name index and uses boundary-aware character trigram matching for
capitalized near-matches.

Candidate labels were checked against Wikidata structured data. Wikidata
structured data is available under CC0:

- <https://www.wikidata.org/wiki/Wikidata:Licensing>
- <https://www.wikidata.org/wiki/Wikidata:Database_download>

The file is maintained as project data and contains only names selected for
transliteration coverage. Additions should be reviewed for spelling, ambiguity,
and whether they improve restoration without overriding common Kyrgyz words.

The general word list in `kyrgyz_frequent.txt` is project-maintained data. It is
separate from the name supplement so applications can inspect names through
`builtin_names()` and extend a copied `Wordlist` safely.
