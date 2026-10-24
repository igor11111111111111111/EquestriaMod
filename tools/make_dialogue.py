# -*- coding: utf-8 -*-
"""Dialogue lines in other languages from the Russian files.

  py tools/make_dialogue.py [Module folder]

Source: Module/ModuleData/Languages/RU/eq_bandits_rus.xml, eq_lords_rus.xml, eq_npc_rus.xml:
they are written by hand and hold the order, groups and substitutions. The script reads them and for
each other language writes the same files (eq_bandits_eng.xml etc.):
  - redirects of vanilla ids to variables ({EQV_...}) - as is, they do not depend on the language;
  - phrases - from tools/dialogue_en.py by string id.
English here is a real language with an EN folder: these strings have no base text in XML, the code builds
TextObject("{=eq_...}") with no default text, and without the English file such a key is empty. The other
languages get a stub with the English text. Whatever is missing from dialogue_en.py stays Russian and
is printed as a list; such strings must be translated, otherwise they will be Russian in the English game too.
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
    """[(id, Russian text)], {id: group header comment before it}, file comment."""
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
    # the file header is the first top-level comment; it explains how the groups are organised
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
    # language_data.xml - for all except EN: the game does not read the English folder (see
    # EquestriaEnglishTexts.cs), the mod supplies its files itself, and a second English language
    # declaration is of no use to the game
    for code, language, suffix in lang.LANGUAGES:
        lang.index(DATA, code, language, suffix)
    log("строк в каждом языке: %d, языков кроме русского: %d" % (total, len(targets)))
    if missing:
        log("без английского (остались русскими): %d — %s" % (len(missing), ", ".join(missing[:30])))
    else:
        log("все реплики переведены")


if __name__ == "__main__":
    main()
