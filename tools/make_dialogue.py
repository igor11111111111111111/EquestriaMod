# -*- coding: utf-8 -*-
"""Реплики на других языках из русских файлов.

  py tools/make_dialogue.py [папка Module]

Исходник — Module/ModuleData/Languages/RU/eq_bandits_rus.xml, eq_lords_rus.xml, eq_npc_rus.xml:
они пишутся руками, там порядок, группы и подстановки. Скрипт читает их и для каждого другого языка
кладёт такие же файлы (eq_bandits_eng.xml и т. д.):
  - перенаправления ванильных id на переменные ({EQV_...}) — как есть, они от языка не зависят;
  - фразы — из tools/dialogue_en.py по id строки.
Английский здесь — настоящий язык с папкой EN: у этих строк нет базового текста в XML, код строит
TextObject("{=eq_...}") без текста по умолчанию, и без английского файла такой ключ пуст. Остальные
языки получают заготовку с английским текстом. Чего нет в dialogue_en.py — остаётся русским и
печатается списком; такие строки надо перевести, иначе они и в английской игре будут русскими.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lang  # noqa: E402
from dialogue_en import EN  # noqa: E402

MOD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Module")
DATA = os.path.join(MOD, "ModuleData")
RU = os.path.join(DATA, "Languages", "RU")
FILES = ("eq_bandits", "eq_lords", "eq_npc")
REDIRECT = re.compile(r"^\{EQV_[A-Z0-9_]+\}$")


def log(*a):
    print("[dialogue]", *a, flush=True)


def read(name):
    """[(id, русский текст)], {id: комментарий-заголовок группы перед ним}, комментарий файла."""
    path = os.path.join(RU, "%s_rus.xml" % name)
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    root = ET.parse(path, parser).getroot()
    pairs, groups, pending = [], {}, None
    for node in root.find("strings"):
        if node.tag is ET.Comment:
            pending = " ".join(node.text.split())
        else:
            if pending:
                groups[node.get("id")] = pending
                pending = None
            pairs.append((node.get("id"), node.get("text") or ""))
    # заголовок файла — первый комментарий верхнего уровня, он объясняет устройство групп
    raw = open(path, encoding="utf-8").read()
    m = re.search(r"<!--(.*?)-->", raw, re.S)
    header = " ".join(m.group(1).split()) if m else name
    return pairs, groups, header


def main():
    missing = []
    total = 0
    targets = [lang.ENGLISH] + [t for t in lang.LANGUAGES if t[0] != "RU"]
    for name in FILES:
        pairs, groups, header = read(name)
        english = []
        for key, ru in pairs:
            if REDIRECT.match(ru):
                english.append((key, ru))
            elif key in EN:
                english.append((key, EN[key]))
            else:
                english.append((key, ru))
                missing.append(key)
        total += len(english)
        comment = ("Собран tools/make_dialogue.py из RU/%s_rus.xml: перенаправления те же, фразы —\n"
                   "     из tools/dialogue_en.py. Правьте их, не этот файл.\n     %s" % (name, header))
        for code, language, suffix in targets:
            folder = os.path.join(DATA, "Languages", code)
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, "%s_%s.xml" % (name, suffix)), "w", encoding="utf-8") as f:
                f.write(lang.strings_file(language, english, comment, groups))
    # language_data.xml — всем, кроме EN: английскую папку игра не читает (см. EquestriaEnglishTexts.cs),
    # её файлы подкладывает сам мод, а второе объявление языка English игре ни к чему
    for code, language, suffix in lang.LANGUAGES:
        lang.index(DATA, code, language, suffix)
    log("строк в каждом языке: %d, языков кроме русского: %d" % (total, len(targets)))
    if missing:
        log("без английского (остались русскими): %d — %s" % (len(missing), ", ".join(missing[:30])))
    else:
        log("все реплики переведены")


if __name__ == "__main__":
    main()
