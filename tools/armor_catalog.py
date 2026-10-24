# Pony armour catalogue: which vanilla items are reworked and which FBX pack they belong to.
#
# Used by adapt_armor.py (which meshes to fit) and make_items.py (which items to describe).
#
# Packs:
#   armor      — the first 20 items: the five best imperial ones in each slot (tools/pick_armor.py).
#                FBX assets/pony_armor/eq_pony_armor.fbx.
#   empire     — all the other armour worn by Equestria's troops (the vanilla imperial tree,
#                tools/make_troops.py). FBX assets/pony_armor_empire/eq_pony_armor_empire.fbx.
#   bandits    — bandit armour that is not in the first two packs.
#                FBX assets/pony_armor_bandits/eq_pony_armor_bandits.fbx.
#
# The cape slot (pauldrons, scarves) is not reworked: the pony has her tail in it.
import os
import re
import xml.etree.ElementTree as ET

GAME = r"D:\Program Files (x86)\Steam\steamapps\common\Mount & Blade II Bannerlord"

FILES = {
    "head_armors.xml": ("Head", "head"),
    "body_armors.xml": ("Body", "body"),
    "leg_armors.xml": ("Leg", "legs"),
    "arm_armors.xml": ("Gloves", "hands"),
}
SLOT_MODE = {slot: mode for slot, mode in FILES.values()}

# The first set, with names chosen by hand.
ARMOR = {
    "head_armors.xml": [
        ("imperial_goggled_helmet", "Шлем катафракта с окулярами"),
        ("heavy_nasalhelm_over_imperial_mail", "Тяжёлый наносник поверх кольчуги"),
        ("empire_guarded_lord_helmet", "Королевский шлем катафракта"),
        ("ironlame_nasalhelm_over_imperial_mail", "Железный наносник поверх кольчуги"),
        ("ironlame_nasalhelm_over_imperial_coif", "Железный наносник поверх койфа"),
    ],
    "body_armors.xml": [
        ("imperial_scale_armor", "Тяжёлая чешуя поверх кольчуги"),
        ("lamellar_with_scale_skirt", "Ламеллярный доспех с чешуйчатой юбкой"),
        ("imperial_lamellar", "Ламеллярный доспех катафракта"),
        ("empire_plate_vest_armor", "Узорчатый чешуйчатый доспех"),
        ("empire_legion_b", "Узорчатая легионерская чешуя"),
    ],
    "leg_armors.xml": [
        ("plated_strip_boots", "Наборные сапоги"),
        ("decorated_imperial_boots", "Украшенные латные сапоги"),
        ("lamellar_plate_boots", "Ламеллярные латные сапоги"),
        ("strapped_leather_boots", "Кожаные сапоги с ремнями"),
        ("empire_horseman_boots", "Сапоги всадника"),
    ],
    "arm_armors.xml": [
        ("lamellar_plate_gauntlets", "Ламеллярные латные рукавицы"),
        ("plated_strip_gauntlets", "Наборные наручи"),
        ("decorated_imperial_gauntlets", "Украшенные имперские рукавицы"),
        ("reinforced_padded_mitten", "Усиленные стёганые рукавицы"),
        ("lordly_padded_mitten", "Господские стёганые рукавицы"),
    ],
}

PACKS = {
    "armor": "eq_pony_armor",
    "empire": "eq_pony_armor_empire",
    "bandits": "eq_pony_armor_bandits",
    "changeling": "eq_pony_armor_changeling",
}
# pack -> troop group from tools/make_troops.py whose armour it reworks
PACK_GROUPS = {
    "empire": "Эквестрия",
    "bandits": "разбойники",
    # the swarm wears the Aserai tree: its own silhouettes (robes, scales, turbans) and its own textures,
    # recoloured into chitin with turquoise (tools/recolor_armor.py)
    "changeling": "Чейнджлинги",
}

_TAG = re.compile(r"\{[^}]*\}")

# Names that are declined incorrectly in the game's localisation.
NAME_FIXES = {
    "wolfhead": "Волчья голова",
    "bearhead": "Медвежья голова",
}


def _paths(game):
    base = os.path.join(game or GAME, "Modules", "SandBoxCore", "ModuleData")
    return (os.path.join(base, "items"),
            os.path.join(base, "spnpccharacters.xml"),
            os.path.join(base, "spcultures.xml"),
            os.path.join(base, "Languages", "RU", "std_spitems_xml_rus.xml"))


def _russian(game):
    """String id -> Russian text without the {.MI} service markers and plural variants.

    Item names are scattered across several files: some in SandBoxCore (std_spitems),
    some in Native (std_common_strings). We read the Russian files of all modules.
    """
    modules = os.path.join(game or GAME, "Modules")
    result = {}
    for module in sorted(os.listdir(modules)):
        folder = os.path.join(modules, module, "ModuleData", "Languages", "RU")
        if not os.path.isdir(folder):
            continue
        for filename in sorted(os.listdir(folder)):
            if not filename.endswith(".xml"):
                continue
            try:
                root = ET.parse(os.path.join(folder, filename)).getroot()
            except ET.ParseError:
                continue
            for s in root.iter("string"):
                text = (s.get("text") or "").split("{@PLURAL")[0]
                result.setdefault(s.get("id"), _agree(text))
    return result


# Russian names in the game files are marked up for declension: {.FI}Leather{.aj} {.FI}cap{.nn}.
# Before the word is the gender (M/F/N), after it the part of speech: aj adjective, ajp plural
# adjective. The engine declines them; we write finished text, so we make them agree ourselves.
_WORD = re.compile(r"\{\.([MFN])\w*\}([^{\s]+)\{\.(ajp|aj|nnp|nn)\}")
_HUSH = "гкхжшщч"


def _adjective(word, gender, plural):
    for ending in ("ый", "ий", "ой"):
        if not word.endswith(ending):
            continue
        stem = word[:-2]
        hard = ending == "ый" or (ending == "ой" and stem[-1:] not in _HUSH) \
            or (ending == "ий" and stem[-1:] in _HUSH)
        if plural:
            return stem + ("ые" if ending == "ый" or (ending == "ой" and stem[-1:] not in _HUSH) else "ие")
        if gender == "F":
            return stem + ("ая" if hard or ending == "ой" else "яя")
        if gender == "N":
            if ending == "ой" or (ending == "ий" and stem[-1:] in "гкх"):
                return stem + "ое"
            return stem + ("ое" if ending == "ый" else "ее")
        return word
    return word


def _agree(text):
    def fix(match):
        gender, word, kind = match.group(1), match.group(2), match.group(3)
        if kind.startswith("aj"):
            return _adjective(word, gender, kind == "ajp")
        return word
    return _TAG.sub("", _WORD.sub(fix, text)).strip()


def _vanilla_items(game):
    """item id -> (file, element)"""
    items_dir = _paths(game)[0]
    result = {}
    for filename in FILES:
        for item in ET.parse(os.path.join(items_dir, filename)).getroot().iter("Item"):
            result[item.get("id")] = (filename, item)
    return result


def _troop_items(game, group):
    """Armour of the group's troops (tools/make_troops.py) in order of appearance."""
    import make_troops  # noqa: E402 — the same troop list as when they are built
    return make_troops.troop_armor(game)[group]


def pieces(pack, game=None):
    """List of the pack's items: dicts with item, file, slot, mode, mesh, name, pony_item, pony_mesh."""
    vanilla = _vanilla_items(game)
    russian = _russian(game)
    first = [(f, item, name) for f, rows in ARMOR.items() for item, name in rows]
    if pack == "armor":
        chosen = first
    elif pack in PACK_GROUPS:
        # Items already included in earlier packs are not repeated, but only among the pony packs.
        # The mod no longer has them (all pony armour was removed, the races wear vanilla), so nothing is
        # taken away from the hive: otherwise 23 of 66 items stayed vanilla and drones walked in
        # sandy robes next to chitin archers (seen in game 25.09.2026).
        taken = set() if pack == "changeling" else {item for _f, item, _n in first}
        for earlier in PACKS:
            if earlier == pack or pack == "changeling":
                break
            if earlier in PACK_GROUPS:
                taken.update(_troop_items(game, PACK_GROUPS[earlier]))
        chosen = []
        for item in _troop_items(game, PACK_GROUPS[pack]):
            if item in taken or item not in vanilla:
                continue
            filename, node = vanilla[item]
            # The hive does not need helmets: changelings do not wear them (no_helmet in tools/make_troops.py),
            # and that is a couple dozen extra textures of 4–11 MB per import.
            if pack == "changeling" and filename == "head_armors.xml":
                continue
            key = (node.get("name") or "").split("}")[0].lstrip("{=")
            name = russian.get(key) or (node.get("name") or item).split("}")[-1]
            name = NAME_FIXES.get(item, name)
            chosen.append((filename, item, name[:1].upper() + name[1:]))
    else:
        raise ValueError("неизвестный пакет брони: " + pack)

    result = []
    seen_meshes = set()
    for filename, item, name in chosen:
        node = vanilla[item][1]
        slot, mode = FILES[filename]
        mesh = node.get("mesh")
        result.append({
            "item": item, "file": filename, "slot": slot, "mode": mode, "mesh": mesh,
            "name": name, "pony_item": "eq_pony_" + item, "pony_mesh": "eq_pony_" + mesh,
            "new_mesh": mesh not in seen_meshes,
        })
        seen_meshes.add(mesh)
    return result


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    for pack in PACKS:
        rows = pieces(pack)
        print(f"== {pack}: {len(rows)} вещей, мешей {len({r['mesh'] for r in rows})}")
        for r in rows:
            print(f"   {r['slot']:6} {r['item']:48} {r['mesh']:40} {r['name']}")
