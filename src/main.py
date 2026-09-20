from kyrgyz_transliteration import to_latin, to_cyrillic

# whole library logic must be from english to kyrgyz and vice versa
# not turkish or any other language


def main():
    print(to_cyrillic("dongolok"))  # it must be дөңгөлөк
    print(to_latin("дөңгөлөк"))  # it must be dongolok

    # ң, ө и ү английскими буквами не пишутся: обратно их восстанавливает
    # встроенный список кыргызских слов — он включён по умолчанию.
    for word in ("Ysyk-Kol", "okmottun jangy dongologu", "uy-bulo", "mumkunchuluk"):
        print("{0:26} -> {1}".format(word, to_cyrillic(word)))

    for word in ("Ысык-Көл", "өкмөттүн жаңы дөңгөлөгү", "үй-бүлө", "мүмкүнчүлүк"):
        print("{0:26} -> {1}".format(word, to_latin(word)))


if __name__ == "__main__":
    main()
