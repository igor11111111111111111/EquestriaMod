# Генерирует культуру "equestria" из ванильной имперской (все ссылки на бойцов, горожан, шаблоны отрядов
# остаются имперскими — пока у Эквестрии нет своих). Культура не основная: кампания не строит на неё
# королевства и поселения, она нужна для выбора происхождения «Пони» при создании героя.
#
# py tools/make_equestria_culture.py <папка Modules игры> <папка Module мода>
import copy
import os
import sys
import xml.etree.ElementTree as ET

GAME_MODULES, MOD = sys.argv[1], sys.argv[2]
OUT = os.path.join(MOD, "ModuleData")

CULTURE_ID = "equestria"
CHANGES = {
    "id": CULTURE_ID,
    "name": "{=eq_culture_equestria}Эквестрия",
    "text": "{=eq_culture_equestria_text}Пони Эквестрии — народ единорогов, пегасов и земных пони.",
    "is_main_culture": "false",
    "color": "0xff9b59b6",   # фиолетовый, как у Твайлайт
    "color2": "0xffF4B6E6",  # розовый
}

root = ET.parse(os.path.join(GAME_MODULES, "SandBoxCore", "ModuleData", "spcultures.xml")).getroot()
empire = next(c for c in root.iter("Culture") if c.get("id") == "empire")
culture = copy.deepcopy(empire)
for key, value in CHANGES.items():
    culture.set(key, value)

cultures = ET.Element("SPCultures")
cultures.append(culture)
ET.indent(cultures, space="\t")
path = os.path.join(OUT, "equestria_cultures.xml")
ET.ElementTree(cultures).write(path, encoding="utf-8", xml_declaration=True)
print("written", path, "root:", root.tag, "attributes:", len(culture.attrib), "children:", len(culture))
