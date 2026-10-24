# -*- coding: utf-8 -*-
"""Bilingual mod strings: English goes into the XML, Russian moves to Languages/RU.

This is how the game itself works: the base text sits right in the XML, and translations are language files
(Modules/Native/ModuleData/Languages/<code>). There is no English file and there cannot be one: English
is the base text itself. While our XML was Russian, a player with any locale saw Russian.

The mod's tables (tools/world_data.py and others) are written in Russian and need no rewriting: here
a Russian string is translated with the dictionary tools/lang_words.py - first as a whole, then word by word
("Honey Creek" = "Honey" + "Creek"). Whatever is missing from the dictionary stays Russian and goes into
the report: `lang.report()` prints the list, and the dictionary is extended from it.

Usage:
    import lang
    body.append('name="%s"' % lang.loc("culture_empire", "<Russian text>"))
    ...
    lang.write(DATA, "eq_world")   # Languages/*/eq_world_*.xml for all game languages
"""
import os
import re

import lang_words

# Game languages: folder code -> (language id as written in language_data.xml, file suffix).
# English is not in the list: it comes from the base text of the XML.
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

# English is also a language with files: the game's own ones sit in the root of Languages (std_*.xml with
# <tag language="English"/>). Needed only for dialogue lines: they have no base text in XML, the code builds
# TextObject("{=eq_...}") with no default text, and without an English file such a key is empty.
ENGLISH = ("EN", "English", "eng")


_CYRILLIC = re.compile(r"[А-Яа-яЁё]")
_TOKEN = re.compile(r"[А-Яа-яЁё]+(?:[-’'][А-Яа-яЁё]+)*")

# Letter-by-letter Latin spelling - for names missing from the dictionary. Almost all map names
# came from Equestria at War and were once English themselves, so the reverse spelling gives
# something close to the original, e.g. Aglossata, Hyarlighamn. This must not be
# done for sentences - they stay Russian and go into the report.
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
    """A name (not a sentence and not an assembled string): no full stop, no substitutions like
    {FIRSTNAME}, and all Russian words capitalised."""
    return ("." not in text and "{" not in text and bool(tokens)
            and all(t[0].isupper() for t in tokens))

_pairs = []       # [(string id, Russian text)] in order of appearance
_seen = set()
_missing = {}      # untranslated -> how many times seen
_translit = {}     # spelled in Latin letter by letter -> how many times


def esc(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def en(ru):
    """English text for a Russian string. Whatever is unknown is returned as is and remembered."""
    ru = (ru or "").strip()
    if not ru or not _CYRILLIC.search(ru):
        return ru
    whole = lang_words.PHRASES.get(ru)
    if whole:
        return whole
    # Compound name: translate word by word, but only if ALL words are known - otherwise we get
    # a half-Russian mess like "Honey" plus an untranslated Russian word, which is then hard to spot in the report.
    tokens = _TOKEN.findall(ru)
    if tokens and all(t in lang_words.WORDS for t in tokens):
        return _TOKEN.sub(lambda m: lang_words.WORDS[m.group(0)], ru)
    if _looks_like_name(ru, tokens):
        # Unknown name: spell it in Latin word by word, still taking known parts from the dictionary.
        # Remembered separately: canon names have a real English spelling (the Russian name is
        # Canterlot, not Kanterlot), and such places need to be reviewed by eye.
        _translit[ru] = _translit.get(ru, 0) + 1
        return _TOKEN.sub(lambda m: lang_words.WORDS.get(m.group(0)) or translit(m.group(0)), ru)
    _missing[ru] = _missing.get(ru, 0) + 1
    return ru


def loc(key, ru, english=None):
    """'{=key}English' for XML; the Russian is remembered for the language file.

    english is passed where the English text is assembled next to the Russian one (settlement descriptions
    are built from a template, and translating a finished sentence with the dictionary would be guesswork).
    """
    text = english if english is not None else en(ru)
    if key not in _seen:
        _seen.add(key)
        _pairs.append((key, ru, text))
    return "{=%s}%s" % (key, esc(text))


def report(log=print, dump=None):
    """How many strings were collected and what remains untranslated.

    The full list is written to a file (tools/lang_missing.txt by default): unknown words at the top
    - these are what should be added to WORDS, because compound names are built from them - and
    whole strings for PHRASES at the bottom.
    """
    log("строк с переводом: %d" % len(_pairs))
    path = dump or os.path.join(os.path.dirname(os.path.abspath(__file__)), "lang_missing.txt")
    if not _missing and not _translit:
        log("весь текст переведён по словарю")
        if os.path.exists(path):
            os.remove(path)   # so that the list from the previous build does not confuse
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
    """Language file text. pairs - [(id, text)], groups - {id: heading comment before it}."""
    groups = dict(groups)
    rows = []
    for key, text in pairs:
        if key in groups:
            rows.append("\n    <!-- %s -->" % groups[key])
        rows.append('    <string id="%s" text="%s" />' % (key, esc(text)))
    # The comment goes only INSIDE <base>: the game takes the document's ChildNodes[1] and expects the root there.
    # A comment before <base> takes that place, and the whole file is silently skipped
    # (LocalizedTextManager.LoadLanguage, checked against the IL 19.09.2026).
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<base xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
            ' xmlns:xsd="http://www.w3.org/2001/XMLSchema" type="string">\n'
            '  <!-- %s -->\n'
            '  <tags>\n    <tag language="%s" />\n  </tags>\n'
            '  <strings>\n%s\n  </strings>\n</base>\n' % (comment, language, "\n".join(rows)))


def index(data_dir, code, language, suffix):
    """language_data.xml of a language folder - from the folder's contents.

    Rebuilt every time, so the builders (world, items, troops, dialogue) drop in their own
    files and overwrite nothing of others; hand-written files get into the list the same way.
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
    """Language files for all game languages. name - the file name stem, e.g. "eq_world".

    RU gets the real translation (our tables are Russian), the others get a stub with the English
    text: a translator only has to replace the strings, and until then the game shows English anyway,
    because it is the base. There is no English folder here: for these strings English is already in the XML,
    and a second copy would only get in the way (you edit the XML - and the game shows the old text from the file).
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
