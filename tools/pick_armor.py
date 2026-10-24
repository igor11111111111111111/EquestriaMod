# Выбирает ванильную имперскую броню для переделки под пони.
#
#   python pick_armor.py [папка игры]
#
# Печатает по пять вещей в каждом слоте (шлем, корпус, ноги, руки) — самые защищённые из имперских,
# с именем меша, которое нужно выгрузить утилитой tpac_export и скормить adapt_armor.py.
import os
import sys
import xml.etree.ElementTree as ET

GAME = sys.argv[1] if len(sys.argv) > 1 else \
    r"D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"
ITEMS = os.path.join(GAME, "Modules", "SandBoxCore", "ModuleData", "items")

# файл -> (как называется слот у нас, какое поле брони считать главным)
SLOTS = [
    ("head_armors.xml", "head", "head_armor"),
    ("body_armors.xml", "body", "body_armor"),
    ("leg_armors.xml", "legs", "leg_armor"),
    ("arm_armors.xml", "hands", "arm_armor"),
]


def armor_value(item, field):
    armor = item.find("ItemComponent/Armor")
    if armor is None:
        return -1
    try:
        return int(armor.get(field) or 0)
    except ValueError:
        return -1


for filename, slot, field in SLOTS:
    root = ET.parse(os.path.join(ITEMS, filename)).getroot()
    rows = []
    for item in root.iter("Item"):
        if (item.get("culture") or "") != "Culture.empire":
            continue
        # Женские варианты и «полные» дубли пропускаем: у пони одна модель на всех.
        item_id = item.get("id") or ""
        if item_id.endswith("_female") or "_civil" in item_id:
            continue
        mesh = item.get("mesh")
        if not mesh:
            continue
        rows.append((armor_value(item, field), item_id, mesh, item.get("name", "")))
    rows.sort(reverse=True)

    print("### %s — %d имперских вещей, берём 5 лучших" % (slot, len(rows)))
    for value, item_id, mesh, name in rows[:5]:
        print('    ("%s", "%s", "eq_pony_%s"),   # защита %d, %s'
              % (mesh, slot, item_id, value, name.split("}")[-1]))
    print()
