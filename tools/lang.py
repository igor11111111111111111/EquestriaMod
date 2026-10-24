# -*- coding: utf-8 -*-
"""Двуязычные строки мода: в XML идёт английский, русский уезжает в Languages/RU.

Так устроена сама игра: базовый текст лежит прямо в XML, а переводы — языковыми файлами
(Modules/Native/ModuleData/Languages/<код>). Английского файла нет и быть не может: английский —
это и есть базовый текст. Пока наши XML были русскими, игрок с любой локалью видел русский.

Таблицы мода (tools/world_data.py и прочие) написаны по-русски, переписывать их не нужно: здесь
русская строка переводится по словарю tools/lang_words.py — сначала целиком, потом по словам
(«Медовый Ручей» = «Медовый» + «Ручей»). Чего в словаре нет, то остаётся русским и попадает в
отчёт: `lang.report()` печатает список, по нему словарь и пополняется.

Пользоваться так:
    import lang
    body.append('name="%s"' % lang.loc("culture_empire", "Эквестрия"))
    ...
    lang.write(DATA, "eq_world")   # Languages/*/eq_world_*.xml для всех языков игры
"""
import os
import re

import lang_words

# Языки игры: код папки -> (id языка, как он записан в language_data.xml, суффикс файлов).
# Английского в списке нет: он берётся из базового текста XML.
LANGUAGES = [
    ("BR", "Português (BR)", "bra"),
    ("CNs", "简体中文", "chs"),
    ("CNt", "繁體中文", "cht"),
    ("DE", "Deutsch", "deu"),
    ("FR", "Français", "fra"),
    ("IT", "Italiano", "ita"),
    ("JP", "日本語", "jpn"),
    ("KO", "한국어", "kor"),
    ("PL", "Polski", "pol"),
    ("RU", "Русский", "rus"),
    ("SP", "Español (LA)", "spa"),
    ("TR", "Türkçe", "tur"),
]

# Английский — тоже язык с файлами: у самой игры они лежат в корне Languages (std_*.xml с
# <tag language="English"/>). Нужен только репликам: их базового текста в XML нет, код строит
# TextObject("{=eq_...}") без текста по умолчанию, и без английского файла такой ключ пуст.
ENGLISH = ("EN", "English", "eng")


_CYRILLIC = re.compile(r"[А-Яа-яЁё]")
_TOKEN = re.compile(r"[А-Яа-яЁё]+(?:[-’'][А-Яа-яЁё]+)*")

# Побуквенная запись латиницей — для имён, которых нет в словаре. Почти все названия на карте
# пришли из Equestria at War и сами были когда-то английскими, поэтому обратная запись даёт
# близкое к исходному: «Аглоссата» → Aglossata, «Хярлигхамн» → Hyarlighamn. Для предложений так
# делать нельзя — они остаются русскими и попадают в отчёт.
_LETTERS = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}


def translit(text):
    out = []
    for ch in text:
        low = ch.lower()
        letter = _LETTERS.get(low)
        if letter is None:
            out.append(ch)
        elif ch == low:
            out.append(letter)
        else:
            out.append(letter.capitalize())
    return "".join(out)


def _looks_like_name(text, tokens):
    """Имя (а не предложение и не собранная строка): без точки, без подстановок вроде
    {FIRSTNAME}, и все русские слова с большой буквы."""
    return ("." not in text and "{" not in text and bool(tokens)
            and all(t[0].isupper() for t in tokens))

_pairs = []       # [(id строки, русский текст)] в порядке появления
_seen = set()
_missing = {}      # непереведённое -> сколько раз встретилось
_translit = {}     # записанное латиницей побуквенно -> сколько раз


def esc(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def en(ru):
    """Английский текст для русской строки. Чего не знаем — отдаём как есть и запоминаем."""
    ru = (ru or "").strip()
    if not ru or not _CYRILLIC.search(ru):
        return ru
    whole = lang_words.PHRASES.get(ru)
    if whole:
        return whole
    # Составное имя: переводим по словам, но только если известны ВСЕ слова — иначе выйдет
    # полурусская каша вроде «Honey Ручей», которую в отчёте потом не разглядеть.
    tokens = _TOKEN.findall(ru)
    if tokens and all(t in lang_words.WORDS for t in tokens):
        return _TOKEN.sub(lambda m: lang_words.WORDS[m.group(0)], ru)
    if _looks_like_name(ru, tokens):
        # Незнакомое имя: пишем латиницей пословно, известные части всё равно берём из словаря.
        # Запоминаем отдельно: у канонных имён есть настоящее английское написание («Кантерлот» —
        # это Canterlot, а не Kanterlot), и такие места надо просматривать глазами.
        _translit[ru] = _translit.get(ru, 0) + 1
        return _TOKEN.sub(lambda m: lang_words.WORDS.get(m.group(0)) or translit(m.group(0)), ru)
    _missing[ru] = _missing.get(ru, 0) + 1
    return ru


def loc(key, ru, english=None):
    """'{=ключ}English' для XML; русский запоминается для языкового файла.

    english передают там, где английский текст собирается рядом с русским (описания поселений
    строятся по шаблону, и переводить готовое предложение по словарю было бы гаданием).
    """
    text = english if english is not None else en(ru)
    if key not in _seen:
        _seen.add(key)
        _pairs.append((key, ru, text))
    return "{=%s}%s" % (key, esc(text))


def report(log=print, dump=None):
    """Сколько строк собрано и что осталось непереведённым.

    Полный список пишется в файл (по умолчанию tools/lang_missing.txt): сверху неизвестные слова
    — их и стоит дописывать в WORDS, потому что из них складываются составные имена, — снизу
    целые строки для PHRASES.
    """
    log("строк с переводом: %d" % len(_pairs))
    path = dump or os.path.join(os.path.dirname(os.path.abspath(__file__)), "lang_missing.txt")
    if not _missing and not _translit:
        log("весь текст переведён по словарю")
        if os.path.exists(path):
            os.remove(path)   # чтобы список от прошлой сборки не сбивал с толку
        return
    words = {}
    for text, count in _missing.items():
        for t in _TOKEN.findall(text):
            if t not in lang_words.WORDS:
                words[t] = words.get(t, 0) + count
    log("без английского: строк %d (неизвестных слов %d), записано латиницей: %d"
        % (len(_missing), len(words), len(_translit)))
    with open(path, "w", encoding="utf-8") as f:
        f.write("# неизвестные слова (в WORDS), сначала самые частые\n")
        for word in sorted(words, key=lambda w: (-words[w], w)):
            f.write("%s\t%d\n" % (word, words[word]))
        f.write("\n# строки целиком (в PHRASES)\n")
        for text in sorted(_missing):
            f.write("%s\n" % text)
        f.write("\n# записаны латиницей побуквенно — у канонных имён надо поставить настоящее\n"
                "# английское написание (в PHRASES или WORDS)\n")
        for text in sorted(_translit):
            f.write("%s\t%s\n" % (text, en(text)))
    log("список записан в " + os.path.basename(path))


def strings_file(language, pairs, comment, groups=()):
    """Текст языкового файла. pairs — [(id, текст)], groups — {id: заголовок-комментарий перед ним}."""
    groups = dict(groups)
    rows = []
    for key, text in pairs:
        if key in groups:
            rows.append("\n    <!-- %s -->" % groups[key])
        rows.append('    <string id="%s" text="%s" />' % (key, esc(text)))
    # Комментарий — только ВНУТРИ <base>: игра берёт ChildNodes[1] документа и ждёт там корень.
    # Комментарий перед <base> занимает это место, и файл молча пропускается целиком
    # (LocalizedTextManager.LoadLanguage, проверено по IL 19.09.2026).
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<base xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
            ' xmlns:xsd="http://www.w3.org/2001/XMLSchema" type="string">\n'
            '  <!-- %s -->\n'
            '  <tags>\n    <tag language="%s" />\n  </tags>\n'
            '  <strings>\n%s\n  </strings>\n</base>\n' % (comment, language, "\n".join(rows)))


def index(data_dir, code, language, suffix):
    """language_data.xml папки языка — по содержимому папки.

    Собирается заново каждый раз, поэтому сборщики (мир, предметы, войска, реплики) кладут свои
    файлы и ничего чужого не затирают; написанные руками файлы попадают в список так же.
    """
    folder = os.path.join(data_dir, "Languages", code)
    os.makedirs(folder, exist_ok=True)
    files = sorted(n for n in os.listdir(folder) if n.endswith("_%s.xml" % suffix))
    rows = "\n".join('  <LanguageFile xml_path="%s/%s" />' % (code, n) for n in files)
    with open(os.path.join(folder, "language_data.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n'
                '<!-- Тексты мода на этом языке. Файлы грузятся после ванильных,\n'
                '     поэтому одинаковые id перекрывают их. Список собран tools/lang.py. -->\n'
                '<LanguageData id="%s">\n%s\n</LanguageData>\n' % (language, rows))
    return folder


def write(data_dir, name, log=print):
    """Языковые файлы всех языков игры. name — основа имени файла, например "eq_world".

    RU получает настоящий перевод (наши таблицы русские), остальные — заготовку с английским
    текстом: переводчику остаётся заменить строки, а до тех пор игра и так покажет английский,
    потому что он базовый. Английской папки здесь нет: для этих строк английский уже лежит в XML,
    и второй экземпляр только мешал бы (правишь XML — а игра показывает старое из файла).
    """
    comment = ("Собран скриптом из tools/. Русский текст берётся из таблиц мода,\n"
               "     английский (базовый, лежит в самих XML) — из tools/lang_words.py.")
    for code, language, suffix in LANGUAGES:
        folder = index(data_dir, code, language, suffix)
        pairs = [(k, ru if code == "RU" else english) for k, ru, english in _pairs]
        with open(os.path.join(folder, "%s_%s.xml" % (name, suffix)), "w", encoding="utf-8") as f:
            f.write(strings_file(language, pairs, comment))
        index(data_dir, code, language, suffix)
    log("%s: языковых папок %d, строк в каждой %d" % (name, len(LANGUAGES), len(_pairs)))
