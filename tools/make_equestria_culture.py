# Generates the "equestria" culture from the vanilla imperial one (all references to troops, townsfolk and
# party templates stay imperial until Equestria has its own). Not a main culture: the campaign builds no
# kingdoms or settlements on it; it is needed to pick the "Pony" origin during character creation.
#
# py tools/make_equestria_culture.py <the game's Modules folder> <the mod's Module folder>
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
    "color": "0xff9b59b6",   # purple, like Twilight's
    "color2": "0xffF4B6E6",  # pink
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
