# Builds equestria_items.xml: race body parts (manes, tails, wings) and the hive armour.
#
#   python make_items.py <mod Module folder> [game folder]
#
# Tails, wings and mane items no longer exist (removed 26.09.2026): body parts are attached to the skeleton.
# The mod has no shared armour of its own: all races are fitted to the vanilla human and wear the game's normal
# items (two hundred-odd duplicates on pony meshes were removed 24.09.2026).
# The exception is the hive: its armour is vanilla Aserai MESHES with our textures (black chitin
# and glowing turquoise veins, tools/hive_armor.py + tools/hive_material.ps1). The geometry is
# vanilla, so it fits everyone just like normal armour; only the materials change, which means
# our own item entries are needed too - the material lives on the mesh, and the mesh is chosen by the item.
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

HIVE_ITEM = "eq_changeling_"    # prefix of hive items
HIVE_MESH = "eq_ch_"            # prefix of our mesh copies (tools/hive_material.ps1)

def log(*a):
    print("[items]", *a, flush=True)


def indent(element, level):
    """Print an element indented with tabs - so the file is readable by eye."""
    pad = "\t" * level
    attrs = "".join('\n%s\t%s="%s"' % (pad, k, v) for k, v in element.attrib.items())
    children = list(element)
    if not children:
        return "%s<%s%s />" % (pad, element.tag, attrs)
    inner = "\n".join(indent(child, level + 1) for child in children)
    return "%s<%s%s>\n%s\n%s</%s>" % (pad, element.tag, attrs, inner, pad, element.tag)


def vanilla_items():
    """{id: (file, element)} - all vanilla armour items."""
    found = {}
    for filename in ("head_armors.xml", "body_armors.xml", "leg_armors.xml", "arm_armors.xml"):
        path = os.path.join(ITEMS_DIR, filename)
        if not os.path.exists(path):
            continue
        for item in ET.parse(path).getroot().iter("Item"):
            found[item.get("id")] = (filename, item)
    return found


def hive_armor():
    """Hive armour: copies of vanilla items on our meshes. Returns chunks of XML."""
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
        # English name - from the vanilla item, Russian - from the catalogue (tools/armor_catalog.py)
        copy.set("name", lang.loc(new_id, "Улей: " + row["name"],
                                  "Hive " + (source[1].get("name") or row["item"]).split("}")[-1]))
        copy.set("mesh", HIVE_MESH + (source[1].get("mesh") or row["item"]))
        # We did not copy the female variant of the mesh - the engine would look for a nonexistent one.
        armor = copy.find("ItemComponent/Armor")
        if armor is not None:
            armor.set("has_gender_variations", "false")
        out.append(indent(copy, 1))
        count += 1
    log("броня улья: вещей %d" % count)
    return out


def meat_item():
    """Prisoner meat (src/EquestriaPrisonerButchery.cs): in the mod all troops are animals, some races are
    predators or omnivores - processing prisoners into supplies fits the lore just like the orcs'
    in The Old Realms. No meshes of our own - we use the vanilla barrel (the same item as oliv/date_fruit
    in SandBoxCore); it is an ordinary IsFood good like those, it just may have no buyer."""
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
    """Flight scroll (src/EquestriaFlightTest.cs): there will be no riding horses in the mod - an animal
    riding an animal is absurd. The horse slot is taken by a scroll instead: Type="Horse" - that is enough
    for the equipment editor to accept the item in the slot (Equipment.IsItemFitsToSlot looks only at
    ItemType, verified by decompilation 05.10.2026) - with no <ItemComponent><Horse .../></ItemComponent>
    at all. It used to have one (referring to its own monster eq_flight_mount, Module/ModuleData/
    eq_flight_monster.xml) - removed once it turned out that the engine reads the hoof sound, the formation class
    (cavalry) and the riding pose itself in battle from the mere presence of a HorseComponent in the
    equipment, bypassing actual mounting: without the component all these systems simply do not
    fire, rather than merely not breaking from our patches - see src/EquestriaFlightScroll.cs.
    modifier_group is deliberately not set: we do not want random "Poor/Fine" in the name."""
    # Three scrolls (10.10.2026): speed +50% / +40% / +30% - the multipliers are in src/EquestriaFlightScroll.cs
    # (Scrolls), the ids there must match. Campaign cavalry gets them by troop tier
    # (EquestriaFlightArmy).
    scrolls = [("eq_flight_scroll_50", "Свиток полёта (великий)", "Greater Scroll of Flight", 500, "lib_scroll_c"),
               ("eq_flight_scroll_40", "Свиток полёта", "Scroll of Flight", 400, "lib_scroll_b"),
               ("eq_flight_scroll_30", "Свиток полёта (малый)", "Lesser Scroll of Flight", 300, "lib_scroll_a")]
    lines = []
    for item_id, ru, en, value, mesh in scrolls:  # mesh = the picture in the inventory (vanilla scrolls lib_scroll_*)
        name = lang.loc(item_id, ru, en)
        lines += ['	<Item',
                  '		id="%s"' % item_id,
                  '		name="%s"' % name,
                  '		mesh="%s"' % mesh,
                  # "war horse, 10.10.2026": the scroll is good for upgrading any cavalry - the troops'
                  # "horse" requirement is replaced with "war horse" at startup (EquestriaFlightArmy)
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
# Vanilla pack animals are "carts" in game (equestria_items.xslt swaps the mesh for a cart);
# we override the names by vanilla string ids (the mod's language files load after the vanilla ones).
lang.loc("P1rL28RT", "Повозка{@Plural}повозки{\@}", "Cart{@Plural}carts{\@}")          # sumpter_horse
lang.loc("VqCS28U1", "Тележка{@Plural}тележки{\@}", "Handcart{@Plural}handcarts{\@}")  # mule
lang.loc("1O761hqN", "Большая повозка{@Plural}большие повозки{\@}", "Wagon{@Plural}wagons{\@}")  # pack_camel
body.append("</Items>\n")
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(body))
lang.write(os.path.dirname(OUT), "eq_items", log)
lang.report(log)
log("записано -> %s" % OUT)
