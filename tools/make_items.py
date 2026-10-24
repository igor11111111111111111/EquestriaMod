# Собирает equestria_items.xml: части тела рас (гривы, хвосты, крылья) и броню улья.
#
#   python make_items.py <папка Module мода> [папка игры]
#
# Хвостов, крыльев и грив-предметов больше нет (удалены 26.09.2026): части тела вешаются на скелет.
# Общей своей брони в моде нет: все расы подогнаны под ванильного человека и носят обычные вещи
# игры (двести с лишним дубликатов на пони-мешах убраны 24.09.2026).
# Исключение — улей: его броня это ванильные асерайские МЕШИ с нашими текстурами (чёрный хитин
# и светящиеся бирюзовые прожилки, tools/hive_armor.py + tools/hive_material.ps1). Геометрия
# ванильная, поэтому садится на всех так же, как обычная; меняются только материалы, а значит
# нужны и свои записи предметов — материал живёт на меше, а меш выбирается предметом.
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MOD = sys.argv[1]
GAME = sys.argv[2] if len(sys.argv) > 2 else \
    r"D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"
ITEMS_DIR = os.path.join(GAME, "Modules", "SandBoxCore", "ModuleData", "items")
OUT = os.path.join(MOD, "ModuleData", "equestria_items.xml")

import armor_catalog  # noqa: E402
import lang  # noqa: E402

HIVE_ITEM = "eq_changeling_"    # приставка предметов улья
HIVE_MESH = "eq_ch_"            # приставка наших копий мешей (tools/hive_material.ps1)

def log(*a):
    print("[items]", *a, flush=True)


def indent(element, level):
    """Печать элемента с отступами табами — чтобы файл читался глазами."""
    pad = "\t" * level
    attrs = "".join('\n%s\t%s="%s"' % (pad, k, v) for k, v in element.attrib.items())
    children = list(element)
    if not children:
        return "%s<%s%s />" % (pad, element.tag, attrs)
    inner = "\n".join(indent(child, level + 1) for child in children)
    return "%s<%s%s>\n%s\n%s</%s>" % (pad, element.tag, attrs, inner, pad, element.tag)


def vanilla_items():
    """{id: (файл, элемент)} — все ванильные вещи брони."""
    found = {}
    for filename in ("head_armors.xml", "body_armors.xml", "leg_armors.xml", "arm_armors.xml"):
        path = os.path.join(ITEMS_DIR, filename)
        if not os.path.exists(path):
            continue
        for item in ET.parse(path).getroot().iter("Item"):
            found[item.get("id")] = (filename, item)
    return found


def hive_armor():
    """Броня улья: копии ванильных вещей на наших мешах. Возвращает куски XML."""
    known = vanilla_items()
    out = []
    count = 0
    for row in armor_catalog.pieces("changeling", GAME):
        source = known.get(row["item"])
        if source is None:
            log("нет ванильной вещи:", row["item"])
            continue
        copy = ET.fromstring(ET.tostring(source[1]))
        new_id = HIVE_ITEM + row["item"]
        copy.set("id", new_id)
        # английское название — у ванильной вещи, русское — из каталога (tools/armor_catalog.py)
        copy.set("name", lang.loc(new_id, "Улей: " + row["name"],
                                  "Hive " + (source[1].get("name") or row["item"]).split("}")[-1]))
        copy.set("mesh", HIVE_MESH + (source[1].get("mesh") or row["item"]))
        # Женского варианта меша мы не копировали — движок искал бы несуществующий.
        armor = copy.find("ItemComponent/Armor")
        if armor is not None:
            armor.set("has_gender_variations", "false")
        out.append(indent(copy, 1))
        count += 1
    log("броня улья: вещей %d" % count)
    return out


def meat_item():
    """Мясо пленных (src/EquestriaPrisonerButchery.cs): в моде все войска — звери, часть рас
    хищники или всеядные — переработка пленных в припасы вписывается в лор так же, как у орков
    в The Old Realms. Мешей своих нет — берём ванильный бочонок (та же вещь, что у oliv/date_fruit
    в SandBoxCore), это такой же обычный товар IsFood, просто покупателя у него может не быть."""
    name = lang.loc("eq_prisoner_meat", "Деликатес", "Delicacy")
    return ['\t<Item',
            '\t\tid="eq_prisoner_meat"',
            '\t\tname="%s"' % name,
            '\t\tmesh="bd_barrel_a"',
            '\t\tIsFood="true"',
            '\t\tvalue="15"',
            '\t\tweight="10"',
            '\t\tType="Goods">',
            '\t\t<ItemComponent>',
            '\t\t\t<Trade morale_bonus="-2" />',
            '\t\t</ItemComponent>',
            '\t\t<Flags Civilian="true" />',
            '\t</Item>']


def flight_scroll_item():
    """Свиток полёта (src/EquestriaFlightTest.cs): ездовых коней в моде не будет — зверю на звере
    ездить верхом нелепо. Слот коня вместо этого занимает свиток: Type="Horse" — этого хватает,
    чтобы редактор снаряжения принял предмет в слот (Equipment.IsItemFitsToSlot смотрит только на
    ItemType, декомпиляцией проверено 05.10.2026) — без <ItemComponent><Horse .../></ItemComponent>
    совсем. Раньше он был (ссылался на свой монстр eq_flight_mount, Module/ModuleData/
    eq_flight_monster.xml) — убрали, когда выяснилось, что движок звук копыт, класс построения
    (кавалерия) и саму позу верховой езды в бою читает по самому наличию HorseComponent в
    снаряжении, в обход реального вмонтирования: без компонента все эти системы просто не
    срабатывают, а не только не ломаются от наших патчей — см. src/EquestriaFlightScroll.cs.
    modifier_group не ставим специально: не хотим случайных «Плохой/Отличный» в названии."""
    # Три свитка (10.10.2026): скорость +50% / +40% / +30% — множители в src/EquestriaFlightScroll.cs
    # (Scrolls), id там должны совпадать. Конница кампании получает их по рангу войска
    # (EquestriaFlightArmy).
    scrolls = [("eq_flight_scroll_50", "Свиток полёта (великий)", "Greater Scroll of Flight", 500, "lib_scroll_c"),
               ("eq_flight_scroll_40", "Свиток полёта", "Scroll of Flight", 400, "lib_scroll_b"),
               ("eq_flight_scroll_30", "Свиток полёта (малый)", "Lesser Scroll of Flight", 300, "lib_scroll_a")]
    lines = []
    for item_id, ru, en, value, mesh in scrolls:  # меш = картинка в инвентаре (ванильные свитки lib_scroll_*)
        name = lang.loc(item_id, ru, en)
        lines += ['	<Item',
                  '		id="%s"' % item_id,
                  '		name="%s"' % name,
                  '		mesh="%s"' % mesh,
                  # «боевой конь» (10.10.2026): свиток годится для улучшения любой конницы — требование
                  # «конь» у войск заменено на «боевой конь» при запуске (EquestriaFlightArmy)
                  '		item_category="war_horse"',
                  '		value="%d"' % value,
                  '		weight="1"',
                  '		is_merchandise="true"',
                  '		Type="Horse" />']
    return lines


body = ['<?xml version="1.0" encoding="utf-8"?>',
        "<!-- Броня улья. Файл собран tools/make_items.py. Хвосты, крылья, рога и гривы — не предметы:",
        "     они части модели расы, их вешает на скелет src/EquestriaBodyParts.cs. -->",
        "<!-- Остальные расы носят ванильную броню (см. шапку make_items.py). -->",
        "<Items>"]
body.append("\n\t<!-- Броня улья: ванильные меши с хитиновыми текстурами и свечением -->")
body.extend(hive_armor())
body.append("\n\t<!-- Мясо пленных: переработка (src/EquestriaPrisonerButchery.cs) -->")
body.append("\n".join(meat_item()))
body.append("\n\t<!-- Свиток полёта: замена ездовым коням (src/EquestriaFlightTest.cs) -->")
body.append("\n".join(flight_scroll_item()))
# Вьючные звери ванили в игре — «повозки» (equestria_items.xslt подменяет меш на телегу);
# названия перекрываем по ванильным строковым id (языковые файлы мода грузятся после ванильных).
lang.loc("P1rL28RT", "Повозка{@Plural}повозки{\@}", "Cart{@Plural}carts{\@}")          # sumpter_horse
lang.loc("VqCS28U1", "Тележка{@Plural}тележки{\@}", "Handcart{@Plural}handcarts{\@}")  # mule
lang.loc("1O761hqN", "Большая повозка{@Plural}большие повозки{\@}", "Wagon{@Plural}wagons{\@}")  # pack_camel
body.append("</Items>\n")
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(body))
lang.write(os.path.dirname(OUT), "eq_items", log)
lang.report(log)
log("записано -> %s" % OUT)
