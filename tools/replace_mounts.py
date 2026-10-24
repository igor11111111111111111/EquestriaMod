# -*- coding: utf-8 -*-
"""Horses → flight scrolls in the troop, lord and equipment set XML (10.10.2026).

The mod has no mounts (see src/EquestriaFlightScroll.cs). In the horse slot of any troop
or hero, instead of an animal there is a flight scroll by level: 26+ (tier 5+) - eq_flight_scroll_50,
16–25 (tiers 3–4) - eq_flight_scroll_40, lower - eq_flight_scroll_30; heroes and lord/ruler
templates get the greater one. The harness (HorseHarness) is removed. The same rule is in code
(EquestriaFlightArmy) for vanilla troops and as a safeguard.

Foot peoples (FOOT_RACES: yaks and deer, their cultures khuzait and nord) neither fly nor ride
(user's request 10.10.2026): for their troops, lords and noble templates the horse slot is cleared,
cavalry becomes infantry (Cavalry → Infantry, HorseArcher → Ranged), and the horse requirement for
upgrading (upgrade_requires="ItemCategory.horse/war_horse") is removed.

Run it LAST, after make_troops.py / make_world.py (they rewrite the files from scratch).
Idempotent: scrolls already in place are recalculated by the same rule.

Run: py tools/replace_mounts.py <mod Module folder> [<game folder>]
"""
import glob
import os
import re
import sys

MODULE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Module")
GAME = sys.argv[2] if len(sys.argv) > 2 else r"D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"
DATA = os.path.join(MODULE, "ModuleData")
FILES = ["equestria_troops.xml", "equestria_lords.xml", "equestria_equipment_sets.xml"]
SCROLLS = {"eq_flight_scroll_50", "eq_flight_scroll_40", "eq_flight_scroll_30"}
# Foot peoples: the entry's race and the noble template's culture (equestria_equipment_sets.xml)
FOOT_RACES = {"yak", "deer"}
FOOT_CULTURES = {"khuzait", "nord"}
FOOT_GROUP = {"Cavalry": "Infantry", "HorseArcher": "Ranged"}


def dismount_head(head):
    """Opening NPCCharacter tag of a foot troop: a group without a horse, upgrade without a horse requirement."""
    for old, new in FOOT_GROUP.items():
        head = head.replace('default_group="%s"' % old, 'default_group="%s"' % new)
    return re.sub(r'\s+upgrade_requires="ItemCategory\.(?:war_)?horse"', "", head)


def scroll_for_level(level, hero):
    if hero or level >= 26:
        return "eq_flight_scroll_50"
    if level >= 16:
        return "eq_flight_scroll_40"
    return "eq_flight_scroll_30"


# All vanilla mounts: items with a <Horse ...> component (horses, camels, mules, tournament ones).
mounts = set()
for path in glob.glob(os.path.join(GAME, "Modules", "*", "ModuleData", "items", "*.xml")) \
        + glob.glob(os.path.join(GAME, "Modules", "*", "ModuleData", "*items*.xml")):
    text = open(path, encoding="utf-8", errors="replace").read()
    for m in re.finditer(r'<Item\s+id="([^"]+)"(.*?)</Item>', text, re.S):
        if "<Horse" in m.group(2) or 'Type="Horse"' in m.group(0):
            mounts.add(m.group(1))
mounts -= SCROLLS
print(f"[mounts] ездовых предметов в игре: {len(mounts)}")

# Keep the tag as it was: in troops and lords (NPCCharacters schema) it is "equipment", and in noble
# templates (equestria_equipment_sets.xml, EquipmentRosters schema) it is "Equipment". Before 10.10.2026
# "equipment" was always written here, and in templates the game silently dropped the line: kings and
# template lords were left without a scroll, and rgl_log was flooded with "invalid child element 'equipment'".
horse_re = re.compile(r'<([Ee]quipment)\s+slot="Horse"\s+id="Item\.([^"]+)"\s*/>')
harness_re = re.compile(r'[ \t]*<[Ee]quipment\s+slot="HorseHarness"\s+id="Item\.[^"]+"\s*/>\r?\n')
char_re = re.compile(r'(<NPCCharacter\b[^>]*>)(.*?)(</NPCCharacter>)', re.S)
roster_re = re.compile(r'(<EquipmentRoster\b[^>]*>)(.*?)(</EquipmentRoster>)', re.S)

for name in FILES:
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        continue
    text = open(path, encoding="utf-8").read()
    replaced = [0]
    unmounted = [0]

    def fix_block(body, level, hero, foot=False):
        def sub(m):
            tag, item = m.group(1), m.group(2)
            if item not in mounts and item not in SCROLLS:
                return m.group(0)
            replaced[0] += 1
            if foot:
                unmounted[0] += 1
                return ""          # foot people: the horse slot is empty
            return '<%s slot="Horse" id="Item.%s"/>' % (tag, scroll_for_level(level, hero))
        body = horse_re.sub(sub, body)
        return harness_re.sub("", body)

    if name == "equestria_equipment_sets.xml":
        # Culture templates (lords/rulers/children): no level, so everyone gets the greater one
        def fix_roster(m):
            culture = re.search(r'culture="Culture\.([^"]+)"', m.group(1))
            foot = bool(culture) and culture.group(1) in FOOT_CULTURES
            return m.group(1) + fix_block(m.group(2), 99, True, foot) + m.group(3)
        text = roster_re.sub(fix_roster, text)
    else:
        def fix_char(m):
            head = m.group(1)
            level_m = re.search(r'level="(\d+)"', head)
            level = int(level_m.group(1)) if level_m else 1
            hero = 'is_hero="true"' in head
            race = re.search(r'race="([^"]+)"', head)
            foot = bool(race) and race.group(1) in FOOT_RACES
            if foot:
                head = dismount_head(head)
            return head + fix_block(m.group(2), level, hero, foot) + m.group(3)
        text = char_re.sub(fix_char, text)
    text = re.sub(r"\n[ \t]*\n(?=[ \t]*<)", "\n", text)   # blank lines left by removed slots
    open(path, "w", encoding="utf-8", newline="\n").write(text)
    left = len(horse_re.findall(text)) - sum(text.count('Item.%s"' % s) for s in SCROLLS)
    print(f"[mounts] {name}: слотов коня заменено {replaced[0]} (из них у пеших народов очищено "
          f"{unmounted[0]}), осталось зверей {max(left, 0)}")
