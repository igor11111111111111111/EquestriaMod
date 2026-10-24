# -*- coding: utf-8 -*-
"""Кони → свитки полёта в XML войск, лордов и наборов снаряжения (10.10.2026).

Ездовых зверей в моде нет (см. src/EquestriaFlightScroll.cs). В слоте коня у любого войска
или героя вместо зверя лежит свиток полёта по уровню: 26+ (ранг 5+) — eq_flight_scroll_50,
16–25 (ранги 3–4) — eq_flight_scroll_40, ниже — eq_flight_scroll_30; герои и шаблоны
лордов/правителей — великий. Сбруя (HorseHarness) убирается. То же правило в коде
(EquestriaFlightArmy) для ванильных войск и как страховка.

Пешие народы (FOOT_RACES: яки и олени, их культуры khuzait и nord) не летают и не ездят
(просьба пользователя 10.10.2026): у их войск, лордов и шаблонов знати слот коня очищается,
конница становится пехотой (Cavalry → Infantry, HorseArcher → Ranged), а требование коня для
улучшения (upgrade_requires="ItemCategory.horse/war_horse") снимается.

Запускать ПОСЛЕДНИМ, после make_troops.py / make_world.py (они переписывают файлы заново).
Идемпотентен: уже стоящие свитки пересчитывает по тому же правилу.

Запуск: py tools/replace_mounts.py <папка Module мода> [<папка игры>]
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
# Пешие народы: раса записи и культура шаблона знати (equestria_equipment_sets.xml)
FOOT_RACES = {"yak", "deer"}
FOOT_CULTURES = {"khuzait", "nord"}
FOOT_GROUP = {"Cavalry": "Infantry", "HorseArcher": "Ranged"}


def dismount_head(head):
    """Открывающий тег NPCCharacter пешего: группа без коня, улучшение без требования коня."""
    for old, new in FOOT_GROUP.items():
        head = head.replace('default_group="%s"' % old, 'default_group="%s"' % new)
    return re.sub(r'\s+upgrade_requires="ItemCategory\.(?:war_)?horse"', "", head)


def scroll_for_level(level, hero):
    if hero or level >= 26:
        return "eq_flight_scroll_50"
    if level >= 16:
        return "eq_flight_scroll_40"
    return "eq_flight_scroll_30"


# Все ездовые звери ванили: предметы с компонентом <Horse ...> (кони, верблюды, мулы, турнирные).
mounts = set()
for path in glob.glob(os.path.join(GAME, "Modules", "*", "ModuleData", "items", "*.xml")) \
        + glob.glob(os.path.join(GAME, "Modules", "*", "ModuleData", "*items*.xml")):
    text = open(path, encoding="utf-8", errors="replace").read()
    for m in re.finditer(r'<Item\s+id="([^"]+)"(.*?)</Item>', text, re.S):
        if "<Horse" in m.group(2) or 'Type="Horse"' in m.group(0):
            mounts.add(m.group(1))
mounts -= SCROLLS
print(f"[mounts] ездовых предметов в игре: {len(mounts)}")

# Тег сохраняем как был: в войсках и лордах (схема NPCCharacters) он «equipment», а в шаблонах
# знати (equestria_equipment_sets.xml, схема EquipmentRosters) — «Equipment». До 10.10.2026 тут
# всегда писалось «equipment», и в шаблонах игра молча выкидывала строку: короли и лорды по шаблону
# оставались без свитка, а rgl_log сыпал «invalid child element 'equipment'».
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
                return ""          # пеший народ: слот коня пуст
            return '<%s slot="Horse" id="Item.%s"/>' % (tag, scroll_for_level(level, hero))
        body = horse_re.sub(sub, body)
        return harness_re.sub("", body)

    if name == "equestria_equipment_sets.xml":
        # Шаблоны культуры (лорды/правители/дети): уровня нет — всем великий
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
    text = re.sub(r"\n[ \t]*\n(?=[ \t]*<)", "\n", text)   # пустые строки от убранных слотов
    open(path, "w", encoding="utf-8", newline="\n").write(text)
    left = len(horse_re.findall(text)) - sum(text.count('Item.%s"' % s) for s in SCROLLS)
    print(f"[mounts] {name}: слотов коня заменено {replaced[0]} (из них у пеших народов очищено "
          f"{unmounted[0]}), осталось зверей {max(left, 0)}")
